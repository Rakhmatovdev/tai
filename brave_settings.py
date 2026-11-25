"""One searchable settings window, reusing the application's existing forms."""
from pathlib import Path
from PyQt6.QtCore import QEvent, QSize, Qt, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QPushButton, QScrollArea,
    QStackedWidget, QVBoxLayout, QWidget)

from brave_i18n import language, localize_widgets, translate as t
from brave_navigation import SECTIONS, SETTINGS, search_entries
from brave_ui import button_style, colors, font, icon, label, set_icon, set_language


class SettingsDialog(QDialog):
    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.setObjectName('BraveSettingsWindow')
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setMinimumSize(840, 520)
        self.resize(920, 660)
        self.current_section = 'appearance'
        self.forms = {}
        self.targets = {}
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(18)
        top = QHBoxLayout()
        self.heading = label('Sozlamalar', 22, colors().WHITE, True)
        top.addWidget(self.heading, 1)
        close = QPushButton(t('Yopish'))
        close.setStyleSheet(button_style())
        close.clicked.connect(self.accept)
        top.addWidget(close)
        root.addLayout(top)
        self.search = QLineEdit()
        self.search.setFont(font(10))
        self.search.setMinimumHeight(42)
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName(t('Sozlamalarni qidirish'))
        self.search_action = self.search.addAction(icon('search'), QLineEdit.ActionPosition.LeadingPosition)
        self.search.installEventFilter(self)
        self.search.textChanged.connect(self.filter)
        root.addWidget(self.search)
        body = QHBoxLayout()
        body.setSpacing(24)
        self.sidebar = QWidget()
        self.sidebar.setFixedWidth(164)
        navigation = QVBoxLayout(self.sidebar)
        navigation.setContentsMargins(0, 0, 0, 0)
        navigation.setSpacing(6)
        self.nav = {}
        for key, title, glyph in SECTIONS:
            button = QPushButton(t(title))
            button.setCheckable(True)
            button.setFixedHeight(42)
            button.setAccessibleName(t(title))
            set_icon(button, glyph)
            button.clicked.connect(lambda checked, value=key: self.select(value))
            self.nav[key] = button
            navigation.addWidget(button)
        navigation.addStretch()
        win._theme_btn = self.nav['appearance']
        body.addWidget(self.sidebar)
        self.pages = QStackedWidget()
        self.sections = {}
        self.layouts = {}
        for key, title, glyph in SECTIONS:
            page = QWidget()
            page.setObjectName('SettingsPage')
            page.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
            layout = QVBoxLayout(page)
            layout.setContentsMargins(0, 0, 8, 0)
            layout.setSpacing(16)
            layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            if key != 'appearance':
                layout.addWidget(label(title, 18, colors().WHITE, True))
            scroll = QScrollArea()
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setWidget(page)
            scroll.viewport().setObjectName('SettingsScrollViewport')
            self.sections[key] = scroll
            self.layouts[key] = layout
            self.pages.addWidget(scroll)
        from brave_appearance import AppearancePage
        self.appearance = AppearancePage(win)
        self.options = self.appearance.options
        self.layouts['appearance'].addWidget(self.appearance)
        self.language_card = QFrame()
        self.language_card.setObjectName('SettingsCard')
        row = QHBoxLayout(self.language_card)
        row.setContentsMargins(16, 14, 16, 14)
        row.addWidget(label('Til', 10, colors().TEXT, True), 1)
        win._language_box = QComboBox()
        win._language_box.setFont(font(10))
        win._language_box.setObjectName('BraveLanguage')
        for title, code in [('O‘zbekcha', 'uz'), ('English', 'en'), ('Русский', 'ru')]:
            win._language_box.addItem(title, code)
        win._language_box.setCurrentIndex(win._language_box.findData(language()))
        win._language_box.setMinimumSize(160, 36)
        win._language_box.setAccessibleName(t('Til'))
        win._language_box.currentIndexChanged.connect(lambda _: set_language(win, win._language_box.currentData()))
        row.addWidget(win._language_box)
        self.layouts['appearance'].addWidget(self.language_card)
        self.targets['language'] = win._language_box

        for entry in SETTINGS:
            if entry.section not in ('plugins', 'system'):
                continue
            self.add_action(entry)

        self.results_page = QWidget()
        results_layout = QVBoxLayout(self.results_page)
        results_layout.setContentsMargins(0, 0, 0, 0)
        self.results = QListWidget()
        self.results.setFont(font(10))
        self.results.setAccessibleName(t('Qidiruv natijalari'))
        self.results.itemActivated.connect(self.activate_result)
        self.results.itemClicked.connect(self.activate_result)
        results_layout.addWidget(self.results)
        self.empty = label('Natija topilmadi.', 11, colors().TEXT_DIM)
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        results_layout.addWidget(self.empty, 1)
        self.pages.addWidget(self.results_page)
        body.addWidget(self.pages, 1)
        root.addLayout(body, 1)
        self.finished.connect(lambda _: win._drawer_btn.setChecked(False))
        self.command_shortcut = QShortcut(QKeySequence('Ctrl+K'), self)
        self.command_shortcut.activated.connect(lambda: __import__('brave_commands').open_commands(win, self))
        self.refresh()
        self.select('appearance')

    def add_action(self, entry):
        if entry.key == 'layout':
            self.add_layout_options(entry)
            return
        card = QFrame()
        card.setObjectName('SettingsCard')
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)
        title = label(entry.title, 10, colors().TEXT, True)
        layout.addWidget(title)
        detail = label(entry.detail, 9, colors().TEXT_DIM)
        detail.setWordWrap(True)
        layout.addWidget(detail)
        button = QPushButton(t('Ochish'))
        button.setAccessibleName(t(entry.title))
        set_icon(button, entry.glyph)
        button.setStyleSheet(button_style())
        button.setMinimumHeight(36)
        button.clicked.connect(lambda checked, key=entry.key: self.run_action(key))
        layout.addWidget(button)
        self.layouts[entry.section].addWidget(card)
        self.targets[entry.key] = button
        if entry.key == 'autostart':
            self.win._autostart_btn = button
        if entry.key == 'remote':
            from memory.config_manager import get_dashboard_enabled
            button.setEnabled(get_dashboard_enabled())
            if not button.isEnabled():
                button.setToolTip(t('Masofaviy boshqaruv xavfsizlik uchun o‘chirilgan.'))

    def add_layout_options(self, entry):
        card = QFrame()
        card.setObjectName('SettingsCard')
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)
        layout.addWidget(label(entry.title, 10, colors().TEXT, True))
        detail = label(entry.detail, 9, colors().TEXT_DIM)
        detail.setWordWrap(True)
        layout.addWidget(detail)
        self.focus_check = QCheckBox(t('Fokus rejimi'))
        self.remember_layout = QCheckBox(t('Joylashuvni eslab qolish'))
        from brave_chat import set_chat_focus
        self.focus_check.toggled.connect(lambda enabled: set_chat_focus(self.win, enabled))
        self.remember_layout.toggled.connect(lambda enabled: self.win._layout_state.set_remember(enabled) if self.win._layout_state is not None else None)
        layout.addWidget(self.focus_check)
        layout.addWidget(self.remember_layout)
        reset = QPushButton(t('Standart joylashuv'))
        reset.setStyleSheet(button_style())
        reset.setMinimumHeight(36)
        reset.clicked.connect(lambda: self.win._layout_state.reset() if self.win._layout_state is not None else None)
        layout.addWidget(reset)
        self.targets['layout'] = self.remember_layout
        self.layouts[entry.section].addWidget(card)
        self.sync_layout()

    def sync_layout(self):
        if not hasattr(self, 'focus_check'):
            return
        state = getattr(self.win, '_layout_state', None)
        for checkbox, checked, title in [
            (self.focus_check, bool(getattr(self.win, '_chat_focus', False)), 'Fokus rejimi'),
            (self.remember_layout, state.remember if state is not None else True, 'Joylashuvni eslab qolish'),
        ]:
            checkbox.blockSignals(True)
            checkbox.setChecked(checked)
            checkbox.setText(t(title))
            checkbox.setAccessibleName(t(title))
            checkbox.blockSignals(False)

    def run_action(self, key):
        handlers = {
            'plugins': self.win._open_plugin_manager,
            'plugin-settings': self.win._open_plugin_settings,
            'desktop': self.win._create_desktop_shortcut,
            'autostart': self.win._toggle_autostart,
            'remote': self.win._open_remote,
        }
        if not self.targets[key].isEnabled():
            return
        if key in ('plugins', 'plugin-settings', 'remote'):
            self.accept()
        handlers[key]()

    def ensure_form(self, section):
        if section in self.forms:
            self.forms[section].show()
            return
        if section == 'profile':
            from ui import CustomizeOverlay, _read_full_config, DEFAULT_UI_COLOR
            config = _read_full_config()
            form = CustomizeOverlay(config.get('assistant_name') or 'Brave', config.get('user_name', ''),
                config.get('ui_color') or DEFAULT_UI_COLOR, config.get('voice_name', ''), embedded=True)
            form.saved.connect(self.win._apply_name_update)
            form.on_preview = self.win._preview_ui_color
            self.win._customize_overlay = form
        elif section == 'audio':
            from ui import AudioDeviceOverlay
            form = AudioDeviceOverlay(embedded=True)
            form.picked.connect(self.win._on_audio_devices_applied)
            self.win._audio_overlay = form
        elif section == 'ai':
            from brave_ai_settings import AISettings
            form = AISettings(self.win)
        else:
            return
        if section != 'ai':
            form.setMinimumHeight(form.sizeHint().height())
        self.layouts[section].addWidget(form)
        self.forms[section] = form
        self.targets[section] = (form._name_input if section == 'profile' else
                                 form.provider if section == 'ai' else form._in_box)
        form.show()

    def select(self, section, target=None):
        if section not in self.sections:
            return
        self.current_section = section
        self.search.clear()
        self.ensure_form(section)
        self.pages.setCurrentWidget(self.sections[section])
        for key, button in self.nav.items():
            button.setChecked(key == section)
        if target in self.targets:
            self.reveal_target(section, target)
            QTimer.singleShot(0, lambda: self.reveal_target(section, target))

    def reveal_target(self, section, target):
        if not self.isVisible() or section != self.current_section or target not in self.targets:
            return
        control = self.targets[target]
        reveal = control.parentWidget() if target == 'layout' else control
        self.sections[section].ensureWidgetVisible(reveal)
        control.setFocus()

    def filter(self, query):
        if not query.strip():
            self.pages.setCurrentWidget(self.sections[self.current_section])
            return
        self.results.clear()
        for entry in search_entries(SETTINGS, query):
            item = QListWidgetItem(icon(entry.glyph), t(entry.title)+'\n'+t(entry.detail))
            item.setData(Qt.ItemDataRole.UserRole, entry)
            item.setSizeHint(QSize(0, 66))
            self.results.addItem(item)
        self.empty.setVisible(self.results.count() == 0)
        self.results.setVisible(self.results.count() > 0)
        if self.results.count():
            self.results.setCurrentRow(0)
        self.pages.setCurrentWidget(self.results_page)

    def activate_result(self, item):
        entry = item.data(Qt.ItemDataRole.UserRole)
        self.select(entry.section, entry.key)

    def eventFilter(self, obj, event):
        if obj is self.search and event.type() == QEvent.Type.KeyPress and self.search.text().strip():
            if event.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                delta = 1 if event.key() == Qt.Key.Key_Down else -1
                self.results.setCurrentRow(max(0, min(self.results.count()-1, self.results.currentRow()+delta)))
                return True
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self.results.currentItem():
                    self.activate_result(self.results.currentItem())
                return True
        return super().eventFilter(obj, event)

    def position_near_window(self):
        bounds = self.win.frameGeometry()
        self.resize(min(920, max(840, bounds.width()-48)), min(660, max(520, bounds.height()-48)))
        self.move(bounds.center()-self.rect().center())

    def done(self, result):
        # An unsaved live accent preview is cancelled when settings closes.
        # Saved values are read afresh when a form is opened again.
        for key, form in list(self.forms.items()):
            if key == 'profile':
                form._cancel()
                self.win._customize_overlay = None
            elif key == 'audio':
                self.win._audio_overlay = None
            elif key == 'ai':
                form.dispose()
            self.layouts[key].removeWidget(form)
            self.targets.pop(key, None)
            form.hide()
            form.deleteLater()
        self.forms.clear()
        super().done(result)

    def refresh(self):
        c = colors()
        arrow = (Path(__file__).resolve().parent / 'assets' / 'chevron.svg').as_posix()
        self.setWindowTitle(t('Sozlamalar'))
        self.setFont(font(10))
        self.setStyleSheet(f'QDialog#BraveSettingsWindow {{background:{c.PANEL};color:{c.TEXT};}} '
            f'QWidget#SettingsPage,QWidget#SettingsScrollViewport {{background:{c.PANEL};}} '
            f'QFrame#SettingsCard {{background:{c.BG};border:1px solid {c.BORDER};border-radius:12px;}} '
            f'QLineEdit,QListWidget,QComboBox {{background:{c.BG};color:{c.TEXT};border:1px solid {c.BORDER};border-radius:9px;padding:9px;}} '
            f'QLineEdit:focus,QComboBox:focus {{border-color:{c.PRI};}} '
            f'QCheckBox {{color:{c.TEXT};spacing:9px;padding:4px 0;}} '
            'QComboBox {padding-right:28px;} QComboBox::drop-down {width:24px;border:none;background:transparent;} '
            f'QComboBox::down-arrow {{image:url("{arrow}");width:10px;height:10px;}} '
            f'QComboBox QAbstractItemView {{background:{c.PANEL2};color:{c.TEXT};selection-background-color:{c.PRI_GHO};}} '
            f'QListWidget::item {{padding:9px;border-radius:7px;}} QListWidget::item:selected {{background:{c.PRI_GHO};color:{c.PRI};}} '
            f'QScrollArea {{background:transparent;border:none;}} QScrollBar:vertical {{background:transparent;width:6px;}} '
            f'QScrollBar::handle:vertical {{background:{c.BORDER_B};min-height:28px;border-radius:3px;}} '
            'QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {height:0;} '
            'QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical {background:transparent;}')
        self.search.setPlaceholderText(t('Sozlamalarni qidirish…'))
        self.search_action.setIcon(icon('search'))
        nav_style = button_style() + f'QPushButton {{background:transparent;border-color:transparent;text-align:left;padding:8px;}} QPushButton:checked {{background:{c.PRI_GHO};color:{c.PRI};border-color:{c.BORDER_B};}}'
        for button in self.nav.values():
            button.setStyleSheet(nav_style)
        self.appearance.refresh()
        if 'profile' in self.forms:
            self.forms['profile'].sync_theme()
        if 'ai' in self.forms:
            self.forms['ai'].show_model_info()
            self.forms['ai'].show_resources()
        localize_widgets(self)
        self.sync_layout()
        if self.search.text().strip():
            self.filter(self.search.text())


def open_settings(win, section=None, target=None):
    dialog = win._quick_drawer
    win._close_controls()
    dialog.refresh()
    dialog.select(section or dialog.current_section, target)
    dialog.position_near_window()
    win._appearance_dialog = dialog
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    win._drawer_btn.setChecked(True)
    if not target:
        dialog.search.setFocus()
