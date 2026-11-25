"""Companion pages for the native Brave Center."""
import uuid
from PyQt6.QtCore import Qt,QTimer
from PyQt6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QPlainTextEdit,
    QPushButton,QListWidget,QListWidgetItem,QComboBox,QCheckBox,QInputDialog,QMessageBox)
from brave_i18n import translate as t
from core import companion,workspace_store

def button(center,layout,title,callback):
    item=QPushButton(t(title));item.setStyleSheet(center.button_style);item.clicked.connect(callback);layout.addWidget(item)
    return item

def memory_page(center):
    from memory.memory_manager import load_memory,edit_fact
    page=QWidget();layout=QVBoxLayout(page)
    note=QLabel(t('Xotira lokal saqlanadi va Gemini suhbat kontekstiga qo‘shilishi mumkin.'));note.setWordWrap(True);layout.addWidget(note)
    search=QLineEdit();search.setPlaceholderText(t('Xotirani qidirish…'));layout.addWidget(search)
    listing=QListWidget();layout.addWidget(listing,1)
    preview=QPlainTextEdit();preview.setReadOnly(True);preview.setMaximumHeight(110);layout.addWidget(preview)
    def refresh():
        listing.clear()
        for category,entries in load_memory().items():
            if not isinstance(entries,dict):continue
            for key,entry in entries.items():
                if not isinstance(entry,dict) or 'value' not in entry:continue
                value=str(entry['value'])
                if search.text().casefold() not in (category+' '+key+' '+value).casefold():continue
                item=QListWidgetItem(category+' / '+key);item.setData(Qt.ItemDataRole.UserRole,(category,key,value));listing.addItem(item)
    def selection():
        item=listing.currentItem();return item.data(Qt.ItemDataRole.UserRole) if item else None
    def changed(*_):
        selected=selection();preview.setPlainText(selected[2] if selected else '')
    def edit():
        selected=selection()
        if not selected:return
        value,ok=QInputDialog.getMultiLineText(center,t('Xotirani tahrirlash'),selected[1],selected[2])
        if ok and value.strip():edit_fact(selected[0],selected[1],value);refresh();center.controller.save()
    def delete():
        selected=selection()
        if not selected:return
        if QMessageBox.question(center,t('O‘chirish'),t('Tanlangan xotira o‘chirilsinmi?'),QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes:
            edit_fact(selected[0],selected[1],None);refresh();center.controller.save()
    row=QHBoxLayout();layout.addLayout(row)
    button(center,row,'Xotirani tahrirlash',edit);button(center,row,'O‘chirish',delete);button(center,row,'Yangilash',refresh)
    search.textChanged.connect(refresh);listing.currentItemChanged.connect(changed);refresh();return page

def conversation_page(center):
    page=QWidget();layout=QVBoxLayout(page);cfg=companion.settings()
    layout.addWidget(QLabel(t('Javob uzunligi')));length=QComboBox()
    for title,key in [('Qisqa','short'),('Muvozanatli','balanced'),('Batafsil','detailed')]:length.addItem(t(title),key)
    length.setCurrentIndex(length.findData(cfg['answer_length']));layout.addWidget(length)
    barge=QCheckBox(t('Gapni bo‘lib savol berish'));barge.setChecked(cfg['barge_in']);layout.addWidget(barge)
    note=QLabel(t('Ovoz bilan bo‘lish xona va karnayga bog‘liq. Esc har doim javobni to‘xtatadi.'));note.setWordWrap(True);layout.addWidget(note)
    recover=QCheckBox(t('Ulanish va ovozni avtomatik tiklash'));recover.setChecked(cfg['auto_recover']);layout.addWidget(recover)
    def save():
        companion.save_settings({'answer_length':length.currentData(),'barge_in':barge.isChecked(),'auto_recover':recover.isChecked()})
        center.controller.save()
    length.currentIndexChanged.connect(save);barge.toggled.connect(save);recover.toggled.connect(save)
    button(center,layout,'Javobni to‘xtatish',center.win._do_interrupt)
    button(center,layout,'Diagnostikani ochish',lambda:__import__('brave_diagnostics').open_diagnostics(center.win))
    layout.addStretch();return page

def routines_page(center):
    page=QWidget();layout=QVBoxLayout(page)
    note=QLabel(t('Ssenariy nomini ayting yoki Ishga tushirish tugmasini bosing. Amallar joriy ruxsatlarga bo‘ysunadi.'));note.setWordWrap(True);layout.addWidget(note)
    listing=QListWidget();layout.addWidget(listing,1)
    name=QLineEdit();name.setPlaceholderText(t('Masalan: Ishni boshlaymiz'));layout.addWidget(name)
    steps=QPlainTextEdit();steps.setPlaceholderText(t('Masalan: VS Code och, loyiha papkasini och, keyin rejamni so‘ra.'));steps.setMaximumHeight(130);layout.addWidget(steps)
    def refresh():
        listing.clear()
        for routine in companion.routines():
            item=QListWidgetItem(routine['name']);item.setData(Qt.ItemDataRole.UserRole,routine);listing.addItem(item)
    def selected():
        item=listing.currentItem();return item.data(Qt.ItemDataRole.UserRole) if item else None
    def select(*_):
        value=selected();name.setText(value['name'] if value else '');steps.setPlainText(value['steps'] if value else '')
    def save():
        if not name.text().strip() or not steps.toPlainText().strip():return
        old=selected();value={'id':old['id'] if old else uuid.uuid4().hex,'name':name.text().strip()[:100],'steps':steps.toPlainText().strip()[:6000]}
        workspace_store.update('routines.json',lambda rows:[row for row in rows if row['id']!=value['id']]+[value])
        refresh();center.controller.save()
    def delete():
        old=selected()
        if old:workspace_store.update('routines.json',lambda rows:[row for row in rows if row['id']!=old['id']]);refresh();center.controller.save()
    def run():
        old=selected()
        if old:
            if center.win._input.text().strip():center.win._log.append_log('ERR: Avval yozilayotgan xabarni yuboring yoki tozalang.');return
            center.win._input.setText(old['name']+'\n'+old['steps']);center.accept();center.win._send()
    row=QHBoxLayout();layout.addLayout(row)
    button(center,row,'Yangi',lambda:(listing.clearSelection(),listing.setCurrentRow(-1),name.clear(),steps.clear()))
    button(center,row,'Saqlash',save);button(center,row,'O‘chirish',delete);button(center,row,'Ishga tushirish',run)
    listing.currentItemChanged.connect(select);refresh();return page

def tasks_page(center):
    page=QWidget();layout=QVBoxLayout(page)
    search=QLineEdit();search.setPlaceholderText(t('Vazifalarni qidirish…'));layout.addWidget(search)
    filters=QComboBox()
    for title,key in [('Barchasi','all'),('Bajarilmoqda','Bajarilmoqda'),('Javob tayyor','Javob tayyor'),('Xato','Xato'),('Bekor qilindi','Bekor qilindi'),('Uzuldi','Uzuldi')]:filters.addItem(t(title),key)
    layout.addWidget(filters)
    summary=QLabel();layout.addWidget(summary)
    note=QLabel(t('Qayta urinish avvalgi amallarni takrorlashi mumkin. So‘rovni tekshirib keyin yuboring.'));note.setWordWrap(True);layout.addWidget(note)
    listing=QListWidget();layout.addWidget(listing,1)
    preview=QPlainTextEdit();preview.setReadOnly(True);layout.addWidget(preview,1)
    def selected():
        item=listing.currentItem();return item.data(Qt.ItemDataRole.UserRole) if item else None
    last=[None]
    def refresh():
        import json
        rows=workspace_store.read('tasks.json',[]) if center.controller.persist else center.win._features.tasks
        fingerprint=json.dumps(rows,ensure_ascii=False)+search.text()+str(filters.currentData())
        if last[0]==fingerprint:return
        last[0]=fingerprint
        old=selected();listing.clear()
        for row in reversed(rows[-100:]):
            if filters.currentData()!='all' and row['status']!=filters.currentData():continue
            if search.text().casefold() not in (row['request']+' '+row.get('result','')).casefold():continue
            item=QListWidgetItem(t(row['status'])+' · '+row['request'][:75]);item.setData(Qt.ItemDataRole.UserRole,row);listing.addItem(item)
            if old and row['id']==old['id']:listing.setCurrentItem(item)
        if listing.currentItem() is None and listing.count():listing.setCurrentRow(0)
        summary.setText(t('Ko‘rsatilgan vazifalar')+': '+str(listing.count()))
    def select(*_):
        row=selected()
        preview.setPlainText((t('So‘rov')+'\n'+row['request']+'\n\n'+t('Bosqichlar')+'\n'+('\n'.join(t(step) for step in row.get('steps',[])) or '—')+'\n\n'+t('Natija')+'\n'+(row.get('result','') or t('Natija hali yo‘q.'))+'\n\n'+t('Davomiylik')+': '+str(row.get('duration','—'))+' s') if row else '')
    def retry():
        row=selected()
        if row and not center.win._input.text().strip():
            center.win._input.setText(row['request']);center.accept();center.win._input.setFocus()
    def delete():
        row=selected()
        if not row:return
        if center.controller.persist:workspace_store.update('tasks.json',lambda rows:[old for old in rows if old['id']!=row['id']])
        features=center.win._features
        features.tasks=[old for old in features.tasks if old['id']!=row['id']]
        if features.current_task and features.current_task['id']==row['id']:features.current_task=None
        refresh()
    row=QHBoxLayout();layout.addLayout(row)
    button(center,row,'So‘rovni qayta tayyorlash',retry);button(center,row,'Javobni to‘xtatish',center.win._do_interrupt)
    button(center,row,'O‘chirish',delete)
    def copy_result():
        from PyQt6.QtWidgets import QApplication
        record=selected()
        if record:QApplication.clipboard().setText(record.get('result',''))
    button(center,row,'Natijani nusxalash',copy_result)
    listing.currentItemChanged.connect(select)
    search.textChanged.connect(refresh);filters.currentIndexChanged.connect(refresh)
    timer=QTimer(page);timer.setInterval(2000);timer.timeout.connect(refresh);timer.start();refresh();return page
