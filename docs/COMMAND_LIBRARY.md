# 66 ta tayyor slash buyruq va shaxsiy buyruqlar

Yangi `/duel`, `/continue`, `/folders` uchun [taqqoslash, davom ettirish va papkalar qo‘llanmasi](COMPARE_CONTINUE_FOLDERS.md)ga qarang.

Yangi `/commands`, `/queue`, `/find` imkoniyatlari uchun [shaxsiy buyruqlar, navbat va qidiruv qo‘llanmasi](PRODUCTIVITY_WORKFLOWS.md)ga qarang. Tayyor buyruqlardan tashqari 50 tagacha shaxsiy prompt buyrug‘i saqlash mumkin.

Chatga `/` yozing. Buyruq nomi yoki o‘zbekcha, inglizcha, ruscha tavsif orqali qidiring. Toifalar: Barchasi, AI matn, Kod, Vositalar, Suhbat va Saralanganlar. ↑↓ tanlash, Tab/Enter qoralamaga qo‘yish, Esc menyuni yopish uchun. So‘ng matnni yozing va Enter bosing. Menyudagi tanlashning o‘zi AI so‘rovi yoki tizim amalini bajarmaydi.

Yulduz tugmasi tanlangan buyruqni saralaydi yoki saralanganlardan chiqaradi. 20 tagacha saralangan va oxirgi 12 ta ishlatilgan buyruq lokal saqlanadi; bu registrda savol yoki javob mazmuni saqlanmaydi. Bo‘sh `/` ro‘yxatida saralanganlar, keyin oxirgi ishlatilganlar chiqadi. Buyruq nomi ortidan bo‘sh joy yozilganda menyu yopiladi va argument yozishni davom ettirasiz.

`/help` qidiruv, toifalar va misollar bilan katalogni ochadi. Uni **Ctrl+K → Slash buyruqlar** orqali ham ochish mumkin. Katalogdagi **Buyruqni qo‘yish** qoralamaga qo‘shadi va avtomatik yubormaydi.

## AI va matn — 21 ta

| Buyruq | Vazifa |
| --- | --- |
| `/plan` | Bosqichli ish rejasi |
| `/think` | O‘rnatilgan thinking modeli, chuqurroq tahlil |
| `/fast` | Kichikroq kontekst va qisqa javob |
| `/translate en matn` | Tarjima; uz/en/ru/tr/de/fr/es/ar/zh/ko/ja |
| `/summarize` | Asosiy fikr va raqamlar xulosasi |
| `/explain` | Sodda tushuntirish |
| `/rewrite` | Ma’noni saqlab ifodani yaxshilash |
| `/vision` | Biriktirilgan yoki shu chatda saqlangan rasmni tushunish |
| `/grammar` | Imlo va grammatika |
| `/shorten` | Ixchamlashtirish |
| `/expand` | Batafsilroq izohlash |
| `/formal` | Rasmiy uslub |
| `/email` | Email qoralamasi; email yubormaydi |
| `/table` | Markdown jadval |
| `/compare` | Variantlarni mezonlar bilan taqqoslash |
| `/brainstorm` | Amaliy g‘oyalar |
| `/quiz` | Savollar va javob kaliti |
| `/teach` | Bosqichli dars, misol va mashq |
| `/extract` | Matndan JSON maydonlarini ajratish |
| `/check` | Ichki zidlik, noaniqlik va hisob xatolarini izlash; internet tekshiruvi emas |
| `/outline` | Matn yoki loyiha tuzilmasi |

Bu buyruqlardan keyin matn yozing. Masalan:

```text
/table Ali: 42 dollar; Sara: 17 dollar
/extract Ism va summa maydonlari: Ali, 42 dollar
/translate en Loyiha tayyor.
/shorten @last
```

`@last` butun argument bo‘lsa, aynan shu chatdagi oxirgi tugallangan javob bilan almashtiriladi. `/translate en @last` ham ishlaydi. Oddiy matn ichidagi `@last` almashtirilmaydi. Tugallangan javob bo‘lmasa yoki kengaygan matn chat limitidan oshsa, yuborilmaydi va qoralama qoladi. Bekor qilingan yoki hali oqimda kelayotgan javob olinmaydi.

