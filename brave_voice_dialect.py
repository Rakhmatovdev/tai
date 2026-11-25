"""Interactive Studio for Uzbek Dialects, Voice Gender, Emotional Tone, Speed, and Pronunciation Shadowing."""
from __future__ import annotations

import re
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy,
    QVBoxLayout, QWidget,
)

from brave_i18n import translate as t
from core.voice_style import (
    DIALECTS, DIALECT_MAP, EMOTIONS, EMOTION_MAP, GENDERS, GENDER_MAP,
    SPEEDS, SPEED_MAP, load_voice_style, normalize_voice_style,
    preview_sentence, recommended_gemini_voice, save_voice_style,
    style_badge_summary,
)


def score_pronunciation(expected: str, actual: str) -> dict:
    """Compare target phrase with spoken/transcribed phrase and return accuracy + word-level diff."""
    def _tokens(txt: str) -> list[str]:
        cleaned = (txt or '').casefold()
        for ap in ('‘', '’', 'ʻ', 'ʼ', '`', '´'):
            cleaned = cleaned.replace(ap, "'")
        return re.findall(r"[\w']+", cleaned)

    exp_words = _tokens(expected)
    act_words = _tokens(actual)
    if not exp_words:
        return {'accuracy': 0.0, 'wer': 1.0, 'matched': [], 'missed': [], 'verdict': 'Matn kiritilmagan'}

    from core.offline_voice import word_error_rate
    wer = float(word_error_rate(' '.join(exp_words), ' '.join(act_words)))
    accuracy = max(0.0, min(100.0, (1.0 - wer) * 100.0))

    act_set = set(act_words)
    matched = [w for w in exp_words if w in act_set]
    missed = [w for w in exp_words if w not in act_set]

    if accuracy >= 90.0:
        verdict = "🌟 A’lo talaffuz! Deyarli xatosiz va ravon."
    elif accuracy >= 72.0:
        verdict = "✅ Yaxshi natija! Ayrim so‘z urg‘ularini yana bir marta mashq qiling."
    elif accuracy >= 45.0:
        verdict = "⚡ O‘rtacha. Avval «🐢 Sekin (0.70×)» rejimda eshitib, bo‘g‘inlab takrorlang."
    else:
        verdict = "🔄 Qayta mashq qiling: jumlani sekin eshitib, har bir so‘zni dona-dona ayting."

    return {
        'accuracy': round(accuracy, 1),
        'wer': round(wer, 3),
        'matched': matched,
        'missed': missed,
        'verdict': verdict,
    }


