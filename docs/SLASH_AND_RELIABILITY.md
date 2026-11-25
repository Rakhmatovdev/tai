# Slash menyu va barqarorlik yangilanishi

Chatning yozish maydonida **/** yozing. Ro‘yxat buyruq nomi va UZ/EN/RU tavsifi bo‘yicha qidiriladi. **↑↓** tanlaydi, **Tab/Enter** buyruqni maydonga qo‘yadi; so‘ng matn yozib yuboring. Sichqoncha bilan ham tanlash mumkin. **Esc** menyuni yopadi, **Shift+Enter** yangi qator kiritadi. Noma’lum buyruq yuborilmaydi va qoralama saqlanadi. Menyu UZ/EN/RU va uch mavzuda ishlaydi. Keyingi yangilanish ro‘yxatni **60 ta** buyruqqa kengaytirdi, toifa, saralanganlar, oxirgi ishlatilganlar va shaxsiy shablonlarni qo‘shdi: [to‘liq joriy qo‘llanma](COMMAND_LIBRARY.md).

## Buyruqlar

| Buyruq | Ishlashi |
| --- | --- |
| `/plan topshiriq` | Bosqichli reja; vositalarni ishga tushirmaydi |
| `/think savol` | O‘rnatilgan thinking modelini tanlaydi, Quality konteksti va alohida 4096-token generatsiya limiti |
| `/fast savol` | Yengilroq/tezligi o‘lchangan model; 2048 kontekst, 256 chiqish limiti, 5 daqiqa retention; yashirin history-summary kutilmaydi |
| `/translate en matn` | Ko‘rsatilgan tilga tarjima; masalan `/translate uz Hello` yoki `/translate ru Salom` |
| `/totext` | Fayldan matn oynasi: audio, rasm/OCR, PDF, DOCX va matn. Natija tekshiriladi, nusxalanadi yoki qoralamaga qo‘yiladi |
| `/summarize matn` | Asosiy fakt va raqamlar xulosasi |
| `/explain matn` | Sodda tushuntirish |
| `/rewrite matn` | Ma’noni saqlab imlo va ifodani yaxshilash |
| `/code topshiriq` | O‘rnatilgan kod modelini tanlab kod bo‘yicha yordam; avtomatik bajarish yo‘q |
| `/vision savol` | Biriktirilgan rasm uchun Vision rejimini tanlaydi; avvalgi rasm xotirasi ham ishlaydi |
| `/screen` | Ekran tahlili, kesish va maxfiy hududlarni yopish |
| `/meeting` | Uchrashuv va tiklanadigan qoralamalar |
| `/review` | Kod/Git tahlili, bir yoki bir nechta fayl diff’i |
| `/test` | Test bajarish oynasi |
| `/models` | Model tanlash, o‘lchovlar va routing sozlamalari |
| `/benchmark` | Mavjud Cold/Warm model taqqoslash oynasi |
| `/voice` | Offline ovoz sozlamalari |
| `/forget` | Faqat shu suhbatning rasm xotirasini unutish |
| `/cancel` | Joriy chat vazifasini to‘xtatish |
| `/help` | To‘liq ro‘yxat va misollar |

Aliaslar: `/quick → /fast`, `/deep → /think`, `/summary → /summarize`, `/ocr`, `/text`, `/transcribe → /totext`, `/stop → /cancel`.

Tarjima til kodlari: uz, en, ru, tr, de, fr, es, ar, zh, ko, ja. Kod ko‘rsatilmasa o‘zbekcha tarjima so‘raladi. Matnsiz translate/summarize/explain/rewrite mavjud matn-amallari oynasini ochadi. Har qanday modelning tarjima sifati tanlangan modelga bog‘liq; kichik model so‘z ma’nosini adashtirishi mumkin.

Fast va Think model rejimlari Ollama uchun. Saqlangan default model, provider va resource profili o‘zgarmaydi; sozlamalar faqat joriy so‘rovga tegishli. Matn rejimlari Gemini’da prompt sifatida ishlaydi; Fast/Think cloud modelining hisoblash rejimini o‘zgartirgandek ko‘rsatilmaydi. Transformatsiya buyruqlari lokal chat vositalarini yoqmaydi. `/totext` lokal o‘qish bo‘lib, Gemini yoki LLM talab qilmaydi; audio uchun o‘rnatilgan Whisper va rasm/skan uchun Tesseract kerak.

Think ichki reasoning matnini ko‘rsatmaydi yoki tarixga saqlamaydi. Server thinking qiymatlarini bildirsa, qo‘llanadigan on/high qiymati tanlanadi; metadata bo‘lmasa thinking modelining default’i ishlatiladi. Alohida kattaroq limit reasoning javob uchun token qoldirmasdan tugab qolish holatini kamaytiradi; cheksiz inference yo‘q. [Ollama thinking controls](https://docs.ollama.com/capabilities/thinking).

## Uchrashuvni saqlash va aniqroq matn

Transkript, til, speaker checkbox, tasdiqlangan hisobot va jonli qaydlar o‘zgargandan 500 ms o‘tib `%LOCALAPPDATA%/Brave/meeting-drafts.json`ga atomik yoziladi. Oxirgi 10 uchrashuv saqlanadi; audio faylga yozilmaydi. Oyna yopilganda ham qoralama saqlanadi. **Saqlangan uchrashuvlar** ichida tiklash, yangi uchrashuv va o‘chirish bor. Tiklash mikrofonni o‘zi yoqmaydi. **Jonli uchrashuvni boshlash** avvalgi transkriptga `[Davom]` segmentini qo‘shadi; yangi segmentning vaqti noldan boshlanadi.

**Til va nutq sozlamalari** ichida:

- **Aniqroq nutq** — beam size 5, 3 soniyadan keyin pauzada bo‘lish, uzluksiz gapda ko‘pi bilan 12 soniyalik qism. Bu odatiy meeting rejimi.
- **Tez nutq** — avvalgi beam size 1 va 8 soniyalik qismlar.
- Speaker modeli va checkbox. Speaker yorliqlari taxminiy qoladi; shaxsni aniqlamaydi.

**Noto‘g‘ri ism yoki raqam → To‘g‘ri shakli → Transkriptda tuzatish** mos butun so‘z/iboralarni almashtiradi, eski xulosani eskirgan deb tozalaydi va qoralamani yangilaydi. Bu audio asosidagi avtomatik fakt tekshirish emas. Whisper va diarizatsiya aniqligi barcha mikrofon, shovqin yoki o‘zbekcha sheva uchun kafolatlanmaydi.

Transkriptdagi raqamlar alohida tekshirish satrida ko‘rsatiladi. Vaqt belgilari va Speaker ID raqamlariga oddiy raqam almashtirishi tegmaydi; speaker nomini o‘zgartirish uchun `Speaker 1` kabi to‘liq yorliqni kiriting. Jonli yozuv davomida asosiy chat va boshqa katta AI tahlillari kutadi; matn qoralamada qoladi. Jonli vazifa qaydlari uchun alohida so‘rovning 30 s limiti bor, shunda nutq navbati uzoq inference ortida qolmaydi.

## Ekran hududi va oldindan model yuklash

Ekran rasmi olingach **Kesish / maxfiy joylarni yopish**ni bosing. Hududni belgilang, Crop yoki Redact tanlang. Redact hududni to‘liq qora rangga bo‘yaydi. **Tayyor** bosilganda qolgan belgilash ham qo‘llanadi; yangilangan rasm asosiy preview’da ko‘rinadi. Qaytarish oxirgi uch tahrirni saqlaydi. Rasm RAM’da; yuboriladigan tasvir PNG, eng katta tomoni 2048 px. Maskalanmagan eski rasm tahlilga berilmaydi.

**Vision modelini oldindan tayyorlash** faqat o‘rnatilgan Vision modelini `/api/generate` orqali promptsiz yuklaydi va 5 daqiqa ushlab turadi. Matn generatsiyasi, model download yoki cloud fallback qilmaydi. Sovuq yuklanish shu tugmada kutib olinadi; keyingi so‘rov tezligi model, xotira va Ollama residency’siga bog‘liq.

## Ko‘p faylli tuzatish va test

**Kod tahlili → Bir nechta kod fayli** orqali 1–8 fayl tanlang. AI tuzatishi faqat shu nomlarga tegishli, aniq bir marta uchraydigan SEARCH/REPLACE JSON beradi. Noto‘g‘ri yoki noaniq moslik, yangi yo‘l, tugallanmagan javob qo‘llanmaydi. AI kirishi profilga sig‘ishi kerak. Har fayl uchun qo‘lda diff tahriri ham bor.

Barcha diff’lar alohida tablarda tekshiriladi. **Barcha difflarni tasdiqlab qo‘llash** oldin hamma faylni conflict uchun tekshiradi. Zaxiralar olinadi; yozish xatosida avval yozilgan fayllar tiklanadi. Bu fayl tizimi darajasidagi umumiy atomik transaction emas: tashqi parallel tahrir tiklashni to‘xtatishi mumkin. Guruhni **Oxirgi tuzatishni qaytarish** orqali tiklashdan oldin hamma fayl hash’i tekshiriladi.

Python fayllari apply’dan oldin AST sintaksis tekshiruvidan o‘tadi. AI satr ichidagi bo‘shliqsiz substring’ni almashtirib, yangi satrlarda chekinishni yo‘qotsa, mavjud chekinish bilan sintaktik to‘g‘ri variant tiklanadi va diffda ko‘rsatiladi. Noto‘g‘ri sintaksis yozilmaydi. Bu NameError kabi semantik xatolarni aniqlash yoki test o‘rnini bosmaydi. Backup registriga yozish xatosida ham manbaning oldingi baytlari tiklanadi.

**Test bajarish** yoki `/test`: loyiha papkasi, Python unittest/pytest yoki Node.js test turi, argumentlar va 1–300 s limitni tanlang. Ko‘rsatilgan argv va papkani tasdiqlash checkbox’i kerak. Buyruq/argument/limit o‘zgarsa tasdiq bekor bo‘ladi. Chiqish oqim bilan ko‘rsatiladi; exit code, vaqt va to‘xtash sababi chiqadi. Shell ishlatilmaydi, credential environment qiymatlari uzatilmaydi. Output 200 ming belgi bilan cheklangan. Cancel, timeout yoki files/code/system ruxsati olib tashlansa process tree to‘xtatiladi.

Test loyiha kodi sifatida foydalanuvchi huquqlarida ishlaydi; bu OS sandbox yoki network izolatsiyasi emas. Test o‘z kodida fayl o‘qishi, yozishi yoki internetga murojaat qilishi mumkin. Model taklifi avtomatik bajarilmaydi. Python loyihasining `.venv` muhiti bo‘lsa shu interpreter ishlatiladi. Pytest tashqi plugin auto-load’i o‘chiq. Jarayon API’si: [Qt QProcess reference](https://doc.qt.io/qt-6/qprocess.html), [Python subprocess](https://docs.python.org/3/library/subprocess.html).

## O‘lchangan model tanlovi

Muvaffaqiyatli chat, tahlil va benchmark’dan faqat model, server manzili, profil, vazifa, TTFT, tok/s va residency kabi raqamli metrikalar `model-performance.json`ga saqlanadi. Prompt va javoblar bu registrga kiritilmaydi. 500 yozuv, 30 kunlik yaroqlilik; kamida 2 ta bir xil task/profile/server namuna kerak. Warm namunalar yetarli bo‘lsa alohida olinadi.

Taqqoslash bahosi median `TTFT + 128/tok_s`. Bu 128 tokenlik javob uchun taxminiy vaqt, sifat bahosi emas. Xotiraga mos modellardan o‘lchovi borlari oldinga olinadi; kodda mos coder modellari bo‘lsa ular saqlanadi. O‘lchov yetishmasa avvalgi metadata reytingi ishlaydi. Model jadvali vaqt va namuna sonini ko‘rsatadi. **Tezlikni o‘lchash** mavjud benchmark’ni ochadi; o‘lchovlar fon rejimida yashirin ishga tushirilmaydi.

## Tekshiruv

`tests/test_slash_workflows.py` parser va dropdown klaviatura/sichqoncha amallari, deklaratsiyadagi barcha action dispatch’lari, Fast/Think payload, tarjima, /totext, qoralama tiklash, ko‘p faylli rollback/conflict, crop/redact piksellari, real test subprocess’i, timeout/ruxsatlar va UZ/EN/RU ko‘rinishlarni tekshiradi.

To‘liq regressiya: **283 test — OK, 129.111 s** (`logs/slash-final-tests.log`). Oxirgi shortcut tuzatishidan keyin **30 ta slash-workflow testi — OK, 11.722 s** (`logs/slash-workflows-tests.log`). Esc ochiq slash menyusini yopadi; shu bosishda global chat interrupt’i ishlamaydi. `pip check`: buzilgan bog‘liqlik topilmadi. 54 ta Studio va 45 ta yangi menyu/dialog ko‘rinishi tekshirildi.

Haqiqiy model/OCR/STT natijalari: `logs/slash-real-smoke.json` va `logs/slash-real-run.log`. Sinovlar faqat sun’iy fayl, audio va vaqtinchalik konfiguratsiyada bajariladi; foydalanuvchining modeli va API kalitlari o‘zgartirilmaydi. To‘liq testlar: `logs/slash-final-tests.log`. Preview’lar: `design-preview/slash/`, `design-preview/ai-studio/`. Eski `dist/` EXE qayta yig‘ilmagan; yangilangan manba `start.ps1` orqali ochiladi.

Haqiqiy sinovning tugallangan natijalari:

| Oqim | Kuzatilgan natija |
| --- | --- |
| `/fast` | `llama3.2:latest`, sovuq yuklash bilan 3.78 s; `2+2 → 4` |
| `/plan` | 5.02 s; uch bosqichli reja, tools ishga tushmadi |
| `/translate en …` | 0.31 s; 42 dollar saqlandi. Kichik model ayrim mazmunni qisqartirishi mumkin |
| `/think` | `qwen3.5:9b`, 27.56 s; `17×23 → 391`, yakuniy javob chiqdi |
| `/totext` rasm | Tesseract 0.30 s; Budget 42 / Ali Monday matni olindi |
| `/totext` audio | Sun’iy SAPI nutqidan Monday vazifasi olindi; `Zira` ismi `Zero` deb tanildi (`logs/slash-audio-smoke.json`) |
| Uchrashuv | 27.51 s sun’iy audio 5.02 s processing; 1/2 speaker yorliqlari, saqlash va tiklash ishladi |
| Kod/test | AI taklifida NameError topildi; inson ko‘rib tuzatgach 2 test o‘tdi, ikki bosqichli undo asl fayl baytlarini tikladi |
| Redact | Tanlangan hududning piksellari to‘liq qora bo‘ldi |

Bu tezlik/aniqlikning umumiy benchmark’i emas. Nutq sinovida `$42` bir joyda `$4.2` deb tanildi. Model, ism, raqam va kod sifati to‘liq tuzalgan deb da’vo qilinmaydi: aniqlik rejimi, ko‘rib tuzatish, sintaksis tekshiruvi va test natijalari aynan shu xatolarni boshqarish uchun bor. Mikrofon transporti sun’iy oqimda, STT/OCR/LLM esa haqiqiy lokal modellar bilan tekshirildi.
