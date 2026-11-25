# AI Studio

Keyingi yangilanish ekran tahlili, jonli uchrashuv, gapiruvchi yorliqlari, kodni diff orqali qo‘llash/qaytarish, avtomatik model yo‘naltirish va rasmli suhbatni davom ettirishni qo‘shdi. [Oltita yangi oqim va tekshiruv](AI_EXTENSIONS.md).

AI Studio’ni **Chat → … → AI Studio**, **Sozlamalar → AI modeli → AI Studio** yoki **Ctrl+K → AI Studio** orqali oching. Oyna Default, Light va Hacker mavzularida, o‘zbek, ingliz va rus tillarida ishlaydi. Kichik oynada bo‘limlarni pastga aylantirish mumkin.

## 1. Aqlli model tavsiyasi

**Model tavsiyasi** bo‘limida Matn, Kod yoki Rasm vazifasini tanlab **Tavsiya olish**ni bosing. Faqat saqlangan loopback Ollama serverida o‘rnatilgan dastlabki 32 ta model tekshiriladi. Matn generatsiyasi imkoniyati ijobiy tasdiqlangan modellar olinadi; Rasm vazifasi uchun Vision imkoniyati ham talab qilinadi. Embedding va cloud modellar tavsiya qilinmaydi.

Saralash o‘lchangan sifat benchmark’i emas. Modelning disk hajmi, mavjud resurslar va kodga yo‘naltirilgan nomi hisobga olinadi. Ish xotirasi taxmini `disk × 1.3 + 0.5 GiB`; u GPU umumiy xotirasining 90%idan kichikligi yoki GPU aniqlanmasa mavjud RAM bilan solishtiriladi. Bu modelning real RAM/VRAM sarfi yoki GPU’ga to‘liq joylashish kafolati emas. Jadvaldagi **Disk GiB** diskdagi hajmni bildiradi.

Model faqat **Modelni tanlash** bosilganda saqlanadi va keyingi lokal so‘rovga qo‘llanadi. Provider o‘z-o‘zidan almashmaydi. Tavsiya olish modelni yuklab olmaydi, generatsiya boshlamaydi va preloading qilmaydi. Jarayonni bekor qilish mumkin.

## 2. Offline kompyuter amallari

**Offline amallar** bo‘limida funksiyani yoqing, fayl qidiriladigan papkani tanlang va **Saqlash**ni bosing. Shu bilan lokal tool chaqiruvlari ham yoqiladi. Chat modeli vositalarni qo‘llashi kerak. Modeldan, masalan, “Notepad’ni och” yoki “Ruxsat berilgan papkadan budget nomli fayllarni top” deb so‘rash mumkin. Shu amallarni AI Studio tugmalari bilan ham bajarish mumkin.

Ruxsat etilgan amallar:

- Notepad, Calculator, Paint, File Explorer yoki VS Code’ni ochishni so‘rash; o‘rnatilgan dasturlargina ishlaydi.
- Faqat foydalanuvchi tanlagan papkada fayl **nomlarini** qidirish. Fayl mazmuni o‘qilmaydi; 5000 ta fayl, 20 ta natija va taxminan 3 soniyalik qidiruv chegarasi bor. Yashirin, build va virtual muhit papkalari hamda symlink/junction orqali chiqish tashlab ketiladi. Cheklovga yetish natijada ko‘rsatiladi.
- Lokal CPU/RAM holatini o‘qish.

Dastur ochish har safar tasdiq so‘raydi. “Ask” siyosatida boshqa amallar ham tasdiqlanadi. `system` va `files` ruxsatlari tegishlicha tekshiriladi. Tanlangan ilova qat’iy ro‘yxatdan olinadi; model shell buyruqlari, boshqa dastur yo‘llari yoki argumentlarini uzata olmaydi. Ishga tushirish shell’siz amalga oshiriladi. `launch_requested` dasturga ochilish so‘rovi berilganini bildiradi; oynasi ochilganini tekshirish kafolati emas.

Bekor qilingan yoki muddati tugagan so‘rovga kech berilgan tasdiq amalni boshlamaydi. Tasdiq oynasi bekor qilishda yopiladi. Model oddiy matnda function-call JSON chiqarsa, u bajarilmaydi va mos model tanlash haqida xato ko‘rsatiladi. Qwen Coder kabi ayrim modellar server tomonidan tools imkoniyati bilan ko‘rsatilsa ham amalda chaqiruvni matn sifatida chiqarishi mumkin. Tekshiruvda `llama3.2:latest` strukturali fayl-qidiruv chaqiruvini bajardi.

