"""Brave desktop presentation: native Qt widgets, no web or network assets."""
from __future__ import annotations

import html
import math
import os
import time
from functools import lru_cache
from pathlib import Path

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontDatabase, QIcon, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient
from PyQt6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSizePolicy,
    QTextEdit, QVBoxLayout, QWidget,
)
from brave_i18n import translate as t


_icon_cache: dict[tuple[str, str | None, int], QIcon] = {}


def clear_icon_cache():
    _icon_cache.clear()

_active_theme = 'dark'
THEMES = {
    'dark': {'BG':'#111217','PANEL':'#191b22','PANEL2':'#22242d','BORDER':'#2a2d37',
             'BORDER_B':'#3d414f','BORDER_A':'#343743','PRI':'#ff9b62','PRI_DIM':'#c4774b',
             'PRI_GHO':'#33281f','ACC':'#f5b783','ACC2':'#dec18d','GREEN':'#85ccae',
             'GREEN_D':'#426b5b','RED':'#f18b98','MUTED_C':'#f18b98','TEXT':'#d5d7df',
             'TEXT_DIM':'#9095a6','TEXT_MED':'#b0b5c3','WHITE':'#f5f4f1','DARK':'#15171d',
             'BAR_BG':'#2c303b','HOVER':'#292b34','ON_ACCENT':'#15151a'},
    'light': {'BG':'#f3f1ed','PANEL':'#fffefa','PANEL2':'#ece9e3','BORDER':'#ddd8d0',
              'BORDER_B':'#c6beb3','BORDER_A':'#d1c9bf','PRI':'#b64e22','PRI_DIM':'#a76647',
              'PRI_GHO':'#f8e8dc','ACC':'#b06538','ACC2':'#92682b','GREEN':'#267457',
              'GREEN_D':'#90b5a4','RED':'#bd4054','MUTED_C':'#bd4054','TEXT':'#333740',
              'TEXT_DIM':'#64676f','TEXT_MED':'#565b64','WHITE':'#24262d','DARK':'#f2f0eb',
              'BAR_BG':'#e0dcd5','HOVER':'#e2ddd5','ON_ACCENT':'#ffffff'},
    'hacker': {'BG':'#090e0c','PANEL':'#101914','PANEL2':'#17231c','BORDER':'#283c30',
               'BORDER_B':'#425f4c','BORDER_A':'#344e3e','PRI':'#a3ef8c','PRI_DIM':'#78c565',
               'PRI_GHO':'#213b25','ACC':'#dbc287','ACC2':'#87d7c6','GREEN':'#83dba7',
               'GREEN_D':'#477d5d','RED':'#ff9aab','MUTED_C':'#ff9aab','TEXT':'#dce7df',
               'TEXT_DIM':'#9bad9f','TEXT_MED':'#bacbbf','WHITE':'#f0f8ef','DARK':'#0c120f',
               'BAR_BG':'#2b4032','HOVER':'#23372a','ON_ACCENT':'#101c11'},
}


def current_theme():
    return _active_theme


def apply_theme(theme):
    global _active_theme
    import ui
    _active_theme = theme if theme in THEMES else 'dark'
    for key, value in THEMES[_active_theme].items():
        setattr(ui.C, key, value)
    ui._PALETTE_DEFAULTS.update({key:getattr(ui.C,key) for key in ui._HUE_LINKED})


def set_theme(win, theme, persist=True):
    clear_icon_cache()
    import ui
    old = {key:getattr(ui.C,key, THEMES['dark'][key]) for key in THEMES['dark']}
    apply_theme(theme)
    saved_accent = ui._read_full_config().get('ui_color', '')
    if _active_theme != 'hacker' and saved_accent and saved_accent.lower() != ui.DEFAULT_UI_COLOR:
        ui.apply_ui_accent(saved_accent)
    new = {key:getattr(ui.C,key) for key in THEMES['dark']}
    ui.retheme_all_widgets(old, new)
    if persist:
        from memory.config_manager import _patch_config
        _patch_config(ui_theme=_active_theme)
    win._log.retheme()
    for button in win.findChildren(QPushButton):
        glyph = button.property('brave_icon')
        if glyph:
            role = button.property('brave_icon_role') or 'TEXT_MED'
            button.setIcon(icon(glyph, getattr(ui.C, role, ui.C.TEXT_MED)))
    style_mute_button(win)
    for bar, role in [(win._bar_cpu,'PRI'),(win._bar_net,'GREEN'),(win._bar_tmp,'ACC')]:
        bar._color = getattr(ui.C,role)
    win._bar_mem._color, win._bar_gpu._color = metric_colors()
    win.hud.update()
    from brave_brand import logo_icon
    win.setWindowIcon(logo_icon())
    for widget in win.findChildren(QWidget):
        widget.update()
    if hasattr(win, '_capabilities'):
        win._capabilities.refresh_header()
    from brave_brand import refresh_logos
    refresh_logos(win, _active_theme)
    if getattr(win, '_customize_overlay', None):
        win._customize_overlay.sync_theme()
    if hasattr(getattr(win, '_quick_drawer', None), 'refresh'):
        win._quick_drawer.refresh()
    if hasattr(win, '_language_tutor'):
        win._language_tutor.refresh_ui()


def set_language(win, code, persist=True):
    from brave_i18n import set_language as activate, localize_widgets
    activate(code)
    if hasattr(win, '_language_box'):
        win._language_box.blockSignals(True)
        win._language_box.setCurrentIndex(win._language_box.findData(code))
        win._language_box.blockSignals(False)
    if persist:
        from memory.config_manager import _patch_config
        _patch_config(ui_language=code)
    localize_widgets(win)
    fit_header(win)
    from brave_chat import refresh_focus_button
    refresh_focus_button(win)
    win._tick_clock()
    win._log.retheme()
    win.hud.update()
    if hasattr(getattr(win, '_quick_drawer', None), 'refresh'):
        win._quick_drawer.refresh()
    if hasattr(win, '_language_tutor'):
        win._language_tutor.refresh_ui()


