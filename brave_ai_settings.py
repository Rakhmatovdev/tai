"""Model controls live only inside the existing searchable Settings window."""
import threading

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QComboBox, QCompleter, QPushButton, QCheckBox

from brave_i18n import translate as t
from brave_ui import label, colors, font, button_style
from core.ollama_chat import Settings, OllamaClient, provider, local_url, local_model
from memory.config_manager import load_api_keys, _patch_config
from core.ollama_service import ensure_server
from core.ollama_resources import sample_resources, sample_hardware, suggested_profile, hardware_summary, hardware_recommendation_text, GIB
from core.ollama_model import require_chat, thinking_choice


class AISettings(QWidget):
    checked = pyqtSignal(object)
    resourcesReady = pyqtSignal(object)
    described = pyqtSignal(object)

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.busy = False
        self.catalog = {}
        self.catalog_url = None
        self.catalog_requested = None
        self.resources = None
        self.sampling = False
        self.stopped = threading.Event()
        self.description_key = None
        self.description = None
        self.description_error = ''
        self.description_revision = 0
        self.description_pending = False
        cfg = load_api_keys()
        preference = cfg.get('ollama_thinking', 'off')
        self.thinking_preference = preference if thinking_choice(preference) else 'off'
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        self.provider = QComboBox()
        self.provider.addItem('Gemini · Online', 'gemini')
        self.provider.addItem('Ollama · Offline', 'ollama')
        self.provider.setCurrentIndex(self.provider.findData(provider(cfg)))
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText(t('Bo‘sh qoldirilsa saqlangan kalit ishlatiladi.'))
        self.url = QLineEdit(str(cfg.get('ollama_url', Settings.url)))
        self.model = QComboBox()
        self.model.setProperty('brave_literal_text', True)
        self.model.setEditable(True)
        self.model.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.model.completer().setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.model.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        self.model.completer().setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.model.setEditText(str(cfg.get('ollama_model', cfg.get('llm_model', Settings.model))))
        self.profile = QComboBox()
        for title, value in [('Avtomatik', 'auto'), ('Tejamkor', 'economy'), ('Muvozanatli', 'balanced'), ('Sifat', 'quality')]:
            self.profile.addItem(t(title), value)
        self.profile.setCurrentIndex(max(0, self.profile.findData(cfg.get('ollama_profile', 'auto'))))
        self.local_widgets = []
        for title, widget in [('Ulanish turi', self.provider), ('Gemini API kaliti', self.key),
                              ('Ollama manzili', self.url), ('Lokal model', self.model),
                              ('Resurs profili', self.profile)]:
            field = QWidget()
            field_row = QHBoxLayout(field)
            field_row.setContentsMargins(0, 0, 0, 0)
            field_row.setSpacing(16)
            caption = label(title, 10, colors().TEXT, True)
            caption.setBuddy(widget)
            caption.setFixedWidth(132)
            caption.setWordWrap(True)
            field_row.addWidget(caption)
            widget.setFont(font(10))
            widget.setMinimumHeight(38)
            widget.setAccessibleName(t(title))
            field_row.addWidget(widget, 1)
            if widget is self.model:
                self.recommend_button = QPushButton(t('Tavsiya'))
                self.recommend_button.setAccessibleName(t('Noutbukka mos eng yaxshi modelni tanlash'))
                self.recommend_button.setToolTip(t('Noutbukingiz quvvatiga qarab eng optimal modelni avtomatik tanlaydi'))
                self.recommend_button.setStyleSheet(button_style())
                self.recommend_button.setMinimumHeight(38)
                self.recommend_button.clicked.connect(self.apply_recommended_model)
                field_row.addWidget(self.recommend_button)
                self.refresh_models_button = QPushButton(t('Yangilash'))
                self.refresh_models_button.setAccessibleName(t('Modellar ro‘yxatini yangilash'))
                self.refresh_models_button.setStyleSheet(button_style())
                self.refresh_models_button.setMinimumHeight(38)
                self.refresh_models_button.clicked.connect(self.refresh_models)
                field_row.addWidget(self.refresh_models_button)
                self.download_button=QPushButton(t('Yuklash'))
                self.download_button.setStyleSheet(button_style());self.download_button.setMinimumHeight(38)
                self.download_button.clicked.connect(lambda:__import__('brave_model_download').open_download(
                    self, initial_model=getattr(self, 'suggested_download', None)))
                field_row.addWidget(self.download_button)
            layout.addWidget(field)
            if widget is self.key:
                self.key_row = field
            elif widget is not self.provider:
                self.local_widgets.append(field)
            if widget is self.model:
                self.model_info = label('O‘rnatilgan modelni ro‘yxatdan tanlang yoki nomini yozing.', 9, colors().TEXT_DIM)
                self.model_info.setWordWrap(True)
                self.model_info.setTextFormat(Qt.TextFormat.PlainText)
                layout.addWidget(self.model_info)
                self.local_widgets.append(self.model_info)
        self.resource_info = label('', 9, colors().TEXT_DIM)
        self.resource_info.setWordWrap(True)
        self.resource_info.setTextFormat(Qt.TextFormat.PlainText)
        self.resource_info.setProperty('brave_literal_text', True)
        layout.addWidget(self.resource_info)
        self.hardware_rec = label('', 9, colors().TEXT_MED)
        self.hardware_rec.setWordWrap(True)
        self.hardware_rec.setTextFormat(Qt.TextFormat.PlainText)
        self.hardware_rec.setProperty('brave_literal_text', True)
        layout.addWidget(self.hardware_rec)
        self.thinking_row = QWidget()
        thinking_layout = QHBoxLayout(self.thinking_row)
        thinking_layout.setContentsMargins(0, 0, 0, 0)
        thinking_label = label('Fikrlash rejimi', 10, colors().TEXT, True)
        thinking_label.setFixedWidth(132)
        thinking_layout.addWidget(thinking_label)
        self.thinking = QComboBox()
        self.thinking.setFont(font(10))
        self.thinking.setMinimumHeight(38)
        self.thinking.setAccessibleName(t('Fikrlash rejimi'))
        thinking_label.setBuddy(self.thinking)
        thinking_layout.addWidget(self.thinking, 1)
        layout.addWidget(self.thinking_row)
        self.local_widgets.append(self.thinking_row)
        self.autostart = QCheckBox(t('Ollama’ni avtomatik ishga tushirish'))
        self.autostart.setFont(font(10))
        self.autostart.setAccessibleName(t('Ollama’ni avtomatik ishga tushirish'))
        self.autostart.setToolTip(t('Standart localhost:11434 uchun. Boshqa manzildagi server qo‘lda boshqariladi.'))
        self.autostart.setChecked(cfg.get('ollama_autostart', True) is True)
        layout.addWidget(self.autostart)
        self.local_widgets.extend([self.resource_info, self.hardware_rec, self.autostart])
        self.local_tools=QCheckBox(t('Lokal hisoblash va manba qidirish vositalari'))
        self.local_tools.setChecked(bool(cfg.get('local_tools_enabled')))
        layout.addWidget(self.local_tools);self.local_widgets.append(self.local_tools)
        studio = QPushButton(t('AI Studio'))
        studio.setStyleSheet(button_style());studio.setMinimumHeight(36)
        studio.clicked.connect(lambda:__import__('brave_ai_studio').open_studio(self.win))
        layout.addWidget(studio);self.local_widgets.append(studio)
        advanced=QPushButton(t('Lokal AI imkoniyatlari…'))
        advanced.setStyleSheet(button_style());advanced.setMinimumHeight(36)
        advanced.clicked.connect(lambda:__import__('brave_local_lab').open_lab(self.win if hasattr(self,'win') else self.window(), self))
        layout.addWidget(advanced);self.local_widgets.append(advanced)
        self.hint = label('Tejamkor — kam xotira. Muvozanatli — kundalik ish. Sifat — uzunroq kontekst va javob.', 9, colors().TEXT_DIM)
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        note = label('Ollama chat, hujjat va ruxsat etilgan offline amallar uchun. AI Studio’da qo‘shimcha imkoniyatlar bor.', 9, colors().TEXT_DIM)
        note.setWordWrap(True)
        layout.addWidget(note)
        note2 = label('Tejamkor profil javobdan keyin modelni bo‘shatadi; qolgan profillar 5 va 10 daqiqa saqlaydi.', 9, colors().TEXT_DIM)
        note2.setWordWrap(True)
        self.retention_note = note2
        layout.addWidget(note2)
        self.local_widgets.extend([self.hint, note, note2])
        self.status = label('', 9, colors().TEXT_MED)
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.status)
        row = QHBoxLayout()
        self.check = QPushButton(t('Ulanishni tekshirish'))
        self.unload = QPushButton(t('Modelni bo‘shatish'))
        self.save = QPushButton(t('Saqlash'))
        for button, callback in [(self.check, lambda: self.probe(False)),
                                 (self.unload, lambda: self.probe(True)), (self.save, self.apply)]:
            button.setStyleSheet(button_style())
            button.setMinimumHeight(36)
            button.clicked.connect(callback)
            row.addWidget(button)
        layout.addLayout(row)
        self.provider.currentIndexChanged.connect(self.sync)
        self.description_timer = QTimer(self)
        self.description_timer.setSingleShot(True)
        self.description_timer.timeout.connect(self.describe_model)
        self.model.editTextChanged.connect(self.selection_changed)
        self.thinking.currentIndexChanged.connect(self.thinking_changed)
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setSingleShot(True)
        self.refresh_timer.timeout.connect(self.refresh_models)
        self.url.textChanged.connect(self.address_changed)
        self.url.textEdited.connect(lambda: self.refresh_timer.start(400))
        self.checked.connect(self.present)
        self.resourcesReady.connect(self.resources_sampled)
        self.described.connect(self.model_described)
        self.profile.currentIndexChanged.connect(self.sync)
        self.sync()

    def values(self):
        controls = self.description and any(v is not False for v in self.description['thinking_values'])
        choice = self.thinking.currentData() if controls else self.thinking_preference
        return Settings(local_url(self.url.text()), local_model(self.model.currentText()), self.profile.currentData(), self.autostart.isChecked(), choice or 'auto')

    def sync(self):
        local = self.provider.currentData() == 'ollama'
        for widget in self.local_widgets:
            widget.setVisible(local)
        self.key_row.setVisible(not local)
        self.check.setVisible(local)
        self.unload.setVisible(local)
        self.resource_info.setVisible(local and self.profile.currentData() == 'auto')
        self.retention_note.setVisible(local and self.profile.currentData() != 'auto')
        self.thinking_row.setVisible(local and bool(self.description and any(v is not False for v in self.description['thinking_values'])))
        self.hint.setText(t('Avtomatik bo‘sh RAM va GPU xotirasiga qarab Tejamkor yoki Muvozanatli profilini tanlaydi. Sifat qo‘lda tanlanadi.' if self.profile.currentData() == 'auto' else
                            'Tejamkor — kam xotira. Muvozanatli — kundalik ish. Sifat — uzunroq kontekst va javob.'))
        for widget in (self.url, self.model, self.profile):
            widget.setEnabled(local)
        self.key.setEnabled(not local)
        self.check.setEnabled(local and not self.busy)
        self.recommend_button.setEnabled(local and not self.busy)
        self.refresh_models_button.setEnabled(local and not self.busy)
        runtime = getattr(self.win, '_local_chat', None)
        self.unload.setEnabled(local and not self.busy and not (runtime and runtime.busy))
        self.layout().invalidate()
        self.layout().activate()
        self.setMinimumHeight(self.layout().sizeHint().height())
        self.show_resources()
        if local and self.profile.currentData() == 'auto' and self.resources is None and not self.sampling:
            self.sampling = True
            def sample():
                result = sample_resources(probe_hardware=True)
                try:
                    self.resourcesReady.emit(result)
                except RuntimeError:
                    pass
            threading.Thread(target=sample, daemon=True, name='brave-resource-check').start()
        if local and not self.busy:
            try:
                url = local_url(self.url.text())
                if url != self.catalog_requested and not self.refresh_timer.isActive():
                    self.refresh_timer.start(0)
            except ValueError:
                pass

    def resources_sampled(self, resources):
        self.resources = resources
        self.sampling = False
        self.show_resources()

    def show_resources(self):
        self.autostart.setText(t('Ollama’ni avtomatik ishga tushirish'))
        if self.resources is None:
            self.resource_info.setText(t('Resurslar tekshirilmoqda…'))
            self.hardware_rec.setText('')
            return
        profile = t('Tejamkor' if suggested_profile(self.resources) == 'economy' else 'Muvozanatli')
        parts = [t('Tavsiya etilgan profil')+': '+profile]
        if self.resources.ram_free is not None:
            parts.append(t('Bo‘sh RAM')+f': {self.resources.ram_free/GIB:.1f} GB')
        if self.resources.gpu_free is not None:
            parts.append(t('Bo‘sh GPU xotirasi')+f': {self.resources.gpu_free/GIB:.1f} GB')
        self.resource_info.setText(' · '.join(parts))
        if hasattr(self, 'hardware_rec'):
            rec_text = hardware_recommendation_text(self.resources)
            self.hardware_rec.setText(rec_text)

    def apply_recommended_model(self):
        """Auto-detect notebook hardware and select the best installed model."""
        if self.busy:
            return
        from core.model_recommender import pick_best_for_hardware, suggest_downloads
        res = self.resources or sample_hardware()
        if self.resources is None:
            self.resources = res
            self.show_resources()
        if self.catalog:
            best = pick_best_for_hardware(list(self.catalog.values()), res)
            if best:
                self.model.setEditText(best['name'])
                self.status.setText(t('Noutbuk uchun eng mos model tanlandi')+f": {best['name']} · {best['badge']}\n"+
                                    t('Saqlashni bosing.'))
                return
        # Never put an uninstalled model into the field: saving it would break offline chat.
        suggestions = [row for row in suggest_downloads(res)
                       if row['name'] not in self.catalog and row['name']+':latest' not in self.catalog]
        if suggestions:
            top = suggestions[0]
            self.suggested_download = top['name']
            self.status.setText(t('O‘rnatilgan modellar orasida mosi topilmadi. Tavsiya')+
                                f": {top['display']} ({top['size_str']}) — {top['reason']}\n"+
                                t('Uni o‘rnatish uchun “Yuklash” tugmasini bosing (internet bir marta kerak).'))
        else:
            self.status.setText(t('Ollama bilan ulanib modellar ro‘yxatini tekshiring.'))

    def dispose(self):
        self.stopped.set()
        self.refresh_timer.stop()
        self.description_timer.stop()
        self.description_revision += 1

    def thinking_changed(self):
        self.thinking_preference = self.thinking.currentData() or 'auto'

    def selection_changed(self):
        self.description_revision += 1
        self.description_key = None
        self.description = None
        self.description_error = ''
        self.description_timer.start(300)
        self.thinking_row.hide()
        self.show_model_info()

    def describe_model(self):
        if self.stopped.is_set() or self.provider.currentData() != 'ollama':
            return
        try:
            settings = self.values()
        except ValueError:
            return
        key = (settings.url, settings.model)
        if key == self.description_key:
            return
        if self.description_pending:
            self.description_timer.start(300)
            return
        self.description_pending = True
        revision = self.description_revision
        def work():
            client = OllamaClient(settings)
            info, error = None, ''
            try:
                info = client.describe()
            except Exception as exc:
                error = str(exc) if isinstance(exc, (ValueError, RuntimeError)) else ''
            finally:
                client.close()
            try:
                self.described.emit((revision, key, info, error))
            except RuntimeError:
                pass
        threading.Thread(target=work, daemon=True, name='brave-model-info').start()

    def model_described(self, result):
        self.description_pending = False
        revision, key, info, error = result
        if self.stopped.is_set() or revision != self.description_revision:
            return
        self.description_key, self.description, self.description_error = key, info, error
        self.show_model_info()
        self.sync()

    def show_model_info(self):
        name = self.model.currentText().strip()
        row = self.catalog.get(name) or self.catalog.get(name+':latest')
        if row and self.catalog_url == self.url.text().strip().rstrip('/'):
            self.model_info.setProperty('brave_literal_text', True)
            details = [f'{t("Disk")}: {row["size"]/1024**3:.1f} GB' if row['size'] else '',
                       row['parameters'], row['quantization']]
            desc_text = ' · '.join(value for value in details if value) or name
            if self.resources:
                from core.model_recommender import model_fit_details
                fit = model_fit_details(name, row.get('size', 0), self.resources)
                desc_text += f"\n{fit['badge']} — {fit['reason']}"
            self.model_info.setText(desc_text)
        else:
            self.model_info.setProperty('brave_literal_text', False)
            self.model_info.setText(t('O‘rnatilgan modelni ro‘yxatdan tanlang yoki nomini yozing.'))
        if self.description:
            caps = self.description['capabilities']
            names = {'completion': 'Matnli chat', 'thinking': 'Fikrlash', 'vision': 'Rasm',
                     'tools': 'Amallar', 'embedding': 'Embedding'}
            detail = ' · '.join(t(names.get(value, value)) for value in caps or [] if value in names)
            if not detail:
                detail = t('Model imkoniyatlari noma’lum.')
            if self.description.get('context_length'):
                detail += ' · '+t('Maksimal kontekst')+f': {self.description["context_length"]:,}'
            if caps and 'completion' not in caps:
                detail += '\n'+t('Bu model matnli chatni qo‘llamaydi. Chat modelini tanlang.')
            self.model_info.setProperty('brave_literal_text', True)
            self.model_info.setText(self.model_info.text()+'\n'+detail)
            self.thinking.blockSignals(True)
            self.thinking.clear()
            self.thinking.addItem(t('Model standarti'), 'auto')
            for value in self.description['thinking_values']:
                title, key = ('O‘chiq', 'off') if value is False else ('Yoqilgan', 'on') if value is True else (value, value)
                self.thinking.addItem(t(title), key)
            index = self.thinking.findData(self.thinking_preference)
            self.thinking.setCurrentIndex(max(0, index))
            self.thinking.blockSignals(False)
        elif self.description_error:
            self.model_info.setText(self.model_info.text()+'\n'+t(self.description_error))

    def address_changed(self):
        self.selection_changed()
        if self.url.text().strip().rstrip('/') != self.catalog_url:
            self.catalog, self.catalog_url = {}, None
            current = self.model.currentText()
            self.model.blockSignals(True)
            self.model.clear()
            self.model.setEditText(current)
            self.model.blockSignals(False)
        self.show_model_info()

    def refresh_models(self):
        if self.busy or self.provider.currentData() != 'ollama':
            return
        try:
            settings = Settings(url=local_url(self.url.text()), autostart=self.autostart.isChecked())
        except ValueError as exc:
            self.status.setText(t(str(exc)))
            return
        self.run_check(settings, 'list')

    def apply(self):
        was_started = bool(getattr(self.win, '_runtime_started', False))
        try:
            selected = self.provider.currentData()
            key = self.key.text().strip()
            manager=getattr(self.win,'_backend_manager',None)
            transition=selected!=self.win._active_provider or (selected=='gemini' and bool(key))
            if manager and was_started and transition and not manager.can_switch():
                raise ValueError('Avval joriy javob tugashini kuting.')
            if selected == 'gemini' and not (key or load_api_keys().get('gemini_api_key')):
                raise ValueError('Gemini API kalitini kiriting.')
            # Disabled Ollama fields must not prevent saving a valid Gemini key.
            settings = self.values() if selected == 'ollama' else Settings()
            if selected == 'ollama':
                if self.description:
                    require_chat(self.description)
                settings.save(selected)
            else:
                import platform
                os_name = load_api_keys().get('os_system') or {'Windows': 'windows', 'Darwin': 'mac'}.get(platform.system(), 'linux')
                _patch_config(chat_provider=selected, os_system=os_name,
                              **({'gemini_api_key': key} if key else {}))
            self.key.clear()
            _patch_config(local_tools_enabled=self.local_tools.isChecked())
        except (ValueError, OSError) as exc:
            self.status.setText(t(str(exc)) if isinstance(exc, ValueError) else t('Sozlamalarni saqlab bo‘lmadi.'))
            return
        if not getattr(self.win, '_runtime_started', False):
            self.win._active_provider = selected
            self.win._ready = True
            if self.win._overlay:
                self.win._overlay.hide()
                self.win._overlay = None
        runtime = getattr(self.win, '_local_chat', None)
        if runtime is not None:
            runtime.apply_profile()
        restart = was_started and (selected != getattr(self.win, '_active_provider', selected) or (selected == 'gemini' and bool(key)))
        if restart and manager:
            if manager.switch(selected,refresh=selected=='gemini' and bool(key)):
                self.status.setText(t('Rejim almashtirilmoqda. Qoralama va tarix saqlanadi.'))
                return
        self.status.setText(t('Saqlandi. Rejimni almashtirish uchun Brave’ni qayta oching.' if restart else 'Sozlamalar saqlandi.'))
        if restart:
            self.win._log.append_log('SYS: '+t('Saqlandi. Rejimni almashtirish uchun Brave’ni qayta oching.'))
        if selected == 'ollama' and settings.autostart and not self.busy:
            self.catalog_requested = None
            self.sync()

    def probe(self, unload):
        if self.busy:
            return
        runtime = getattr(self.win, '_local_chat', None)
        if unload and runtime and runtime.busy:
            self.status.setText(t('Avval joriy javob tugashini kuting.'))
            return
        try:
            settings = self.values()
        except ValueError as exc:
            self.status.setText(t(str(exc)))
            return
        self.run_check(settings, 'unload' if unload else 'verify')

    def run_check(self, settings, mode):
        self.refresh_timer.stop()
        self.busy = True
        if mode != 'unload':
            self.catalog_requested = settings.url
        self.sync()
        self.status.setText(t('Modellar ro‘yxati yuklanmoqda…' if mode == 'list' else 'Tekshirilmoqda…'))
        def work():
            client = OllamaClient(settings)
            models, error = [], ''
            try:
                if mode != 'unload' and settings.autostart:
                    if not ensure_server(settings.url, cancelled=self.stopped):
                        return
                if self.stopped.is_set():
                    return
                if mode == 'unload':
                    client.unload()
                else:
                    models = client.catalog()
                    if mode == 'verify':
                        client.verify()
            except (RuntimeError, ValueError) as exc:
                error = str(exc)
            except Exception:
                error = 'Ollama javobi uzildi. Qayta urinib ko‘ring.'
            finally:
                client.close()
            try:
                self.checked.emit((settings, mode, models, error))
            except RuntimeError:
                pass  # Settings closed while the check was in flight.
        threading.Thread(target=work, daemon=True, name='brave-ollama-check').start()

    def present(self, result):
        self.busy = False
        self.sync()
        settings, mode, models, error = result
        if self.provider.currentData() != 'ollama':
            self.status.clear()
            return
        try:
            if settings.url != local_url(self.url.text()) or (mode != 'list' and settings != self.values()):
                self.status.clear()
                return
        except ValueError:
            return
        if mode != 'unload' and (not error or models):
            current = self.model.currentText().strip()
            self.catalog = {row['name']: row for row in models}
            self.catalog_url = settings.url
            self.model.blockSignals(True)
            self.model.clear()
            for row in models:
                self.model.addItem(row['name'])
            if current not in self.catalog and current+':latest' in self.catalog:
                current += ':latest'
            index = self.model.findText(current)
            self.model.setCurrentIndex(index)
            if index < 0:
                self.model.setEditText(current)
            self.model.blockSignals(False)
            self.description_revision += 1
            self.description_key = None
            self.description = None
            self.description_error = ''
            self.thinking_row.hide()
            self.show_model_info()
            self.description_timer.start(0)
        self.status.setText(t(error) if error else t(
            'Model xotiradan bo‘shatildi.' if mode == 'unload' else
            ('Modellar ro‘yxati yangilandi. Tanlang va Saqlashni bosing.' if models else
             'Lokal model topilmadi. Avval uni Ollama orqali yuklang.') if mode == 'list' else
            'Ollama ulandi. Lokal model tayyor.'))