Sozlamalar `%LOCALAPPDATA%/Brave/offline-desktop.json` ichida; funksiya odatda o‘chiq. Internet yoki mikrofon kerak emas. Fayllarni yozish, ko‘chirish, o‘chirish, xabar yuborish va ixtiyoriy kod bajarish bu ro‘yxatga kirmaydi.

## 3. Uchrashuv yordamchisi

**Uchrashuv → Audio tanlash → Matnga aylantirish** yozuvni o‘rnatilgan mahalliy faster-whisper modeli orqali transkript qiladi. Model oldindan mavjud bo‘lishi kerak; uni avvalgi **Offline ovoz** oynasida aniq yuklash mumkin. Inference hech narsa yuklab olmaydi.

Qo‘llanadigan fayllar: WAV, MP3, M4A, FLAC, OGG, AAC, MP4 va WEBM. Chegaralar: 500 MB, 2 soat va 160 ming belgi transkript. Audio diskdan oqim bilan ochiladi, mono 16 kHz’ga moslanadi va 30 soniyalik qismlarda taniladi. Butun audio RAM’ga olinmaydi. Vaqt belgilari qismlarning boshlanishiga tegishli; ular har bir so‘zning aniq vaqti emas. Fon worker’i interfeysni bloklamaydi.

Transkriptni tekshirib tahrirlang, so‘ng **Xulosa va vazifalar**ni bosing. Natijada qisqa xulosa, qarorlar va vazifa/mas’ul/muddat jadvali so‘raladi. Ko‘rsatilmagan mas’ul yoki muddat noma’lum deb olinishi kerak. Gapiruvchilarni ajratish uchun yangi checkbox va lokal model mavjud; [yangi qo‘llanma](AI_EXTENSIONS.md)ni ko‘ring.

Uzun tahlil ko‘pi bilan 256 ta kirish qismi va 8 ta birlashtirish bosqichi bilan cheklangan; butun tahlilning 30 daqiqalik chegarasi bor. Alohida generatsiya odatiy transport chegaralaridan foydalanadi. Chegaraga yetilsa transkriptni kichikroq qismlarga ajratish mumkin.

Transkript o‘zgarsa avvalgi tahlil natijasi eskirgan deb tozalanadi. Uzun matn profil kontekstiga sig‘adigan qismlarda lokal tahlil qilinib, oraliq dalillar yakuniy javobga birlashtiriladi. Bu qo‘shimcha generatsiyalar vaqt oladi. Token chegarasiga yetish ko‘rsatiladi. Xato yoki bekor qilishda qisman AI natijasi eksport/chatga qo‘yish uchun tayyor natija hisoblanmaydi. Transkriptni alohida TXT, hisobotni Markdown/TXT sifatida saqlash mumkin.

Import bilan birga **Jonli uchrashuvni boshlash** endi mikrofon transkriptini uzluksiz oladi. **Jonli vazifalarni yangilash** yozuvni to‘xtatmasdan shu paytdagi matndan vazifalar oladi. Oddiy F4/Speak chat oqimi alohida qoladi.

## 4. Kod va Git tahlili

**Kod tahlili**da kod fayli yoki Git repozitoriyning asosiy papkasini tanlang. **Manbani ko‘rish** tahlilga beriladigan matnni ko‘rsatadi. **Kodni tekshirish** tanlangan lokal modeldan konkret xatolar, fayl/qator, sabab, ta’sir va tuzatish takliflarini so‘raydi.

Oddiy tahlil kodni bajarmaydi yoki o‘zgartirmaydi. Yangi **AI tuzatish tayyorlash** va **Diff bilan tahrirlash** alohida oynada ko‘rsatilgan o‘zgarishni tasdiqlagach qo‘llaydi va zaxira yaratadi. Model tavsiyasi xato bo‘lishi mumkin; diffni tekshiring. Testlar avtomatik ishga tushirilmaydi.

Git rejimi `HEAD` bilan kuzatilgan o‘zgarishlarni, shu jumladan staged va unstaged o‘zgarishlarni oladi. Commit qilinmagan yangi untracked fayllar qo‘shilmaydi. `HEAD` bo‘lmagan repo uchun fayl rejimidan foydalaning. Git faqat o‘qish buyruqlarida ishlatiladi; tashqi diff va textconv drayverlari o‘chiriladi.

Chegaralar: 30 ta o‘zgargan fayl; alohida fayl va eski blob 180 KB; diff jami 180 ming belgi; umumiy tahlil matni 200 ming belgi. Katta kirish yashirin qisqartirilmaydi, xato va qismlarga ajratish taklifi beriladi. Maxfiy sozlama nomlari chiqarib tashlanadi, tanilgan kalit/secret shakllari niqoblanadi. Bu barcha maxfiy ma’lumotlarni topish kafolati emas. `files` va `code` ruxsatlari kerak.