def tick_clock(win):
    from datetime import datetime, timezone, timedelta
    from brave_i18n import language
    now = datetime.now(timezone(timedelta(hours=5)))
    months = {
        'uz':['yan','fev','mar','apr','may','iyun','iyul','avg','sen','okt','noy','dek'],
        'en':['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],
        'ru':['янв','фев','мар','апр','май','июн','июл','авг','сен','окт','ноя','дек'],
    }
    win._clock_lbl.setText(now.strftime('%H:%M:%S'))
    win._clock_lbl.setAccessibleName(now.strftime('%H:%M:%S'))
    win._date_lbl.setText(f'{now.day} {months[language()][now.month-1]} {now.year}')


def colors():
    from ui import C
    return C


def metric_colors():
    if current_theme() == 'hacker':
        return colors().ACC2, colors().GREEN
    return ('#a699e8', '#88abd4') if current_theme() == 'dark' else ('#7868aa', '#527f9d')


_fonts_loaded = False


def _ensure_fonts_loaded():
    global _fonts_loaded
    if not _fonts_loaded:
        # Offscreen Windows rendering has no system font discovery. Load the
        # OS's own fonts so previews and the desktop use identical typography.
        font_dir = os.path.join(os.environ.get('WINDIR', 'C:/Windows'), 'Fonts')
        for filename in ('segoeui.ttf', 'seguisb.ttf', 'segoeuib.ttf', 'consola.ttf'):
            path = os.path.join(font_dir, filename)
            if os.path.isfile(path):
                QFontDatabase.addApplicationFont(path)
        _fonts_loaded = True


@lru_cache(maxsize=128)
def font(size=10, bold=False):
    _ensure_fonts_loaded()
    return QFont("Segoe UI", size, QFont.Weight.DemiBold if bold else QFont.Weight.Normal)


@lru_cache(maxsize=128)
def mono_font(size=9, bold=False):
    _ensure_fonts_loaded()
    f = QFont("Consolas", size, QFont.Weight.DemiBold if bold else QFont.Weight.Normal)
    return f


def label(text, size=10, color=None, bold=False):
    widget = QLabel(t(text))
    widget.setFont(font(size, bold))
    widget.setStyleSheet(f"color: {color or colors().TEXT}; background: transparent; border: none;")
    return widget


def button_style(accent=False):
    c = colors()
    return f"""
        QPushButton {{ background: {c.PRI if accent else c.PANEL2};
            color: {getattr(c, 'ON_ACCENT', '#15151a') if accent else c.TEXT}; border: 1px solid {c.PRI if accent else c.BORDER};
            border-radius: 10px; padding: 8px 12px; font-family: 'Segoe UI'; font-size: 13px; }}
        QPushButton:hover {{ background: {c.PRI_DIM if accent else getattr(c, 'HOVER', '#292b34')}; border-color: {c.PRI_DIM}; }}
        QPushButton:pressed {{ background: {c.PRI_DIM if accent else c.BG}; }}
        QPushButton:checked {{ background: {c.PRI_GHO}; color: {c.PRI}; border-color: {c.PRI_DIM}; }}
        QPushButton:focus {{ border-color: {c.PRI}; }}
        QPushButton:disabled {{ color: {c.TEXT_DIM}; background: {c.PANEL}; border-color: {c.BORDER}; }}
    """


def icon(name, color=None, size=20):
    """Small consistent vector icons rendered locally; no emoji/font dependency."""
    key = (name, color, size)
    cached = _icon_cache.get(key)
    if cached is not None:
        return cached
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(size / 12, size / 12)
    painter.setPen(QPen(QColor(color or colors().TEXT_MED), 1.5, Qt.PenStyle.SolidLine,
                        Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    if name == 'search':
        painter.drawEllipse(QRectF(4, 4, 11, 11))
        painter.drawLine(QPointF(14, 14), QPointF(20, 20))
    elif name == 'more':
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color or colors().TEXT_MED))
        for x in (5, 12, 19):
            painter.drawEllipse(QRectF(x-1.3, 10.7, 2.6, 2.6))
    elif name == 'terminal':
        painter.drawRoundedRect(QRectF(3, 4, 18, 16), 3, 3)
        painter.drawLine(QPointF(7, 9), QPointF(10, 12))
        painter.drawLine(QPointF(10, 12), QPointF(7, 15))
        painter.drawLine(QPointF(13, 15), QPointF(17, 15))
    elif name == 'palette':
        painter.drawEllipse(QRectF(3, 3, 18, 18))
        for x, y in [(8, 8), (14, 7), (17, 12)]:
            painter.drawEllipse(QRectF(x-1, y-1, 2, 2))
        painter.drawLine(QPointF(8, 15), QPointF(12, 17))
    elif name == 'plus':
        painter.drawLine(QPointF(12,5),QPointF(12,19))
        painter.drawLine(QPointF(5,12),QPointF(19,12))
    elif name == 'download':
        painter.drawLine(QPointF(12,3),QPointF(12,15))
        painter.drawLine(QPointF(7,10),QPointF(12,15))
        painter.drawLine(QPointF(17,10),QPointF(12,15))
        painter.drawLine(QPointF(5,16),QPointF(5,21))
        painter.drawLine(QPointF(5,21),QPointF(19,21))
        painter.drawLine(QPointF(19,21),QPointF(19,16))
    elif name == "chat":
        painter.drawRoundedRect(QRectF(4, 4, 16, 13), 3, 3)
        painter.drawLine(QPointF(7, 17), QPointF(7, 21))
        painter.drawLine(QPointF(7, 21), QPointF(12, 17))
        painter.drawLine(QPointF(8, 9), QPointF(16, 9))
        painter.drawLine(QPointF(8, 12), QPointF(13, 12))
    elif name == "mic":
        painter.drawRoundedRect(QRectF(9, 3, 6, 12), 3, 3)
        painter.drawArc(QRectF(6, 7, 12, 12), 180 * 16, 180 * 16)
        painter.drawLine(QPointF(12, 19), QPointF(12, 22))
        painter.drawLine(QPointF(9, 22), QPointF(15, 22))
    elif name == "sliders":
        for x, y in [(6, 9), (12, 15), (18, 7)]:
            painter.drawLine(QPointF(x, 4), QPointF(x, 20))
            painter.drawRoundedRect(QRectF(x - 2, y - 2, 4, 4), 1, 1)
    elif name == "memory":
        painter.drawRoundedRect(QRectF(5, 4, 14, 16), 3, 3)
        painter.drawLine(QPointF(9, 4), QPointF(9, 20))
        painter.drawLine(QPointF(12, 9), QPointF(16, 9))
        painter.drawLine(QPointF(12, 13), QPointF(16, 13))
    elif name == "settings":
        painter.drawEllipse(QRectF(7, 7, 10, 10))
        painter.drawEllipse(QRectF(10, 10, 4, 4))
        for angle in range(0, 360, 45):
            a = math.radians(angle)
            painter.drawLine(QPointF(12 + math.cos(a) * 6, 12 + math.sin(a) * 6),
                             QPointF(12 + math.cos(a) * 9, 12 + math.sin(a) * 9))
    elif name == "arrow":
        painter.drawLine(QPointF(12, 19), QPointF(12, 5))
        painter.drawLine(QPointF(6, 11), QPointF(12, 5))
        painter.drawLine(QPointF(18, 11), QPointF(12, 5))
    elif name == "file":
        path = QPainterPath(QPointF(6, 3))
        for point in [(14, 3), (19, 8), (19, 21), (6, 21), (6, 3)]:
            path.lineTo(*point)
        painter.drawPath(path)
        painter.drawLine(QPointF(14, 3), QPointF(14, 8))
        painter.drawLine(QPointF(14, 8), QPointF(19, 8))
    elif name == "stop":
        painter.drawRoundedRect(QRectF(6, 6, 12, 12), 2, 2)
    elif name in ('star','star-filled'):
        path=QPainterPath()
        for index in range(10):
            angle=math.radians(-90+index*36);radius=10 if index%2==0 else 4.5
            point=QPointF(12+math.cos(angle)*radius,12+math.sin(angle)*radius)
            if index==0:path.moveTo(point)
            else:path.lineTo(point)
        path.closeSubpath()
        if name=='star-filled':painter.setBrush(QColor(color or colors().TEXT_MED))
        painter.drawPath(path)
    elif name == "spark":
        path = QPainterPath(QPointF(12, 2))
        for point in [(15, 9), (22, 12), (15, 15), (12, 22), (9, 15), (2, 12), (9, 9), (12, 2)]:
            path.lineTo(*point)
        painter.drawPath(path)
    elif name == 'sun':
        painter.drawEllipse(QRectF(8, 8, 8, 8))
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            painter.drawLine(QPointF(12+math.cos(rad)*7,12+math.sin(rad)*7),
                             QPointF(12+math.cos(rad)*10,12+math.sin(rad)*10))
    elif name == 'moon':
        path = QPainterPath(QPointF(16, 3))
        path.cubicTo(4, 1, 1, 16, 12, 21)
        path.cubicTo(17, 23, 22, 17, 21, 13)
        path.cubicTo(11, 17, 7, 7, 16, 3)
        painter.drawPath(path)
    elif name == 'copy':
        painter.drawRoundedRect(QRectF(8,8,12,13),2,2)
        painter.drawLine(QPointF(15,4),QPointF(4,4))
        painter.drawLine(QPointF(4,4),QPointF(4,16))
    elif name == 'attach':
        path=QPainterPath(QPointF(16,7))
        path.lineTo(8,15)
        path.cubicTo(4,19,8,23,12,19)
        path.lineTo(20,11)
        path.cubicTo(25,6,18,0,14,4)
        path.lineTo(5,13)
        painter.drawPath(path)
    elif name == 'expand':
        painter.drawLine(QPointF(14,4),QPointF(20,4))
        painter.drawLine(QPointF(20,4),QPointF(20,10))
        painter.drawLine(QPointF(20,4),QPointF(13,11))
        painter.drawLine(QPointF(4,14),QPointF(4,20))
        painter.drawLine(QPointF(4,20),QPointF(10,20))
        painter.drawLine(QPointF(4,20),QPointF(11,13))
    elif name == 'collapse':
        for a, b in [((4,4),(10,10)), ((10,4),(10,10)), ((4,10),(10,10)),
                     ((20,20),(14,14)), ((14,20),(14,14)), ((20,14),(14,14))]:
            painter.drawLine(QPointF(*a), QPointF(*b))
    elif name == 'pen':
        path = QPainterPath(QPointF(4, 20))
        for point in [(8, 19), (19, 8), (16, 5), (5, 16), (4, 20)]:
            path.lineTo(*point)
        painter.drawPath(path)
        painter.drawLine(QPointF(14, 7), QPointF(17, 10))
    elif name == 'headphones':
        painter.drawArc(QRectF(4, 4, 16, 15), 0, 180 * 16)
        painter.drawRoundedRect(QRectF(4, 12, 4, 7), 1.5, 1.5)
        painter.drawRoundedRect(QRectF(16, 12, 4, 7), 1.5, 1.5)
    painter.end()
    pixmap.setDevicePixelRatio(2)
    res = QIcon(pixmap)
    _icon_cache[key] = res
    return res


def set_icon(button, glyph, role='TEXT_MED'):
    button.setProperty('brave_icon',glyph)
    button.setProperty('brave_icon_role',role)
    button.setIcon(icon(glyph,getattr(colors(),role,colors().TEXT_MED)))


class BraveMark(QWidget):
    def __init__(self, size=36):
        super().__init__()
        self.setFixedSize(size, size)

    def paintEvent(self, event):
        from brave_brand import logo_pixmap
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.drawPixmap(self.rect(), logo_pixmap(self.width(), current_theme(), 2))
        p.end()


def card(widget, name):
    c = colors()
    widget.setObjectName(name)
    widget.setStyleSheet(f"QWidget#{name} {{ background: {c.PANEL}; border: 1px solid {c.BORDER}; border-radius: 18px; }}")


def fit_header(win):
    compact = win.width() < 1180
    win._sub_lbl.setVisible(win.width() >= 1120)
    if hasattr(win, '_header_academy_btn'):
        win._header_academy_btn.setVisible(win.width() >= 1220)
    win._ctrl_btn.setText('' if compact else t('Boshqaruv'))
    win._ctrl_btn.setFixedWidth(42 if compact else win._ctrl_btn.sizeHint().width())


def build_header(win):
    c = colors()
    widget = QWidget()
    win._header_widget = widget
    widget.setObjectName('BraveTopbar')
    widget.setFixedHeight(86)
    layout = QHBoxLayout(widget)
    layout.setContentsMargins(24, 12, 24, 12)
    layout.setSpacing(10)
    layout.addWidget(BraveMark(46))
    brand = QVBoxLayout()
    brand.setSpacing(2)
    win._title_lbl = label(win._assistant_name, 20, c.WHITE, True)
    win._sub_lbl = label("30 Yillik Professor · Til O‘rgatuvchi AI Akademiyasi", 8, c.TEXT_DIM)
    brand.addWidget(win._title_lbl)
    brand.addWidget(win._sub_lbl)
    layout.addLayout(brand)
    layout.addStretch()
    win._header_academy_btn = QPushButton()
    win._header_academy_btn.setObjectName('BraveHeaderAcademyBtn')
    win._header_academy_btn.setProperty('brave_literal_text', True)
    win._header_academy_btn.setFixedHeight(32)
    win._header_academy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    win._header_academy_btn.setToolTip("Til, Daraja va Ustoz Rolini sozlash")
    win._header_academy_btn.clicked.connect(lambda: win.open_tutor_dialog())
    layout.addWidget(win._header_academy_btn)

    def separator():
        line = QFrame()
        line.setFixedSize(1, 26)
        line.setStyleSheet(f'background: {c.BORDER}; border: none;')
        layout.addWidget(line)

    win._connection_lbl = label("●  Ulanmoqda", 9, c.TEXT_MED)
    win._connection_lbl.setFixedHeight(32)
    win._connection_lbl.setStyleSheet(f"color: {c.TEXT_MED}; background: {c.PANEL2}; border: 1px solid {c.BORDER}; border-radius: 12px; padding: 7px 12px;")
    layout.addWidget(win._connection_lbl)
    separator()
    win._clock_frame = QFrame()
    win._clock_frame.setObjectName('BraveClock')
    win._clock_frame.setFixedSize(118, 52)
    win._clock_frame.setStyleSheet(f'QFrame#BraveClock {{background: {c.PANEL}; border: 1px solid {c.BORDER}; border-radius: 11px;}}')
    clock = QVBoxLayout(win._clock_frame)
    clock.setContentsMargins(10, 5, 10, 5)
    clock.setSpacing(2)
    win._clock_lbl = label("00:00:00", 13, c.WHITE, True)
    win._clock_lbl.setFont(mono_font(13, True))
    win._date_lbl = label("", 8, c.TEXT_DIM)
    for item in (win._clock_lbl, win._date_lbl):
        item.setAlignment(Qt.AlignmentFlag.AlignCenter)
        clock.addWidget(item)
    layout.addWidget(win._clock_frame)
    separator()
    win._hub_btn=QPushButton('Markaz')
    set_icon(win._hub_btn,'sliders')
    win._hub_btn.setFixedHeight(40)
    win._hub_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    win._hub_btn.setStyleSheet(button_style())
    win._hub_btn.clicked.connect(lambda:win._capabilities.open())
    layout.addWidget(win._hub_btn)
    win._ctrl_btn = QPushButton("Boshqaruv")
    win._ctrl_btn.setToolTip(t('Boshqaruv'))
    win._ctrl_btn.setAccessibleName(t('Boshqaruv'))
    set_icon(win._ctrl_btn,'sliders')
    win._drawer_btn = QPushButton()
    set_icon(win._drawer_btn,'settings')
    win._drawer_btn.setToolTip("Sozlamalar")
    win._drawer_btn.setAccessibleName("Sozlamalar")
    win._drawer_btn.setFixedWidth(42)
    for button, slot in [(win._ctrl_btn, win._toggle_controls), (win._drawer_btn, win._toggle_drawer)]:
        button.setCheckable(True)
        button.setFixedHeight(40)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setStyleSheet(button_style())
        button.clicked.connect(slot)
        layout.addWidget(button)
    return widget


def build_left_panel(win):
    from ui import MetricBar, _LEFT_W
    from brave_language_tutor import SKILLS, TutorController
    c = colors()
    if not hasattr(win, '_language_tutor'):
        win._language_tutor = TutorController(win)
    tutor = win._language_tutor
    widget = QWidget()
    widget.setFixedWidth(_LEFT_W)
    card(widget, "BraveSidebar")
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(14, 14, 14, 12)
    layout.setSpacing(4)
    layout.addWidget(label("TIL VA USTOZ ROLI", 8, c.TEXT_DIM, True))
    win._tutor_role_btn = QPushButton()
    win._tutor_role_btn.setObjectName('BraveTutorRoleBtn')
    win._tutor_role_btn.setProperty('brave_literal_text', True)
    win._tutor_role_btn.setFixedHeight(30)
    win._tutor_role_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    win._tutor_role_btn.clicked.connect(tutor.open_dialog)
    layout.addWidget(win._tutor_role_btn)
    layout.addSpacing(2)
    layout.addWidget(label("7 O‘QUV CHATLAR", 8, c.TEXT_DIM, True))
    win._skill_buttons = {}
    for skill in SKILLS:
        button = QPushButton(skill.short_title)
        button.setObjectName(f"BraveSkill_{skill.key}")
        button.setProperty('brave_literal_text', True)
        button.setToolTip(t(skill.subtitle))
        button.setAccessibleName(skill.short_title)
        button.setFixedHeight(27)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(lambda checked=False, k=skill.key: tutor.switch_skill(k))
        win._skill_buttons[skill.key] = button
        layout.addWidget(button)
    diag_btn = QPushButton('Diagnostika')
    diag_btn.setFixedHeight(26)
    set_icon(diag_btn, 'sliders', 'TEXT_MED')
    diag_btn.setStyleSheet(button_style() + f"QPushButton {{text-align: left; padding: 3px 10px; font-size: 11px; border: 1px solid transparent; background: transparent;}} QPushButton:hover {{background: {c.PANEL2}; border-color: {c.BORDER};}} QPushButton:focus {{border-color: {c.PRI};}}")
    diag_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    diag_btn.clicked.connect(lambda: __import__('brave_diagnostics').open_diagnostics(win))
    layout.addWidget(diag_btn)
    tutor.refresh_sidebar()
    layout.addStretch(1)
    layout.addWidget(label("QURILMA HOLATI", 8, c.TEXT_DIM, True))
    win._bar_cpu = MetricBar("CPU", c.PRI)
    mem_color, gpu_color = metric_colors()
    win._bar_mem = MetricBar("RAM", mem_color)
    win._bar_net = MetricBar("Tarmoq", c.GREEN)
    win._bar_gpu = MetricBar("GPU", gpu_color)
    win._bar_tmp = MetricBar("Harorat", c.ACC)
    for bar in (win._bar_cpu, win._bar_mem, win._bar_net, win._bar_gpu, win._bar_tmp):
        bar.setFixedHeight(22)
        layout.addWidget(bar)
    win._uptime_lbl = label("UP --:--", 8, c.TEXT_DIM)
    win._proc_lbl = label("PROC --", 8, c.TEXT_DIM)
    info = QHBoxLayout()
    info.addWidget(win._uptime_lbl)
    info.addStretch()
    info.addWidget(win._proc_lbl)
    layout.addLayout(info)
    note = label("30 yillik Professor AI.\n7 yo‘nalishda mukammal til.", 8, c.TEXT_MED)
    win._sidebar_note = note
    note.setFixedHeight(38)
    note.setWordWrap(True)
    note.setStyleSheet(f"color: {c.TEXT_MED}; background: {c.PANEL2}; border: none; border-radius: 8px; padding: 5px 8px;")
    layout.addWidget(note)
    return widget


from brave_chat import ConversationLog


def build_right_panel(win):
    from brave_chat import build_right_panel as build
    return build(win)


def build_input_row(win):
    from brave_chat import build_input_row as build
    return build(win)


def build_drawer(win, controls=False):
    if not controls:
        from brave_settings import SettingsDialog
        return SettingsDialog(win)
    c = colors()
    widget = QWidget(win.centralWidget())
    widget.setObjectName('BraveControls' if controls else 'BraveSettings')
    card(widget, widget.objectName())
    widget.hide()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(16, 16, 16, 16)
    layout.setSpacing(8)
    layout.addWidget(label('Boshqaruv' if controls else 'Sozlamalar', 12, c.WHITE, True))
    layout.addWidget(label('Suhbatni o‘zingizga moslang.' if controls else 'Brave’ni o‘zingizga moslang.', 9, c.TEXT_DIM))
    layout.addSpacing(6)
    win._BTN_PRI = button_style() + f'QPushButton {{color: {c.PRI}; text-align: left;}}'
    win._BTN_DIM = button_style() + 'QPushButton {text-align: left;}'

    def row(title, glyph, slot, attr=None, close=False):
        button = QPushButton(title)
        button.setAccessibleName(t(title))
        set_icon(button,glyph)
        button.setFixedHeight(38)
        button.setStyleSheet(win._BTN_DIM)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        def invoke():
            if close:
                win._close_setup()
                win._close_controls()
            slot()
        button.clicked.connect(invoke)
        layout.addWidget(button)
        if attr:
            setattr(win, attr, button)
        return button

    if controls:
        row('To‘liq ekran · F11', 'sliders', win._toggle_fullscreen)
        row('Kunlik sharh', 'file', win._toggle_brief, '_brief_btn')
        row('Ovozli uyg‘otish', 'mic', win._toggle_wake_word, '_wake_btn')
        row('Uyg‘otish', 'mic', win._tap_wake_manual, '_wake_sleep_btn').hide()
        row('Gapirish rejimi', 'mic', win._toggle_ptt, '_ptt_btn')
        row('Ovoz animatsiyasi', 'spark', win._toggle_hud_style, '_hud_btn')
        win._refresh_talk_btns()
        win._refresh_hud_btn()
    return widget


def style_mute_button(win):
    c = colors()
    if win._active_provider == 'ollama':
        voice = getattr(win, '_local_voice', None)
        recording = bool(voice and voice.recording)
        speaking = bool(voice and getattr(voice, 'speaking', False))
        muted = getattr(win, '_muted', False)
        if hasattr(win,'_capabilities') and not win._capabilities.policy['permissions']['microphone']:muted=True
        text_only=getattr(win,'_text_only',False)
        if text_only:
            label = 'Matnli rejim'
            btn_color = c.RED
            btn_icon = 'chat'
        elif muted:
            label = 'Mikrofon o‘chiq'
            btn_color = c.RED
            btn_icon = 'mic'
        elif speaking:
            label = 'Javob bermoqda…'
            btn_color = c.PRI
            btn_icon = 'mic'
        elif recording:
            label = 'Tinglanmoqda…'
            btn_color = c.GREEN
            btn_icon = 'mic'
        else:
            label = 'Mikrofon yoqilgan'
            btn_color = c.GREEN
            btn_icon = 'mic'
        win._mute_btn.setText(t(label))
        win._mute_btn.setIcon(icon(btn_icon, btn_color))
        win._mute_btn.setToolTip(t("Mikrofonni yoqish / o‘chirish · F4"))
        win._mute_btn.setFont(font(9, True))
        win._mute_btn.setStyleSheet(button_style()+f'QPushButton {{color: {btn_color}; background: {c.PANEL2};}}')
        return
    muted = win._muted
    if hasattr(win,'_capabilities') and not win._capabilities.policy['permissions']['microphone']:muted=True
    text_only=getattr(win,'_text_only',False)
    win._mute_btn.setText(t('Matnli rejim' if text_only else ("Mikrofon o‘chiq" if muted else "Mikrofon yoqilgan")))
    win._mute_btn.setIcon(icon('chat' if text_only else "mic", c.RED if muted else c.GREEN))
    win._mute_btn.setToolTip(t("Mikrofonni yoqish / o‘chirish · F4"))
    win._mute_btn.setFont(font(9, True))
    win._mute_btn.setStyleSheet(button_style() + f"QPushButton {{color: {c.RED if muted else c.GREEN}; background: {c.PANEL2};}}")


def build_footer(win):
    c = colors()
    widget = QWidget()
    win._footer_widget = widget
    widget.setFixedHeight(38)
    layout = QHBoxLayout(widget)
    layout.setContentsMargins(26, 0, 26, 0)
    layout.addWidget(label("F4  mikrofon     /     Esc  to‘xtatish     /     F11  to‘liq ekran", 8, c.TEXT_DIM))
    layout.addStretch()
    win._provider_footer = label('Lokal suhbat · Ollama' if win._active_provider=='ollama' else 'Ovozli suhbat · Google Gemini', 8, c.TEXT_DIM)
    layout.addWidget(win._provider_footer)
    return widget


def paint_voice_canvas(canvas):
    c = colors()
    hacker = current_theme() == 'hacker'
    p = QPainter(canvas)
    if not p.isActive():
        return
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    width, height = canvas.width(), canvas.height()
    p.fillRect(canvas.rect(), QColor(c.BG))
    p.setBrush(QColor(c.PANEL))
    p.setPen(QPen(QColor(c.BORDER), 1))
    p.drawRoundedRect(QRectF(.5, .5, width-1, height-1), 18, 18)
    compact = height < 450
    p.setPen(QColor(c.PRI if hacker else c.TEXT_DIM))
    p.setFont(mono_font(8, True) if hacker else font(8, True))
    win_obj = canvas.window()
    tutor = getattr(win_obj, '_language_tutor', None)
    if tutor is not None:
        from brave_language_tutor import language_display_name, role_display, skill_display
        t_lang = language_display_name(tutor.state)
        t_lvl = tutor.state.get('level', 'B1')
        t_role = role_display(tutor.state)
        t_skill = skill_display(tutor.state)
        eyebrow = f"TAI · 30 YILLIK PROFESSOR · {t_lang.upper()} ({t_lvl})"
        sub_txt = f"{t(t_role.badge)}  ·  {t_skill.short_title} bo‘limi  ·  Ovoz va Matn"
    else:
        eyebrow = t('TAI · 30 YILLIK PROFESSOR TIL AKADEMIYASI')
        sub_txt = t('7 ta maxsus o‘quv chat · 12 til · CEFR A1–C2')
    eyebrow = p.fontMetrics().elidedText(eyebrow, Qt.TextElideMode.ElideRight, width-56)
    p.drawText(QRectF(28, 25, width-56, 18), Qt.AlignmentFlag.AlignLeft, eyebrow)
    headline = t('Siz gapiring. TAI tahlil qiladi va o‘rgatadi.')
    headline_size = 16 if compact else (20 if width > 430 else 17)
    p.setFont(font(headline_size, True))
    while headline_size > 11 and p.fontMetrics().horizontalAdvance(headline) > width-48:
        headline_size -= 1
        p.setFont(font(headline_size, True))
    p.setFont(font(headline_size, True))
    p.setPen(QColor(c.WHITE))
    p.drawText(QRectF(24, 55, width-48, 40), Qt.AlignmentFlag.AlignCenter, headline)
    if not compact:
        p.setFont(font(9))
        p.setPen(QColor(c.TEXT_MED))
        subtitle = p.fontMetrics().elidedText(sub_txt, Qt.TextElideMode.ElideRight, width-48)
        p.drawText(QRectF(24, 102, width-48, 22), Qt.AlignmentFlag.AlignCenter, subtitle)

    status_y = height - (100 if compact else 146)
    band_top = 102 if compact else 146
    band_height = max(90, status_y - band_top - 22)
    portrait_width = min(width-64, band_height*.97, 360)
    portrait_rect = QRectF((width-portrait_width)/2, band_top, portrait_width, band_height)
    tint = QColor(c.PRI)
    tint.setAlpha(13 if current_theme() != 'light' else 10)
    p.setBrush(tint)
    p.setPen(QPen(QColor(c.BORDER), 1))
    radius = 14 if hacker else min(80,portrait_width*.22)
    p.drawRoundedRect(portrait_rect, radius, radius)
    # A quiet, clipped instrument grid gives the optional hacker theme its
    # identity without adding flashing effects or decorative fake telemetry.
    p.save()
    clip = QPainterPath()
    clip.addRoundedRect(portrait_rect.adjusted(1, 1, -1, -1), radius, radius)
    p.setClipPath(clip)
    glow = QRadialGradient(portrait_rect.center(), portrait_width*.72)
    glow_color = QColor(c.PRI)
    glow_color.setAlpha(26 if hacker else 14)
    glow.setColorAt(0, glow_color)
    glow_color.setAlpha(0)
    glow.setColorAt(1, glow_color)
    p.fillRect(portrait_rect, glow)
    if hacker:
        grid = QColor(c.PRI)
        grid.setAlpha(17)
        p.setPen(QPen(grid, .7))
        for x in range(int(portrait_rect.left()), int(portrait_rect.right()), 24):
            p.drawLine(QPointF(x, portrait_rect.top()), QPointF(x, portrait_rect.bottom()))
        for y in range(int(portrait_rect.top()), int(portrait_rect.bottom()), 24):
            p.drawLine(QPointF(portrait_rect.left(), y), QPointF(portrait_rect.right(), y))
    p.restore()
    if hacker:
        p.setPen(QPen(QColor(c.PRI_DIM), 1.5))
        for x, dx in [(portrait_rect.left()-6, 1), (portrait_rect.right()+6, -1)]:
            for y, dy in [(portrait_rect.top()-6, 1), (portrait_rect.bottom()+6, -1)]:
                p.drawLine(QPointF(x, y+16*dy), QPointF(x, y))
                p.drawLine(QPointF(x, y), QPointF(x+16*dx, y))
    # Quiet side contours replace the old orb/rings: a portrait, with real anatomy.
    for side in (-1, 1):
        line = QPainterPath(QPointF(width/2 + side*portrait_width*.43, band_top+band_height*.18))
        line.cubicTo(width/2+side*portrait_width*.65,band_top+band_height*.40,
                     width/2+side*portrait_width*.65,band_top+band_height*.62,
                     width/2+side*portrait_width*.40,band_top+band_height*.85)
        stroke = QColor(c.PRI)
        stroke.setAlpha(38)
        p.setPen(QPen(stroke, 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(line)
    if canvas._avatar is not None:
        avatar = canvas._avatar
        avatar.shaded = canvas.hud_style == 'face' and not hacker
        scale = min(portrait_width*.44, (band_height-20)/(avatar.SPAN+.10))
        head_y = band_top + (band_height-avatar.SPAN*scale)/2 + scale
        primary = QColor(c.PRI if hacker else '#66514b' if current_theme() == 'light' else '#efc5a8')
        accent = QColor(c.RED if canvas.muted else c.PRI)
        avatar.paint(p, width/2, head_y, scale, primary, accent, QColor(c.PANEL))
    else:
        # A face-shaped fallback still presents a person if the mesh is missing.
        cx, cy = width/2, band_top+band_height*.45
        rx, ry = portrait_width*.26, band_height*.34
        p.setPen(QPen(QColor(c.PRI_DIM), 2))
        p.setBrush(QColor(c.PANEL2))
        contour = QPainterPath(QPointF(cx,cy-ry))
        contour.cubicTo(cx+rx*1.4,cy-ry,cx+rx,cy+ry*.65,cx,cy+ry)
        contour.cubicTo(cx-rx,cy+ry*.65,cx-rx*1.4,cy-ry,cx,cy-ry)
        p.drawPath(contour)
        for side in (-1,1):
            p.drawLine(QPointF(cx+side*rx*.25,cy-ry*.16),QPointF(cx+side*rx*.58,cy-ry*.16))
        p.drawLine(QPointF(cx,cy-ry*.12),QPointF(cx-rx*.09,cy+ry*.2))
        p.drawArc(QRectF(cx-rx*.32,cy+ry*.30,rx*.64,ry*.23),180*16,180*16)
    if not compact:
        p.setPen(QColor(c.TEXT_DIM))
        p.setFont(font(7, True))
        p.drawText(QRectF(24,status_y-20,width-48,16),Qt.AlignmentFlag.AlignCenter,t('OVOZ INTERFEYSI' if hacker else 'OVOZGA MOS HARAKAT'))

    states = {
        'LISTENING': ('Sizni tinglayapman','Gapirgach, bir lahza jim turing.'),
        'THINKING': ('O‘ylayapman','Javobingiz tayyorlanmoqda.'),
        'PROCESSING': ('Vazifa bajarilmoqda','Brave sizning topshirig‘ingiz ustida ishlayapti.'),
        'SPEAKING': ('Brave javob bermoqda','Javobni to‘xtatish uchun Esc bosing.'),
        'SLEEPING': ('Suhbatga ulanmoqda','Ulanish tiklanishini kuting.'),
        'INITIALISING': ('Tayyorlanmoqda','Ovozli suhbatga ulanyapmiz.'),
        'CONNECTING': ('Suhbatga ulanmoqda','Ovozli suhbatga ulanyapmiz.'),
    }
    title, note = states.get(canvas.state, ('Suhbatga tayyor','Brave bilan suhbatni boshlang.'))
    if canvas.speaking:
        title, note = states['SPEAKING']
    if canvas.muted:
        title, note = 'Mikrofon o‘chirilgan','Davom etish uchun F4 bosing.'
    win=canvas.window()
    if getattr(win,'_active_provider',None)=='ollama' and canvas.state in ('LISTENING','MUTED'):
        voice=getattr(win,'_local_voice',None)
        if voice and voice.busy:
            title, note = ('Sizni tinglayapman','Gapirgach, bir lahza jim turing.') if voice.recording else ('Nutq lokal tanilmoqda…','Javobingiz tayyorlanmoqda.')
        else:
            title, note = 'Suhbatga tayyor','Gapirish uchun F4 bosing yoki matn yozing.'
    p.setFont(font(13 if not compact else 11,True))
    p.setPen(QColor(c.WHITE))
    p.drawText(QRectF(20,status_y,width-40,28),Qt.AlignmentFlag.AlignCenter,t(title))
    if not compact:
        p.setFont(font(9))
        p.setPen(QColor(c.TEXT_DIM))
        p.drawText(QRectF(20,status_y+33,width-40,20),Qt.AlignmentFlag.AlignCenter,t(note))
    count, step = 39, 6
    left = (width-count*step)/2
    phase = canvas._tick*.06
    for n in range(count):
        envelope = max(0,1-abs(n-count/2)/(count/2))
        value = 3 if canvas.muted else 4+math.sin(phase+n*.65)*2+canvas._amp_disp*25*envelope
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(c.BORDER_B if canvas.muted or canvas._amp_disp<.03 else c.PRI))
        p.drawRoundedRect(QRectF(left+n*step,status_y+(44 if compact else 76)-value/2,3,value),1.5,1.5)
    p.setFont(mono_font(9) if current_theme() == 'hacker' else font(8))
    p.setPen(QColor(c.TEXT_DIM))
    footer = t('Ovoz bilan boshqaring  ·  Matn bilan davom eting')
    footer = p.fontMetrics().elidedText(footer,Qt.TextElideMode.ElideRight,width-40)
    p.drawText(QRectF(20,height-30,width-40,18),Qt.AlignmentFlag.AlignCenter,footer)
    p.end()


def paint_metric(bar):
    c = colors()
    p = QPainter(bar)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    width, height = bar.width(), bar.height()
    p.setFont(font(8))
    p.setPen(QColor(c.TEXT_MED))
    p.drawText(QRectF(0, 0, width, 18), Qt.AlignmentFlag.AlignLeft, t(bar._label))
    p.setPen(QColor(c.TEXT if bar._text != "N/A" else c.TEXT_DIM))
    p.setFont(mono_font(8))
    p.drawText(QRectF(0, 0, width, 18), Qt.AlignmentFlag.AlignRight, bar._text)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(c.BAR_BG))
    p.drawRoundedRect(QRectF(0, height - 7, width, 3), 1.5, 1.5)
    p.setBrush(QColor(c.RED if bar._value > 85 else bar._color))
    p.drawRoundedRect(QRectF(0, height - 7, width * bar._value / 100, 3), 1.5, 1.5)
    p.end()


def paint_dropzone(canvas):
    c = colors()
    zone = canvas._z
    p = QPainter(canvas)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    w, h = canvas.width(), canvas.height()
    p.setBrush(QColor(c.PRI_GHO if zone._drag_over else c.PANEL2))
    p.setPen(QPen(QColor(c.PRI_DIM if zone._hovering or zone._drag_over else c.BORDER_B), 1, Qt.PenStyle.DashLine))
    p.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), 11, 11)
    icon("file", c.PRI, 20).paint(p, 14, int(h / 2 - 10), 20, 20)
    p.setFont(font(9, True))
    p.setPen(QColor(c.TEXT))
    title = "Faylni shu yerga tashlang"
    subtitle = "yoki tanlash uchun bosing"
    if zone._current_file:
        from pathlib import Path
        title = p.fontMetrics().elidedText(Path(zone._current_file).name, Qt.TextElideMode.ElideMiddle, w - 64)
        subtitle = "Fayl tayyor · Savolingizni bering"
    elif zone._drag_over:
        title, subtitle = "Biriktirish uchun qo‘yib yuboring", ""
    p.drawText(QRectF(48, h / 2 - 20, w - 58, 22), Qt.AlignmentFlag.AlignLeft, t(title))
    p.setFont(font(8))
    p.setPen(QColor(c.TEXT_DIM))
    p.drawText(QRectF(48, h / 2 + 4, w - 58, 20), Qt.AlignmentFlag.AlignLeft, t(subtitle))
    p.end()


