# Brave xavfsizlik tekshiruvi

Sana: 2026-10-13. Mahalliy manba kod va o'rnatilgan Python kutubxonalari tekshirildi.

## Xulosa

Tekshirilgan kodda muallifning noma'lum serveriga kalit, fayl yoki ovozni yashirin yuboruvchi aniq mexanizm topilmadi. Bu dastur oflayn emas: asosiy yordamchi Google Gemini xizmatidan foydalanadi. Statik tekshiruv barcha kelajakdagi model buyruqlari, yuklab olinadigan plaginlar va kutubxonalar xavfsizligini kafolatlamaydi.

## Ma'lumot qayerga boradi

| Xizmat / manzil | Yuboriladigan ma'lumot va shart |
| --- | --- |
| Google Gemini, `google-genai` SDK | Suhbat matni, mikrofon ovozi, tizim promptiga qo'shilgan xotira; vazifaga qarab ekran/kamera rasmi, tahlil qilinadigan hujjat yoki kod. `main.py`, `core/gemini.py`, `actions/file_processor.py`. |
| Qidiruv xizmatlari | Qidiruv so'rovi va tanlangan sahifalar; Gemini qidiruvi yoki DDGS, shuningdek Google/Bing/DuckDuckGo/Yandex brauzer qidiruvi. `actions/web_search.py`, `actions/browser_control.py`. |
| YouTube / Steam | Video/qidiruv so'rovlari va o'yin nomlari, tegishli funksiyalar ishlatilganda. `actions/youtube_video.py`, `actions/video_player.py`, `actions/game_updater.py`. |
| Ochilgan saytlar va xabar xizmatlari | Brauzer avtomatlashtirish orqali saytdagi amallar va so'ralgan xabarlar. Model boshqaradigan brauzer istalgan manzilga o'tishi mumkin. |
| ElevenLabs / Edge TTS | Muqobil `core/tts.py` dvigatellari ishlatilsa, ovozga aylantiriladigan matn. Asosiy `main.py` ovozli sessiyasi Gemini'da ishlaydi. |
| Mahalliy Ollama / mos server | `core/llm_client.py` odatda `localhost:11434` bilan ishlaydi, ammo `llm_url` o'zgartirilsa boshqa serverga yuboradi. Asosiy `main.py` bundan foydalanmaydi. |
| PyPI / paket va brauzer yuklash manzillari | O'rnatish va ixtiyoriy qo'shimchalarni yuklash so'rovlari. Kutubxona zaiflik auditi paket nomlari/versiyalarini audit xizmatiga yuboradi. |
| cdnjs | Telefon panelida mahalliy CryptoJS fayli yo'q bo'lsa, skript CDN'dan olinadi. Hozir mahalliy fayl bor; panel standart holatda o'chirilgan. |

## Tuzatilgan joylar

- Telefon paneli oldin avtomatik ochilar, `0.0.0.0` manzilida tinglar va firewall ruxsatini o'zgartirishga urinar edi. Endi `config/api_keys.json` ichida `"dashboard_enabled": true` aniq yozilmaguncha panel import qilinmaydi va ishga tushmaydi.
- Mikrofon oldin standart holatda doimiy uzatishga tayyor edi. Endi push-to-talk standart holatda yoqilgan: `Ctrl+Space` bosib turilganda ovoz yuboriladi. Sozlamada foydalanuvchi buni o'chirishi mumkin; bu rejim matn, xotira yoki boshqa vositalarning so'rovlarini to'smaydi.
- `.gitignore` ichidagi fayl nomidan keyingi izohlar Git tomonidan izoh emas, patternning qismi deb qabul qilinar edi. Izohlar alohida qatorga ko'chirildi; API kalitlar, sertifikatlar, OAuth va WhatsApp sessiyalari haqiqiy Git tekshiruvi bilan himoyalandi.
- Kutubxona auditi `cryptography 49.0.0` va `PyPDF2 3.0.1`da 2 ta alohida ma'lum zaiflikni ko'rsatdi (cryptography yozuvi auditda ikki marta takrorlangan). `cryptography 50.0.2`ga yangilandi; eski PyPDF2 olib tashlanib, PDF fallback `pypdf 6.20.1`ga o'tkazildi. Talablar fayli ham yangilandi. Manbalar: [cryptography advisory](https://github.com/pyca/cryptography/security/advisories/GHSA-g6cj-pr64-35w5), [PDF advisory](https://github.com/py-pdf/pypdf/security/advisories/GHSA-4vvm-4w3v-6mr8).

