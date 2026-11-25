"""Cancellable Ollama chat over Qt's event-driven network stack."""
import json
import time

from PyQt6.QtCore import QByteArray, QObject, QTimer, QUrl, pyqtSignal
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkProxy, QNetworkReply, QNetworkRequest

from core.ollama_chat import chat_payload, local_model, local_url, model_catalog, model_present
from core.ollama_model import model_info, require_chat, response_metrics, server_version


class ChatRequest(QObject):
    phase = pyqtSignal(str)
    partial = pyqtSignal(str)
    finished = pyqtSignal(str, str, bool)
    META_MS = 8000
    ADVISORY_MS = 250
    FIRST_TOKEN_MS = 120000
    IDLE_MS = 45000
    TOTAL_MS = 300000

    def __init__(self, settings, messages, parent=None, *, tools=None, tool_handler=None, output_schema=None, images=None, cold=False, keep_alive=None, output_limit=None,generation_limit=None):
        super().__init__(parent)
        local_url(settings.url)
        local_model(settings.model)
        self.settings, self.messages = settings, messages
        self.tools,self.tool_handler=tools,tool_handler
        self.output_schema,self.images=output_schema,images
        self.tool_calls=[];self.tool_rounds=0
        self.cold=cold
        self.keep_alive=keep_alive
        if output_limit is not None and (type(output_limit) is not int or output_limit < 1):
            raise ValueError('output_limit must be a positive integer')
        self.output_limit = output_limit
        if generation_limit is not None and (type(generation_limit) is not int or not 1<=generation_limit<=8192):
            raise ValueError('generation_limit must be 1–8192')
        self.generation_limit=generation_limit
        self.manager = QNetworkAccessManager(self)
        self.manager.setProxy(QNetworkProxy(QNetworkProxy.ProxyType.NoProxy))
        self.reply = None
        self.ended = False
        self.text = ''
        self.buffer = bytearray()
        self.last_emit = 0
        self.first_text = False
        self.first_thinking = False
        self.info = model_info({})
        self.started_at = None
        self.metrics = {'model': settings.model, 'profile': settings.profile, 'residency': 'unknown'}
        self.idle = QTimer(self)
        self.idle.setSingleShot(True)
        self.idle.timeout.connect(self.timeout)
        self.deadline = QTimer(self)
        self.deadline.setSingleShot(True)
        self.deadline.timeout.connect(self.deadline_timeout)

    def start(self):
        self.started_at = time.monotonic()
        self.deadline.start(self.TOTAL_MS)
        self.phase.emit('checking')
        if self.cold:
            self.request('/api/generate',lambda data:self.request('/api/tags',self.tags),
                {'model':self.settings.model,'keep_alive':0,'stream':False})
        else:self.request('/api/tags', self.tags)

    def request(self, path, callback=None, payload=None):
        if self.ended:
            return
        self.buffer.clear()
        self.callback = callback
        self.streaming = path == '/api/chat'
        request = QNetworkRequest(QUrl(self.settings.url+path))
        request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                             QNetworkRequest.RedirectPolicy.ManualRedirectPolicy)
        request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, 'application/json')
        self.reply = (self.manager.get(request) if payload is None else
                      self.manager.post(request, QByteArray(json.dumps(payload).encode('utf-8'))))
        reply = self.reply
        reply.readyRead.connect(lambda: self.read(reply))
        reply.finished.connect(lambda: self.received(reply))
        timeout = self.FIRST_TOKEN_MS if self.streaming else self.META_MS
        if callback in (self.running, self.versioned):
            # Diagnostics must not add two eight-second waits before inference.
            timeout = min(timeout, self.ADVISORY_MS)
        self.idle.start(timeout)

    def read(self, reply):
        if self.ended or reply is not self.reply:
            return
        self.buffer.extend(bytes(reply.readAll()))
        if len(self.buffer) > 4*1024*1024:
            self.fail('Ollama noto‘g‘ri javob qaytardi. Qayta urinib ko‘ring.')
            return
        if self.streaming:
            # Inspect the HTTP status before treating any body as model output.
            code = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            if code != 200:
                return
            while b'\n' in self.buffer and not self.ended and reply is self.reply:
                raw, _, rest = self.buffer.partition(b'\n')
                self.buffer = bytearray(rest)
                if raw.strip():
                    self.chunk(raw)

    def received(self, reply):
        if self.ended or reply is not self.reply:
            return
        self.read(reply)
        if self.ended or reply is not self.reply:
            return
        code = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        error = reply.error()
        callback = self.callback
        self.reply = None
        reply.deleteLater()
        self.idle.stop()
        if code and 300 <= code < 400:
            self.fail('Ollama lokal manzildan boshqa joyga yo‘naltirdi.')
        elif error != QNetworkReply.NetworkError.NoError or code != 200:
            # /ps is advisory; an old server without it can still chat.
            if callback in (self.running, self.versioned):
                callback(None)
            else:
                self.fail('Model topilmadi. Avval uni Ollama orqali yuklang.' if code == 404 else
                          'Ollama ishlamayapti. Ollama ilovasini yoki ollama serve buyrug‘ini ishga tushiring.' if not code else
                          'Ollama javob bera olmadi. Model va bo‘sh xotirani tekshiring.')
        elif self.streaming:
            if self.buffer.strip():
                self.chunk(bytes(self.buffer))
            # A final tool-call chunk can start a new request here, including
            # servers that omit the last newline. Do not fail that new round.
            if not self.ended and self.reply is None:
                self.fail('Ollama javobi uzildi. Qayta urinib ko‘ring.')
        else:
            try:
                data = json.loads(self.buffer)
                callback(data)
            except (ValueError, TypeError, KeyError, AttributeError):
                self.fail('Ollama noto‘g‘ri javob qaytardi. Qayta urinib ko‘ring.')

    def tags(self, data):
        names = [row['name'] for row in model_catalog(data)]
        if not model_present(self.settings.model, names):
            self.fail('Model topilmadi. Avval uni Ollama orqali yuklang.')
            return
        self.request('/api/show', self.shown, {'model': self.settings.model})

    def shown(self, data):
        try:
            self.info = model_info(data)
            self.metrics['capabilities'] = self.info['capabilities']
            require_chat(self.info)
        except ValueError as exc:
            self.fail(str(exc))
            return
        self.request('/api/version', self.versioned)

    def versioned(self, data):
        self.metrics['server_version'] = server_version(data)
        self.request('/api/ps', self.running)

    def running(self, data):
        rows = data.get('models') if isinstance(data, dict) else None
        if not isinstance(rows, list):
            rows = []
        names = [row.get('name', row.get('model', '')) for row in rows or []
                 if isinstance(row, dict)]
        loaded = model_present(self.settings.model, names)
        if isinstance(data, dict) and isinstance(data.get('models'), list):
            self.metrics['residency'] = 'loaded' if loaded else 'not_loaded'
        self.phase.emit('waiting' if loaded else 'loading')
        payload = chat_payload(self.settings, self.messages, self.info)
        if self.generation_limit is not None:payload['options']['num_predict']=self.generation_limit
        if self.output_limit is not None:
            payload['options']['num_predict'] = min(payload['options']['num_predict'], self.output_limit)
        if self.keep_alive is not None:
            payload['keep_alive']=self.keep_alive
            self.metrics['keep_alive']=self.keep_alive
        if self.images:
            if 'vision' not in (self.info.get('capabilities') or []):
                self.fail('Tanlangan model rasmni qo‘llamaydi. Vision modelini tanlang.');return
            payload['messages']=[dict(row) for row in self.messages]
            payload['messages'][-1]['images']=self.images
            self.messages = payload['messages']
        if self.output_schema:payload['format']=self.output_schema
        if self.tools:
            if 'tools' not in (self.info.get('capabilities') or []):
                self.fail('Tanlangan model lokal vositalarni qo‘llamaydi. Sozlamada vositalarni o‘chiring yoki mos model tanlang.');return
            payload['tools']=self.tools
        self.payload=payload
        self.metrics['context_length'] = payload['options']['num_ctx']
        self.metrics['thinking'] = payload.get('think')
        self.request('/api/chat', payload=payload)

    def chunk(self, raw):
        try:
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError()
            if data.get('error'):
                self.fail('Ollama javob bera olmadi. Model va bo‘sh xotirani tekshiring.')
                return
            message = data.get('message') or {}
            calls=message.get('tool_calls') or []
            if calls:
                if not self.tools or not isinstance(calls,list) or len(self.tool_calls)+len(calls)>4:
                    raise ValueError()
                self.tool_calls.extend(calls)
            text = message.get('content', '')
            thinking = message.get('thinking', '')
            if not isinstance(text, str) or not isinstance(thinking, str):
                raise ValueError()
            if thinking or text:
                self.idle.start(self.IDLE_MS)
            if thinking and not self.first_text and not self.first_thinking:
                self.first_thinking = True
                self.phase.emit('thinking')
            if text:
                if not self.first_text:
                    self.first_text = True
                    self.metrics['first_reply_s'] = time.monotonic()-self.started_at
                    self.phase.emit('replying')
                self.text += text
                if not self.tools and time.monotonic()-self.last_emit >= .075:
                    self.partial.emit(self.text)
                    self.last_emit = time.monotonic()
            if data.get('done') is True:
                self.metrics.update(response_metrics(data))
                if self.tool_calls:
                    self.continue_tools();return
                if self.tools:
                    try: printed_call=json.loads(self.text)
                    except (ValueError,TypeError): printed_call=None
                    if (isinstance(printed_call,dict) and set(printed_call)=={'name','arguments'}
                            and printed_call['name'] in {row['function']['name'] for row in self.tools}
                            and isinstance(printed_call['arguments'],dict)):
                        self.fail('Model vosita chaqiruvini matn sifatida qaytardi. Boshqa vosita modelini tanlang.');return
                self.finish()
        except (ValueError, TypeError, AttributeError):
            self.fail('Ollama noto‘g‘ri javob qaytardi. Qayta urinib ko‘ring.')

    def continue_tools(self):
        if self.tool_rounds>=3:
            self.fail('Lokal vosita chaqiruvlari chegarasiga yetildi.');return
        self.tool_rounds+=1
        # A tool may open a confirmation dialog or wait for a local worker.
        # Detach the completed transport BEFORE entering any nested Qt loop;
        # its finished signal must not fail the request while the tool runs.
        reply,self.reply=self.reply,None
        if reply is not None:
            if reply.isRunning():reply.abort()
            reply.deleteLater()
        calls,self.tool_calls=self.tool_calls,[]
        responses=[]
        try:
            allowed={row['function']['name'] for row in self.tools}
            for call in calls:
                function=call['function'];name=function['name'];arguments=function['arguments']
                if name not in allowed or not isinstance(arguments,dict) or len(json.dumps(arguments))>4000:
                    raise ValueError()
                result=self.tool_handler(name,arguments)
                if self.ended:return
                responses.append({'role':'tool','tool_name':name,'content':json.dumps(result,ensure_ascii=False)})
        except (ValueError,TypeError,KeyError,RuntimeError):
            self.fail('Lokal vosita bajarilmadi yoki ruxsat berilmadi.');return
        self.messages=[*self.messages,{'role':'assistant','content':self.text,'tool_calls':calls},*responses]
        self.text=''
        self.first_text=False;self.first_thinking=False;self.metrics.pop('first_reply_s',None)
        payload=dict(self.payload);payload['messages']=self.messages
        # Replace the completed reply before sending the next round. Keep global deadline.
        self.request('/api/chat',payload=payload)

    def timeout(self):
        if not self.streaming and self.callback in (self.running, self.versioned):
            callback, reply = self.callback, self.reply
            self.reply = None
            if reply is not None:
                reply.abort()
                reply.deleteLater()
            callback(None)
            return
        self.deadline_timeout()

    def deadline_timeout(self):
        self.fail('Ollama javob vaqti tugadi. Yengilroq model yoki Tejamkor profilini tanlang.')

    def fail(self, message):
        self.finish(message)

    def cancel(self):
        self.finish(cancelled=True)

    def finish(self, error='', cancelled=False):
        if self.ended:
            return
        self.ended = True
        self.metrics['status'] = 'cancelled' if cancelled else 'error' if error or not self.text.strip() else 'completed'
        if self.tools:self.metrics['tool_rounds']=self.tool_rounds
        if self.started_at is not None:
            self.metrics['request_s'] = time.monotonic()-self.started_at
        self.idle.stop()
        self.deadline.stop()
        reply, self.reply = self.reply, None
        if reply is not None:
            if reply.isRunning():
                reply.abort()
            reply.deleteLater()
        self.finished.emit(self.text, error, cancelled)