def finish_window(win):
    """Bring retained utility panels into the same visual system."""
    c = colors()
    for widget in win.findChildren(QWidget):
        current = widget.font()
        if current.family() in ("Courier New", "Arial"):
            current.setFamily("Segoe UI")
            if current.pointSize() > 0 and current.pointSize() < 9:
                current.setPointSize(9)
            widget.setFont(current)
    for drawer in (win._quick_drawer, win._ctrl_drawer):
        if drawer.isWindow():
            continue
        drawer.setStyleSheet(f"QWidget#{drawer.objectName()} {{background: {c.PANEL2}; border: 1px solid {c.BORDER_B}; border-radius: 14px;}}")
        drawer.layout().setContentsMargins(16, 14, 16, 16)
        drawer.layout().setSpacing(8)
        for button in drawer.findChildren(QPushButton):
            button.setMinimumHeight(34)
            button.setMaximumHeight(42)
            button.setStyleSheet(button_style() + "QPushButton {text-align: left;}")
    from brave_brand import logo_icon
    win.setWindowIcon(logo_icon())
    from brave_i18n import localize_widgets
    localize_widgets(win)
    fit_header(win)


def style_overlay(widget):
    """Retained feature dialogs share the Brave typography and opaque surfaces."""
    c = colors()
    widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    widget.setObjectName('BraveDialog')
    widget.setStyleSheet(f'QWidget#BraveDialog {{background: {c.PANEL2}; border: 1px solid {c.BORDER_B}; border-radius: 16px;}}')
    translations = {
        'AUDIO DEVICES': 'Audio qurilmalar',
        'CUSTOMISE ASSISTANT': 'Shaxsiylashtirish',
        'ASSISTANT NAME': 'Yordamchi nomi',
        'YOUR NAME  (leave blank for default sir / efendim)': 'Sizning ismingiz · ixtiyoriy',
        'ASSISTANT VOICE': 'Yordamchi ovozi',
        'UI COLOUR  —  drag the handle': 'Interfeys rangi',
        'MICROPHONE — what BRAVE hears you with': 'Mikrofon · ovozingizni qabul qilish',
        'SPEAKERS — what BRAVE talks through': 'Karnay yoki quloqchin · javob ovozi',
        'Applying reconnects the session. Your conversation is kept.': 'Qurilmalar yangilanganda suhbat saqlanadi.',
        'APPLY': 'Saqlash', 'APPLY CHANGES': 'Saqlash', 'CANCEL': 'Bekor qilish',
        'CLOSE': 'Yopish', 'DEFAULT': 'Standart', 'CONFIRM': 'Tasdiqlash',
        'API CONFIGURATION': 'Brave’ga ulanish', 'GEMINI API KEY': 'Gemini API kaliti',
        'OPERATING SYSTEM': 'Operatsion tizim', 'INITIALISE SYSTEMS': 'Suhbatni boshlash',
        'PLUGIN MANAGER': 'Plaginlar', 'PLUGIN SETTINGS': 'Plagin sozlamalari',
        'LONG-TERM MEMORY': 'Yordamchi xotirasi',
    }
    decorations = '⚙🎧▸◈◉⊞⛶🧑▶● '
    for item in widget.findChildren(QLabel):
        text = item.text().strip().lstrip(decorations)
        translated = translations.get(text)
        if translated:
            item.setText(translated)
        item.setFont(font(max(9, item.font().pointSize()), item.font().bold()))
    voices = {'Charon', 'Puck', 'Kore', 'Fenrir', 'Aoede'}
    for button in widget.findChildren(QPushButton):
        text = button.text().strip().lstrip(decorations)
        button.setText(translations.get(text, button.text()))
        if text in voices:
            button.setFont(font(8, button.isChecked()))
            continue
        accent = text in {'APPLY', 'APPLY CHANGES', 'CONFIRM', 'INITIALISE SYSTEMS'}
        button.setStyleSheet(button_style(accent))
        button.setStyleSheet(button.styleSheet() + 'QPushButton {padding: 4px 9px;}')
        button.setFont(font(9, accent))
        if button.height() < 28 and text in translations:
            button.setFixedHeight(28)
            button.setMinimumWidth(80)
    for field in widget.findChildren(QLineEdit):
        field.setFont(font(10))
        field.setStyleSheet(f'QLineEdit {{background: {c.BG}; color: {c.WHITE}; border: 1px solid {c.BORDER}; border-radius: 8px; padding: 5px 9px;}} QLineEdit:focus {{border-color: {c.PRI};}}')
    for combo in widget.findChildren(QComboBox):
        combo.setFont(font(9))
        combo.setStyleSheet(f'QComboBox {{background: {c.BG}; color: {c.TEXT}; border: 1px solid {c.BORDER}; border-radius: 8px; padding: 5px 9px;}} QComboBox QAbstractItemView {{background: {c.PANEL2}; color: {c.TEXT}; selection-background-color: {c.PRI_GHO};}}')
    from brave_i18n import localize_widgets
    localize_widgets(widget)


def paint_overlay(widget):
    c = colors()
    p = QPainter(widget)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.fillRect(widget.rect(),QColor(c.BG))
    p.setBrush(QColor(c.PANEL2))
    p.setPen(QPen(QColor(c.BORDER_B), 1))
    p.drawRoundedRect(QRectF(.5, .5, widget.width() - 1, widget.height() - 1), 16, 16)
    p.end()