## Qolgan muhim cheklovlar

- API kalit va plagin tokenlari `config/api_keys.json` ichida shifrlanmagan holda saqlanadi. Loyiha OneDrive papkasida: sinxronlash yoqilgan bo'lsa, bu fayl va xotira Microsoft bulutiga ham ko'chishi mumkin. Git ignore OneDrive sinxronlashini to'xtatmaydi.
- `actions/desktop.py` model yaratgan Python kodini `exec` orqali bajaradi; undagi Path/ctypes kabi obyektlar haqiqiy xavfsizlik sandboxi emas. `code_helper` va `dev_agent` ham kod va jarayonlar ishga tushira oladi. Zararli sayt yoki hujjatdagi ko'rsatmalar modelni chalg'itishi mumkin.
- `plugins/` ichidagi yangi Python fayllari tekshirishdan oldin import qilinadi. Hozir bu papkada faqat `__init__.py` va `_template.py` bor, faol tashqi plagin yo'q. Keyinchalik qo'shilgan plaginlar alohida audit talab qiladi.
- To'liq Gemini suhbatini sinash API kalitni talab qiladi. Hech qanday kalit kiritilmadi, haqiqiy shaxsiy hujjat/ovoz tashqi xizmatga sinov uchun yuborilmadi.

## Tekshiruvlar

- 49 Python fayli sintaktik tahlildan o'tdi.
- Standart push-to-talk, standart o'chirilgan panel, panelning faqat boolean `true` bilan yoqilishi tekshirildi.
- Panel importi va serverni ishga tushirish kodi opt-in sharti ichida ekanligi tekshirildi.
- Vaqtinchalik Git repository orqali 6 turdagi maxfiy fayl uchun `git check-ignore` muvaffaqiyatli o'tdi.
- Qayta `pip-audit`: 122 paket, ma'lum zaifliklar 0, o'tkazib yuborilgan paketlar 0. Natija: `logs/dependency-audit.json`. Bu malware auditi yoki noma'lum zaifliklar yo'qligi kafolati emas.
- `uv pip check`: o'rnatilgan paketlar o'zaro mos.
- PDF fallback bo'sh sahifani xatosiz o'qishi va yangilangan cryptography bilan panelning AES encrypt/decrypt mosligi tekshirildi.
- API kalitsiz dastlabki oyna tarmoq ulanishi, port ochish va child-process ishga tushirishni bloklovchi Python audit hook bilan tekshirildi. Setup oynasi ko'rindi; bloklanadigan hodisalar umuman kuzatilmadi. Yangilashdan keyin ham sinov o'tdi. Bu natija faqat dastlabki API-kalitsiz holatga tegishli.
- SDK'da yakuniy Gemini manzili `https://generativelanguage.googleapis.com/` ekanligi kalitsiz client yaratib tekshirildi; haqiqiy API so'rovi yuborilmadi.
- Dastur `start.ps1` orqali ishga tushirildi. To'liq suhbat API kalit kiritilmagani sababli tekshirilmagan. Playwright brauzer binarlari o'rnatilmadi, brauzer avtomatlashtirish uchun qo'shimcha `python -m playwright install chromium firefox` kerak bo'lishi mumkin.

## Ishga tushirish

Loyiha papkasida PowerShell orqali `./start.ps1` ishlating. Yoki `.venv/Scripts/python.exe main.py`.
API kalitni faqat dastur oynasiga kiriting. Dastur loglari `logs/` papkasida saqlanadi.