class VoiceDialectDialog(QDialog):
    """Studio dialog to configure Voice Gender, Uzbek Dialect, Emotional Tone, Pace, and Shadowing."""

    def __init__(self, win, parent=None):
        super().__init__(parent or win)
        from brave_ui import button_style, colors, font
        from brave_control_center import style_dialog

        self.win = win
        self.state = load_voice_style()
        self._custom_preview_edited = False
        c = colors()

        title_txt = t('Ovoz, Sheva va Talaffuz Studiyasi')
        self.setWindowTitle(title_txt)
        self.setFont(font(10))
        screen = win.screen().availableGeometry()
        self.resize(min(860, screen.width() - 48), min(730, screen.height() - 56))
        style_dialog(self, title_txt)

        if not getattr(win, '_local_voice', None):
            from brave_local_voice import LocalVoice
            win._local_voice = LocalVoice(win)
        self.voice = win._local_voice

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)

        # Header Banner
        banner = QFrame()
        banner.setStyleSheet(f'QFrame {{background:{c.PRI_GHO};border:1px solid {c.PRI_DIM};border-radius:12px;}}')
        b_lay = QVBoxLayout(banner)
        b_lay.setContentsMargins(14, 10, 14, 10)
        b_lay.setSpacing(3)
        head = QLabel(t('🎙️ O‘zbek Shevalari · Ayol va Erkak Ovozi · Hissiy Ohang va Talaffuz'))
        head.setFont(font(12, True))
        head.setStyleSheet(f'color:{c.PRI};border:none;background:transparent;')
        sub = QLabel(t(
            'AI ustoz va ovozli yordamchining jinsi, hududiy o‘zbek shevasi (Toshkent, Vodiy, Samarqand–Buxoro, '
            'Xorazm, Qashqadaryo–Surxon), gapirish ohangi (mayin/nejniy, muhabbat bilan, qattiqqo‘l, dangal/qo‘pol) '
            'hamda talaffuz tezligini (0.70×–1.40×) bir joyda boshqaring.'
        ))
        sub.setWordWrap(True)
        sub.setFont(font(9))
        sub.setStyleSheet(f'color:{c.TEXT};border:none;background:transparent;')
        b_lay.addWidget(head)
        b_lay.addWidget(sub)
        root.addWidget(banner)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet('QScrollArea {background:transparent;border:none;}')
        body = QWidget()
        body.setStyleSheet('background:transparent;')
        form = QVBoxLayout(body)
        form.setContentsMargins(2, 2, 8, 2)
        form.setSpacing(12)

        # 1. Gender & Speed Card
        gs_card = QFrame()
        gs_card.setStyleSheet(f'QFrame {{background:{c.PANEL2};border:1px solid {c.BORDER};border-radius:12px;}}')
        gs_lay = QVBoxLayout(gs_card)
        gs_lay.setContentsMargins(14, 12, 14, 12)
        gs_lay.setSpacing(8)
        gs_title = QLabel(t('1. Ovoz Jinsi va Gapirish Tezligi'))
        gs_title.setFont(font(10, True))
        gs_title.setStyleSheet(f'color:{c.WHITE};border:none;background:transparent;')
        gs_lay.addWidget(gs_title)

        gender_row = QHBoxLayout()
        gender_row.setSpacing(8)
        self.gender_buttons: dict[str, QPushButton] = {}
        for g in GENDERS:
            btn = QPushButton(f"{g.badge}  —  {t(g.title)}")
            btn.setCheckable(True)
            btn.setChecked(self.state['gender'] == g.key)
            btn.setMinimumHeight(38)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, k=g.key: self._select_gender(k))
            self.gender_buttons[g.key] = btn
            gender_row.addWidget(btn, 1)
        gs_lay.addLayout(gender_row)

        speed_row = QHBoxLayout()
        speed_row.setSpacing(8)
        sp_lbl = QLabel(t('Talaffuz va nutq tezligi:'))
        sp_lbl.setFont(font(9, True))
        sp_lbl.setStyleSheet(f'color:{c.TEXT_MED};border:none;background:transparent;')
        self.speed_combo = QComboBox()
        self.speed_combo.setMinimumHeight(34)
        for sp in SPEEDS:
            self.speed_combo.addItem(f"{sp.badge}  ·  {t(sp.title)}", sp.key)
        self.speed_combo.setCurrentIndex(max(0, self.speed_combo.findData(self.state['speed'])))
        self.speed_combo.currentIndexChanged.connect(self._on_speed_changed)
        speed_row.addWidget(sp_lbl)
        speed_row.addWidget(self.speed_combo, 1)
        gs_lay.addLayout(speed_row)

        self.auto_gemini_chk = QCheckBox(t('Gemini Live ovozini tanlangan jins va ohangga avtomatik moslashtirish'))
        self.auto_gemini_chk.setChecked(bool(self.state.get('auto_sync_gemini_voice', True)))
        self.auto_gemini_chk.setFont(font(9))
        self.auto_gemini_chk.setStyleSheet(f'color:{c.TEXT};border:none;background:transparent;')
        gs_lay.addWidget(self.auto_gemini_chk)
        form.addWidget(gs_card)

        # 2. Uzbek Dialects Grid
        dial_card = QFrame()
        dial_card.setStyleSheet(f'QFrame {{background:{c.PANEL2};border:1px solid {c.BORDER};border-radius:12px;}}')
        dc_lay = QVBoxLayout(dial_card)
        dc_lay.setContentsMargins(14, 12, 14, 12)
        dc_lay.setSpacing(8)
        dc_title = QLabel(t('2. O‘zbek Tili Shevalari (Suhbat va Tushuntirish Lahjasi)'))
        dc_title.setFont(font(10, True))
        dc_title.setStyleSheet(f'color:{c.WHITE};border:none;background:transparent;')
        dc_lay.addWidget(dc_title)

        self.dialect_buttons: dict[str, QPushButton] = {}
        dial_grid = QGridLayout()
        dial_grid.setSpacing(8)
        for idx, d in enumerate(DIALECTS):
            btn = QPushButton()
            btn.setCheckable(True)
            btn.setChecked(self.state['dialect'] == d.key)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(68)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            bl = QVBoxLayout(btn)
            bl.setContentsMargins(10, 7, 10, 7)
            bl.setSpacing(2)
            d_head = QLabel(f"🗺️ {t(d.title)}  ·  {d.region}")
            d_head.setFont(font(9, True))
            d_head.setStyleSheet(f'color:{c.WHITE};background:transparent;border:none;')
            d_desc = QLabel(d.summary)
            d_desc.setWordWrap(True)
            d_desc.setFont(font(8))
            d_desc.setStyleSheet(f'color:{c.TEXT_DIM};background:transparent;border:none;')
            for ch in (d_head, d_desc):
                ch.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                bl.addWidget(ch)
            btn.clicked.connect(lambda _=False, k=d.key: self._select_dialect(k))
            self.dialect_buttons[d.key] = btn
            dial_grid.addWidget(btn, idx // 2, idx % 2)
        dc_lay.addLayout(dial_grid)

        self.phonetic_chk = QCheckBox(t('Lokal o‘zbek ovozida (TTS) sheva qo‘shimchalarini talaffuzga qo‘llash (-votti, -opti, galing va h.k.)'))
        self.phonetic_chk.setChecked(bool(self.state.get('phonetic_dialect_tts', True)))
        self.phonetic_chk.setFont(font(9))
        self.phonetic_chk.setStyleSheet(f'color:{c.TEXT};border:none;background:transparent;')
        dc_lay.addWidget(self.phonetic_chk)
        form.addWidget(dial_card)

        # 3. Emotional Tone & Character Cards
        emo_card = QFrame()
        emo_card.setStyleSheet(f'QFrame {{background:{c.PANEL2};border:1px solid {c.BORDER};border-radius:12px;}}')
        ec_lay = QVBoxLayout(emo_card)
        ec_lay.setContentsMargins(14, 12, 14, 12)
        ec_lay.setSpacing(8)
        ec_title = QLabel(t('3. Hissiy Ohang va Gaplashish Xarakteri'))
        ec_title.setFont(font(10, True))
        ec_title.setStyleSheet(f'color:{c.WHITE};border:none;background:transparent;')
        ec_lay.addWidget(ec_title)

        self.emotion_buttons: dict[str, QPushButton] = {}
        emo_grid = QGridLayout()
        emo_grid.setSpacing(7)
        for idx, emo in enumerate(EMOTIONS):
            btn = QPushButton()
            btn.setCheckable(True)
            btn.setChecked(self.state['emotion'] == emo.key)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(60)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            bl = QVBoxLayout(btn)
            bl.setContentsMargins(10, 6, 10, 6)
            bl.setSpacing(2)
            e_head = QLabel(f"{emo.badge}  —  {t(emo.title)}")
            e_head.setFont(font(9, True))
            e_head.setStyleSheet(f'color:{c.WHITE};background:transparent;border:none;')
            e_desc = QLabel(t(emo.summary))
            e_desc.setWordWrap(True)
            e_desc.setFont(font(8))
            e_desc.setStyleSheet(f'color:{c.TEXT_DIM};background:transparent;border:none;')
            for ch in (e_head, e_desc):
                ch.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                bl.addWidget(ch)
            btn.clicked.connect(lambda _=False, k=emo.key: self._select_emotion(k))
            self.emotion_buttons[emo.key] = btn
            emo_grid.addWidget(btn, idx // 2, idx % 2)
        ec_lay.addLayout(emo_grid)
        form.addWidget(emo_card)

        # 4. Live Voice Preview & Pronunciation Shadowing Trainer
        lab_card = QFrame()
        lab_card.setStyleSheet(f'QFrame {{background:{c.PANEL2};border:1px solid {c.BORDER};border-radius:12px;}}')
        lb_lay = QVBoxLayout(lab_card)
        lb_lay.setContentsMargins(14, 12, 14, 12)
        lb_lay.setSpacing(8)
        lb_head = QHBoxLayout()
        lb_title = QLabel(t('4. Jonli Eshitib Ko‘rish va Talaffuz Mashqi (Shadowing)'))
        lb_title.setFont(font(10, True))
        lb_title.setStyleSheet(f'color:{c.PRI};border:none;background:transparent;')
        lb_head.addWidget(lb_title)
        lb_head.addStretch()
        reset_sample_btn = QPushButton(t('🔄 Sheva namunasini qo‘yish'))
        reset_sample_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_sample_btn.setStyleSheet(button_style() + 'QPushButton {padding:3px 9px;font-size:11px;}')
        reset_sample_btn.clicked.connect(self._reset_sample_text)
        lb_head.addWidget(reset_sample_btn)
        lb_lay.addLayout(lb_head)

        self.preview_input = QPlainTextEdit(preview_sentence(self.state))
        self.preview_input.setFixedHeight(64)
        self.preview_input.setPlaceholderText(t('Eshitib ko‘rish yoki talaffuz mashqi uchun matn yozing…'))
        self.preview_input.textChanged.connect(self._on_preview_text_edited)
        lb_lay.addWidget(self.preview_input)

        play_row = QHBoxLayout()
        play_row.setSpacing(6)
        self.play_btn = QPushButton(t('🔊 Tanlangan Ovozda Eshitish'))
        self.play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.play_btn.setStyleSheet(button_style(True) + 'QPushButton {padding:6px 12px;font-weight:600;}')
        self.play_btn.clicked.connect(lambda: self.preview_audio(slow_override=False))

        self.slow_play_btn = QPushButton(t('🐢 Sekin Bo‘g‘inlab Eshitish (0.70×)'))
        self.slow_play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.slow_play_btn.setStyleSheet(button_style() + 'QPushButton {padding:6px 12px;}')
        self.slow_play_btn.clicked.connect(lambda: self.preview_audio(slow_override=True))

        self.stop_play_btn = QPushButton(t('⏹ To‘xtatish'))
        self.stop_play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_play_btn.setStyleSheet(button_style() + 'QPushButton {padding:6px 10px;}')
        self.stop_play_btn.clicked.connect(lambda: self.voice.cancel())

        play_row.addWidget(self.play_btn)
        play_row.addWidget(self.slow_play_btn)
        play_row.addWidget(self.stop_play_btn)
        play_row.addStretch()
        lb_lay.addLayout(play_row)

        # Shadowing pronunciation check row
        shadow_row = QHBoxLayout()
        shadow_row.setSpacing(6)
        self.spoken_input = QLineEdit()
        self.spoken_input.setPlaceholderText(t('Talaffuz tekshiruvi: mikrofon bilan ayting yoki eshitganingizni yozib tekshiring…'))
        self.record_shadow_btn = QPushButton(t('🎙️ Mikrofon bilan aytish'))
        self.record_shadow_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.record_shadow_btn.setStyleSheet(button_style() + 'QPushButton {padding:5px 10px;}')
        self.record_shadow_btn.clicked.connect(self._toggle_shadow_record)

        self.check_pron_btn = QPushButton(t('✅ Talaffuzni Baholash'))
        self.check_pron_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.check_pron_btn.setStyleSheet(button_style(True) + 'QPushButton {padding:5px 12px;}')
        self.check_pron_btn.clicked.connect(self._evaluate_pronunciation)

        shadow_row.addWidget(self.spoken_input, 1)
        shadow_row.addWidget(self.record_shadow_btn)
        shadow_row.addWidget(self.check_pron_btn)
        lb_lay.addLayout(shadow_row)

        self.feedback_lbl = QLabel(t('💡 Maslahat: Lokal o‘zbek AI ovozi yuklangan bo‘lsa internetsiz ishlaydi, aks holda Windows ovozi qo‘llanadi.'))
        self.feedback_lbl.setWordWrap(True)
        self.feedback_lbl.setFont(font(9))
        self.feedback_lbl.setStyleSheet(f'color:{c.TEXT_MED};border:none;background:transparent;')
        lb_lay.addWidget(self.feedback_lbl)
        form.addWidget(lab_card)

        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        # Footer
        footer = QHBoxLayout()
        self.summary_lbl = QLabel()
        self.summary_lbl.setFont(font(9, True))
        self.summary_lbl.setStyleSheet(f'color:{c.PRI};border:none;background:transparent;')
        footer.addWidget(self.summary_lbl, 1)

        cancel_btn = QPushButton(t('Yopish'))
        cancel_btn.setMinimumHeight(36)
        cancel_btn.setStyleSheet(button_style())
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton(t('Saqlash va Qo‘llash'))
        save_btn.setMinimumHeight(36)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setStyleSheet(button_style(True) + 'QPushButton {padding:6px 18px;font-weight:600;}')
        save_btn.clicked.connect(self.apply_and_save)

        footer.addWidget(cancel_btn)
        footer.addWidget(save_btn)
        root.addLayout(footer)

        self.voice.result.connect(self._on_shadow_transcribed)
        self._refresh_styles()

    def current_draft_style(self) -> dict:
        return normalize_voice_style({
            **self.state,
            'speed': self.speed_combo.currentData() or 'normal',
            'phonetic_dialect_tts': self.phonetic_chk.isChecked(),
            'auto_sync_gemini_voice': self.auto_gemini_chk.isChecked(),
        })

    def _select_gender(self, key: str):
        self.state['gender'] = key
        for k, b in self.gender_buttons.items():
            b.setChecked(k == key)
        self._refresh_styles()

    def _select_dialect(self, key: str):
        self.state['dialect'] = key
        for k, b in self.dialect_buttons.items():
            b.setChecked(k == key)
        if not self._custom_preview_edited:
            self._set_preview_programmatically(preview_sentence(self.current_draft_style()))
        self._refresh_styles()

    def _select_emotion(self, key: str):
        self.state['emotion'] = key
        for k, b in self.emotion_buttons.items():
            b.setChecked(k == key)
        if not self._custom_preview_edited:
            self._set_preview_programmatically(preview_sentence(self.current_draft_style()))
        self._refresh_styles()

    def _on_speed_changed(self):
        self.state['speed'] = self.speed_combo.currentData() or 'normal'
        self._refresh_styles()

    def _set_preview_programmatically(self, text: str):
        self.preview_input.blockSignals(True)
        self.preview_input.setPlainText(text)
        self.preview_input.blockSignals(False)

    def _on_preview_text_edited(self):
        self._custom_preview_edited = True

    def _reset_sample_text(self):
        self._custom_preview_edited = False
        self._set_preview_programmatically(preview_sentence(self.current_draft_style()))

    def _refresh_styles(self):
        from brave_ui import button_style, colors
        c = colors()
        for k, b in self.gender_buttons.items():
            b.setStyleSheet(button_style(b.isChecked()))
        for group in (self.dialect_buttons, self.emotion_buttons):
            for k, b in group.items():
                active = b.isChecked()
                b.setStyleSheet(
                    f'QPushButton {{background:{c.PRI_GHO if active else c.BG};'
                    f'border:1px solid {c.PRI if active else c.BORDER};border-radius:10px;text-align:left;}}'
                    f'QPushButton:hover {{border-color:{c.PRI_DIM};}}'
                )
        draft = self.current_draft_style()
        gem_voice = recommended_gemini_voice(draft)
        self.summary_lbl.setText(f"Faol profil: {style_badge_summary(draft)}  ·  Gemini ovozi: {gem_voice}")

    def preview_audio(self, slow_override: bool = False):
        text = self.preview_input.toPlainText().strip() or preview_sentence(self.current_draft_style())
        draft = self.current_draft_style()
        if slow_override:
            draft = {**draft, 'speed': 'very_slow'}
        from core import uzbek_tts
        voice_id = uzbek_tts.VOICE_ID if uzbek_tts.ready() else ''
        self.feedback_lbl.setText(
            f"🔊 Ijro etilmoqda: {style_badge_summary(draft)} "
            + ("(Lokal O‘zbek VITS AI)" if voice_id else "(Tizim SAPI ovozi)")
        )
        self.voice.say(text, voice_id=voice_id, force=True, style=draft)

    def _toggle_shadow_record(self):
        if self.voice.recording:
            self.voice.stop_record.set()
            self.record_shadow_btn.setText(t('🎙️ Mikrofon bilan aytish'))
            return
        from memory.config_manager import load_api_keys
        from core import offline_voice
        cfg = load_api_keys()
        stt_path = cfg.get('local_stt_path', str(offline_voice.model_directory()))
        lang_code = 'uz'
        if hasattr(self.win, '_language_tutor'):
            t_lang = self.win._language_tutor.state.get('target_language', 'uz')
            if t_lang in ('en', 'ru', 'de', 'fr', 'es', 'it', 'tr', 'ar', 'zh', 'ja', 'ko'):
                # Use auto so both Uzbek preview sentences and foreign target sentences transcribe cleanly
                lang_code = 'auto'
        self.voice.record(stt_path, lang_code, live=False, auto_stop=True, chat_id=None, allow_any_provider=True)
        if self.voice.recording:
            self.record_shadow_btn.setText(t('⏹ Yozishni to‘xtatish'))
            self.feedback_lbl.setText(t('🎙️ Gapiring… Jumlani aniq o‘qib bering.'))
        else:
            self.feedback_lbl.setText(t('💡 Mikrofon bilan tekshirish uchun Offline Ovoz bo‘limida STT modelini yuklang yoki matnni qo‘lda yozib sinang.'))

    def _on_shadow_transcribed(self, revision: int, text: str, error: str):
        self.record_shadow_btn.setText(t('🎙️ Mikrofon bilan aytish'))
        if text.strip():
            self.spoken_input.setText(text.strip())
            self._evaluate_pronunciation()
        elif error:
            self.feedback_lbl.setText(t(error))

    def _evaluate_pronunciation(self):
        target = self.preview_input.toPlainText().strip()
        spoken = self.spoken_input.text().strip()
        if not spoken:
            self.feedback_lbl.setText(t('Avval jumlani mikrofon orqali ayting yoki pastdagi maydonga yozing.'))
            return
        report = score_pronunciation(target, spoken)
        missed_txt = (
            f"  |  E’tibor bering: {', '.join(report['missed'][:6])}"
            if report['missed'] else "  |  Barcha kalit so‘zlar to‘liq aytildi!"
        )
        self.feedback_lbl.setText(f"🎯 Talaffuz aniqligi: {report['accuracy']:.1f}% — {report['verdict']}{missed_txt}")

    def apply_and_save(self):
        saved = save_voice_style(self.current_draft_style())
        voice_changed = False
        if saved.get('auto_sync_gemini_voice', True):
            from memory.config_manager import get_voice, save_voice
            target_gem = recommended_gemini_voice(saved)
            if target_gem != get_voice():
                save_voice(target_gem)
                voice_changed = True

        if getattr(self.win, 'on_voice_change', None):
            # Reconnect Live session so both prebuilt voice & new dialect/emotion system prompt apply immediately
            try:
                self.win.on_voice_change()
            except Exception:
                pass
        if hasattr(self.win, '_language_tutor'):
            self.win._language_tutor.refresh_ui()
        if hasattr(self.win, '_log'):
            self.win._log.append_log(
                f"SYS: 🎙️ Ovoz va sheva yangilandi: {style_badge_summary(saved)}"
                + (f" (Gemini ovozi: {recommended_gemini_voice(saved)})" if voice_changed else "")
            )
        self.accept()

    def done(self, result):
        try:
            self.voice.result.disconnect(self._on_shadow_transcribed)
        except (TypeError, RuntimeError):
            pass
        super().done(result)


def open_voice_dialect_studio(win, parent=None):
    dialog = VoiceDialectDialog(win, parent=parent)
    win._voice_dialect_dialog = dialog
    dialog.exec()
    return dialog
