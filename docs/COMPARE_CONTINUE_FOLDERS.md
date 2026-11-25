# Ikki modelni taqqoslash, javobni davom ettirish va chat papkalari

## Ikki model — `/duel`

**Chat → … → Ikki modelni taqqoslash**, **Ctrl+K** yoki `/duel` orqali oching. Ikki xil o‘rnatilgan Ollama modelini, Economy/Balanced/Quality profilini va savolni tanlang. **Modellarni yangilash** faqat lokal inventarni o‘qiydi; inference yoki download boshlamaydi. Model nomini qo‘lda kiritish ham mumkin.

**Taqqoslash** bosilganda aynan bir xil system/user xabarlari va bir xil profil ikkala modelga yuboriladi. Avval chap, keyin o‘ng model ishlaydi. Shared inference gate chat va navbat bilan resurs talashuvini boshqaradi. Model capability/context chegaralari baribir har bir modelga alohida qo‘llanadi. Model default’i va global profil o‘zgarmaydi; auto-routing tanlangan modellarni almashtirmaydi. Chat tarixi, rasmlar va biriktirilgan fayllar yuborilmaydi.

Javoblar yonma-yon, model nomi va haqiqiy vaqt bilan chiqadi. Server metrikani bersa TTFT va tok/s ham ko‘rsatiladi. Umumiy vaqt kutish/tayyorlash/yuklashni o‘z ichiga oladi; tok/s esa generatsiya tezligi. Cold/warm holati, ketma-ket model yuklanishi va kesh vaqtga ta’sir qiladi. Bu sifat reytingi yoki laboratoriya benchmark’i emas. Natijani foydalanuvchi baholaydi; ilova avtomatik g‘olib tanlamaydi.

Birinchi model xato qilsa ikkinchisi sinab ko‘riladi. Cancel joriy ishni bekor qilib keyingi modelni boshlamaydi; tugallangan avvalgi natija qoladi, joriy partial natija ishlatilmaydi. Oyna yoki ilova yopilganda comparison bekor qilinadi. Provider almashishi yoki jonli meeting yozuvi ham ishni to‘xtatadi.

Har bir tugallangan javobni **Nusxalash** yoki **Qoralamaga qo‘yish** mumkin; yuborish avtomatik emas. **Taqqoslashni eksport qilish** savol, model nomlari, profil, vaqt va natijalarni tanlangan Markdown fayliga atomik yozadi. Taqqoslash chat tarixiga o‘zi qo‘shilmaydi.

Yangilanish: oxirgi 20 ta taqqoslash alohida lokal tarixga saqlanadi. Qayta ochish va o‘chirish, chat joylashuvi qoralamalari hamda navbat eksporti [saqlangan natijalar qo‘llanmasida](SAVED_RESULTS.md).

## Javobni davom ettirish — `/continue`

Ollama `done_reason: length` bilan tugatgan javobning tagida **Davom ettir** paydo bo‘ladi. `/continue` va Ctrl+K’dagi shu amal ham mavjud. Oddiy `stop`, xato, bekor qilingan yoki hali kelayotgan javobda ilova davom ettirish kerakligini taxmin qilmaydi.

Har bir bosish bitta yangi so‘rov yuboradi. Kontekstda dastlabki savolning cheklangan qismi, oxirgi javobning oxirgi qismi va tugallanmagan gap/kodni davom ettirish ko‘rsatmasi bor. Oldingi javobning haqiqiy modeli va profili ishlatiladi; joriy default sozlama o‘zgarmaydi. Profilning belgilar limiti saqlanadi. Yashirin summary, avtomatik qayta urinish yoki cheksiz continuation zanjiri yo‘q.

Avvalgi javob o‘zgarmaydi: tarixga `Davom ettir` foydalanuvchi xabari va yangi javob yoziladi. Shu paytdagi qoralama va biriktirilgan fayllar o‘z holida qoladi; ular continuation so‘roviga yuborilmaydi va uning attachment tarixiga yozilmaydi. Lokal vositalar o‘chiq. Oldingi rasmlar bu so‘rovga qo‘shilmaydi. Bu rasmni qayta tahlil qilish emas, matnni davom ettirish oqimi.

Yangi savol berilgan bo‘lsa eski continuation tugmasi ishlamaydi. Busy chat yoki jonli yozuvda so‘rov bloklanadi. Cancel partial javobni tarixga qo‘shmaydi; asl length-limited javob keyin yana davom ettirilishi mumkin. Agar keyingi javob ham limitga yetsa, yana bosish kerak. Model hali ham mazmunni takrorlashi, raqamni o‘tkazib yuborishi yoki tugallanmagan gapni noto‘g‘ri yakunlashi mumkin; ayniqsa kichik model javobi tekshiriladi.

