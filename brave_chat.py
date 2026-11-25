"""Native, accessible conversation UI. No embedded browser or remote assets."""
from __future__ import annotations

import html
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PyQt6.QtCore import QByteArray, QEvent, QTimer, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QColor,QTextBlockFormat,QTextCursor,QTextDocument,QTextFormat,QTextOption
from PyQt6 import sip
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
    QScrollArea, QSizePolicy, QTextBrowser, QTextEdit, QVBoxLayout, QWidget,
)

from brave_i18n import translate as t


def design():
    from brave_ui import colors, font, icon, button_style
    return colors(), font, icon, button_style


class MessageText(QTextBrowser):
    """Markdown with HTML disabled; messages cannot load files or network images."""
    def __init__(self, text, parent=None, markdown=True):
        super().__init__(parent)
        c, font, _, _ = design()
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFont(font(10))
        self.setReadOnly(True)
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(f'QTextBrowser {{background: transparent; color: {c.TEXT}; border: none; padding: 0; selection-background-color: {c.PRI_GHO};}}')
        self.document().setDocumentMargin(0)
        self.document().setDefaultStyleSheet(
            f'p {{margin-top: 0; margin-bottom: 8px; line-height: 145%;}} '
            f'pre {{font-family: Consolas; background-color: {c.BG}; color: {c.TEXT}; padding: 8px;}} '
            f'code {{font-family: Consolas;}} a {{color: {c.PRI};}}'
        )
        if markdown:
            self.document().setMarkdown(text, QTextDocument.MarkdownFeature.MarkdownNoHTML)
        else:
            self.setPlainText(text)
        option=self.document().defaultTextOption()
        option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.document().setDefaultTextOption(option)
        block=self.document().begin()
        while block.isValid():
            format=block.blockFormat()
            format.setLineHeight(135,QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
            if format.hasProperty(QTextFormat.Property.BlockCodeFence) or format.hasProperty(QTextFormat.Property.BlockCodeLanguage):
                format.setBackground(QColor(c.PANEL2))
                format.setLeftMargin(8)
                format.setRightMargin(8)
                format.setTopMargin(6)
                format.setBottomMargin(6)
                format.setNonBreakableLines(False)
            cursor=QTextCursor(block)
            cursor.setBlockFormat(format)
            block=block.next()
        self.document().contentsChanged.connect(self.fit_height)
        self.anchorClicked.connect(self.open_link)
        QTimer.singleShot(0, self.fit_height)

    def loadResource(self, resource_type, name):
        # This also blocks local/file: images from untrusted model markdown.
        return QByteArray()

    def open_link(self, url):
        if url.scheme().lower() == 'brave-source' and len(url.host()) == 32:
            from brave_conversation import source_dialog
            source_dialog(self,url.host())
            return
        if url.scheme().lower() in {'https','http'} and url.host():
            url_str = url.toString()
            from core.access_policy import is_educational_url_allowed, current as current_policy
            if current_policy().get('educational_filter', True) and not is_educational_url_allowed(url_str):
                from PyQt6.QtWidgets import QMessageBox
                box = QMessageBox(self)
                box.setWindowTitle("TAI · Ta'lim Xavfsizligi")
                box.setIcon(QMessageBox.Icon.Warning)
                box.setText("Ushbu havola ta'lim xavfsizligi ro'yxatida mavjud emas.")
                msg = (
                    f"Manzil: {url.host()}\n\n"
                    "TAI (Til O'rgatuvchi AI) rejimida chalg'ituvchi saytlarning oldini olish "
                    "uchun faqat YouTube va ta'limiy manbalarga (Cambridge, Oxford, BBC, TED va h.k.) "
                    "ruxsat berilgan.\n\nBaribir ochmoqchimisiz?"
                )
                box.setInformativeText(msg)
                btn_open = box.addButton("Baribir ochish", QMessageBox.ButtonRole.AcceptRole)
                btn_cancel = box.addButton("Bekor qilish", QMessageBox.ButtonRole.RejectRole)
                box.setDefaultButton(btn_cancel)
                box.exec()
                if box.clickedButton() != btn_open:
                    return
            import webbrowser
            webbrowser.open(url_str)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_height()

    def fit_height(self):
        if getattr(self,'_fitting',False):
            return
        self._fitting=True
        try:
            self.document().setTextWidth(max(60,self.viewport().width()))
            height=max(22,math.ceil(self.document().size().height())+3)
            if self.height()!=height:
                self.setFixedHeight(height)
        finally:
            self._fitting=False


class MessageCard(QFrame):
    def __init__(self, role, text, stamp, assistant, parent=None):
        super().__init__(parent)
        self.role=role;self.answer_text=text;self.reply_seq=None
        c, font, icon, button_style = design()
        self.setObjectName('BraveMessage')
        self.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Minimum)
        self.setMaximumWidth(760)
        background=c.PANEL2 if role=='you' else c.BG
        border=c.BORDER if role!='error' else c.RED
        self.setStyleSheet(f'QFrame#BraveMessage {{background: {background}; border: 1px solid {border}; border-radius: 14px;}}')
        layout=QVBoxLayout(self)
        self._layout=layout
        layout.setContentsMargins(14,12,14,12)
        layout.setSpacing(8)
        header=QHBoxLayout()
        header.setSpacing(7)
        name=t('Siz') if role=='you' else (t('Muammo') if role=='error' else ('TAI' if assistant.lower()=='tai' else assistant.capitalize()))
        badge=QLabel('B' if role=='ai' else (name[:1] if role=='you' else '!'))
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedSize(22,22)
        badge.setFont(font(8,True))
        badge.setStyleSheet(f'background: {c.PRI_GHO if role=="ai" else c.PANEL}; color: {c.PRI if role=="ai" else c.TEXT_MED}; border: none; border-radius: 7px;')
        if role == 'ai':
            badge.setProperty('brave_logo_size', 22)
            from brave_brand import logo_pixmap
            from brave_ui import current_theme
            badge.setPixmap(logo_pixmap(22, current_theme(), 2))
            badge.setStyleSheet('background: transparent; border: none;')
        header.addWidget(badge)
        speaker=QLabel(name)
        speaker.setFont(font(9,True))
        speaker.setStyleSheet(f'color: {c.PRI if role=="ai" else c.TEXT}; background: transparent; border: none;')
        header.addWidget(speaker)
        header.addStretch()
        date=QLabel(stamp)
        date.setFont(font(8))
        date.setStyleSheet(f'color: {c.TEXT_DIM}; background: transparent; border: none;')
        header.addWidget(date)
        layout.addLayout(header)
        self.body=MessageText(text,self,markdown=role=='ai')
        layout.addWidget(self.body)
        if role=='ai':
            footer=QHBoxLayout()
            copy=QPushButton(t('Nusxalash'))
            copy.setIcon(icon('copy'))
            copy.setFont(font(8))
            copy.setCursor(Qt.CursorShape.PointingHandCursor)
            copy.setAccessibleName(t('Javobni nusxalash'))
            copy.setStyleSheet(button_style()+'QPushButton {border: none; background: transparent; padding: 3px 0; text-align: left;}')
            copy.clicked.connect(lambda: self.copy_answer(copy,text))
            footer.addWidget(copy)
            actions = QPushButton(t('AI amallari'))
            actions.setObjectName('BraveAnswerActions')
            actions.setFont(font(8))
            actions.setStyleSheet(button_style()+'QPushButton {border: none; background: transparent; padding: 3px 0;}')
            actions.clicked.connect(lambda: self.open_actions(text))
            footer.addWidget(actions)
            save_vocab_btn = QPushButton("📚 Lug‘atga+")
            save_vocab_btn.setObjectName('BraveSaveVocab')
            save_vocab_btn.setProperty('brave_literal_text', True)
            save_vocab_btn.setFont(font(8))
            save_vocab_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            save_vocab_btn.setToolTip(t('Javobdagi yangi so‘z va iboralarni shaxsiy lug‘atga saqlash'))
            save_vocab_btn.setStyleSheet(button_style()+f'QPushButton {{border: none; background: transparent; padding: 3px 4px; color: {c.PRI};}}')
            save_vocab_btn.clicked.connect(lambda: self.save_to_vocab(save_vocab_btn, text))
            footer.addWidget(save_vocab_btn)
            speak_btn = QPushButton("🔊 O‘qish")
            speak_btn.setObjectName('BraveSpeakAnswer')
            speak_btn.setProperty('brave_literal_text', True)
            speak_btn.setFont(font(8))
            speak_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            speak_btn.setToolTip(t('Javobni tanlangan ovoz, sheva va ohangda eshitish (to‘xtatish uchun qayta bosing)'))
            speak_btn.setStyleSheet(button_style()+f'QPushButton {{border: none; background: transparent; padding: 3px 4px; color: {c.TEXT_MED};}}')
            speak_btn.clicked.connect(lambda: self.speak_answer(speak_btn, text, slow=False))
            footer.addWidget(speak_btn)
            slow_btn = QPushButton("🐢 0.7×")
            slow_btn.setObjectName('BraveSlowSpeakAnswer')
            slow_btn.setProperty('brave_literal_text', True)
            slow_btn.setFont(font(8))
            slow_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            slow_btn.setToolTip(t('Javobni bo‘g‘inlab sekin (0.70×) talaffuzda eshitish'))
            slow_btn.setStyleSheet(button_style()+f'QPushButton {{border: none; background: transparent; padding: 3px 3px; color: {c.TEXT_DIM};}}')
            slow_btn.clicked.connect(lambda: self.speak_answer(slow_btn, text, slow=True))
            footer.addWidget(slow_btn)
            self.continue_button=QPushButton(t('Davom ettir'));self.continue_button.setObjectName('BraveContinueAnswer')
            self.continue_button.setStyleSheet(button_style()+'QPushButton {padding:3px 7px;}')
            self.continue_button.clicked.connect(self.continue_answer);self.continue_button.hide();footer.addWidget(self.continue_button)
            footer.addStretch()
            layout.addLayout(footer)

    def continue_answer(self):
        owner=self.window()
        if hasattr(owner,'_features'):
            from brave_continuation import continue_answer
            continue_answer(owner,self.reply_seq)

    def open_actions(self, text):
        owner = self
        while owner is not None and not hasattr(owner, '_features'):
            owner = owner.parentWidget()
        if owner is not None:
            from brave_text_actions import open_text_actions
            selected = self.body.textCursor().selectedText().replace('\u2029', '\n')
            open_text_actions(owner, selected or text)

    def save_to_vocab(self, button, text):
        owner = self
        while owner is not None and not (hasattr(owner, '_language_tutor') or hasattr(owner, '_tutor_controller')):
            owner = owner.parentWidget()
        tutor = getattr(owner, '_language_tutor', None) or getattr(owner, '_tutor_controller', None) if owner is not None else None
        if tutor is not None and hasattr(tutor, 'quick_save_from_message'):
            selected = self.body.textCursor().selectedText().replace('\u2029', '\n').strip()
            count = tutor.quick_save_from_message(selected or text)
            if count > 0 and button is not None and not sip.isdeleted(button):
                button.setText(f"📚 +{count} Saqlandi")
                QTimer.singleShot(1600, lambda: None if sip.isdeleted(button) else button.setText("📚 Lug‘atga+"))

    def speak_answer(self, button, text, slow: bool = False):
        owner = self.window()
        if owner is None:
            return
        if not getattr(owner, '_local_voice', None):
            from brave_local_voice import LocalVoice
            owner._local_voice = LocalVoice(owner)
        voice = owner._local_voice
        if getattr(voice, 'speaking', False):
            voice.cancel()
            return
        selected = self.body.textCursor().selectedText().replace('\u2029', '\n').strip()
        target_text = (selected or text).split('\n\n---\n')[0].strip()
        if not target_text:
            return
        from core.voice_style import load_voice_style
        style = dict(load_voice_style())
        if slow:
            style['speed'] = 'very_slow'
        voice.say(target_text, force=True, style=style)

    def copy_answer(self,button,text):
        clipboard=QApplication.clipboard()
        if clipboard.text()!=text:
            self.window()._clipboard_self_value=text
            clipboard.setText(text)
        button.setText(t('Nusxalandi'))
        QTimer.singleShot(1400,lambda:None if sip.isdeleted(button) else button.setText(t('Nusxalash')))


