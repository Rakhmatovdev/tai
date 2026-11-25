# Saqlangan natijalar va qoralama himoyasi

## Model taqqoslash tarixi

`/duel` oynasining yuqorisidagi ro‘yxatdan taqqoslashni tanlab, **Saqlangan natijani ochish**ni bosing. Savol, ikki modelning tugallangan javoblari, profil va metrikalar tiklanadi. Bu amal Ollama so‘rovi yubormaydi va global model/profilni o‘zgartirmaydi. Joriy savol boshqacha bo‘lsa almashtirishdan oldin tasdiq so‘raladi.

Har bir tugallangan javob darhol `%LOCALAPPDATA%/Brave/model-comparisons.json` fayliga atomik saqlanadi. Ikkinchi model hali ishlayotgan paytda ham birinchi javob saqlangan bo‘ladi. Cancel qilingan qisman javob saqlanmaydi; avval tugallangan javob qoladi. Ikkala javob ham tugallanmagan bo‘lsa bo‘sh yozuv yaratilmaydi.

Tarix **20 ta taqqoslash** bilan cheklangan; yangi natija eng eski yozuvni chiqaradi. Savol va javoblar shu qurilmada saqlanadi, ilova backup’iga kiradi. Uzoq muddat kerakli taqqoslashni Markdown’ga eksport qiling. **Saqlangan natijani o‘chirish** tasdiqdan keyin tarix yozuvini olib tashlaydi. Hozir oynada ochiq natija nusxalash/eksport uchun qoladi, oynani yopish o‘chirilgan yozuvni qayta yaratmaydi. Avval yaratilgan backup yoki eksport nusxalari o‘zgarishsiz qoladi.

Saqlash muvaffaqiyatsiz bo‘lsa xato ko‘rsatiladi va joriy natijani eksport qilish mumkin. Noto‘g‘ri tarix yozuvlari yuklashda o‘tkazib yuboriladi; metrikalarda faqat ruxsat etilgan sonlar va yakun sababi saqlanadi. Ro‘yxatdagi sana **UTC**, vaqtlar esa shu ishning haqiqiy metrikalaridir; ular yangi o‘lchov sifatida ko‘rsatilmaydi.

## Papka va teg qoralamalari

`/folders` yoki suhbatlar tarixida papka, teg va mahkamlashni o‘zgartirgandan keyin boshqa chat, qidiruv yoki filtrga o‘tish tahrirni yo‘qotmaydi. Oynada har bir chatning alohida qoralamasi saqlanadi. Pastdagi yozuv saqlanmagan chatlar sonini ko‘rsatadi. Tegishli chatga qaytib **Joylashuvni saqlash**ni bosing.

Qoralamalar tarix bazasiga avtomatik yozilmaydi va faqat shu dialog ochiq paytda yashaydi. Saqlanmagan o‘zgarishlar bilan oynani yopish yoki chatni davom ettirishda bekor qilish tasdig‘i chiqadi. **Yo‘q** oynani va tahrirlarni saqlab qoladi. **Ha** saqlanmagan o‘zgarishlardan voz kechadi. Noto‘g‘ri teg uchun saqlash rad etilsa tahrir joyida qoladi. Papka o‘chirilganda uning qoralamadagi havolasi ham Papkalanmagan holatiga o‘tadi.

## Navbat natijalarini eksport qilish

`/queue` oynasida tugallangan vazifani tanlang va **Natijani eksport qilish**ni bosing:

- **Markdown (.md)**: vazifa sarlavhasi, model/profil va natija.
- **Text (.txt)**: faqat natija matni, UTF-8.

Manba fayllarning to‘liq matni eksportga qo‘shimcha qilib yozilmaydi. Model o‘zi natijaga kiritgan matn saqlanadi. Navbatdagi, ishlayotgan yoki xatolik bilan tugagan vazifalar eksport qilinmaydi. Fayl ruxsati eksport oldidan va fayl tanlash oynasi yopilgandan keyin tekshiriladi. Yozish xatosida mavjud fayl saqlanib qoladi; vaqtinchalik fayl tozalanadi. Chat qoralamasi o‘zgarmaydi.

## Tekshiruv

`tests/test_saved_results.py`: 12 ta test. Saqlash/qayta ochish, 20 ta yozuv chegarasi, noto‘g‘ri yozuv/metrikalar, backup, ikkinchi modelni bekor qilish, disk xatosi, qoralama himoyasi, eksport va ruxsat bekor qilinishi tekshiriladi. Transport testlari haqiqiy Qt HTTP oqimi va lokal test serveridan foydalanadi.

To‘liq regressiya: **380 test OK, 184.432 s** (`logs/improvements-regression.log`). Yakuniy o‘zgarishlardan keyin 12 ta yo‘naltirilgan test yana muvaffaqiyatli o‘tdi (`logs/saved-results-tests.log`). `pip check`: buzilgan bog‘liqlik topilmadi.

`scripts/preview_saved_results.py` faqat sun’iy ma’lumot va vaqtinchalik sozlamalar bilan 3 oyna × 3 mavzu × 3 til uchun 27 ko‘rinish yaratadi: `design-preview/saved-results/`. Inference boshlanmaydi. Manba versiyasini `start.ps1` orqali oching; mavjud `dist/` EXE bu o‘zgarishlarni o‘z ichiga olishi uchun qayta yig‘ilishi kerak.
