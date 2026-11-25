"""RAM-only image cropping and opaque redaction, with visible undo."""
from PyQt6.QtCore import Qt,QRect,QRectF,QPoint
from PyQt6.QtGui import QPainter,QColor,QPen,QPixmap
from PyQt6.QtWidgets import QWidget,QDialog,QVBoxLayout,QHBoxLayout,QPushButton,QLabel,QComboBox
from brave_i18n import translate as t


class ImageCanvas(QWidget):
    def __init__(self,pixmap,parent=None):
        super().__init__(parent);self.image=pixmap.copy();self.history=[];self.anchor=None;self.selection=QRect();self.mode='crop'
        self.setMinimumSize(320,220);self.setMouseTracking(True)

    def image_rect(self):
        size=self.image.size();size.scale(self.size(),Qt.AspectRatioMode.KeepAspectRatio)
        return QRect((self.width()-size.width())//2,(self.height()-size.height())//2,size.width(),size.height())

    def paintEvent(self,event):
        painter=QPainter(self);painter.fillRect(self.rect(),QColor('#15171c'))
        painter.drawPixmap(self.image_rect(),self.image)
        if not self.selection.isNull():
            painter.setPen(QPen(QColor('#fa984c'),2));painter.fillRect(self.selection,QColor(250,152,76,45));painter.drawRect(self.selection)

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton and self.image_rect().contains(event.position().toPoint()):
            self.anchor=event.position().toPoint();self.selection=QRect();self.update()

    def mouseMoveEvent(self,event):
        if self.anchor is not None:
            self.selection=QRect(self.anchor,event.position().toPoint()).normalized().intersected(self.image_rect());self.update()

    def mouseReleaseEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton and self.anchor is not None:
            self.selection=QRect(self.anchor,event.position().toPoint()).normalized().intersected(self.image_rect())
            self.anchor=None;self.update()

    def source_rect(self):
        rect=self.image_rect();selection=self.selection.intersected(rect)
        if selection.width()<3 or selection.height()<3:return QRect()
        sx=self.image.width()/rect.width();sy=self.image.height()/rect.height()
        return QRect(int((selection.x()-rect.x())*sx),int((selection.y()-rect.y())*sy),
                     max(1,int(selection.width()*sx)),max(1,int(selection.height()*sy))).intersected(self.image.rect())

    def apply_selection(self):
        rect=self.source_rect()
        if rect.isEmpty():return False
        self.history.append(self.image.copy());self.history=self.history[-3:]
        if self.mode=='crop':self.image=self.image.copy(rect)
        else:
            painter=QPainter(self.image);painter.fillRect(rect,QColor('black'));painter.end()
        self.selection=QRect();self.update();return True

    def undo(self):
        if self.history:self.image=self.history.pop();self.selection=QRect();self.update()


class ImageEditDialog(QDialog):
    def __init__(self,parent,pixmap,completed):
        super().__init__(parent);self.completed=completed
        from brave_control_center import style_dialog
        style=style_dialog(self,'Rasmni kesish va yashirish');self.resize(900,650)
        layout=QVBoxLayout(self);note=QLabel(t('Hududni sichqoncha bilan belgilang. Kesish yoki qora rang bilan yashirishni qo‘llang.'))
        note.setWordWrap(True);layout.addWidget(note)
        self.canvas=ImageCanvas(pixmap,self);layout.addWidget(self.canvas,1)
        row=QHBoxLayout();layout.addLayout(row);self.mode=QComboBox()
        self.mode.addItem(t('Kesish'),'crop');self.mode.addItem(t('Maxfiy hududni yashirish'),'redact');row.addWidget(self.mode)
        self.mode.currentIndexChanged.connect(lambda:self.set_mode())
        for title,callback in [('Belgilangan hududga qo‘llash',self.canvas.apply_selection),('Qaytarish',self.canvas.undo),
                               ('Tayyor',self.finish),('Bekor qilish',self.reject)]:
            button=QPushButton(t(title));button.setStyleSheet(style);button.clicked.connect(callback);row.addWidget(button)

    def set_mode(self):self.canvas.mode=self.mode.currentData()

    def finish(self):
        if not self.canvas.selection.isNull():self.canvas.apply_selection()
        self.completed(self.canvas.image.copy());self.accept()