class PromptButton(QPushButton):
    """A single keyboard-accessible action with distinct title and detail."""
    def __init__(self, title, detail, glyph, parent=None):
        super().__init__(parent)
        c, font, icon, button_style = design()
        self.setAccessibleName(t(title))
        self.setAccessibleDescription(t(detail))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(button_style() + f'QPushButton {{text-align: left; padding: 0; background: {c.BG};}} QPushButton:hover {{background: {c.PRI_GHO}; border-color: {c.PRI_DIM};}}')
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 8, 12, 8)
        row.setSpacing(10)
        symbol = QLabel()
        symbol.setFixedSize(20, 20)
        symbol.setPixmap(icon(glyph, c.PRI).pixmap(20, 20))
        symbol.setStyleSheet('background: transparent; border: none;')
        row.addWidget(symbol)
        copy = QVBoxLayout()
        copy.setSpacing(2)
        self.title = QLabel(t(title))
        self.title.setFont(font(9, True))
        self.title.setStyleSheet(f'color: {c.TEXT}; background: transparent; border: none;')
        self.detail = QLabel(t(detail))
        self.detail.setFont(font(8))
        self.detail.setStyleSheet(f'color: {c.TEXT_DIM}; background: transparent; border: none;')
        copy.addWidget(self.title)
        copy.addWidget(self.detail)
        row.addLayout(copy, 1)
        arrow = QLabel('›')
        arrow.setFont(font(14))
        arrow.setStyleSheet(f'color: {c.TEXT_DIM}; background: transparent; border: none;')
        row.addWidget(arrow)
        self._symbol = symbol
        self._prompt_text = ''
        for child in self.findChildren(QWidget):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def update_card(self, title, detail, prompt, glyph):
        c, _, icon, _ = design()
        self.title.setText(t(title))
        self.detail.setText(t(detail))
        self.setAccessibleName(t(title))
        self.setAccessibleDescription(t(detail))
        self._symbol.setPixmap(icon(glyph, c.PRI).pixmap(20, 20))
        self._prompt_text = prompt

    def set_compact(self, compact):
        self.detail.setVisible(not compact)
        self.setFixedHeight(40 if compact else 60)


