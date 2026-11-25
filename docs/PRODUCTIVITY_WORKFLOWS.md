# Shaxsiy buyruqlar, vazifalar navbati va chat qidiruvi

Uchala imkoniyat **Chat → …**, **Ctrl+K** va slash menyuda mavjud. Tayyor slash buyruqlar soni hozir 66 ta. Shaxsiy buyruqlar ularga qo‘shimcha qo‘shiladi. Keyingi yangilanishda [ikki modelni taqqoslash, javobni davom ettirish va chat papkalari](COMPARE_CONTINUE_FOLDERS.md) ham qo‘shildi.

## Shaxsiy slash buyruqlar

`/commands` oynasida:

1. **Yangi**ni bosing, masalan `myplan` nomini va tavsifini yozing.
2. Prompt yozing: `Ushbu vazifa uchun uch bosqichli reja tuz: {input}`.
3. Istasangiz o‘rnatilgan Ollama modeli nomi va resurs profilini tanlang. Model bo‘sh yoki profil **Joriy profil** bo‘lsa, joriy chat sozlamasi olinadi.
4. **Saqlash**ni bosing. Chatda `/myplan yangi sayt` kabi foydalaning.

`{input}` buyruqdan keyingi matn bilan oddiy almashtiriladi; ifodalar yoki Python kodi bajarilmaydi. Boshqa `{...}` matni literal qoladi. `{input}` bo‘lmasa, saqlangan promptdan keyin qo‘shimcha matn qo‘shiladi; buyruqni argumentsiz ham yuborish mumkin. `{input}` bo‘lsa argument kerak. `/myplan @last` joriy suhbatning oxirgi tugallangan javobini oladi.

Model va profil faqat shu so‘rovga tegishli. Model aniq tanlangan bo‘lsa auto-routing uni almashtirmaydi. Model bo‘sh bo‘lsa mavjud routing qoidalari saqlanadi. Global provider, model va profil o‘zgarmaydi. O‘rnatilmagan yoki rasmga mos bo‘lmagan model xato ko‘rsatadi; avtomatik model download yoki provider almashishi yo‘q.

Shaxsiy promptlar lokal vositalarni chaqirmaydi, fayllarni tahrirlamaydi va kodni bajarmaydi. Gemini’da model/profilsiz shaxsiy promptlar ishlaydi; Ollama modeli yoki profili saqlangan buyruq uchun Ollama rejimi kerak. Qo‘yish tugmasi faqat qoralama yaratadi.

Buyruqlar nomi 2–24 ta lotin harfi/raqam/underscore, birinchi belgi harf. Tayyor buyruq yoki alias nomini egallab bo‘lmaydi. 50 tagacha buyruq; sarlavha 1–80, prompt 1–10000 belgi. Kengaygan custom prompt qo‘shimcha 12000-belgi limiti va chatning haqiqiy profil limiti bilan tekshiriladi. Xatoda qoralama qoladi. Saqlanmagan tahrirni almashtirish yoki yopishda bekor qilish tasdig‘i bor.

Buyruqlar `/` menyusi, tavsif bo‘yicha qidiruv, `/help`, saralanganlar va oxirgi ishlatilganlarda paydo bo‘ladi. Fayl ruxsati o‘chiq bo‘lsa tahrirlash/yuborish bloklanadi. Saqlash manzili: `%LOCALAPPDATA%/Brave/custom-commands.json`.

## Vazifalar navbati

`/queue` oynasida nom, tur, topshiriq, manba matni yoki fayllarni tanlang. Model/profil bo‘sh bo‘lsa, qo‘shish vaqtidagi joriy Ollama sozlamalari yozib olinadi; ularni keyin chat sozlamasini o‘zgartirish almashtirmaydi. Har bir ishning tanlangan modeli/profili ro‘yxatda ko‘rinadi.

- **AI tahlil**: xulosa, tarjima, solishtirish kabi topshiriq va manba matni/fayl.
- **Fayldan matnga**: mavjud lokal PDF/DOCX/matn, rasm OCR va audio STT konvertori. Matn LLM’ga yuborilmaydi; audio uchun mavjud Whisper, rasm/skan uchun OCR kerak.
- **Har bir fayl alohida vazifa**: bitta tanlovdagi fayllarni alohida ishlar qilib qo‘shadi. Checkbox o‘chiq bo‘lsa ular bitta ishning manbasi bo‘ladi.

**Navbatga qo‘shish** inference boshlamaydi. **Boshlash**dan keyin ishlar ketma-ket yuradi. Natijalar chat tarixidan alohida; chatdagi qoralama va suhbat almashtirilmaydi. **Qoralamaga qo‘yish** natijani mavjud matnga qo‘shadi, avtomatik yubormaydi. **Nusxalash** clipboard’ga oladi.

**Pauza** yangi ish boshlashni to‘xtatadi, joriy ish tugaydi. **Bekor qilish** tanlangan faol yoki kutilayotgan ishni bekor qiladi. **Qayta navbatga** xato/bekor qilingan/uzilgan ishni pending holatiga qaytaradi; navbat to‘xtagan bo‘lsa yana Boshlash kerak. **O‘chirish** faol bo‘lmagan ishni va natijasini ro‘yxatdan olib tashlaydi.