## 5. Shaxsiy o‘zbekcha lug‘at

**Shaxsiy lug‘at**da uchta ustun bor:

- **Atama** — matnda ko‘rinishi kerak bo‘lgan yozuv, masalan `Shahzod`.
- **Tanilish varianti** — nutqdan noto‘g‘ri taniladigan yozuv, masalan `shaxzod`.
- **Talaffuz** — ovoz chiqarishdagi shakl, masalan `Shah zod`.

**Lug‘atni tekshirish** model va mikrofon ishlatmasdan misolni ko‘rsatadi. **Saqlash** keyingi tanish va ovozli javobga qo‘llaydi. Lug‘at mahalliy `speech-dictionary.json` faylida saqlanadi; 200 ta yozuv, har maydon 120 belgi bilan cheklangan.

Atamalar Whisper’ga 500 belgigacha recognition hint sifatida ham beriladi. Tanilish varianti butun so‘z/ibora bo‘yicha almashtiriladi; almashtirishlar ketma-ket yana bir-birini o‘zgartirmaydi. Apostrof variantlari hisobga olinadi. Talaffuz faqat ovozga beriladigan nusxaga qo‘llanadi, chat matni o‘zgarmaydi. Bu shaxsiy tuzatish/hint mexanizmi, STT yoki TTS modelini qayta o‘qitish emas.

## Sinovlar va real tekshiruv

`tests/test_ai_studio.py` model filtri/tanlovini, ruxsatlar, launch, filename scope, bekor qilish, kech tasdiq, tool JSON’ni bajarmaslik, uzoq audio qismlari, Git diff, STT/TTS lug‘ati va Qt oynalarini tekshiradi. Hozirgi 6 bo‘lim × 3 mavzu × 3 til ko‘rinishlari `design-preview/ai-studio/` ichida. Quyidagi 235 testlik natija avvalgi bosqichga tegishli; joriy dalillar [AI_EXTENSIONS.md](AI_EXTENSIONS.md)da.

Yakuniy natija: yangi bo‘limlar uchun **26 ta test**, to‘liq to‘plamda **235 ta test — OK** (107,643 s). `pip check`: **No broken requirements found**.

Haqiqiy sinov foydalanuvchi fayllari yoki tarixisiz, vaqtinchalik sun’iy ma’lumot bilan o‘tkazildi:

| Funksiya | Natija |
| --- | --- |
| Model tavsiyasi | O‘rnatilgan 10 chat modelidan kod uchun `qwen2.5-coder:7b` tavsiya qilindi |
| Offline chat vositasi | `llama3.2:latest` `find_local_files`ni chaqirib `budget-report.txt`ni topdi |
| Kod tahlili | `qwen2.5-coder:7b` nolga bo‘lish xatosini topdi; kod baytlari o‘zgarmadi |
| Audio | 66,17 soniyalik sun’iy lokal SAPI WAV o‘rnatilgan Whisper base orqali transkript qilindi |
| Uchrashuv | $42 budjet va Ali/Dushanba vazifasi hisobotda saqlandi |
| Lug‘at | `Allie/Alley → Ali`, `Brave → Breyv` tekshirildi |

So‘nggi real namuna: filename vositasi 0,813 s, kod tahlili 6,359 s, transkripsiya 10,282 s, uchrashuv hisoboti 1,765 s. Model yuklanishi, OS keshi va boshqa ishlar vaqtga ta’sir qiladi; bular umumiy tezlik/sifat benchmark’i emas. Inglizcha sun’iy nutq ishlatildi; o‘zbekcha nutqning umumiy aniqligi baholanmadi. Dastur ochishning chaqiruvi testlarda mock bilan tekshirildi; ish paytidagi dasturlar o‘z-o‘zidan ochilmadi.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_ai_studio.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts\smoke_ai_studio.py --audio --output logs\studio-real-smoke.json
```

Xom dalillar: `logs/studio-real-smoke.json`, `logs/studio-real-smoke.png`, `logs/studio-final-tests.log`. Haqiqiy sinov tanlangan modelni faqat vaqtinchalik config ichida almashtirdi; foydalanuvchining modeli va kalitlari saqlandi. Eski yig‘ilgan `dist/` EXE qayta yig‘ilmadi; manba kod `start.ps1` orqali ochiladi.

API tayanchi: [Ollama chat](https://docs.ollama.com/api/chat), [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [PyAV audio](https://pyav.org/docs/stable/api/audio.html), [git diff](https://git-scm.com/docs/git-diff). STT lokal fayllar rejimida, Ollama so‘rovlari faqat loopback’da va proxy/redirect’siz ishlaydi.