class WelcomeCard(QWidget):
    promptChosen=pyqtSignal(str)

    def __init__(self,parent=None):
        super().__init__(parent)
        c,font,icon,button_style=design()
        layout=QVBoxLayout(self)
        self._layout=layout
        self._cards=[]
        self._compact=None
        layout.setContentsMargins(10,18,10,16)
        layout.setSpacing(12)
        badge=QLabel('B')
        badge.setFixedSize(44,44)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFont(font(21,True))
        badge.setStyleSheet(f'background: {c.PRI_GHO}; color: {c.PRI}; border-radius: 14px;')
        from brave_brand import logo_pixmap
        from brave_ui import current_theme
        badge.setPixmap(logo_pixmap(44, current_theme(), 2))
        badge.setProperty('brave_logo_size', 44)
        badge.setStyleSheet('background: transparent; border: none;')
        layout.addWidget(badge)
        self._badge=badge
        eyebrow = QLabel(t('30 YILLIK PROFESSOR AI · TIL AKADEMIYASI'))
        eyebrow.setFont(font(8, True))
        eyebrow.setStyleSheet(f'color: {c.PRI}; background: transparent;')
        layout.addWidget(eyebrow)
        self._eyebrow = eyebrow
        title=QLabel(t('Brave bilan nimadan boshlaymiz?'))
        title.setWordWrap(True)
        title.setFont(font(17,True))
        title.setStyleSheet(f'color: {c.WHITE}; background: transparent;')
        layout.addWidget(title)
        self._title=title
        subtitle=QLabel(t('Gapiring yoki quyida yozing. Xohlasangiz, tayyor taklifdan boshlang.'))
        subtitle.setWordWrap(True)
        subtitle.setFont(font(10))
        subtitle.setStyleSheet(f'color: {c.TEXT_MED}; background: transparent;')
        layout.addWidget(subtitle)
        self._subtitle=subtitle
        for title_s,detail_s,prompt_s,glyph in [
            ('Kunimni rejalashtir','Muhim ishlarni tartiblang.','Bugungi kunimni rejalashtirishga yordam ber.','sliders'),
            ('Matnni tushuntir','Murakkab fikrni soddalashtiring.','Bir matnni oddiy tilda tushuntirishga yordam ber.','file'),
            ('Birga g‘oya topamiz','Yangi yo‘l yoki yechim izlang.','Yangi g‘oyalar topishga yordam ber.','spark'),
        ]:
            button=PromptButton(title_s, detail_s, glyph)
            button._prompt_text = prompt_s
            button.clicked.connect(lambda _,b=button:self.promptChosen.emit(t(b._prompt_text)))
            layout.addWidget(button)
            self._cards.append((button,title_s,detail_s))
        self.refresh_for_tutor()

    def refresh_for_tutor(self, state=None):
        try:
            from brave_language_tutor import (
                load_state, language_display_name, role_display, skill_display,
            )
            state = state or load_state()
            lang_name = language_display_name(state)
            level = state.get('level', 'B1')
            role = role_display(state)
            skill = skill_display(state)
            self._eyebrow.setProperty('brave_literal_text', True)
            self._eyebrow.setText(f"🎓 {lang_name.upper()} ({level}) · {t(role.badge).upper()}")
            self._title.setProperty('brave_literal_text', True)
            self._title.setText(f"{skill.title}")
            self._subtitle.setProperty('brave_literal_text', True)
            self._subtitle.setText(f"{t(skill.subtitle)}")
            for idx, (button, _, _) in enumerate(self._cards):
                if idx < len(skill.starters):
                    s_title, s_detail, s_prompt, s_glyph = skill.starters[idx]
                    button.update_card(s_title, s_detail, s_prompt, s_glyph)
                    self._cards[idx] = (button, s_title, s_detail)
        except Exception:
            pass

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if not hasattr(self,'_cards'):
            return
        compact=self.window().height()<790
        if compact==self._compact:
            return
        self._compact=compact
        _,font,_,_=design()
        self._badge.setVisible(not compact)
        self._eyebrow.setVisible(not compact)
        self._subtitle.setVisible(not compact)
        self._title.setFont(font(14 if compact else 17,True))
        self._layout.setContentsMargins(4 if compact else 10,8 if compact else 18,4 if compact else 10,8 if compact else 16)
        self._layout.setSpacing(8 if compact else 12)
        for button,title,detail in self._cards:
            button.set_compact(compact)