Oynani yopish boshlangan navbatni davom ettiradi. Ilovani yopish faol ishni to‘xtatib **Uzuldi** deb belgilaydi. Keyingi ochishda avtomatik inference yoki qayta urinish bo‘lmaydi. Foydalanuvchi Qayta navbatga/Boshlashni tanlaydi. Chat, tahlil va boshqa lokal inference umumiy resurs darvozasidan foydalanadi; yangi queue ishi chat band bo‘lsa kutadi. Jonli yozuv, provider almashishi yoki files ruxsatining olinishi faol queue ishini bekor qilib navbatni pauzaga qo‘yadi. Serverning hisoblashni qachon to‘xtatishi Ollama disconnect’ni sezishiga bog‘liq.

Navbat uchun **Ollama rejimi va files ruxsati** kerak. Boshqa provider avtomatik tanlanmaydi. Qo‘shilgan faylning o‘lchami yoki o‘zgartirish vaqti o‘zgargan bo‘lsa, o‘qishdan oldin xato qaytadi: uni qayta qo‘shing. Bu tekshiruv fayl mazmunining kriptografik nusxasi emas.

30 tagacha ish (tayyor natijalar ham shu limitda), bir ishda 10 tagacha fayl; topshiriq 4000, manba matni 10000 belgi. Konvertatsiya/qismlarga tahlilda umumiy manba 200000 belgi bilan cheklangan. Natijalar va ish sozlamalari `%LOCALAPPDATA%/Brave/ai-queue.json`da saqlanadi. Disk xatosida navbat davom etmaydi; joriy sessiyada qolgan natijani nusxalash mumkin. Batch qo‘shish bitta atomik yozuv orqali amalga oshadi.

## Chat ichida qidirish

**Ctrl+F** yoki `/find ibora` bilan joriy suhbatni qidiring. Qidiruv hozir ko‘rinayotgan sahifadan tashqaridagi saqlangan xabarlarni ham qamrab oladi. Kirill/lotinda registrga befarq, literal qidiruv; `%` va `_` wildcard sifatida ishlamaydi. Matn yoki koddagi iborani qidirish mumkin.

Natijalar 50 tadan sahifalanadi, har biri qisqa parcha bilan. **Xabarga o‘tish** kerakli tarix sahifasini ochadi, xabarni ko‘rinadigan joyga olib keladi va ko‘rsatilgan matnda topilgan iborani ajratadi. Busy chatda qidirish mumkin, lekin oqimni buzmaslik uchun xabarga o‘tish javob tugaguncha bloklanadi. Chat almashsa eski natija boshqa suhbatni ochmaydi. Qoralama, attachments va chat ID o‘zgarmaydi. Qidiruv lokal SQLite’da; AI so‘rovi yuborilmaydi.

## Tekshiruv

`tests/test_productivity_workflows.py`: **29 test**. Custom CRUD/nom bandligi, literal prompt kengayishi, haqiqiy Qt HTTP payload’da model/profil, queue tartibi, pause/cancel, kechikkan javoblar, policy o‘zgarishi, disk xatosi, batch rollback, ilova yopilishidagi interruption, tiklash, totext, eski tarixga o‘tish, highlighting va Ctrl+F tekshirilgan. Uch til × uch mavzuda 27 ta oyna preview: `design-preview/productivity/`.

Haqiqiy Ollama sinovi: `scripts/smoke_productivity.py`, natija `logs/productivity-real-smoke.json`. `llama3.2:latest` bilan `/mybrief` 3.09 s ichida Ali/Monday/$42 ni saqladi. AI xulosasi va fayldan matn olish navbati 0.45 s ichida tugadi; natijalar tiklandi. 140 ta qo‘shimcha sun’iy xabar orasidan eski sahifadagi ibora topildi. Bu umumiy tezlik kafolati emas; natija model va manbaga bog‘liq. Shaxsiy fayllar ishlatilmadi va global sozlamalar baytma-bayt o‘zgarmagani tekshirildi.

5001 ta sun’iy xabarli xotiradagi SQLite bazasida oxirgi xabardagi iborani qidirish 19.29 ms oldi (`logs/chat-search-performance.json`). Bu disk yoki to‘liq UI uchun benchmark kafolati emas.

To‘liq regressiya: **338 test OK, 144.353 s** (`logs/productivity-final-tests.log`). `pip check`: buzilgan bog‘liqlik yo‘q. Umumiy testda aniqlangan highlighting vaqti muammosi tuzatildi: belgilash sahifa yaratilishi bilan darhol qo‘llanadi, layout’dan keyin faqat scroll bajariladi.

Yangilanish manba kodiga tegishli: `start.ps1` orqali ochiladi; oldingi `dist/` EXE qayta yig‘ilmagan. Custom buyruq va queue registrlari backup/restore ro‘yxatiga kiritilgan.