Ollama’da `/extract` serverga `format: "json"` yuboradi. Natija JSON sifatida tekshiriladi; buzilgan, tugallanmagan JSON va NaN/Infinity tugallangan javobga yoki muvaffaqiyatli tezlik namunasiga yozilmaydi. Natijaga Markdown manba qo‘shimchasi qo‘shilmaydi. JSON shakli to‘g‘ri bo‘lishi faktlar to‘g‘ri ekanini kafolatlamaydi. Gemini’da bu matnli ko‘rsatma sifatida ishlaydi; alohida JSON validator cloud oqimiga qo‘shilmagan.

## Kod — 9 ta

| Buyruq | Vazifa |
| --- | --- |
| `/code` | Kod yozish yoki tushuntirish |
| `/debug` | Sabab, minimal tuzatish va tekshirish taklifi |
| `/fix` | Minimal tuzatish |
| `/refactor` | Tashqi xatti-harakatni saqlab tozalash |
| `/optimize` | Tezlik/xotira tahlili va o‘lchash taklifi |
| `/tests` | Test kodi yozish |
| `/document` | Hujjat va foydalanish misoli |
| `/sql` | SQL so‘rovi va izohi |
| `/regex` | Regex va mos/nomos misollar |

Ollama’da ushbu buyruqlar kod vazifasi sifatida mos o‘rnatilgan modelga yo‘naltiriladi. Mavjud metadata reytingi va yetarli o‘lchovlar ishlatiladi. Saqlangan model/profil o‘zgarmaydi. Bu buyruqlar faylni tahrirlamaydi va kodni bajarmaydi. Faylga tuzatish uchun `/review` orqali diff’ni ko‘ring; test bajarish uchun `/test` oynasidagi buyruqni tekshirib tasdiqlang. `/tests` esa faqat test matnini yozadi.

## Suhbat — 14 ta

| Buyruq | Vazifa |
| --- | --- |
| `/new` | Yangi chat |
| `/history loyiha` | Tarix oynasini ko‘rsatilgan qidiruv bilan ochish; chatni avtomatik almashtirmaydi |
| `/find ibora` | Shu suhbatdagi xabarlarni qidirish va topilgan joyga o‘tish; Ctrl+F ham ishlaydi |
| `/continue` | Token chegarasida tugagan oxirgi Ollama javobini davom ettirish |
| `/folders` | Chat papkalari, teglar va mahkamlash bilan tarix oynasi |
| `/export` | Joriy chatni tanlangan Markdown fayliga eksport qilish |
| `/copy` | Oxirgi tugallangan javobni clipboard’ga nusxalash |
| `/retry` | Oxirgi savoldan yangi suhbat versiyasini yaratib qayta yuborish |
| `/edit` | Oxirgi savolni tahrirlash, yangi versiyada qoralama tayyorlash |
| `/memory` | Joriy suhbat xotirasi |
| `/focus` | Fokus ko‘rinishini almashtirish |
| `/fullscreen` | To‘liq ekran |
| `/forget` | Joriy chatning rasm kontekstini unutish |
| `/cancel` | Joriy chat javobini to‘xtatish |

`new/retry/edit/memory` faol javob yoki chat almashishini bloklagan vazifa davomida ishlamaydi; matn qoralamada qoladi. `/retry` asl tarixni saqlab, yangi versiyada javob oladi. `/cancel` yordamchi oynadagi alohida test/meeting ishini avtomatik to‘xtatmaydi; o‘sha oynaning Stop/Cancel tugmasidan foydalaning.

## Vositalar — 22 ta