class ConversationLog(QWidget):
    messageAdded=pyqtSignal(str,str)
    _sig=pyqtSignal(str)
    fileDropped=pyqtSignal(str)
    promptChosen=pyqtSignal(str)

    def __init__(self,parent=None):
        super().__init__(parent)
        self._ai_name_lc='brave'
        self._history=[]
        self._rows=[]
        self._activity=[]
        self.setAcceptDrops(True)
        layout=QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(6)
        self.scroll=QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.host=QWidget()
        self.host.setStyleSheet('background: transparent;')
        self.messages=QVBoxLayout(self.host)
        self.messages.setContentsMargins(1,2,7,10)
        self.messages.setSpacing(12)
        self.messages.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.host)
        layout.addWidget(self.scroll,1)
        self.page_bar=QWidget();page_layout=QHBoxLayout(self.page_bar);page_layout.setContentsMargins(0,0,0,0)
        self.older_page=QPushButton(t('Oldingi xabarlar ↑'));self.newer_page=QPushButton(t('Keyingi xabarlar ↓'))
        self.page_caption=QLabel()
        for widget in (self.older_page,self.page_caption,self.newer_page):page_layout.addWidget(widget)
        self.page_bar.hide();layout.addWidget(self.page_bar)
        self.new_messages=QPushButton(t('Yangi xabar ↓'))
        self.new_messages.clicked.connect(self.scroll_bottom)
        self.new_messages.hide()
        layout.addWidget(self.new_messages)
        self.activity_button=QPushButton(t('Faoliyat'))
        self.activity_button.setCheckable(True)
        self.activity_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.activity_button.clicked.connect(lambda opened:self.activity_view.setVisible(opened))
        layout.addWidget(self.activity_button)
        self.activity_view=QTextEdit()
        self.activity_view.setReadOnly(True)
        self.activity_view.setFixedHeight(110)
        self.activity_view.document().setMaximumBlockCount(120)
        self.activity_view.hide()
        layout.addWidget(self.activity_view)
        self._sig.connect(self._enqueue)
        self.refresh_chrome()
        self.add_welcome()

    def refresh_chrome(self):
        c,font,_,button_style=design()
        self.scroll.setStyleSheet(f'QScrollArea {{background: transparent; border: none;}} QScrollBar:vertical {{background: transparent; width: 6px;}} QScrollBar::handle:vertical {{background: {c.BORDER_B}; border-radius: 3px; min-height: 28px;}} QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {{height: 0;}} QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical {{background: transparent;}}')
        self.new_messages.setText(t('Yangi xabar ↓'))
        self.new_messages.setStyleSheet(button_style())
        self.activity_button.setText(t('Faoliyat')+(f' · {len(self._activity)}' if self._activity else ''))
        self.activity_button.setStyleSheet(f'QPushButton {{color: {c.TEXT_DIM}; background: transparent; border: none; text-align: left; padding: 4px 2px; font-family: "Segoe UI"; font-size: 11px;}} QPushButton:hover {{color: {c.TEXT};}}')
        self.activity_view.setFont(font(8))
        self.activity_view.setStyleSheet(f'QTextEdit {{background: {c.BG}; color: {c.TEXT_DIM}; border: 1px solid {c.BORDER}; border-radius: 9px; padding: 7px;}}')

    def add_welcome(self):
        self.welcome=WelcomeCard(self.host)
        self.welcome.setMaximumWidth(650)
        self.welcome.promptChosen.connect(self.promptChosen.emit)
        self.messages.addWidget(self.welcome,alignment=Qt.AlignmentFlag.AlignHCenter)
        QTimer.singleShot(0,self.fit_welcome)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        QTimer.singleShot(0,self.fit_welcome)

    def fit_welcome(self):
        if hasattr(self,'welcome') and self.welcome is not None and not sip.isdeleted(self.welcome):
            self.welcome.setFixedWidth(min(650,max(240,self.scroll.viewport().width()-20)))

    def append_log(self,text):
        self._sig.emit(str(text))

    def update_stream(self, text):
        """Transient plain text; persist and render Markdown once at completion."""
        bar = self.scroll.verticalScrollBar()
        at_bottom = bar.maximum()-bar.value() < 60
        if not getattr(self, '_stream_row', None):
            stamp=datetime.now(timezone(timedelta(hours=5))).strftime('%H:%M')
            self._render(self._ai_name_lc+': '+text, stamp)
            self._stream_row = self._rows[-1]
            self._stream_body = self._stream_row.findChild(MessageCard).body
            # Copy only becomes available for a completed answer.
            for button in self._stream_row.findChildren(QPushButton):
                button.hide()
        self._stream_text = text
        self._stream_body.setPlainText(text)
        if at_bottom:
            if not getattr(self, '_scroll_scheduled', False):
                self._scroll_scheduled = True
                def _do_scroll():
                    self._scroll_scheduled = False
                    self.scroll_bottom()
                QTimer.singleShot(16, _do_scroll)

    def end_stream(self):
        self._scroll_scheduled = False
        row = getattr(self, '_stream_row', None)
        self._stream_text = ''
        self._stream_row = None
        if row is not None and not sip.isdeleted(row):
            self.messages.removeWidget(row)
            if row in self._rows:
                self._rows.remove(row)
            row.hide()
            row.deleteLater()

    def _enqueue(self,text):
        stamp=datetime.now(timezone(timedelta(hours=5))).strftime('%H:%M')
        self._history.append((text,stamp))
        self._history=self._history[-300:]
        self._render(text,stamp)
        self.messageAdded.emit(text,stamp)

    def conversation_markdown(self):
        """Export displayed conversation only; exclude internal activity/errors."""
        rows=['# Brave', '']
        for text,stamp in self._history:
            prefix,separator,body=text.partition(':')
            role=prefix.strip().casefold()
            if not separator or role not in {'you','brave','tai',self._ai_name_lc}:
                continue
            name=t('Siz') if role=='you' else self._ai_name_lc.capitalize()
            rows.extend([f'## {name} · {stamp}', '', body.strip(), ''])
        return '\n'.join(rows)

    def export_conversation(self):
        if not any(text.partition(':')[0].strip().casefold() in {'you','brave',self._ai_name_lc} for text,_ in self._history):
            self.append_log('ERR: Saqlash uchun avval suhbat boshlang.')
            return
        stamp=datetime.now(timezone(timedelta(hours=5))).strftime('%Y-%m-%d_%H-%M')
        path,_=QFileDialog.getSaveFileName(self,t('Suhbatni saqlash'),f'Brave_{stamp}.md','Markdown (*.md)')
        if not path:
            return
        try:
            Path(path).write_text(self.conversation_markdown(),encoding='utf-8')
        except OSError:
            self.append_log('ERR: Suhbatni saqlab bo‘lmadi. Boshqa papkani tanlang.')
        else:
            self.append_log('SYS: Suhbat faylga saqlandi.')

    def _render(self,text,stamp,scroll=True):
        prefix,separator,body=text.partition(':')
        kind=prefix.strip().casefold()
        if kind=='you' or kind in {self._ai_name_lc,'brave','tai','err','error'}:
            role='you' if kind=='you' else ('error' if kind in {'err','error'} else 'ai')
            bar=self.scroll.verticalScrollBar()
            at_bottom=bar.maximum()-bar.value()<60
            if hasattr(self,'welcome') and self.welcome:
                self.messages.removeWidget(self.welcome)
                self.welcome.hide()
                self.welcome.deleteLater()
                self.welcome=None
            row=QWidget(self.host)
            line=QHBoxLayout(row)
            line.setContentsMargins(0,0,0,0)
            content=body.strip() if separator else text
            card=MessageCard(role,t(content) if role=='error' else content,stamp,self._ai_name_lc,row)
            if role=='you':
                line.addSpacing(24)
            line.addWidget(card,1)
            if role!='you':
                line.addSpacing(10)
            self.messages.addWidget(row)
            self._rows.append(row)
            if len(self._rows)>120:
                old=self._rows.pop(0)
                self.messages.removeWidget(old)
                old.hide()
                old.deleteLater()
            if scroll:
                if at_bottom:
                    QTimer.singleShot(0,self.scroll_bottom)
                else:
                    self.new_messages.show()
        else:
            self._activity.append((stamp,body.strip() if separator else text))
            self._activity=self._activity[-120:]
            self.activity_view.append(html.escape(stamp+'  '+t(body.strip() if separator else text)))
            self.refresh_chrome()

    def _clear_widgets(self):
        while self.messages.count():
            item=self.messages.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        self._rows=[]
        self._activity=[]
        self.activity_view.clear()
        self.welcome=None
        self.new_messages.hide()

    def clear(self):
        self.end_stream()
        self._history=[]
        self._clear_widgets()
        self.add_welcome()
        self.refresh_chrome()

    def retheme(self):
        streaming = getattr(self, '_stream_text', '')
        self.end_stream()
        bar=self.scroll.verticalScrollBar()
        position=bar.value()
        at_bottom=bar.maximum()-position<60
        self._clear_widgets()
        self.add_welcome()
        for text,stamp in self._history:
            self._render(text,stamp,scroll=False)
        if streaming:
            self.update_stream(streaming)
        self.refresh_chrome()
        owner=self.window()
        if hasattr(owner,'_features'):
            from brave_continuation import refresh
            refresh(owner)
        if at_bottom:
            QTimer.singleShot(0,self.scroll_bottom)
        else:
            QTimer.singleShot(0,lambda:bar.setValue(position))

    def scroll_bottom(self):
        if sip.isdeleted(self) or sip.isdeleted(self.scroll):
            return
        bar=self.scroll.verticalScrollBar()
        bar.setValue(bar.maximum())
        self.new_messages.hide()

    def toPlainText(self):
        return '\n'.join(text for text,_ in self._history)

    def toHtml(self):
        return '\n'.join(card.body.toHtml() for card in self.findChildren(MessageCard))

    def dragEnterEvent(self,event):
        if event.mimeData().hasUrls() and any(url.isLocalFile() for url in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self,event):
        for url in event.mimeData().urls():
            if url.isLocalFile() and Path(url.toLocalFile()).is_file():
                self.fileDropped.emit(url.toLocalFile())
                event.acceptProposedAction()


