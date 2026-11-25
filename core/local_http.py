"""Cancellable local JSON requests for worker threads with Qt event dispatchers."""
import json
from PyQt6.QtCore import QCoreApplication,QEventLoop,QTimer,QUrl,QByteArray
from PyQt6.QtNetwork import QNetworkAccessManager,QNetworkProxy,QNetworkRequest,QNetworkReply
from core.local_jobs import Cancelled
from core.ollama_chat import local_url


def embedding_request(url,payload,cancelled):
    local_url(url)
    if QCoreApplication.instance() is None:
        raise RuntimeError('Semantik qidiruvni Brave ilovasida ishga tushiring.')
    if cancelled.is_set():raise Cancelled('Bekor qilindi.')
    manager=QNetworkAccessManager()
    manager.setProxy(QNetworkProxy(QNetworkProxy.ProxyType.NoProxy))
    request=QNetworkRequest(QUrl(url+'/api/embed'))
    request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,QNetworkRequest.RedirectPolicy.ManualRedirectPolicy)
    request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader,'application/json')
    reply=manager.post(request,QByteArray(json.dumps(payload).encode('utf-8')))
    loop=QEventLoop();poll=QTimer();deadline=QTimer();buffer=bytearray();reason=[]
    def read():
        buffer.extend(bytes(reply.readAll()))
        if len(buffer)>4*1024*1024:reason.append('Embedding javobi juda katta.');reply.abort()
    def check():
        if cancelled.is_set():reply.abort()
    def timeout():reason.append('Embedding modeli javob vaqti tugadi.');reply.abort()
    reply.readyRead.connect(read);reply.finished.connect(loop.quit)
    poll.timeout.connect(check);poll.start(50);deadline.setSingleShot(True);deadline.timeout.connect(timeout);deadline.start(120000)
    try:
        if not reply.isFinished():loop.exec()
        read()
        if cancelled.is_set():raise Cancelled('Bekor qilindi.')
        if reason:raise ValueError(reason[0])
        code=reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        if code!=200 or reply.error()!=QNetworkReply.NetworkError.NoError:
            raise ValueError('Embedding modeli javob bermadi. Model va serverni tekshiring.')
        return json.loads(buffer)
    finally:
        poll.stop();deadline.stop()
        from PyQt6 import sip
        sip.delete(manager)
