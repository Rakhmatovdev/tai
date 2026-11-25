"""Shared vector identity for the Brave header, window and desktop shortcut."""
from pathlib import Path
from functools import lru_cache

from PyQt6.QtCore import QByteArray, Qt, QRectF
from PyQt6.QtGui import QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

ASSETS = Path(__file__).resolve().parent / 'assets'


@lru_cache(maxsize=32)
def logo_pixmap(size=256, theme='dark', scale=1):
    variant = '-light' if theme == 'light' else ''
    detail = '-small' if size <= 24 else ''
    path = ASSETS / f'brave-logo{variant}{detail}.svg'
    if theme == 'hacker':
        svg = path.read_text(encoding='utf-8')
        for source, target in {
            '#292c36':'#1f3628', '#111217':'#090e0c', '#41434e':'#425f4c',
            '#ffdcaf':'#ddffd0', '#ffa46b':'#a3ef8c', '#e3653e':'#4aaf6b',
        }.items():
            svg = svg.replace(source, target)
        renderer = QSvgRenderer(QByteArray(svg.encode('utf-8')))
    else:
        renderer = QSvgRenderer(str(path))
    if not renderer.isValid():
        raise ValueError(f'Invalid Brave logo: {path}')
    pixmap = QPixmap(size * scale, size * scale)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, size * scale, size * scale))
    painter.end()
    pixmap.setDevicePixelRatio(scale)
    return pixmap


def logo_icon(theme=None):
    if theme is None:
        from brave_ui import current_theme
        theme = current_theme()
    result = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        result.addPixmap(logo_pixmap(size, theme))
    return result


def refresh_logos(root, theme):
    from PyQt6.QtWidgets import QLabel
    for widget in root.findChildren(QLabel):
        size = widget.property('brave_logo_size')
        if size:
            widget.setPixmap(logo_pixmap(size, theme, 2))


def export_icon(path):
    """Export the same SVG to a Windows icon with native small-size frames."""
    import io
    from PIL import Image
    from PyQt6.QtCore import QBuffer, QIODevice
    frames = []
    sizes = (256, 128, 64, 48, 32, 24, 16)
    for size in sizes:
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        logo_pixmap(size, scale=4).save(buffer, 'PNG')
        image = Image.open(io.BytesIO(bytes(buffer.data()))).convert('RGBA')
        frames.append(image.resize((size, size), Image.Resampling.LANCZOS))
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(destination, format='ICO', append_images=frames[1:],
                   sizes=[(size, size) for size in sizes])