class ComposerEdit(QPlainTextEdit):
    returnPressed=pyqtSignal()
    MIN_HEIGHT = 50
    MAX_HEIGHT = 138

    def __init__(self, parent=None):
        super().__init__(parent)
        self.textChanged.connect(self.adjust_composer_height)

    def text(self):
        return self.toPlainText()

    def setText(self,text):
        self.setPlainText(text)
        cursor=self.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.setTextCursor(cursor)
        self.adjust_composer_height()

    def adjust_composer_height(self):
        lines = max(1, self.document().blockCount())
        txt = self.toPlainText()
        if txt:
            approx_wrap = sum(max(1, math.ceil(len(line) / 56)) for line in txt.splitlines() or [''])
            lines = max(lines, approx_wrap)
        line_h = max(18, self.fontMetrics().lineSpacing())
        desired = min(self.MAX_HEIGHT, max(self.MIN_HEIGHT, lines * line_h + 14))
        if self.height() != desired:
            self.setFixedHeight(desired)

    def keyPressEvent(self,event):
        if event.key() in {Qt.Key.Key_Return,Qt.Key.Key_Enter} and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            self.returnPressed.emit()
            event.accept()
        else:
            super().keyPressEvent(event)


class ComposerSurface(QFrame):
    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Type.FocusIn, QEvent.Type.FocusOut):
            self.setProperty('editing', event.type() == QEvent.Type.FocusIn)
            self.style().unpolish(self)
            self.style().polish(self)
            self.update()
        return super().eventFilter(obj, event)