| Buyruq | Oyna yoki amal |
| --- | --- |
| `/totext` | Audio/rasm/hujjat → matn |
| `/screen savol` | Ekran tahlili, ixtiyoriy savol |
| `/meeting` | Uchrashuv va saqlangan transkriptlar |
| `/review` | Kod tahlili va diff |
| `/test` | Test bajarish oynasi |
| `/models` | Model tavsiyasi va sozlamalar |
| `/benchmark` | Model tezligini o‘lchash oynasi |
| `/voice` | Offline ovoz sozlamalari |
| `/help` | Qidiriladigan buyruqlar katalogi |
| `/knowledge` | Bilim kutubxonasi |
| `/project` | Loyiha fayllari va profillari |
| `/settings ai` | Sozlamalar, ixtiyoriy bo‘lim |
| `/diagnostics` | Diagnostika |
| `/attach` | Fayl tanlash |
| `/dictionary` | Shaxsiy nutq lug‘ati |
| `/desktop` | Ruxsatli offline amallar |
| `/permissions` | Ruxsatlar markazi |
| `/warmup` | Vision modelini promptsiz oldindan yuklash |
| `/snippets` | Shaxsiy prompt shablonlari |
| `/commands` | Shaxsiy slash buyruq yaratish va model/profilini tanlash |
| `/queue` | Lokal AI va fayldan matn olish vazifalari navbati |
| `/duel` | Ikki o‘rnatilgan modelga bir xil savol yuborib taqqoslash |

`/settings` bo‘limlari: `ai`, `appearance`, `audio`, `profile`, `plugins`, `system`. `/history`, `/settings`, `/screen`, `/help`, `/find` matn argumentini oladi; qolgan oynalar ortiqcha argumentni xato sifatida ko‘rsatadi va matnni saqlaydi. Oynani ochish mikrofon, ekran olish, model download yoki fayl apply’ni o‘zi boshlamaydi. `/warmup` o‘rnatilgan mos modelni yuklaydi, yangi model yuklab olmaydi.

## Shaxsiy shablonlar

`/snippets` → **Yangi** → nom va prompt → **Saqlash**. 30 tagacha shablon, nom 1–80, prompt 1–10000 belgi. **Qoralamaga qo‘yish** matnni mavjud qoralamaga qo‘shadi va yubormaydi. Saqlanmagan tahrirni yopish/almashtirishda uni bekor qilish tasdig‘i so‘raladi. O‘chirish ham tasdiqlanadi.

Shablonlar `%LOCALAPPDATA%/Brave/prompt-snippets.json`, saralangan/oxirgi buyruqlar `slash-preferences.json`da saqlanadi. Ikkalasi ham ilovaning backup/restore ro‘yxatiga kiritilgan. Shablonlarni o‘qish, saqlash va qo‘yish joriy files ruxsatini tekshiradi. Saqlangan shablonlarni maxfiy ma’lumotlar uchun ombor sifatida ishlatmang: ular oddiy lokal JSON.

Aliaslar: quick→fast, deep→think, summary/xulosa→summarize, tarjima→translate, reja→plan, yordam→help, ocr/text/transcribe→totext, stop→cancel, newchat→new.

Fast/Think Ollama rejimlari; qolgan prompt buyruqlari ikkala provider’da ishlaydi. Matn buyruqlari lokal avtomatik vositalarni o‘chiradi. Model javob sifati tanlangan model va berilgan manbaga bog‘liq.

## Tekshiruv

2026-10-19: umumiy regressiya **309 test OK, 134.384 s** (`logs/commands-full-tests.log`). Keyingi JSON metrikasi va vektor yulduz belgilari tuzatishi yangi funksiyalar testlari bilan tekshirildi (`logs/command-library-tests.log`). `pip check`: buzilgan bog‘liqlik yo‘q. 27 ta menu/katalog/shablon preview uch til va uch mavzuda: `design-preview/commands/`.

Haqiqiy Ollama, sun’iy ma’lumot va vaqtinchalik tarix/sozlamalar bilan (`scripts/smoke_command_library.py`, `logs/commands-real-smoke.json`):

| Buyruq | Kuzatilgan natija |
| --- | --- |
| `/debug` | qwen2.5-coder:7b, 11.28 s; nolga bo‘lish sababi va taklif. Kod avtomatik bajarilmadi |
| `/table` | llama3.2:latest, 5.83 s; Ali 42 va Sara 17 saqlandi |
| `/extract` | llama3.2:latest, 0.45 s; `{"name":"Ali","amount":42}` |
| Lokal amallar | @last kengayishi, copy, shablonni saqlash/qoralamaga qo‘yish ishladi |

Bu umumiy tezlik kafolati emas. Foydalanuvchining global sozlamalari baytma-bayt o‘zgarmagani tekshirildi. Yangilanish manba kodiga tegishli: `start.ps1` bilan ochiladi; avvalgi `dist/` EXE qayta yig‘ilmagan.
