"""Offline integration checks for native appearance switching.

Run: .venv/Scripts/python.exe -m unittest discover -s tests -v
Optional screenshots: set BRAVE_UI_PREVIEWS to a destination directory.
"""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton

import ui
import brave_ui
from brave_appearance import open_appearance
from brave_i18n import translate
from memory import config_manager
from core import workspace_store


class AppearanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.temp = tempfile.TemporaryDirectory()
        cls.config = Path(cls.temp.name) / 'settings.json'
        cls.patches = [
            patch.object(ui, 'API_FILE', cls.config),
            patch.object(config_manager, 'CONFIG_FILE', cls.config),
            patch.object(workspace_store, 'directory', return_value=Path(cls.temp.name)),
            patch.object(ui.MainWindow, '_check_config', return_value=True),
            patch.object(ui.MainWindow, '_check_autostart', return_value=False),
        ]
        for item in cls.patches:
            item.start()
        cls.win = ui.MainWindow('')
        cls.win.show()
        cls.win.resize(1440, 900)
        cls.app.processEvents()

    @classmethod
    def tearDownClass(cls):
        cls.win.close()
        cls.win.deleteLater()
        cls.app.processEvents()
        for item in reversed(cls.patches):
            item.stop()
        cls.temp.cleanup()

    def setUp(self):
        palette = getattr(self.win, '_command_palette', None)
        if palette is not None:
            palette.reject()
        self.win._close_setup()
        from brave_chat import set_chat_focus
        self.win._layout_state.timer.stop()
        self.win._layout_state.ready = False
        self.win.showNormal()
        self.win.setMinimumSize(ui._MIN_W, ui._MIN_H)
        set_chat_focus(self.win, False, persist=False)
        self.win._layout_state.remember = True
        self.win._layout_state.ready = True
        (Path(self.temp.name) / 'ui-layout.json').unlink(missing_ok=True)
        self.config.write_text('{}', encoding='utf-8')
        brave_ui.set_language(self.win, 'uz', persist=False)
        brave_ui.set_theme(self.win, 'dark', persist=False)
        self.win._log.clear()
        self.win._input.clear()
        self.win.resize(1440, 900)
        self.win.activateWindow()
        self.app.processEvents()

    def test_click_persists_and_returns_to_default(self):
        open_appearance(self.win)
        dialog = self.win._appearance_dialog
        for index, key in [(2, 'hacker'), (1, 'light'), (0, 'dark')]:
            QTest.mouseClick(dialog.options[index], Qt.MouseButton.LeftButton)
            self.app.processEvents()
            self.assertEqual(brave_ui.current_theme(), key)
            self.assertEqual(json.loads(self.config.read_text())['ui_theme'], key)
            self.assertEqual(sum(option.isChecked() for option in dialog.options), 1)
            self.assertEqual(ui.C.PRI, brave_ui.THEMES[key]['PRI'])
        dialog.accept()

    def test_keyboard_selection(self):
        open_appearance(self.win)
        dialog = self.win._appearance_dialog
        dialog.options[2].setFocus()
        QTest.keyClick(dialog.options[2], Qt.Key.Key_Space)
        self.assertEqual(brave_ui.current_theme(), 'hacker')
        dialog.accept()

    def test_custom_accent_does_not_override_hacker(self):
        self.config.write_text(json.dumps({'ui_color': '#4677ee'}), encoding='utf-8')
        brave_ui.set_theme(self.win, 'hacker', persist=False)
        self.assertEqual(ui.C.PRI, brave_ui.THEMES['hacker']['PRI'])
        brave_ui.set_theme(self.win, 'dark', persist=False)
        self.assertNotEqual(ui.C.PRI, brave_ui.THEMES['dark']['PRI'])

    def test_restart_restores_hacker(self):
        brave_ui.set_theme(self.win, 'hacker')
        second = ui.MainWindow('')
        try:
            self.assertEqual(brave_ui.current_theme(), 'hacker')
            self.assertEqual(ui.C.PRI, brave_ui.THEMES['hacker']['PRI'])
            self.assertEqual(second._theme_btn.accessibleName(), 'Ko‘rinish')
        finally:
            second.close()
            second.deleteLater()
            self.app.processEvents()

    def test_chat_draft_survives_theme_changes(self):
        draft = 'Matnni keyin yuboraman.'
        self.win._input.setText(draft)
        self.win._log.append_log('You: UI sinovi')
        self.win._log.append_log('Brave: **Tayyor.** `hello()`')
        history = list(self.win._log._history)
        for key in ('hacker', 'light', 'dark', 'hacker', 'dark'):
            brave_ui.set_theme(self.win, key, persist=False)
            self.app.processEvents()
            self.assertEqual(self.win._input.text(), draft)
            self.assertEqual(self.win._log._history, history)
        self.win._input.clear()

    def test_all_languages_and_sizes_render(self):
        destination = os.environ.get('BRAVE_UI_PREVIEWS')
        if destination:
            Path(destination).mkdir(parents=True, exist_ok=True)
        for lang in ('uz', 'en', 'ru'):
            brave_ui.set_language(self.win, lang, persist=False)
            for key in ('dark', 'light', 'hacker'):
                brave_ui.set_theme(self.win, key, persist=False)
                for width, height in ((1440, 900), (1040, 700)):
                    self.win.resize(width, height)
                    # Qt resolves the scroll area's width and height-for-width
                    # labels over several layout passes, like a real event loop.
                    QTest.qWait(90)
                    self.assertEqual(self.win.width(), width)
                    self.assertEqual(self.win.height(), height)
                    self.assertGreaterEqual(self.win.hud.width(), 300)
                    self.assertRegex(self.win._clock_lbl.text(), r'^\d{2}:\d{2}:\d{2}$')
                    self.assertTrue(self.win._date_lbl.isVisible())
                    self.assertTrue(self.win._header_widget.rect().contains(self.win._clock_frame.geometry()))
                    if width >= 1180:
                        self.assertGreaterEqual(self.win._ctrl_btn.width(), self.win._ctrl_btn.sizeHint().width())
                    welcome = self.win._log.welcome
                    self.assertLessEqual(welcome.geometry().right(), self.win._log.scroll.viewport().width())
                    self.assertTrue(self.win._right_panel.rect().contains(self.win._input.mapTo(self.win._right_panel, self.win._input.rect().topLeft())))
                    if destination:
                        self.win.grab().save(str(Path(destination) / f'brave-{key}-{lang}-{width}.png'))
            open_appearance(self.win)
            self.app.processEvents()
            self.assertEqual(self.win._appearance_dialog.options[0].accessibleName(), translate('Standart'))
            if destination:
                self.win._appearance_dialog.grab().save(str(Path(destination) / f'brave-appearance-{lang}.png'))
            self.win._appearance_dialog.accept()

    def test_palette_replacement_does_not_cascade(self):
        widget = QLabel()
        widget.setStyleSheet('color: #112233; background: #445566;')
        ui.retheme_all_widgets({'a': '#112233', 'b': '#445566'}, {'a': '#445566', 'b': '#778899'})
        self.assertEqual(widget.styleSheet(), 'color: #445566; background: #778899;')
        widget.deleteLater()

    def test_clock_seconds_and_midnight_rollover(self):
        from datetime import datetime, timedelta, timezone
        current = [datetime(2026, 10, 15, 18, 59, 59, tzinfo=timezone.utc)]

        class ClockTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return current[0].astimezone(tz)

        with patch('datetime.datetime', ClockTime):
            brave_ui.tick_clock(self.win)
            self.assertEqual(self.win._clock_lbl.text(), '23:59:59')
            self.assertEqual(self.win._date_lbl.text(), '15 okt 2026')
            current[0] += timedelta(seconds=1)
            brave_ui.tick_clock(self.win)
            self.assertEqual(self.win._clock_lbl.text(), '00:00:00')
            self.assertEqual(self.win._date_lbl.text(), '16 okt 2026')
            self.assertEqual(self.win._clock_lbl.accessibleName(), '00:00:00')
        self.assertTrue(self.win._clock_tmr.isActive())
        self.assertEqual(self.win._clock_tmr.interval(), 1000)

    def test_settings_actions_have_one_entry_point(self):
        for lang in ('uz', 'en', 'ru'):
            brave_ui.set_language(self.win, lang, persist=False)
            for title in ('Ko‘rinish', 'Audio qurilmalar', 'Shaxsiylashtirish'):
                buttons = [button for button in self.win.findChildren(QPushButton)
                           if button.text() == translate(title)]
                self.assertEqual(len(buttons), 1, (lang, title))
                self.assertTrue(self.win._quick_drawer.isAncestorOf(buttons[0]))
            self.assertNotIn(self.win._theme_btn, self.win._header_widget.findChildren(QPushButton))
            self.assertFalse(any(button.text() == translate('Xotira')
                                 for button in self.win._left_panel.findChildren(QPushButton)))
        self.assertFalse(hasattr(self.win, '_chat_export_btn'))

    def test_appearance_stays_inside_single_settings_window(self):
        QTest.mouseClick(self.win._drawer_btn, Qt.MouseButton.LeftButton)
        self.assertTrue(self.win._quick_drawer.isVisible())
        dialog = self.win._quick_drawer
        QTest.mouseClick(self.win._theme_btn, Qt.MouseButton.LeftButton)
        self.app.processEvents()
        try:
            self.assertIs(self.win._appearance_dialog, dialog)
            self.assertTrue(dialog.isVisible())
            self.assertEqual(dialog.current_section, 'appearance')
            self.assertTrue(self.win._drawer_btn.isChecked())
        finally:
            dialog.accept()
        self.assertFalse(self.win._drawer_btn.isChecked())

    def test_export_remains_available_in_chat_tools(self):
        tools = self.win.findChild(QPushButton, 'BraveChatTools')
        self.assertIsNotNone(tools)
        labels=[action.text() for action in tools.menu().actions()]
        self.assertEqual(len(labels),len(set(labels)))
        self.win._log.append_log('You: Eksport tugmasi sinovi')
        self.win._log.append_log('Brave: Natija saqlanishi kerak.')
        self.win._log.append_log('SYS: internal-activity-export-check')
        destination = Path(self.temp.name) / 'conversation.md'
        with patch('brave_chat_tools.QFileDialog.getSaveFileName', return_value=(str(destination), 'Markdown (*.md)')):
            tools.menu().actions()[0].trigger()
        content = destination.read_text(encoding='utf-8')
        self.assertIn('Eksport tugmasi sinovi', content)
        self.assertIn('Natija saqlanishi kerak.', content)
        self.assertNotIn('internal-activity-export-check', content)

    def test_theme_round_trip_keeps_surface_colors(self):
        style = self.win.centralWidget().styleSheet()
        for key in ('hacker', 'light', 'dark'):
            brave_ui.set_theme(self.win, key, persist=False)
        self.assertEqual(self.win.centralWidget().styleSheet(), style)

    def test_retheme_hides_retired_widgets_immediately(self):
        previous = self.win._log.welcome
        self.win._log.retheme()
        self.assertTrue(previous.isHidden())

    def test_composer_focus_is_visible(self):
        self.win.activateWindow()
        self.win._input.setFocus()
        QTest.qWait(20)
        self.assertTrue(self.win._input.parentWidget().property('editing'))

    def test_starter_action_fills_draft_without_sending(self):
        with patch.object(self.win, '_send') as send:
            QTest.mouseClick(self.win._log.welcome._cards[0][0], Qt.MouseButton.LeftButton)
            self.assertTrue(self.win._input.text().strip())
            send.assert_not_called()

    def test_customization_keeps_hacker_palette(self):
        brave_ui.set_theme(self.win, 'hacker', persist=False)
        self.win._open_customize()
        overlay = self.win._customize_overlay
        self.assertFalse(overlay._wheel.isEnabled())
        self.assertTrue(overlay._hex_input.isReadOnly())
        self.win._preview_ui_color('#4677ee')
        self.win._apply_name_update('Brave', '', '#4677ee')
        self.assertEqual(ui.C.PRI, brave_ui.THEMES['hacker']['PRI'])
        brave_ui.set_theme(self.win, 'dark', persist=False)
        self.assertTrue(overlay._wheel.isEnabled())
        overlay.hide()

    def test_readable_theme_text(self):
        def luminance(value):
            channels = [int(value[i:i+2], 16)/255 for i in (1, 3, 5)]
            linear = [channel/12.92 if channel <= .04045 else ((channel+.055)/1.055)**2.4 for channel in channels]
            return sum(a*b for a, b in zip(linear, (.2126, .7152, .0722)))

        for key, palette in brave_ui.THEMES.items():
            for foreground in ('TEXT', 'TEXT_MED', 'TEXT_DIM'):
                for background in ('BG', 'PANEL', 'PANEL2'):
                    a, b = sorted([luminance(palette[foreground]), luminance(palette[background])])
                    self.assertGreaterEqual((b+.05)/(a+.05), 4.5, (key, foreground, background))

    def test_settings_search_matches_translations_and_apostrophes(self):
        from brave_navigation import SETTINGS, search_entries
        for query, expected in [("ko'rinish", 'appearance'), ('оформление', 'appearance'),
                                ('microphone', 'audio'), ('микрофон', 'audio'), ('ovoz nom', 'profile')]:
            self.assertIn(expected, [entry.key for entry in search_entries(SETTINGS, query)])
        self.assertEqual(search_entries(SETTINGS, 'no-such-setting-928'), [])

    def test_settings_search_navigates_without_saving(self):
        from brave_settings import open_settings
        open_settings(self.win)
        dialog = self.win._quick_drawer
        before = self.config.read_text()
        dialog.search.setText('микрофон')
        self.assertEqual(dialog.results.count(), 1)
        self.assertEqual(self.config.read_text(), before)
        with patch('core.audio_devices.list_devices', return_value=[]):
            QTest.keyClick(dialog.search, Qt.Key.Key_Return)
        self.assertEqual(dialog.current_section, 'audio')
        self.assertTrue(dialog.forms['audio'].isVisible())
        self.assertEqual(self.config.read_text(), before)

    def test_settings_language_change_stays_in_same_window(self):
        from brave_settings import open_settings
        open_settings(self.win, 'appearance', 'language')
        dialog = self.win._quick_drawer
        self.win._language_box.setCurrentIndex(self.win._language_box.findData('ru'))
        self.assertTrue(dialog.isVisible())
        self.assertEqual(dialog.windowTitle(), 'Настройки')
        self.assertEqual(json.loads(self.config.read_text())['ui_language'], 'ru')
        self.assertIs(dialog, self.win._quick_drawer)

    def test_embedded_profile_save_keeps_settings_visible(self):
        self.win._open_customize()
        dialog = self.win._quick_drawer
        form = dialog.forms['profile']
        form._user_input.setText('Test User')
        form._save()
        self.assertTrue(dialog.isVisible())
        self.assertTrue(form.isVisible())
        self.assertEqual(json.loads(self.config.read_text())['user_name'], 'Test User')

    def test_unsaved_accent_is_reverted_when_settings_closes(self):
        before = ui.current_palette()
        self.win._open_customize()
        form = self.win._customize_overlay
        form._set_color('#4677ee')
        self.assertNotEqual(ui.current_palette(), before)
        self.win._quick_drawer.reject()
        self.assertEqual(ui.current_palette(), before)
        self.assertIsNone(self.win._customize_overlay)
        self.assertEqual(json.loads(self.config.read_text()), {})

    def test_embedded_audio_applies_only_explicitly(self):
        from memory.config_manager import get_input_device, get_output_device
        with patch('core.audio_devices.list_devices', return_value=[]):
            self.win._open_audio_devices()
        form = self.win._audio_overlay
        before = self.config.read_text()
        form._in_box.addItem('Test mic', 'Test mic')
        form._in_box.setCurrentIndex(form._in_box.count()-1)
        form._out_box.addItem('Test speaker', 'Test speaker')
        form._out_box.setCurrentIndex(form._out_box.count()-1)
        self.assertEqual(self.config.read_text(), before)
        with patch.object(self.win, '_on_audio_devices_applied'):
            # The existing signal uses its bound handler; the actual backend
            # callback is absent in this offline fixture.
            form._apply()
        self.assertEqual(get_input_device(), 'Test mic')
        self.assertEqual(get_output_device(), 'Test speaker')
        self.assertTrue(form.isVisible())
        self.assertTrue(self.win._quick_drawer.isVisible())

    def test_ctrl_k_and_escape_preserve_draft(self):
        self.win._input.setText('Saqlanadigan qoralama')
        self.win.activateWindow()
        self.win._input.setFocus()
        QTest.qWait(20)
        with patch('brave_commands.invoke') as dispatch:
            QTest.keyClick(self.win._input, Qt.Key.Key_K, Qt.KeyboardModifier.ControlModifier)
            QTest.qWait(30)
            dialog = self.win._command_palette
            self.assertTrue(dialog.isVisible())
            dialog.search.setText('fullscreen')
            QTest.keyClick(dialog.search, Qt.Key.Key_Escape)
            QTest.qWait(20)
            dispatch.assert_not_called()
        self.assertEqual(self.win._input.text(), 'Saqlanadigan qoralama')

    def test_ctrl_k_works_inside_settings(self):
        from brave_settings import open_settings
        open_settings(self.win)
        settings = self.win._quick_drawer
        QTest.qWait(20)
        QTest.keyClick(settings.search, Qt.Key.Key_K, Qt.KeyboardModifier.ControlModifier)
        QTest.qWait(20)
        self.assertTrue(self.win._command_palette.isVisible())
        self.win._command_palette.reject()
        self.assertTrue(settings.isVisible())

    def test_fast_enter_activates_current_query_only(self):
        from brave_commands import open_commands
        dialog = open_commands(self.win)
        with patch('brave_commands.invoke') as dispatch:
            dialog.search.setText('fullscreen')
            QTest.keyClick(dialog.search, Qt.Key.Key_Return)
            QTest.qWait(30)
            dispatch.assert_called_once_with(self.win, 'fullscreen')

    def test_no_result_enter_runs_nothing(self):
        from brave_commands import open_commands
        dialog = open_commands(self.win)
        with patch('brave_commands.invoke') as dispatch:
            dialog.search.setText('no-such-command-928')
            QTest.keyClick(dialog.search, Qt.Key.Key_Return)
            self.assertEqual(dialog.results.count(), 0)
            self.assertTrue(dialog.isVisible())
            dispatch.assert_not_called()

    def test_unavailable_microphone_command_stays_disabled(self):
        from brave_commands import open_commands
        previous = self.win._text_only
        self.win._text_only = True
        try:
            dialog = open_commands(self.win)
            dialog.search.setText('mute')
            dialog.timer.stop()
            dialog.refresh_results()
            self.assertEqual(dialog.results.count(), 1)
            item = dialog.results.item(0)
            self.assertFalse(item.flags() & Qt.ItemFlag.ItemIsEnabled)
            with patch('brave_commands.invoke') as dispatch:
                dialog.activate(item)
                dispatch.assert_not_called()
        finally:
            self.win._text_only = previous

    def test_busy_guard_is_rechecked_at_command_activation(self):
        from brave_commands import open_commands
        dialog = open_commands(self.win)
        dialog.search.setText('new chat')
        dialog.timer.stop()
        dialog.refresh_results()
        item = next(dialog.results.item(index) for index in range(dialog.results.count())
                    if dialog.results.item(index).data(Qt.ItemDataRole.UserRole) == ('entry', 'new-chat'))
        previous = self.win.can_change_chat
        self.win.can_change_chat = lambda: False
        try:
            with patch('brave_commands.invoke') as dispatch:
                dialog.activate(item)
                dispatch.assert_not_called()
                self.assertTrue(dialog.isVisible())
        finally:
            self.win.can_change_chat = previous

    def test_chat_search_is_local_and_previews_before_resume(self):
        from brave_commands import open_commands
        chat_id = self.win._features.store.new_id()
        self.win._features.store.append(chat_id, 'user', 'ПРИВЕТ НАВИГАЦИЯ <script>alert(1)</script>', '12:00')
        current_chat = self.win._features.chat_id
        dialog = open_commands(self.win)
        dialog.search.setText('привет навигация')
        dialog.timer.stop()
        dialog.refresh_results()
        self.assertEqual(dialog.results.count(), 1)
        self.assertIn('<script>', dialog.results.item(0).text())
        self.assertEqual(self.win._features.chat_id, current_chat)
        with patch('brave_commands.preview_chat') as preview, patch.object(self.win._features, 'switch_chat') as resume:
            dialog.activate(dialog.results.item(0))
            QTest.qWait(30)
            preview.assert_called_once_with(self.win, chat_id, 'привет навигация')
            resume.assert_not_called()

    def test_history_search_keeps_percent_and_underscore_literal(self):
        from brave_history import HistoryStore
        store = HistoryStore()
        try:
            store.append('literal', 'user', 'ПЛАН 100%: a_b', '12:00')
            store.append('other', 'user', 'ПЛАН 1000: acb', '12:00')
            self.assertEqual([row[0] for row in store.search('план 100%')], ['literal'])
            self.assertEqual([row[0] for row in store.search('a_b')], ['literal'])
        finally:
            store.close()

    def test_arrow_navigation_flushes_pending_query(self):
        from brave_commands import open_commands
        dialog = open_commands(self.win)
        with patch('brave_commands.invoke') as dispatch:
            dialog.search.setText('chat')
            QTest.keyClick(dialog.search, Qt.Key.Key_Down)
            self.assertEqual(dialog.results.currentRow(), 1)
            kind, key = dialog.results.currentItem().data(Qt.ItemDataRole.UserRole)
            self.assertEqual(kind, 'entry')
            QTest.keyClick(dialog.search, Qt.Key.Key_Return)
            QTest.qWait(20)
            dispatch.assert_called_once_with(self.win, key)

    def test_pending_query_cannot_activate_stale_mouse_result(self):
        from brave_commands import open_commands
        dialog = open_commands(self.win)
        old = dialog.results.item(0)
        with patch('brave_commands.invoke') as dispatch:
            dialog.search.setText('fullscreen')
            dialog.activate(old)
            dispatch.assert_not_called()
            self.assertTrue(dialog.isVisible())
            self.assertEqual(dialog.results.count(), 1)

    def test_settings_and_palette_render_in_all_themes(self):
        from brave_commands import open_commands
        from brave_settings import open_settings
        destination = os.environ.get('BRAVE_UI_PREVIEWS')
        self.win.resize(1040, 700)
        for lang in ('uz', 'en', 'ru'):
            brave_ui.set_language(self.win, lang, persist=False)
            for theme in ('dark', 'light', 'hacker'):
                brave_ui.set_theme(self.win, theme, persist=False)
                open_settings(self.win, 'appearance')
                QTest.qWait(40)
                settings = self.win._quick_drawer
                self.assertLessEqual(settings.width(), self.win.width())
                self.assertLessEqual(settings.height(), self.win.height())
                self.assertTrue(all(option.width() >= 180 for option in settings.options))
                if destination:
                    settings.grab().save(str(Path(destination) / f'brave-settings-{theme}-{lang}.png'))
                settings.accept()
                dialog = open_commands(self.win)
                dialog.search.setText('audio')
                dialog.timer.stop()
                dialog.refresh_results()
                QTest.qWait(20)
                self.assertEqual({dialog.results.item(i).data(Qt.ItemDataRole.UserRole)[1]
                                  for i in range(dialog.results.count())}, {'audio','ai-studio'})
                self.assertLessEqual(dialog.height(), self.win.height())
                if destination:
                    dialog.grab().save(str(Path(destination) / f'brave-commands-{theme}-{lang}.png'))
                dialog.reject()

    def test_long_profile_form_scrolls_to_save(self):
        from brave_settings import open_settings
        self.win.resize(1040, 700)
        open_settings(self.win, 'profile')
        QTest.qWait(40)
        dialog = self.win._quick_drawer
        form = dialog.forms['profile']
        save = next(button for button in form.findChildren(QPushButton) if button.text() == translate('Saqlash'))
        scroll = dialog.sections['profile']
        scroll.ensureWidgetVisible(save)
        QTest.qWait(20)
        self.assertTrue(scroll.viewport().rect().contains(save.mapTo(scroll.viewport(), save.rect().center())))

    def test_full_focus_hides_workspace_and_returns_with_same_button(self):
        original = self.win._chat_focus_btn
        QTest.mouseClick(original, Qt.MouseButton.LeftButton)
        QTest.qWait(40)
        self.assertTrue(self.win._chat_focus)
        for widget in (self.win._header_widget, self.win._footer_widget, self.win._left_panel, self.win._center_split):
            self.assertTrue(widget.isHidden())
        self.assertGreater(self.win._right_panel.width(), 1000)
        self.assertEqual(original.accessibleName(), translate('Fokusdan chiqish')+' · Ctrl+Shift+F')
        QTest.mouseClick(original, Qt.MouseButton.LeftButton)
        QTest.qWait(40)
        self.assertIs(original, self.win._chat_focus_btn)
        self.assertFalse(self.win._chat_focus)
        self.assertTrue(self.win._header_widget.isVisible())
        self.assertTrue(self.win._left_panel.isVisible())
        self.assertEqual(self.win._right_panel.width(), ui._RIGHT_W)

    def test_focus_keyboard_and_quick_search_remain_reachable(self):
        self.win._input.setText('Fokus uchun qoralama')
        self.win._input.setFocus()
        QTest.qWait(20)
        QTest.keyClick(self.win._input, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
        self.assertTrue(self.win._chat_focus)
        QTest.keyClick(self.win._input, Qt.Key.Key_K, Qt.KeyboardModifier.ControlModifier)
        QTest.qWait(20)
        palette = self.win._command_palette
        self.assertTrue(palette.isVisible())
        palette.reject()
        self.win.activateWindow()
        self.win._input.setFocus()
        QTest.qWait(20)
        QTest.keyClick(self.win._input, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
        self.assertFalse(self.win._chat_focus)
        self.assertEqual(self.win._input.text(), 'Fokus uchun qoralama')

    def test_focus_preserves_draft_messages_and_attachments(self):
        from brave_chat import set_chat_focus, remove_attachment
        attachment = Path(self.temp.name) / 'focus-attachment.txt'
        attachment.write_text('Local UI test', encoding='utf-8')
        self.win._drop_zone._set_file(str(attachment))
        self.win._input.setText('Biriktirilgan fayl haqida savol')
        self.win._log.append_log('You: Fokus sinovi')
        self.win._log.append_log('Brave: Javob saqlansin.')
        messages = list(self.win._log._history)
        for enabled in (True, False, True, False):
            set_chat_focus(self.win, enabled)
            QTest.qWait(20)
            self.assertEqual(self.win._log._history, messages)
            self.assertEqual(self.win._input.text(), 'Biriktirilgan fayl haqida savol')
            self.assertEqual(self.win._drop_zone.current_files(), [str(attachment)])
        remove_attachment(self.win)

    def test_layout_snapshot_and_restart_restore_focus(self):
        from brave_chat import set_chat_focus
        from brave_layout import FILENAME
        from PyQt6.QtCore import QRect
        set_chat_focus(self.win, True)
        self.win.resize(1180, 760)
        self.win.move(100, 50)
        QTest.qWait(30)
        self.assertTrue(self.win._layout_state.flush())
        data = workspace_store.read(FILENAME, {})
        self.assertEqual(data['geometry'][2:], [1180, 760])
        self.assertTrue(data['focus'])
        self.assertNotIn('draft', data)
        self.assertNotIn('messages', data)
        # A compact geometry fits the offscreen test display as well as a real
        # desktop, allowing an exact size check after a fresh window is built.
        workspace_store.write(FILENAME, dict(data, geometry=[40, 40, 700, 700]))
        second = ui.MainWindow('')
        try:
            second.show()
            QTest.qWait(40)
            self.assertTrue(second._chat_focus)
            self.assertTrue(second._header_widget.isHidden())
            self.assertEqual(second.size().width(), 700)
            self.assertEqual(second.size().height(), 700)
            self.assertFalse(second.isFullScreen())
        finally:
            second.close()
            second.deleteLater()
            self.app.processEvents()
        self.assertTrue(workspace_store.read(FILENAME, {})['focus'])

    def test_remember_layout_can_be_disabled(self):
        from brave_chat import set_chat_focus
        from brave_layout import FILENAME
        set_chat_focus(self.win, True)
        self.win._layout_state.set_remember(False)
        data = workspace_store.read(FILENAME, {})
        self.assertEqual(data, {'version': 1, 'remember': False})
        self.assertFalse(self.win._quick_drawer.remember_layout.isChecked())
        second = ui.MainWindow('')
        try:
            self.assertFalse(second._layout_state.remember)
            self.assertFalse(second._chat_focus)
        finally:
            second.close()
            second.deleteLater()
            self.app.processEvents()

    def test_layout_reset_returns_workspace(self):
        from brave_chat import set_chat_focus
        from brave_layout import FILENAME
        set_chat_focus(self.win, True)
        self.win._layout_state.reset()
        QTest.qWait(40)
        self.assertFalse(self.win._chat_focus)
        self.assertFalse(self.win.isFullScreen())
        self.assertTrue(self.win._header_widget.isVisible())
        self.assertFalse(self.win._quick_drawer.focus_check.isChecked())
        self.assertFalse(workspace_store.read(FILENAME, {})['focus'])

    def test_layout_validation_and_changed_monitors(self):
        from brave_layout import fit_geometry, parse_geometry
        from PyQt6.QtCore import QRect
        areas = [QRect(0, 0, 1920, 1040), QRect(-1600, 0, 1600, 900)]
        secondary = QRect(-1400, 40, 1200, 780)
        self.assertEqual(fit_geometry(secondary, areas), secondary)
        missing = fit_geometry(QRect(6000, 2000, 1200, 780), [areas[0]])
        self.assertTrue(areas[0].contains(missing))
        self.assertEqual(fit_geometry(QRect(0, 0, 4000, 2000), [areas[0]]), areas[0])
        for invalid in (None, [], [True, 0, 1000, 800], ['x', 1, 1000, 800], [0, 0, -1000, 800], [0, 0, 2**40, 800]):
            self.assertIsNone(parse_geometry(invalid))

    def test_corrupt_layout_does_not_block_startup(self):
        from brave_layout import FILENAME
        (Path(self.temp.name) / FILENAME).write_text('{invalid', encoding='utf-8')
        second = ui.MainWindow('')
        try:
            self.assertFalse(second._chat_focus)
            self.assertTrue(second._layout_state.remember)
        finally:
            second.close()
            second.deleteLater()
            self.app.processEvents()

    def test_layout_save_is_debounced(self):
        from brave_layout import FILENAME
        self.win._layout_state.timer.stop()
        with patch('core.workspace_store.write') as write:
            for width in (1150, 1200, 1250):
                self.win.resize(width, 760)
                self.app.processEvents()
            write.assert_not_called()
            QTest.qWait(800)
            self.assertEqual(write.call_count, 1)
            self.assertEqual(write.call_args.args[0], FILENAME)
            self.assertEqual(write.call_args.args[1]['geometry'][2], 1250)

    def test_fullscreen_snapshot_keeps_normal_bounds_and_maximized_state(self):
        self.win.showMaximized()
        QTest.qWait(30)
        self.win._toggle_fullscreen()
        QTest.qWait(30)
        self.assertTrue(self.win.isFullScreen())
        snapshot = self.win._layout_state.snapshot()
        self.assertTrue(snapshot['maximized'])
        self.assertNotIn('fullscreen', snapshot)
        self.win._toggle_fullscreen()
        QTest.qWait(30)
        self.assertTrue(self.win.isMaximized())

    def test_focus_renders_in_all_themes(self):
        from brave_chat import set_chat_focus
        destination = os.environ.get('BRAVE_UI_PREVIEWS')
        for lang in ('uz', 'en', 'ru'):
            brave_ui.set_language(self.win, lang, persist=False)
            for theme in ('dark', 'light', 'hacker'):
                brave_ui.set_theme(self.win, theme, persist=False)
                set_chat_focus(self.win, True)
                QTest.qWait(40)
                self.assertTrue(self.win._right_panel.isVisible())
                self.assertEqual(self.win._chat_focus_btn.property('brave_icon'), 'collapse')
                if destination:
                    self.win.grab().save(str(Path(destination) / f'brave-focus-{theme}-{lang}.png'))
        set_chat_focus(self.win, False)

    def test_layout_search_reveals_controls_below_fold(self):
        from brave_settings import open_settings
        self.win.resize(1040, 700)
        open_settings(self.win, 'system', 'layout')
        QTest.qWait(60)
        dialog = self.win._quick_drawer
        scroll = dialog.sections['system']
        for control in (dialog.focus_check, dialog.remember_layout):
            self.assertTrue(scroll.viewport().rect().contains(control.mapTo(scroll.viewport(), control.rect().center())))
        reset = next(button for button in dialog.findChildren(QPushButton) if button.text() == translate('Standart joylashuv'))
        self.assertTrue(scroll.viewport().rect().contains(reset.mapTo(scroll.viewport(), reset.rect().center())))


if __name__ == '__main__':
    unittest.main()