def build_input_row(win):
    from brave_ui import set_icon
    c,font,icon,button_style=design()
    row=QHBoxLayout()
    row.setContentsMargins(0,0,0,0)
    composer=ComposerSurface()
    composer.setObjectName('BraveComposer')
    composer.setStyleSheet(f'QFrame#BraveComposer {{background: {c.PANEL2}; border: 1px solid {c.BORDER_B}; border-radius: 14px;}} QFrame#BraveComposer[editing="true"] {{border-color: {c.PRI};}}')
    content=QVBoxLayout(composer)
    content.setContentsMargins(12,10,10,9)
    content.setSpacing(7)
    win._input=ComposerEdit()
    win._input.installEventFilter(composer)
    win._input.setFont(font(10))
    win._input.setPlaceholderText(t('Savolingizni yozing yoki / orqali buyruq tanlang…'))
    win._input.setAccessibleName(t('Savol yoki buyruq'))
    win._input.setFixedHeight(ComposerEdit.MIN_HEIGHT)
    win._input.setStyleSheet(f'QPlainTextEdit {{background: transparent; color: {c.TEXT}; border: none; padding: 0; selection-background-color: {c.PRI_GHO};}}')
    win._input.returnPressed.connect(win._send)
    from brave_slash import SlashMenu
    old=getattr(win,'_slash_menu',None)
    if old:old.popup.close();old.popup.deleteLater();old.deleteLater()
    win._slash_menu=SlashMenu(win)
    content.addWidget(win._input)
    tools=QHBoxLayout()
    tools.setSpacing(8)
    attach=QPushButton()
    set_icon(attach,'attach')
    attach.setFixedSize(30,32)
    attach.setToolTip(t('Fayl biriktirish'))
    attach.setAccessibleName(t('Fayl biriktirish'))
    attach.setStyleSheet(button_style()+'QPushButton {border: none; background: transparent; padding: 4px;}')
    attach.setCursor(Qt.CursorShape.PointingHandCursor)
    attach.clicked.connect(win._drop_zone._browse)
    tools.addWidget(attach)
    win._image_mode = QComboBox()
    win._image_mode.setObjectName('BraveImageMode')
    win._image_mode.setAccessibleName(t('Rasm bilan ishlash'))
    win._image_mode.addItem(t('Matnni o‘qish · OCR'), 'ocr')
    win._image_mode.addItem(t('Rasmni tushunish · Vision'), 'vision')
    win._image_mode.setMaximumWidth(220)
    win._image_mode.setFont(font(8))
    arrow = (Path(__file__).resolve().parent/'assets'/'chevron.svg').as_posix()
    win._image_mode.setStyleSheet(
        f'QComboBox {{color:{c.TEXT};background:{c.PANEL2};border:1px solid {c.BORDER};'
        'border-radius:7px;padding:5px 22px 5px 7px;}'
        f' QComboBox::drop-down {{width:18px;border:none;}} QComboBox::down-arrow {{image:url("{arrow}");width:9px;height:9px;}}')
    win._image_mode.setToolTip(t('Vision uchun rasmni tushunadigan lokal model kerak.'))
    tools.addWidget(win._image_mode)
    if not getattr(win, '_image_mode_bound', False):
        win._drop_zone.files_changed.connect(lambda: refresh_image_mode(win))
        win._image_mode_bound = True
    refresh_image_mode(win)
    tools.addStretch()
    win._word_count_lbl = QLabel('')
    win._word_count_lbl.setProperty('brave_literal_text', True)
    win._word_count_lbl.setFont(font(8))
    win._word_count_lbl.setStyleSheet(f'color: {c.TEXT_DIM}; background: transparent; border: none; padding-right: 4px;')
    win._word_count_lbl.hide()
    tools.addWidget(win._word_count_lbl)
    win._send_btn=QPushButton(t('Yuborish'))
    set_icon(win._send_btn,'arrow','ON_ACCENT')
    win._send_btn.setAccessibleName(t('Yuborish'))
    win._send_btn.setFixedHeight(34)
    win._send_btn.setStyleSheet(button_style(True)+'QPushButton {padding: 5px 10px;}')
    win._send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    win._send_btn.clicked.connect(win._send)
    win._send_btn.setEnabled(False)
    def _on_composer_changed():
        raw = win._input.text()
        stripped = raw.strip()
        win._send_btn.setEnabled(bool(stripped))
        if stripped:
            words = len(stripped.split())
            win._word_count_lbl.setText(f"{words} so‘z")
            win._word_count_lbl.show()
        else:
            win._word_count_lbl.hide()
    win._input.textChanged.connect(_on_composer_changed)
    tools.addWidget(win._send_btn)
    content.addLayout(tools)
    row.addWidget(composer,1)
    return row


