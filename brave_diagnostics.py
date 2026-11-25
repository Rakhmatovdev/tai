"""User-triggered health checks for the active cloud or local backend."""
import platform
import threading
import urllib.error
import urllib.request

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QDialog,QHBoxLayout,QLabel,QPushButton,QVBoxLayout,QScrollArea,QWidget
from brave_i18n import translate as t


def probe_network():
    try:
        with urllib.request.urlopen('https://generativelanguage.googleapis.com/',timeout=4):
            return True
    except urllib.error.HTTPError:
        # An HTTP reply confirms DNS/TLS/reachability, not API authentication.
        return True
    except Exception:
        return False


def collect_checks(runtime,network_probe=probe_network,device_probe=None):
    if runtime.get('provider') == 'ollama':
        from core.ollama_chat import Settings, OllamaClient
        client = None
        try:
            client = OllamaClient(Settings.read())
            client.verify()
            status, detail = 'good', 'Ollama ulandi. Lokal model tayyor.'
        except (ValueError, RuntimeError) as exc:
            status, detail = 'error', str(exc)
        except Exception:
            status, detail = 'error', 'Ollama javobi uzildi. Qayta urinib ko‘ring.'
        finally:
            if client is not None:
                client.close()
        return [('Ollama · Offline', status, detail),
                ('Audio', 'info', 'Offline ovoz suhbat menyusidan, mikrofon faqat yozishda ochiladi.'),
                ('Lokal chat', 'info', 'Ollama: lokal chat va hujjatlar. Offline ovoz suhbat menyusida.')]+local_performance_checks(runtime)
    from core.audio_hotplug import endpoint_snapshot
    from memory.config_manager import get_gemini_key
    device_probe=device_probe or endpoint_snapshot
    results=[]
    reachable=network_probe()
    results.append(('Internet / Gemini','good' if reachable else 'error',
        'Gemini serveriga xavfsiz HTTPS ulanish ishlaydi.' if reachable else
        'Gemini serveriga ulanib bo‘lmadi. Internet yoki VPN sozlamalarini tekshiring.'))
    configured=bool(get_gemini_key())
    results.append(('Gemini / API','good' if runtime.get('connected') else ('warn' if configured else 'error'),
        'Gemini bilan jonli ulanish tasdiqlandi.' if runtime.get('connected') else
        ('API kaliti saqlangan. Jonli ulanish hali tasdiqlanmagan.' if configured else 'API kaliti topilmadi. Sozlamalarda kalitni kiriting.')))
    if runtime.get('network_allowed') is False:
        results[-1]=('Gemini / API','info','Internet ruxsati o‘chiq. Brave markazidan yoqing.')
    try:
        snapshot=device_probe()
        if platform.system()=='Windows':
            output_count=len(snapshot[0][0]);input_count=len(snapshot[0][1])
            denied='Deny' in snapshot[2]
        else:
            input_count=sum(d[1]>0 for d in snapshot[0]);output_count=sum(d[2]>0 for d in snapshot[0]);denied=False
        for label,kind,count in [('Mikrofon','microphone',input_count),('Karnay / quloqchin','speaker',output_count)]:
            if runtime.get('text_only'):
                status,detail='info','Faqat matn rejimi yoqilgan. Ovoz uzatilmaydi va ijro etilmaydi.'
            elif kind=='microphone' and runtime.get('microphone_allowed') is False:
                status,detail='info','Brave mikrofon ruxsati o‘chiq. Brave markazidan yoqing.'
            elif kind=='microphone' and denied:
                status,detail='error','Windows mikrofon ruxsati o‘chiq. Privacy & security → Microphone bo‘limini tekshiring.'
            elif runtime.get(kind):
                status,detail='good','Audio oqimi ochiq va ishlashga tayyor.'
            elif count:
                status,detail='warn','Qurilma mavjud, lekin audio oqimi ochilmagan. Audio qurilmalarni yangilang yoki boshqa qurilmani tanlang.'
            else:
                status,detail='error','Faol audio qurilma topilmadi. Ulanish yoki Windows Sound sozlamalarini tekshiring.'
            results.append((label,status,detail))
    except Exception:
        results.append(('Audio qurilmalar','warn','Audio qurilmalarni tekshirib bo‘lmadi. Qurilmalarni yangilang va qayta tekshiring.'))
    watching=runtime.get('hotplug')
    results.append(('Avtomatik aniqlash','good' if watching=='watching' else 'warn',
        'Audio qurilmalar o‘zgarishi avtomatik kuzatilmoqda.' if watching=='watching' else
        ('Qurilmalar yangilanmoqda. Birozdan keyin qayta tekshiring.' if watching=='refreshing' else 'Avtomatik kuzatuv hali tayyor emas. Audio qurilmalarni yangilang.')))
    return results


