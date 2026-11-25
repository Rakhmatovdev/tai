"""Conversation memory, non-destructive retries and trusted source previews."""
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPlainTextEdit,QPushButton,QCheckBox,QInputDialog
from brave_i18n import translate as t
from core.chat_memory import fingerprint


def idle(win):
    return not win._features.started and not (win.can_change_chat and not win.can_change_chat())


def memory_dialog(win):
    if not idle(win):
        win._log.append_log('ERR: '+t('Avval joriy javob tugashini kuting.'))
        return
    from brave_control_center import style_dialog
    store, chat_id = win._features.store, win._features.chat_id
    memory = store.memory(chat_id)
    dialog = QDialog(win); style = style_dialog(dialog, 'Suhbat xotirasi'); dialog.resize(620,520)
    layout = QVBoxLayout(dialog)
    enabled = QCheckBox(t('Eski suhbatni lokal xulosalash')); enabled.setChecked(bool(memory['enabled']));layout.addWidget(enabled)
    layout.addWidget(QLabel(t('Mahkamlangan talablar')))
    pinned = QPlainTextEdit(memory['pinned']);pinned.setPlaceholderText(t('Muhim talablar · 1000 belgigacha'));layout.addWidget(pinned)
    layout.addWidget(QLabel(t('Tahrirlanadigan lokal xulosa')))
    summary = QPlainTextEdit(memory['summary']);layout.addWidget(summary)
    note = QLabel(t('Xulosa xato qilishi mumkin. Xotira faqat shu suhbatga tegishli.'));note.setWordWrap(True);layout.addWidget(note)
    status = QLabel();status.setWordWrap(True);layout.addWidget(status)
    actions = QHBoxLayout();layout.addLayout(actions)
    clear = QPushButton(t('Xotirani tozalash'));save = QPushButton(t('Saqlash'))
    cleared = [False]
    def clear_memory():
        pinned.clear();summary.clear();cleared[0]=True
    clear.clicked.connect(clear_memory)
    def commit():
        if not idle(win) or chat_id != win._features.chat_id:
            return
        if len(pinned.toPlainText())>1000 or len(summary.toPlainText())>1600:
            status.setText(t('Talablar 1000, xulosa 1600 belgidan oshmasin.'));return
        memory.update(pinned=pinned.toPlainText(),summary=summary.toPlainText(),enabled=enabled.isChecked())
        runtime = getattr(win,'_local_chat',None)
        if cleared[0] and runtime:
            memory.update(covered=len(runtime.history),fingerprint=fingerprint(runtime.history),offset=0)
        store.save_memory(chat_id,memory)
        dialog.accept()
    save.clicked.connect(commit)
    for button in (clear,save):button.setStyleSheet(style);actions.addWidget(button)
    dialog.exec()


def branch_last(win, edit=False, index=None):
    if not idle(win):
        win._log.append_log('ERR: '+t('Avval joriy javob tugashini kuting.'));return False
    features = win._features
    rows = features.store.messages(features.chat_id)
    if index is None:index = next((i for i in range(len(rows)-1,-1,-1) if rows[i][0]=='user'),None)
    if index is not None and (not 0<=index<len(rows) or rows[index][0]!='user'):return False
    if index is None:
        return False
    text = rows[index][1]
    if edit:
        text, ok = QInputDialog.getMultiLineText(win,t('Oxirgi xabarni tahrirlash'),t('Yangi variant alohida suhbatda ochiladi.'),text)
        if not ok or not text.strip():return False
    # Preserve the original transcript; only its prefix is copied into the fork.
    files=features.store.files(features.chat_id,index)
    new_id = features.store.fork(features.chat_id,index)
    from memory.config_manager import load_api_keys
    model=load_api_keys().get('ollama_model','') if win._active_provider=='ollama' else 'gemini'
    with features.store.db:
        features.store.db.execute('UPDATE chat_branches SET model=? WHERE child=?',(model,new_id))
    if not features.switch_chat(new_id):return False
    from brave_chat import remove_attachment
    remove_attachment(win)
    for path in files:win._drop_zone._set_file(path)
    win._input.setText(text)
    if not edit:
        import time
        timer=QTimer(win);timer.setInterval(100);deadline=time.monotonic()+30
        chat_id=features.chat_id
        provider=win._active_provider
        def send_when_ready():
            if features.chat_id!=chat_id or win._active_provider!=provider or win._input.text()!=text or time.monotonic()>deadline:
                timer.stop();timer.deleteLater();return
            if win.can_send_text and win.can_send_text():
                timer.stop();timer.deleteLater();win._send()
        timer.timeout.connect(send_when_ready);timer.start()
    return True


def source_dialog(widget, key):
    owner = widget
    while owner is not None and not hasattr(owner,'_features'):
        owner = owner.parentWidget()
    if owner is None:return
    source = owner._features.store.source(key)
    if not source:return
    from brave_control_center import style_dialog
    dialog=QDialog(owner);style=style_dialog(dialog,'Manba parchasi');dialog.resize(650,500)
    layout=QVBoxLayout(dialog)
    title=QLabel(source['label']);title.setTextFormat(Qt.TextFormat.PlainText);title.setWordWrap(True);layout.addWidget(title)
    path=QLabel(source['path']);path.setTextFormat(Qt.TextFormat.PlainText);path.setWordWrap(True);layout.addWidget(path)
    excerpt=QPlainTextEdit(source['text']);excerpt.setReadOnly(True);layout.addWidget(excerpt)
    note=QLabel(t('Bu javob tayyorlanayotganda berilgan lokal parcha.'));note.setWordWrap(True);layout.addWidget(note)
    close=QPushButton(t('Yopish'));close.setStyleSheet(style);close.clicked.connect(dialog.accept);layout.addWidget(close)
    dialog.exec()