## Keyingi mahalliy o'zgarishlar

Foydalanuvchi test uchun avtomatik tinglashni tanladi; shu sababli hozir push-to-talk o'chirilgan. Real suhbatda nutq tanilishi va ovozli javob foydalanuvchi tomonidan tasdiqlandi.

UI Brave nomi bilan qayta ishlangan. EN/UZ/RU tarjimalari mahalliy lug'atdan olinadi, dark/light tema va ovozga mos inson portreti qo'shilgan. Dizayn uchun yangi tashqi xizmat yoki yangi Python kutubxonasi ishlatilmagan. Suhbat, audio va qurilmalar bilan ishlovchi asosiy yo'llar saqlangan. UI tarjimasi suhbat mazmunini tarjima xizmatiga yubormaydi. Remote dashboard opt-in himoyasi saqlangan.
# Brave Center update

The new local access policy is checked before tool execution. Ask/smart modes require human approval for their applicable actions; Full access and Turbo intentionally authorize automatic execution, including irreversible actions. Approval cannot be supplied through a model-written `confirmed` argument. A trusted approval scope avoids duplicate confirmation inside an already approved tool. Individual grants apply to assistant tool dispatch; they are not an OS sandbox and do not isolate generated Python/shell code or installed plugin imports. In-flight actions may finish after a permission change.

Internet-off prevents new Live connections and central Gemini helper calls; microphone-off stops streaming and opening the assistant microphone stream. Action audits contain names/decisions, not raw arguments. Project auto-context excludes common secret files and redacts recognizable credentials, but remains heuristic. Only explicit project sends transmit selected content to Gemini. Reminders are local scheduled tasks with unique identifiers; cancellation accepts only Brave reminder names. The Windows scheduler test created and removed its own future test job without firing a notification.

# Companion feature update

Multiple selected attachments share a bounded text budget and a 50 MB total input limit, retaining per-file secret checks and explicit-send permission gates. Project profiles are local snapshots, and applying one can intentionally change the active permission policy and routines. Profile application sends no file content by itself.

The file-control write/create-overwrite handlers capture exact pre-write backups locally. Recovery and Undo verify the current file hash against the post-write hash and reject intervening edits. Persistent restore also refuses changed symlink paths. These backups are plain local document copies, not encrypted; the Recovery UI provides deletion. Generated code and other file-producing tools are outside this backup integration.

Voice calibration samples only normalized microphone levels through the existing audio stream. Both microphone capture dispatch and the realtime network sender suppress microphone uploads during calibration; the wizard does not store PCM. Usage counters contain byte totals and request counts only. Search provenance uses actual provider grounding URLs plus retrieval time, and does not claim independent verification.

Attachment preview uses the same local content preparation as chat attachments and makes no provider call. Explicit sends recheck permissions and cancellation after reading. Both the UI and runtime reserve one active text request, preventing overlapping sends. The response watchdog excludes active tools and audible playback; after 120 seconds of no server content progress it reconnects with a fresh resumption state, without resending the uncertain request. Task retry still requires explicit human send.

Attachment selection no longer starts a network request. An explicit chat send reads the captured attachment path and sends supported text/image content to Gemini, after checking file and network permissions. Image export removes EXIF; text redacts recognizable credential assignments and rejects private keys and common secret filenames. These checks do not guarantee removal of every secret, especially in images. Extracted text is bounded and labeled as reference data. PDF/DOCX/XLSX parsing is local and uses the existing installed libraries.

Named routines are locally saved user instructions for the existing Gemini/tool pipeline; they retain all runtime permission and approval gates. No schedule or automatic execution is created by saving a routine. Task retry prepares a draft for human review and never automatically repeats uncertain external actions. Task requests and replies contain conversation data, are local under `%LOCALAPPDATA%\Brave`, and can be deleted in Tasks. Memory edits use a shared lock and atomic replacement; concurrent normal memory updates use the same lock.