Model/profil/limit sababi SQLite’dagi assistant xabariga bog‘langan `reply_metadata` jadvalida saqlanadi. Qayta ochish, mavzu almashishi va suhbat versiyasiga ko‘chirishda metadata saqlanadi. Eski javoblar uchun limit sababi o‘ylab topilmaydi.

## Chat papkalari — `/folders`

Tarix tugmasi yoki `/folders`ni oching. Yuqorida papka, teg va **Mahkamlanganlar** filtrlari; pastda tanlangan chatning papkasi, vergul bilan ajratilgan teglari va **Mahkamlash** checkbox’i bor. **Joylashuvni saqlash** bilan qo‘llang.

- **Yangi papka** — 1–40 belgili nom, ko‘pi bilan 30 ta papka. Nomlar registrga befarq tekshiriladi, kirill ham ishlaydi.
- **Papkani nomlash** — filtrda yoki assignment maydonida tanlangan papkani nomlaydi.
- **Papkani o‘chirish** — tasdiqdan keyin faqat papkani olib tashlaydi. Suhbatlar Papkalanmagan bo‘limga o‘tadi; xabarlar, teglar va mahkamlash qoladi.
- Chatga 8 tagacha teg: har biri 1–32 belgi, vergul va boshqaruv belgilarisiz. Registr bilan farq qiladigan takrorlar birlashtiriladi.
- Mahkamlangan suhbatlar qidiruv natijasida oldinga chiqadi. Qolganlari yangilanish vaqtiga qarab saralanadi.
- Chat ro‘yxati 100 tadan sahifalanadi. Bu xabar preview’ining 60-xabarli sahifalaridan alohida.

Papka/teg filtrlari matn qidiruvi bilan birga ishlaydi. Qidiruvdagi `%` va `_` literal bo‘lib qoladi. Filtrlash, papkalash va preview AI so‘rovi yubormaydi; **Suhbatni davom ettirish** alohida amal. Faol javob paytida joriy chatni o‘chirish bloklanadi. Joriy idle chat o‘chirilsa runtime va ko‘rinish yangi suhbatga o‘tadi, qoralama saqlanadi.

Yangi suhbat versiyasi ota chatning papka va teglarini oladi, lekin avtomatik mahkamlanmaydi. Papka/teg/mahkamlash SQLite’dagi `chat_folders`, `chat_organization`, `chat_tags` jadvallarida saqlanadi. Eski uch ustunli `chats` jadvali va mavjud xabarlar o‘zgartirilmagan; yangi jadvallar startup’da yaratiladi. Oddiy app backup/restore butun SQLite bazasini olgani uchun metadata ham saqlanadi.

## Tekshiruv va haqiqiy sinov

`tests/test_compare_continue_folders.py`: 30 ta test. Bir xil payload/profil, ketma-ketlik, model xatosi, cancel/kechikkan signal, gate egasini saqlash, provider almashishi, export, continuation modeli/profili, qoralama/attachment saqlanishi, chetdagi whitespace, eski tugma, bekor qilish/qayta bosish, schema migration, branch, folder/tag/pin, pagination va pinned chatni nomlash tekshiriladi.

Uch til × uch mavzuda comparison, papkalar va continuation ko‘rinishlari tekshirildi: `design-preview/compare/`. Uzun papka nomlari ham 800 px test ekraniga sig‘adi.

`scripts/smoke_compare_continue.py` haqiqiy Ollama, sun’iy savol va vaqtinchalik sozlama/tarix bilan ishlaydi. `logs/compare-real-smoke.json` tugallangan:

| Oqim | Kuzatilgan natija |
| --- | --- |
| llama3.2:latest, Economy | `17 × 23 = 391`, 3.50 s |
| qwen2.5-coder:7b, Economy | `391` va arifmetik tekshiruv, 5.55 s |
| Continuation | 256-token haqiqiy length javobidan keyin bir bosish, 5.69 s; keyingi javob ham length bo‘lgani uchun yana bosish mumkin |
| Papka/teg/pin | SQLite backup’dan qayta ochilganda tiklandi; 4 ta chat xabari saqlandi |

Bu vaqtlar umumiy tezlik kafolati emas. Global sozlamalar baytma-bayt o‘zgarmagani tekshirildi. Yakuniy keng regressiya: **367 test OK, 161.490 s** (`logs/compare-final-tests.log`). Javob chetidagi whitespace uchun so‘nggi tuzatishdan keyin **30 ta yangi oqim testi OK, 16.247 s** (`logs/compare-continue-tests.log`). `pip check`: buzilgan bog‘liqlik topilmadi. Manbani `start.ps1` bilan oching; avvalgi `dist/` EXE bu yangilanishda qayta yig‘ilmagan.