def local_performance_checks(runtime):
    profiles = {'auto': 'Avtomatik', 'economy': 'Tejamkor', 'balanced': 'Muvozanatli', 'quality': 'Sifat'}
    configured = t(profiles.get(runtime.get('configured_profile'), 'Avtomatik'))
    effective = t(profiles.get(runtime.get('profile'), 'Tejamkor'))
    profile = t('Tanlangan profil')+': '+configured+' · '+t('Amaldagi profil')+': '+effective
    metrics = runtime.get('last_request')
    if not metrics:
        return [('Resurs profili', 'info', profile),
                ('Tezlik o‘lchovlari', 'info', t('Hali o‘lchov yo‘q. Lokal xabar yuboring.'))]
    state = t({'completed': 'Tugallandi', 'cancelled': 'Bekor qilindi', 'error': 'Xato'}.get(metrics.get('status'), 'Xato'))
    residency = t({'loaded': 'Model xotirada edi', 'not_loaded': 'Model xotirada emas edi'}.get(metrics.get('residency'), 'Model holati noma’lum'))
    context = str(metrics.get('context_length') or '—')
    model = str(metrics.get('model') or '—')
    version = str(metrics.get('server_version') or '—')
    request_profile = t(profiles.get(metrics.get('profile'), 'Tejamkor'))
    request = (f'{model} · Ollama {version}\n{state} · {residency}\n'+
               t('So‘rov profili')+': '+request_profile+' · '+t('Kontekst')+': '+context)
    def seconds(key):
        value = metrics.get(key)
        return f'{value:.2f} s' if isinstance(value, (int, float)) else '—'
    speed = metrics.get('tokens_per_second')
    details = [t('Birinchi javob')+': '+seconds('first_reply_s')+' · '+t('Jami vaqt')+': '+seconds('elapsed_s'),
               t('Tayyorlash')+': '+seconds('preparation_s')+' · '+t('Modelni yuklash')+': '+seconds('load_s'),
               t('Generatsiya tezligi')+': '+(f'{speed:.1f} token/s' if isinstance(speed, (int, float)) else '—'),
               t('Kirish / chiqish tokenlari')+': '+str(metrics.get('prompt_eval_count', '—'))+' / '+str(metrics.get('eval_count', '—'))]
    if metrics.get('done_reason') == 'length':
        details.append(t('Javob uzunlik chegarasiga yetdi. Davom ettirishni so‘rashingiz mumkin.'))
    return [('Resurs profili', 'info', profile), ('So‘nggi lokal so‘rov', 'info', request),
            ('Tezlik o‘lchovlari', 'warn' if metrics.get('done_reason') == 'length' else 'info', '\n'.join(details))]


