"""Local chat export and keyboard reference; no network access."""
from datetime import datetime
from pathlib import Path
from PyQt6.QtWidgets import QDialog,QVBoxLayout,QGridLayout,QLabel,QPushButton,QFileDialog
from brave_i18n import translate as t

def markdown(messages):
    rows=['# Brave','']
    for role,body,stamp in messages:
        rows.extend(['## '+(t('Siz') if role=='user' else 'Brave')+' · '+stamp,'',body,''])
    return '\n'.join(rows)

def export_chat(win):
    messages=win._features.store.messages(win._features.chat_id)
    if not messages:
        win._log.append_log('SYS: Eksport qilish uchun suhbat hali yo‘q.')
        return
    path,_=QFileDialog.getSaveFileName(win,t('Suhbatni eksport qilish'),'Brave-'+datetime.now().strftime('%Y-%m-%d')+'.md','Markdown (*.md)')
    if not path:return
    target=Path(path)
    if not target.suffix:target=target.with_suffix('.md')
    import uuid
    temporary=target.with_name(target.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        temporary.write_text(markdown(messages),encoding='utf-8');temporary.replace(target)
        win._log.append_log('SYS: Suhbat faylga saqlandi.')
    except OSError:
        win._log.append_log('ERR: Faylni saqlab bo‘lmadi. Boshqa joy tanlang.')
    finally:
        if temporary.exists():temporary.unlink()

def shortcut_help(win):
    from brave_control_center import style_dialog
    dialog=QDialog(win);style=style_dialog(dialog,'Klaviatura yordami');dialog.resize(480,420)
    layout=QVBoxLayout(dialog);layout.addWidget(QLabel(t('Brave bilan tezroq ishlang')))
    grid=QGridLayout();layout.addLayout(grid)
    for row,(key,action) in enumerate([('Ctrl+K','Tezkor qidiruv'),('Ctrl+F','Suhbat ichida qidirish'),('Ctrl+Shift+F','Fokus rejimi'),('Enter','Xabar yuborish'),('Shift+Enter','Yangi qator'),('Esc','Javobni to‘xtatish'),('Ctrl+L','Xabar maydoniga o‘tish'),('Ctrl+Shift+E','Suhbatni eksport qilish'),('Ctrl+Alt+F8','Mini oyna'),('F4','Mikrofonni yoqish / o‘chirish'),('F11','To‘liq ekran'),('F1','Klaviatura yordami')]):
        grid.addWidget(QLabel(key),row,0);grid.addWidget(QLabel(t(action)),row,1)
    note=QLabel(t('Mini oyna tugmasi tizim bo‘ylab ishlaydi; qolgan tugmalar Brave oynasida ishlaydi.'));note.setWordWrap(True);layout.addWidget(note)
    close=QPushButton(t('Yopish'));close.setStyleSheet(style);close.clicked.connect(dialog.accept);layout.addWidget(close)
    dialog.exec()
