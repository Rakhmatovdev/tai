# Internet uzilganda offline rejimga o‘tish

Gemini rejimida internet yo‘qolgani aniqlansa **“Offline rejimga o‘tamizmi?”** oynasi ochiladi. Dastur allaqachon Ollama rejimida bo‘lsa bu oyna kerak emas va chiqmaydi.

- **Offline’ga o‘tish**: saqlangan Ollama manzili va model tekshiriladi. Mavjud serverdan foydalaniladi yoki avtomatik ishga tushirish yoqilgan bo‘lsa o‘rnatilgan server ishga tushiriladi. Chatga yaroqli model topilsa Gemini to‘xtatiladi va Ollama yoqiladi. Provider tanlovi keyingi ishga tushirish uchun ham saqlanadi.
- **Hozir emas / Esc / oynani yopish**: provider o‘zgarmaydi. Gemini odatdagi qayta ulanish tartibini davom ettiradi. Shu uzilish uchun popup qayta chiqmaydi.
- **Lokal model yoki server yo‘q**: popup xatoni ko‘rsatadi va **Qayta urinish** tugmasini yoqadi. Model avtomatik yuklab olinmaydi. AI model sozlamalarida manzil yoki tanlangan modelni tuzatish mumkin.
- **Internet qaytdi**: hali ochiq popup yopiladi; rejim avtomatik Gemini’ga qaytmaydi. Tekshiruv paytida internet qaytsa yoki popup yopilsa kech kelgan natija provider’ni o‘zgartirmaydi.

Saqlangan suhbat, biriktirilgan fayllar va yozilayotgan qoralama saqlanadi. Lokal kontekstga faqat tugallangan user/assistant juftliklari olinadi. Uzilgan yoki qisman tugagan so‘rov avtomatik qayta yuborilmaydi. Gemini kaliti saqlanadi.

Oyna asosiy Qt oqimida ochiladi, lokal serverni tekshirish alohida worker’da bajariladi. Ishlayotgan yoki qayta ulanayotgan Gemini bo‘lsa ham, foydalanuvchining aniq tasdig‘idan keyin runtime bekor qilinib to‘xtatiladi; eski backend to‘liq to‘xtagandan keyin Ollama boshlanadi. Eski callback va kech kelgan tekshiruvlar yangi rejimni o‘zgartira olmaydi.

Aniqlash Qt `QNetworkInformation` orqali operatsion tizimning reachability hodisalariga tayanadi. Qo‘shimcha ravishda Gemini’dagi DNS/socket/HTTP transport ulanish xatolari ham oynani chaqiradi. API kaliti, kvota va audio qurilma xatolari internet uzilishi deb olinmaydi. Alohida doimiy internet so‘rovlari qo‘shilmagan. Operatsion tizim hodisani qachon bildirsa, oyna o‘shanda chiqadi; backend mavjud bo‘lmasa bulut transport xatosi orqali aniqlanadi. OS reachability ma’lumoti internet mavjudligini mutlaq kafolatlamaydi: [Qt rasmiy hujjati](https://doc.qt.io/qt-6/qnetworkinformation.html).

## Tekshiruv

Haqiqiy tarmoq adapteri o‘chirilmadi. OS hodisalari simulyatsiya qilinib, lokal HTTP server va test Gemini runtime bilan quyidagilar tekshirildi:

- uzilganda darhol bitta popup va yangi uzilishda yana chiqishi;
- tasdiq bilan band Gemini’ni to‘xtatib Ollama’ga o‘tish;
- tarix, qoralama va API kalitining saqlanishi;
- xulosalash/generatsiya yoki model yuklashni o‘tish paytida o‘z-o‘zidan boshlamaslik;
- model topilmasa provider’ni almashtirmaslik;
- tekshiruv vaqtida internet qaytishi yoki rad etilganda kech natijani inkor qilish;
- eski runtime signallarini inkor qilish;
- allaqachon offline rejimda yoki reachability noma’lum bo‘lsa popup chiqarmaslik;
- Default, Light, Hacker mavzularida Uzbek, English, Russian ko‘rinishi.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_connectivity.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Popup sinovlari: `tests/test_connectivity.py`. Skrinshotlar: `design-preview/offline/`. O‘zgarishlar lokal manbaga kiritildi; oldin ishga tushirilgan ilova yangilikni olishi uchun yopib, `start.ps1` orqali qayta ochish kerak.

Natija: popup uchun **9 ta test**, to‘liq to‘plamda **194 ta test — OK** (83,79 s). Ushbu Windows kompyuterida Qt’ning `networklistmanager` backend’i yuklandi va joriy `Online` holatini qaytardi. To‘liq log: `logs/offline-fallback-all-tests.log`.
