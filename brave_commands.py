"""Keyboard-first command search. All results are local and explicitly activated."""
from PyQt6.QtCore import QEvent, QSize, Qt, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (QApplication, QDialog, QHBoxLayout, QLineEdit,
    QListWidget, QListWidgetItem, QVBoxLayout)

from brave_i18n import translate as t
from brave_navigation import ACTIONS, SETTINGS, action_enabled, invoke, preview_chat, search_entries
from brave_ui import colors, font, icon, label


class CommandPalette(QDialog):
    def __init__(self, win, parent=None):
        super().__init__(parent or win)
        self.win = win
        self.setObjectName('BraveCommandPalette')
        self.setWindowTitle(t('Tezkor qidiruv'))
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.resize(660, 510)
        self.setMinimumSize(580, 200)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        top = QHBoxLayout()
        top.addWidget(label('Tezkor qidiruv', 17, colors().WHITE, True), 1)
        top.addWidget(label('Ctrl+K', 9, colors().TEXT_DIM))
        layout.addLayout(top)
        self.search = QLineEdit()
        self.search.setFont(font(10))
        self.search.setPlaceholderText(t('Sozlama, amal yoki suhbatni qidiring…'))
        self.search.setAccessibleName(t('Tezkor qidiruv'))
        self.search.setClearButtonEnabled(True)
        self.search.setMaxLength(200)
        self.search.setMinimumHeight(44)
        self.search.addAction(icon('search'), QLineEdit.ActionPosition.LeadingPosition)
        self.search.installEventFilter(self)
        layout.addWidget(self.search)
        self.results = QListWidget()
        self.results.setFont(font(10))
        self.results.setAccessibleName(t('Qidiruv natijalari'))
        self.results.itemClicked.connect(self.activate)
        self.results.itemActivated.connect(self.activate)
        layout.addWidget(self.results, 1)
        self.empty = label('Natija topilmadi.', 11, colors().TEXT_DIM)
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.empty)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(120)
        self.timer.timeout.connect(self.refresh_results)
        self.search.textChanged.connect(self.schedule_search)
        c = colors()
        self.setFont(font(10))
        self.setStyleSheet(f'QDialog#BraveCommandPalette {{background:{c.PANEL};color:{c.TEXT};}} '
            f'QLineEdit {{background:{c.BG};color:{c.TEXT};border:1px solid {c.BORDER};border-radius:10px;padding:10px;}} '
            f'QLineEdit:focus {{border-color:{c.PRI};}} QListWidget {{background:transparent;color:{c.TEXT};border:none;}} '
            f'QListWidget::item {{padding:9px;border-radius:8px;}} QListWidget::item:selected {{background:{c.PRI_GHO};color:{c.PRI};}} '
            f'QListWidget::item:disabled {{color:{c.TEXT_DIM};}} '
            f'QScrollBar:vertical {{background:transparent;width:6px;}} QScrollBar::handle:vertical {{background:{c.BORDER_B};border-radius:3px;min-height:24px;}} '
            'QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {height:0;}')
        self.refresh_results()

    def refresh_results(self):
        query = self.search.text().strip()
        self.results.clear()
        self.results.setEnabled(True)
        entries = search_entries((*SETTINGS, *ACTIONS), query) if query else list(ACTIONS)
        for entry in entries[:12]:
            category = t('Sozlamalar') if entry in SETTINGS else t('Amallar')
            detail = category+' · '+t(entry.detail)
            if entry.shortcut:
                detail += ' · '+entry.shortcut
            item = QListWidgetItem(icon(entry.glyph), t(entry.title)+'\n'+detail)
            item.setData(Qt.ItemDataRole.UserRole, ('entry', entry.key))
            item.setSizeHint(QSize(0, 64))
            if not action_enabled(self.win, entry.key):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self.results.addItem(item)
        if len(query) >= 2:
            for chat_id, title, updated in self.win._features.store.search(query)[:8]:
                item = QListWidgetItem(icon('chat'), title.replace('\n', ' ')+'\n'+t('Suhbatlar tarixi')+' · '+updated[:10])
                item.setData(Qt.ItemDataRole.UserRole, ('chat', chat_id))
                item.setSizeHint(QSize(0, 64))
                self.results.addItem(item)
        self.empty.setVisible(self.results.count() == 0)
        self.resize(self.width(), min(520, max(200, 176+64*min(self.results.count(), 6))))
        for index in range(self.results.count()):
            if self.results.item(index).flags() & Qt.ItemFlag.ItemIsEnabled:
                self.results.setCurrentRow(index)
                break

    def activate(self, item):
        if self.timer.isActive():
            self.timer.stop()
            self.refresh_results()
            return
        if not item or not item.flags() & Qt.ItemFlag.ItemIsEnabled:
            return
        kind, key = item.data(Qt.ItemDataRole.UserRole)
        if kind == 'entry' and not action_enabled(self.win, key):
            self.refresh_results()
            return
        query = self.search.text().strip()
        self.accept()
        self.win._close_setup()
        self.win._close_controls()
        # Execute after this modal closes. The shared dispatcher checks live
        # availability again; typing, selection changes and Escape do nothing.
        QTimer.singleShot(0, lambda: preview_chat(self.win, key, query) if kind == 'chat' else invoke(self.win, key))

    def eventFilter(self, obj, event):
        if obj is self.search and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                if self.timer.isActive():
                    self.timer.stop()
                    self.refresh_results()
                delta = 1 if event.key() == Qt.Key.Key_Down else -1
                index = self.results.currentRow()+delta
                while 0 <= index < self.results.count():
                    if self.results.item(index).flags() & Qt.ItemFlag.ItemIsEnabled:
                        self.results.setCurrentRow(index)
                        break
                    index += delta
                return True
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                # Flush pending search before Enter, so fast typing cannot
                # activate an older result from the previous query.
                if self.timer.isActive():
                    self.timer.stop()
                    self.refresh_results()
                self.activate(self.results.currentItem())
                return True
        return super().eventFilter(obj, event)

    def schedule_search(self):
        self.results.setEnabled(False)
        self.timer.start()

    def done(self, result):
        self.timer.stop()
        super().done(result)


def open_commands(win, parent=None):
    existing = getattr(win, '_command_palette', None)
    if existing is not None and existing.isVisible():
        existing.search.setFocus()
        return existing
    # Use the current settings window as parent when it is modal. The palette
    # can then close with Escape without losing unsaved settings edits.
    parent = parent or (win._quick_drawer if win._quick_drawer.isVisible() else win)
    dialog = CommandPalette(win, parent)
    win._command_palette = dialog
    dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    bounds = parent.frameGeometry()
    dialog.move(bounds.center()-dialog.rect().center())
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    dialog.search.setFocus()
    dialog.finished.connect(lambda _: setattr(win, '_command_palette', None))
    return dialog


def install_shortcut(win):
    shortcut = QShortcut(QKeySequence('Ctrl+K'), win)
    shortcut.activated.connect(lambda: open_commands(win))
    win._command_shortcut = shortcut
