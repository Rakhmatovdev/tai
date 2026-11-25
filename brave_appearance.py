"""Native appearance chooser with local, resolution-independent previews."""
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QButtonGroup, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from brave_i18n import translate as t
from brave_ui import THEMES, button_style, colors, current_theme, font, label, mono_font, set_theme


OPTIONS = (
    ('dark', 'Standart', 'Sokin grafit va iliq aksent. Har kun uchun.'),
    ('light', 'Och', 'Yorug‘ fon va yumshoq ranglar. Tiniq ko‘rinish.'),
    ('hacker', 'Hacker', 'Qora-yashil palitra. Terminal ruhi va raqamli portret.'),
)


class ThemeOption(QPushButton):
    def __init__(self, key, title, description, parent=None):
        super().__init__(parent)
        self.key, self.title, self.description = key, title, description
        self.setCheckable(True)
        self.setMinimumWidth(180)
        self.setFixedHeight(244)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(t(title))
        self.setAccessibleDescription(t(description))
        self.setProperty('brave_fixed_palette', True)

    def paintEvent(self, event):
        c, theme = colors(), THEMES[self.key]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(1, 1, self.width()-2, self.height()-2)
        p.setBrush(QColor(c.PRI_GHO if self.isChecked() else c.PANEL2))
        p.setPen(QPen(QColor(c.PRI if self.isChecked() else c.BORDER_B if self.underMouse() else c.BORDER), 1.5))
        p.drawRoundedRect(rect, 14, 14)
        if self.hasFocus():
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(c.TEXT_DIM), 1, Qt.PenStyle.DotLine))
            p.drawRoundedRect(rect.adjusted(4, 4, -4, -4), 10, 10)

        # Fixed palette inside each miniature lets users compare all three
        # themes even while the surrounding dialog changes immediately.
        p.save()
        p.translate(12, 13)
        p.scale((self.width()-24)/176, 1)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(theme['BG']))
        p.drawRoundedRect(QRectF(0, 0, 176, 116), 8, 8)
        p.setBrush(QColor(theme['PANEL2']))
        p.drawRoundedRect(QRectF(7, 7, 12, 12), 3, 3)
        p.setBrush(QColor(theme['PRI']))
        p.drawEllipse(QRectF(10, 10, 6, 6))
        p.drawRoundedRect(QRectF(24, 11, 30, 3), 1, 1)
        p.setBrush(QColor(theme['BORDER_B']))
        p.drawRoundedRect(QRectF(143, 10, 25, 5), 2, 2)
        for x, w in [(7, 31), (43, 64), (112, 57)]:
            p.setBrush(QColor(theme['PANEL']))
            p.drawRoundedRect(QRectF(x, 26, w, 82), 5, 5)
        p.setBrush(QColor(theme['PRI_GHO']))
        p.drawRoundedRect(QRectF(11, 32, 23, 9), 2, 2)
        p.setPen(QPen(QColor(theme['BORDER_B']), 2))
        for y in (49, 58, 67, 93):
            p.drawLine(QPointF(12, y), QPointF(30, y))
        p.setPen(QPen(QColor(theme['PRI']), 1.2))
        p.drawEllipse(QRectF(64, 44, 22, 30))
        p.drawLine(QPointF(69, 56), QPointF(72, 56))
        p.drawLine(QPointF(79, 56), QPointF(82, 56))
        p.drawLine(QPointF(72, 66), QPointF(78, 66))
        if self.key == 'hacker':
            p.setPen(QPen(QColor(theme['BORDER']), .6))
            for x in range(48, 106, 8):
                p.drawLine(QPointF(x, 30), QPointF(x, 103))
            for y in range(31, 104, 8):
                p.drawLine(QPointF(47, y), QPointF(103, y))
        p.setPen(QPen(QColor(theme['PRI']), 1.5))
        for n, value in enumerate((3, 7, 12, 6, 16, 9, 5, 11, 3)):
            p.drawLine(QPointF(59+n*4, 93-value/2), QPointF(59+n*4, 93+value/2))
        p.setPen(Qt.PenStyle.NoPen)
        for y, w in [(33, 31), (40, 42), (57, 37), (64, 26)]:
            p.setBrush(QColor(theme['TEXT_MED'] if y in (33, 57) else theme['BORDER_B']))
            p.drawRoundedRect(QRectF(119, y, w, 2), 1, 1)
        p.setBrush(QColor(theme['PANEL2']))
        p.drawRoundedRect(QRectF(117, 85, 47, 18), 3, 3)
        p.setBrush(QColor(theme['PRI']))
        p.drawRoundedRect(QRectF(153, 94, 7, 5), 1, 1)
        p.restore()

        p.setPen(QColor(c.WHITE))
        p.setFont(font(12, True))
        p.drawText(QRectF(16, 144, self.width()-54, 26), Qt.AlignmentFlag.AlignLeft, t(self.title))
        p.setFont(font(9))
        p.setPen(QColor(c.TEXT_MED))
        p.drawText(QRectF(16, 180, self.width()-32, 54), Qt.TextFlag.TextWordWrap, t(self.description))
        p.setBrush(QColor(c.PRI if self.isChecked() else c.PANEL))
        p.setPen(QPen(QColor(c.PRI if self.isChecked() else c.BORDER_B), 1))
        p.drawEllipse(QRectF(self.width()-35, 148, 18, 18))
        if self.isChecked():
            p.setPen(QPen(QColor(c.ON_ACCENT), 1.6))
            p.drawLine(QPointF(self.width()-30, 157), QPointF(self.width()-27, 160))
            p.drawLine(QPointF(self.width()-27, 160), QPointF(self.width()-21, 153))
        p.end()


class AppearancePage(QWidget):
    def __init__(self, win, parent=None):
        super().__init__(parent)
        self.win = win
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        eyebrow = label('ISH MAYDONINGIZ', 8, colors().PRI, True)
        eyebrow.setFont(mono_font(9, True))
        layout.addWidget(eyebrow)
        layout.addWidget(label('Sizga mos muhit.', 23, colors().WHITE, True))
        description = label('Ko‘rinishni tanlang. Istalgan payt standart mavzuga qaytishingiz mumkin.', 10, colors().TEXT_MED)
        description.setWordWrap(True)
        layout.addWidget(description)
        layout.addSpacing(6)
        row = QHBoxLayout()
        row.setSpacing(12)
        self.group = QButtonGroup(self)
        self.options = []
        for key, title, detail in OPTIONS:
            option = ThemeOption(key, title, detail, self)
            option.setChecked(key == current_theme())
            option.clicked.connect(lambda checked, value=key: self.choose(value))
            self.group.addButton(option)
            self.options.append(option)
            row.addWidget(option, 1)
        layout.addLayout(row)
        layout.addSpacing(4)
        bottom = QHBoxLayout()
        note = label('Tanlov avtomatik saqlanadi.', 9, colors().TEXT_DIM)
        bottom.addWidget(note, 1)
        layout.addLayout(bottom)
        self.refresh()

    def choose(self, key):
        set_theme(self.win, key)
        self.refresh()

    def refresh(self):
        from brave_i18n import localize_widgets
        for option in self.options:
            option.setChecked(option.key == current_theme())
            option.setAccessibleName(t(option.title))
            option.setAccessibleDescription(t(option.description))
            option.update()
        localize_widgets(self)


def open_appearance(win):
    from brave_settings import open_settings
    open_settings(win, 'appearance')