def refresh_image_mode(win):
    if not hasattr(win, '_image_mode'):
        return
    from core.local_documents import IMAGES
    visible = (win._active_provider == 'ollama' and
               any(Path(path).suffix.lower() in IMAGES for path in win._drop_zone.current_files()))
    win._image_mode.setVisible(visible)


def toggle_chat_focus(win):
    set_chat_focus(win, not getattr(win, '_chat_focus', False))


def set_chat_focus(win, enabled, persist=True):
    bar = win._log.scroll.verticalScrollBar()
    position, at_bottom = bar.value(), bar.maximum()-bar.value() < 60
    win._chat_focus = bool(enabled)
    win._left_panel.setVisible(not win._chat_focus)
    win._center_split.setVisible(not win._chat_focus)
    win._header_widget.setVisible(not win._chat_focus)
    win._footer_widget.setVisible(not win._chat_focus)
    win._body_layout.setContentsMargins(20, 20 if win._chat_focus else 0, 20, 20 if win._chat_focus else 8)
    win._close_controls()
    if win._chat_focus:
        win._right_panel.setMinimumWidth(440)
        win._right_panel.setMaximumWidth(16777215)
        win._right_panel.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)
    else:
        from ui import _RIGHT_W
        win._right_panel.setFixedWidth(_RIGHT_W)
    refresh_focus_button(win)
    QTimer.singleShot(0, lambda: None if sip.isdeleted(bar) else bar.setValue(bar.maximum() if at_bottom else position))
    controller = getattr(win, '_layout_state', None)
    if controller is not None:
        if persist:
            controller.schedule()
        controller.sync_settings()


def refresh_focus_button(win):
    from brave_ui import set_icon
    focused = bool(getattr(win, '_chat_focus', False))
    win._chat_focus_btn.setToolTip(t('Fokusdan chiqish' if focused else 'Fokus rejimi')+' · Ctrl+Shift+F')
    win._chat_focus_btn.setAccessibleName(win._chat_focus_btn.toolTip())
    set_icon(win._chat_focus_btn, 'collapse' if focused else 'expand')


def set_chat_state(win,state):
    if not hasattr(win,'_chat_status_lbl'):
        return
    c,_,_,_=design()
    labels={
        'LISTENING':('Ovoz yoki matn bilan davom eting.',c.TEXT_DIM),
        'TEXT_READY':('Yozing — javoblar chatda ko‘rinadi.',c.TEXT_DIM),
        'SPEAKING':('Brave javob bermoqda',c.PRI),
        'THINKING':('Brave o‘ylayapti…',c.PRI),
        'PROCESSING':('Topshiriq bajarilmoqda…',c.PRI),
        'CANCEL_PENDING':('Bekor qilish so‘raldi. Boshlangan amal tugashi kutilmoqda.',c.TEXT_DIM),
        'APPROVAL':('Ruxsat kutilmoqda…',c.TEXT_DIM),
        'BLOCKED':('Internet ruxsati o‘chiq. Brave markazidan yoqing.',c.TEXT_DIM),
        'MUTED':('Mikrofon o‘chiq · matn yozishingiz mumkin.',c.TEXT_DIM),
        'SLEEPING':('Brave uyquda. Davom etish uchun uyg‘oting.',c.TEXT_DIM),
    }
    text,color=labels.get(state,('Gemini’ga ulanmoqda…',c.TEXT_DIM))
    win._chat_status_lbl.setText(t(text))
    win._chat_status_lbl.setStyleSheet(f'color: {color}; background: transparent; border: none;')