class DiagnosticsDialog(QDialog):
    resultsReady=pyqtSignal(object)

    def __init__(self,win):
        super().__init__(win)
        from brave_ui import colors,font,button_style
        self.win=win;self.busy=False
        c=colors();self.setWindowTitle(t('Diagnostika'));self.setFont(font(10));self.resize(650,530)
        self.setStyleSheet(f'QDialog {{background:{c.PANEL};color:{c.TEXT};}} QLabel {{font-family:"Segoe UI";}}')
        layout=QVBoxLayout(self);layout.setContentsMargins(22,18,22,18);layout.setSpacing(12)
        title=QLabel(t('Brave ishlash holati'));title.setFont(font(17,True));title.setStyleSheet(f'color:{c.WHITE};');layout.addWidget(title)
        self.summary=QLabel(t('Tekshirilmoqda…'));self.summary.setFont(font(9));self.summary.setWordWrap(True);self.summary.setStyleSheet(f'color:{c.TEXT_DIM};');layout.addWidget(self.summary)
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet(f'QScrollArea {{background:{c.PANEL};border:none;}} '
            f'QScrollBar:vertical {{background:transparent;width:6px;}} '
            f'QScrollBar::handle:vertical {{background:{c.BORDER_B};min-height:28px;border-radius:3px;}} '
            'QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {height:0;} '
            'QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical {background:transparent;}')
        scroll.viewport().setStyleSheet(f'background:{c.PANEL};')
        content=QWidget();content.setObjectName('DiagnosticsContent')
        content.setStyleSheet(f'QWidget#DiagnosticsContent {{background:{c.PANEL};}}')
        self.rows=QVBoxLayout(content);self.rows.setContentsMargins(0,0,4,0);self.rows.setSpacing(8)
        self.rows.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(content);layout.addWidget(scroll,1)
        note=QLabel(t('Bu tekshiruv ovoz yozmaydi va API kalitini ko‘rsatmaydi.'))
        note.setFont(font(9))
        note.setWordWrap(True);note.setStyleSheet(f'color:{c.TEXT_DIM};');layout.addWidget(note)
        actions=QHBoxLayout()
        self.check=QPushButton(t('Qayta tekshirish'));self.check.clicked.connect(self.run)
        refresh=QPushButton(t('Audio yangilash'));refresh.clicked.connect(self.refresh_audio)
        choose=QPushButton(t('Qurilma tanlash'));choose.clicked.connect(self.choose_audio)
        reconnect=QPushButton(t('Qayta ulanish'));reconnect.clicked.connect(self.reconnect)
        for button in (self.check,refresh,choose,reconnect):button.setStyleSheet(button_style());actions.addWidget(button)
        if getattr(win, '_active_provider', 'gemini') == 'ollama':
            refresh.setEnabled(False)
            choose.setEnabled(False)
        layout.addLayout(actions)
        self.resultsReady.connect(self.present)
        QTimer.singleShot(0,self.run)

    def run(self):
        if self.busy:return
        self.busy=True;self.check.setEnabled(False);self.summary.setText(t('Tekshirilmoqda…'))
        callback=self.win.get_diagnostics
        runtime=callback() if callback else {}
        def work():
            try:
                results=collect_checks(runtime)
            except Exception:
                results=[('Diagnostika','error','Tekshiruv bajarilmadi. Qayta urinib ko‘ring.')]
            try:self.resultsReady.emit(results)
            except RuntimeError:pass  # The main window was closed during a check.
        threading.Thread(target=work,daemon=True,name='brave-diagnostics').start()

    def present(self,results):
        from brave_ui import colors,font
        c=colors();self.busy=False;self.check.setEnabled(True)
        while self.rows.count():
            item=self.rows.takeAt(0)
            if item.widget():item.widget().deleteLater()
        self.summary.setText(t('Tekshiruv tugadi. Quyidagi holatlarni ko‘rib chiqing.'))
        for name,status,detail in results:
            color={'good':c.GREEN,'warn':c.ACC2,'error':c.RED,'info':c.TEXT_DIM}[status]
            literal = name in ('Resurs profili', 'So‘nggi lokal so‘rov', 'Tezlik o‘lchovlari')
            row=QLabel('●  '+t(name)+'\n'+(detail if literal else t(detail)));row.setWordWrap(True);row.setFont(font(9))
            row.setTextFormat(Qt.TextFormat.PlainText)
            row.setProperty('brave_literal_text', True)
            row.setStyleSheet(f'color:{color};background:{c.PANEL2};border:1px solid {c.BORDER};border-radius:10px;padding:10px;')
            self.rows.addWidget(row)

    def refresh_audio(self):
        if self.win.on_audio_device_change:
            self.win.on_audio_device_change()
            self.summary.setText(t('Qurilmalar yangilanmoqda. Birozdan keyin qayta tekshiring.'))

    def reconnect(self):
        if getattr(self.win, '_active_provider', 'gemini') == 'ollama':
            self.run()
            return
        if self.win.on_access_change:
            self.win.on_access_change()
            self.summary.setText(t('Qayta ulanish so‘raldi.'))

    def choose_audio(self):
        self.accept()
        QTimer.singleShot(0,self.win._open_audio_devices)


def open_diagnostics(win):
    DiagnosticsDialog(win).exec()
