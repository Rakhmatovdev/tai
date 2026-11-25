# Yangi AI imkoniyatlari — 2026-10-19

## Oddiy chatda rasm haqida savol berish

1. **Sozlamalar → AI modeli** ichida Ollama va rasmni tushunadigan modelni tanlab saqlang. Oddiy matnli model Vision rejimida ishlamaydi. Ushbu kompyuterda `gemma4:12b` bilan haqiqiy sinov o‘tkazildi; kundalik matnli chatning avvalgi model tanlovi o‘zgartirilmadi.
2. Chatga rasm biriktiring. Yozish maydonidagi **Matnni o‘qish · OCR / Rasmni tushunish · Vision** tanlovidan keraklisini belgilang.
3. Rasmga oid savol yozib **Yuborish**ni bosing.

**OCR** avvalgi odatiy yo‘l: rasmdagi matnni Tesseract o‘qiydi va matn parchalari beriladi. **Vision** rasm piksellarini tanlangan lokal modelga beradi. Vision’da Tesseract shart emas. Bu ikkala rejim bir-biriga yashirin almashtirilmaydi. Vision qo‘llamaydigan model tanlansa xabar yozish maydoniga qaytariladi, biriktirma saqlanadi va xato ko‘rsatiladi.

Bir so‘rovda ko‘pi bilan 3 ta rasm, har biri 25 megapiksel va jami 50 megapiksel. Avvalgi 25 MB/fayl va 50 MB jami disk hajmi chegaralari ham saqlanadi. EXIF burilishi to‘g‘rilanadi, rasmlar eng katta tomoni 2048 pikselgacha kichraytirilib JPEG sifatida yuboriladi. Fayl o‘qish va tayyorlash GUI oqimini band qilmaydi.

Rasm va matnli hujjatni birga biriktirish mumkin: hujjat tegishli parchalar va ishlaydigan manba havolalari orqali, rasm esa piksellar orqali beriladi. Rasm ichidagi matn buyruq emas, ma’lumot sifatida belgilangan.

Tarixda savol, javob va biriktirilgan fayl yo‘llari saqlanadi; base64 piksellar diskka yozilmaydi. Endi muvaffaqiyatli rasmli javobdan keyin oxirgi rasm shu suhbatning keyingi savoliga RAM’dan beriladi. **AI Studio → Model tavsiyasi** ichida eslab turishni o‘chirish yoki **Rasm kontekstini unutish** mumkin. Ilova yopilganda tasvirlar unutiladi. Biriktirmani olib tashlash suhbatning vizual xotirasini tozalamaydi; Unutish tugmasidan foydalaning. Avtomatik model tanlash alohida yoqiladigan sozlama. Tafsilotlar [AI_EXTENSIONS.md](AI_EXTENSIONS.md)da.

## Matn bilan tezkor AI amallari

Tugallangan javob ostidagi **AI amallari**ni bosing. Matnning bir qismini belgilasangiz, faqat belgilangan qism olinadi; aks holda javobning to‘liq matni olinadi. Ixtiyoriy matn bilan ishlash uchun **Chat → … → AI amallari** yoki **Ctrl+K → AI amallari** ham mavjud.

- **Qisqa xulosa** — muhim fikr, raqam va faktlarni ajratadi.
- **Tarjima qilish** — o‘zbek, ingliz yoki rus tiliga tarjima qiladi.
- **Sodda tushuntirish** — oddiyroq izoh va misol tayyorlaydi.
- **Matnni yaxshilash** — imlo, grammatika va ifodani tahrirlaydi.

Manba matnini va natija tilini tanlab **Yaratish**ni bosing. Natija alohida oynada oqim sifatida chiqadi. **Nusxalash** clipboard’ga oladi. **Chatga qo‘yish** mavjud qoralamaga natijani qo‘shadi, xabarni yubormaydi. Asl suhbat tarixi o‘zgarmaydi. Yuborish odatdagi chat tugmasi orqali amalga oshiriladi.

Amallar faqat tanlangan lokal Ollama modelidan foydalanadi; Gemini avtomatik chaqirilmaydi. Kirish matni profilning belgilar chegarasiga, chiqish esa profilning token chegarasiga bo‘ysunadi. Matn sig‘masa izoh beriladi; yashirin qisqartirilmaydi. Chiqish uzunlik chegarasiga yetsa natija to‘liq emasligi ko‘rsatiladi. Bekor qilingan, xatoli va qisman tugagan natija chatga qo‘yish uchun faollashtirilmaydi. Navbat yoki tayyorlash paytidagi bekor qilish kech kelgan generatsiyani boshlamaydi.

## Tekshiruv va amaliy chegaralar

`tests/test_ai_actions.py` rasm baytlari, OCR/Vision ajratilishi, aralash hujjat/rasm, vision imkoniyatini tekshirish, bekor qilish, fayl ruxsati, vosita davomidagi rasm, matn amallari, qoralama va asl tarixning saqlanishini tekshiradi. Interfeys UZ/EN/RU va Default/Light/Hacker’da ko‘rildi. Skrinshotlar `design-preview/ai-actions/` ichida.

Natija: yangi imkoniyatlar uchun **15 ta test**, to‘liq to‘plamda **209 ta test — OK** (94,17 s). `pip check` paketlar orasida buzilgan talab topmadi. To‘liq log: `logs/ai-features-final-tests.log`.

Haqiqiy, vaqtinchalik sun’iy ma’lumot bilan sinov:

| Amal | Model | Natija | Vaqt |
| --- | --- | --- | ---: |
| Loyiha eslatmasi xulosasi | `llama3.2:latest`, Balanced | 42 birlik, Dushanba va Ali saqlandi | 0,703 s |
| Asosiy chatga qizil rasm biriktirib rangini so‘rash | `gemma4:12b`, Balanced | `Red` | 23,360 s |

Vision sinovida modelni dastlab yuklash 16,072 s oldi. 8 GiB RTX 4060 Laptop’da `ollama ps` shu katta model uchun 31% CPU / 69% GPU ko‘rsatdi. Bu tezlik va sifatning umumiy benchmark’i emas. Katta vision modeli sekinroq javob berishi mumkin; matnli chatning kichik modeli avtomatik almashtirilmaydi. Sinovdan keyin test uchun yuklangan vision modeli xotiradan chiqarildi.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_ai_actions.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts\smoke_ai_actions.py --vision-model gemma4:12b --output logs\ai-real-smoke.json
```

Haqiqiy natijalar `logs/ai-real-smoke.json` va `logs/ai-real-smoke.png` ichida. Ushbu tekshiruv foydalanuvchining hujjatlari yoki suhbat tarixini ishlatmadi. Yangiliklar lokal manbaga kiritildi; ishlayotgan ilovani yopib `start.ps1` orqali qayta oching. Oldingi `dist/` EXE qayta yig‘ilmadi.

Vision transporti rasmiy [Ollama Vision](https://docs.ollama.com/capabilities/vision) va [chat API](https://docs.ollama.com/api/chat) shakliga mos: base64 tasvirlar `messages[].images` orqali faqat loopback serverga beriladi.