def build_right_panel(win):
    from ui import FileDropZone,LogWidget,_RIGHT_W
    from brave_ui import card,label,set_icon
    from brave_language_tutor import build_tutor_chat_bar
    c,font,icon,button_style=design()
    widget=QWidget()
    widget.setFixedWidth(_RIGHT_W)
    card(widget,'BraveConversation')
    layout=QVBoxLayout(widget)
    layout.setContentsMargins(16,14,16,14)
    layout.setSpacing(7)
    heading=QHBoxLayout()
    win._chat_heading_lbl = label('Suhbat',15,c.WHITE,True)
    win._chat_heading_lbl.setProperty('brave_literal_text', True)
    heading.addWidget(win._chat_heading_lbl)
    heading.addStretch()
    win._chat_focus_btn=QPushButton()
    set_icon(win._chat_focus_btn,'expand')
    win._chat_focus_btn.setFixedSize(32,32)
    win._chat_focus_btn.setAccessibleName(t('Chatni kengaytirish'))
    win._chat_focus_btn.setToolTip(t('Chatni kengaytirish'))
    win._chat_focus_btn.setStyleSheet(button_style()+'QPushButton {border: none; background: transparent; padding: 4px;}')
    win._chat_focus_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    win._chat_focus_btn.clicked.connect(lambda:toggle_chat_focus(win))
    heading.addWidget(win._chat_focus_btn)
    layout.addLayout(heading)
    build_tutor_chat_bar(win, layout)
    win._chat_status_lbl=label('Ovoz yoki matn bilan davom eting.',9,c.TEXT_DIM)
    win._chat_status_lbl.setWordWrap(True)
    layout.addWidget(win._chat_status_lbl)
    win._log=LogWidget()
    win._log._ai_name_lc=win._assistant_name.lower()
    from brave_features import build_features
    build_features(win,layout)
    if hasattr(win, '_language_tutor'):
        win._language_tutor.refresh_ui()
    win._log.promptChosen.connect(lambda text:(win._input.setText(text),win._input.setFocus()))
    layout.addWidget(win._log,1)
    win._drop_zone=FileDropZone()
    win._drop_zone.setFixedHeight(58)
    win._drop_zone.file_selected.connect(win._on_file_selected)
    win._drop_zone.hide()
    win._log.fileDropped.connect(win._drop_zone._set_file)
    attachment=QHBoxLayout()
    attachment.addWidget(win._drop_zone,1)
    win._preview_file_btn=QPushButton(t('Ko‘rish'))
    win._preview_file_btn.setStyleSheet(button_style());win._preview_file_btn.hide()
    win._preview_file_btn.clicked.connect(lambda:__import__('brave_attachment_preview').open_preview(win))
    attachment.addWidget(win._preview_file_btn)
    win._remove_file_btn=QPushButton('×')
    win._remove_file_btn.setFixedSize(28,28)
    win._remove_file_btn.setStyleSheet(button_style()+'QPushButton {padding: 0;}')
    win._remove_file_btn.setToolTip(t('Biriktirilgan faylni olib tashlash'))
    win._remove_file_btn.clicked.connect(lambda:remove_attachment(win))
    win._remove_file_btn.hide()
    attachment.addWidget(win._remove_file_btn)
    layout.addLayout(attachment)
    win._file_hint=label('Fayl biriktirildi. Nima qilish kerakligini yozing.',8,c.TEXT_DIM)
    win._file_hint.setWordWrap(True)
    win._file_hint.hide()
    layout.addWidget(win._file_hint)
    layout.addLayout(win._build_input_row())
    controls=QHBoxLayout()
    controls.setSpacing(8)
    win._mute_btn=QPushButton()
    win._mute_btn.setFixedHeight(38)
    win._mute_btn.setMaximumWidth(300)
    win._mute_btn.clicked.connect(win._toggle_mute)
    win._mute_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    win._style_mute_btn()
    win._mute_btn.setEnabled(not win._text_only)
    controls.addWidget(win._mute_btn,1)
    controls.addStretch(1)
    win._interrupt_btn=QPushButton(t('To‘xtatish'))
    set_icon(win._interrupt_btn,'stop')
    win._interrupt_btn.setFixedHeight(38)
    win._interrupt_btn.setToolTip(t('Javobni to‘xtatish · Esc'))
    win._interrupt_btn.setStyleSheet(button_style()+'QPushButton {padding: 5px 10px;}')
    win._interrupt_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    win._interrupt_btn.clicked.connect(win._do_interrupt)
    controls.addWidget(win._interrupt_btn)
    layout.addLayout(controls)
    return widget


def show_attachment(win):
    win._drop_zone.show()
    win._file_hint.setText(t('Fayl biriktirildi. Nima qilish kerakligini yozing.'))
    win._file_hint.show()
    win._remove_file_btn.show()
    win._preview_file_btn.show()


def remove_attachment(win):
    win._drop_zone.clear_file()
    win._current_file=None
    win._drop_zone.hide()
    win._file_hint.hide()
    win._remove_file_btn.hide()
    win._preview_file_btn.hide()
