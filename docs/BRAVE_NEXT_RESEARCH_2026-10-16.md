# Brave: keyingi bosqich uchun chuqur tadqiqot

Keyingi holat: foydalanuvchining «go add» topshirig‘idan so‘ng quyidagi yo‘nalishlar amalga oshirildi. Joriy foydalanish yo‘llari, haqiqiy sinovlar va qolgan sifat/unumdorlik chegaralari [NEXT_LOCAL_FEATURES.md](NEXT_LOCAL_FEATURES.md)da. 164 ta test o‘tdi; haqiqiy Ollama’da embedding, vosita, JSON va vision, lokal OCR’da rasm/skan PDF tekshirildi. Quyidagi matn tadqiqot paytidagi boshlang‘ich holatni saqlaydi.

Sana: 2026-10-16. Asos: joriy Python/PyQt6 kodi, mavjud imkoniyatlar qo‘llanmasi va bevosita rasmiy manbalar. Bu safar yangi funksiyalar, model o‘rnatish yoki benchmark bajarilmadi. Quyidagi ustuvorliklar koddagi cheklovlardan chiqarilgan muhandislik tavsiyalari; tezlashuv va o‘zbekcha sifat natijalari hali o‘lchanmagan.

Ollama model tanlash/yuklash, lokal xotira, oxirgi xabarni tahrirlash/qayta javob, manbali hujjatlar, provayderni qayta ochmasdan almashtirish va offline ovoz allaqachon bor. Loyiha konteksti, ruxsatlar va fayl o‘zgarishlarini tiklash ham mavjud. Quyidagi takliflar shu asosni rivojlantiradi.

| Navbat | Qo‘shimcha | Asosiy foyda | Nisbiy hajm |
|---|---|---|---|
| 1 | Semantik qidiruv va doimiy bilim kutubxonasi | Boshqacha yozilgan savolga tegishli hujjatni topish | Katta |
| 2 | O‘lchovga tayangan optimizatsiya va model taqqoslash | Shu kompyuter uchun sifat/tezlik muvozanatini aniqlash | O‘rta–katta |
| 3 | Skan va rasmni lokal o‘qish | Skan PDF, skrinshot, jadval bilan ishlash | Katta |
| 4 | Ollama uchun lokal vositalar | Savolga javobdan amaliy natijaga o‘tish | Katta |
| 5 | Istalgan xabardan suhbat shoxlari | Turli yechimlarni yo‘qotmasdan solishtirish | O‘rta |
| 6 | Xotirada fakt, qaror va manbani ajratish | Uzun suhbatda aniq talablarni saqlash | O‘rta–katta |
| 7 | O‘zbekcha ovoz sifati va uzluksiz suhbat | Kamroq kutish, yaxshiroq nutq tajribasi | Katta |
| 8 | Katta tarix uchun tez chat | Uzoq suhbatlarni qulay ochish va qidirish | O‘rta |
| 9 | Tayyor Windows tarqatmasi va qayta tiklanadigan yangilash | Boshqa kompyuterga oson o‘rnatish | Katta |

Hajmlar vaqt va’dasi emas. 1 va 2 asosiy navbat; 3 va 4 ulardan keyin. Qolganlari foydalanishdagi ehtiyojga qarab olinadi.

## 1. Semantik qidiruv + bilim kutubxonasi

**Aniqlangan holat:** `core/local_documents.py:retrieve()` hujjatlarni har so‘rovda qayta ochadi, so‘zlar takrorlanishi bo‘yicha saralaydi va ko‘pi bilan to‘rtta parchani beradi. Barcha ballar nol bo‘lsa ham dastlabki parchalar tanlanadi. Masalan, hujjatdagi «to‘lov muddati»ni foydalanuvchi «pulni qachon berish kerak?» deb so‘rasa, tegishli parcha tushib qolishi mumkin. Manba ko‘rsatish allaqachon bor, lekin manba mavjudligi javobning to‘g‘riligini o‘zi tasdiqlamaydi.

**Taklif:** aniq so‘z qidiruvi va ma’no qidiruvini birlashtirish. Faqat foydalanuvchi tanlagan hujjat/papkalardan lokal kutubxona yaratish. Parchalar, fayl xeshi, sahifa, indeks versiyasi va embedding modeli identifikatorini saqlash; o‘zgarmagan faylni qayta hisoblamaslik. Model yoki bo‘laklash qoidasi almashsa, kerakli indeksni qayta yaratish. Qidiruv modeli uchun ham mavjud explicit yuklash jarayonidan foydalanish.

Ollama `/api/embed` lokal embedding yaratishni, jumladan matnlar to‘plamini bir so‘rovda hisoblashni qo‘llaydi. Indekslash va savol uchun bir xil model ishlatilishi kerak. [Ollama embeddings](https://docs.ollama.com/capabilities/embeddings).

Sinov nomzodi — kichik EmbeddingGemma: ishlab chiqaruvchi 100 dan ortiq tillardagi ma’lumot bilan o‘qitilganini ko‘rsatadi. Bu o‘zbekcha topshiriqlarimizdagi sifat kafolati emas; modelni oldindan «eng yaxshi» deb belgilamaslik kerak. [Google model kartasi](https://huggingface.co/google/embeddinggemma-300m).

Open WebUI ham hujjat kutubxonasi, manbalar va indeks sozlamalari o‘zgarganda qayta indekslash yo‘lini hujjatlashtiradi. Biz uchun foydali tajriba — indeksning hayot davrini qidiruvning o‘zi bilan birga loyihalash. [Open WebUI RAG](https://docs.openwebui.com/features/chat-conversations/rag/).

**Tayyorlik mezoni:** kamida 30 ta belgilangan savol bilan hozirgi qidiruvga taqqoslash: sinonim, o‘zbek lotin/kirill, ruscha hujjatga o‘zbekcha savol, aniq raqam va umuman javobi yo‘q savollar. Tegishli parchaning topilishi va manbasiz da’volar alohida o‘lchansin. Yetarli dalil topilmasa, «hujjatdan tasdiqlanmadi» holati ko‘rsatilsin. Bitta universal similarity chegarasi sinovsiz olinmasin.

**UI:** mavjud Markaz ichida bilim kutubxonasi; biriktirish oynasidan kutubxona tanlash. Javobda hozirgi manbalar ko‘rinishidan foydalanish.

## 2. Haqiqiy optimizatsiya + modelni taqqoslash

**Aniqlangan holat:** `core/ollama_resources.py` avtomatik profilni asosan bo‘sh RAM va NVIDIA VRAM chegaralaridan tanlaydi. Eng so‘nggi so‘rov diagnostikasi bor, lekin model sifati/tezligining takrorlangan taqqoslashi yo‘q. Yuklangan modelning o‘zi band qilgan VRAMni boshqa dastur bosimidan ajratish foydali bo‘ladi.

**Taklif:** foydalanuvchi boshlaydigan «Kompyuterimda tekshirish» amali. O‘rnatilgan tanlangan modellarni bir xil savol, kontekst va chiqish limiti bilan tekshirish; sovuq ishga tushish va xotirada turgan modelni alohida o‘lchash. Har holat kamida uch marta; median va natijalar oralig‘i ko‘rsatilsin. TTFT, umumiy vaqt, token/sekund va kuzatilgan RAM/VRAM; mavjud bo‘lmagan o‘lchov «noma’lum» bo‘lsin. O‘zbekcha javob sifati alohida namuna/to‘g‘ri javoblar bilan baholansin. Tez model avtomatik ravishda sifatli model deb hisoblanmasin.

`/api/ps` xotirada turgan modellar va ularning VRAM ma’lumotini beradi. Shu signal mavjud resurs o‘lchoviga qo‘shilishi mumkin. [Ollama running models](https://docs.ollama.com/api/ps).

Faol suhbat, nutq tanish va indekslash uchun umumiy ish navbati kerak: foydalanuvchining so‘rovi ustuvor, fon indekslash pauzalanadigan bo‘lsin. Modelni xotirada tutish keyingi javob boshlanishini tezlashtirishi, darhol bo‘shatish esa xotirani tejashi mumkin. Parallel so‘rovlar qo‘shimcha xotira sarflaydi. Flash Attention va KV-cache siqish server/backendga bog‘liq; ularni hamma kompyuterda majburan yoqish o‘rniga o‘lchangan, ixtiyoriy sinov kerak. [Ollama FAQ](https://docs.ollama.com/faq).

**Tayyorlik mezoni:** bir xil yukda bazaviy holatga taqqoslash; bekor qilish ishlashi; UI javob berishi; xotira yetishmaganda boshqariladigan pasayish. «30% tezroq» kabi raqam faqat real taqqoslashdan keyin. Tashqi Ollama xizmatining global sozlamalari yashirincha almashtirilmasin.

**UI:** Sozlamalar → AI modeli / mavjud Diagnostika ichida. Bosh oynaga doimiy yangi resurs grafiklari kerak emas.

## 3. OCR va lokal rasm tahlili

**Aniqlangan holat:** lokal PDF yo‘li `pypdf` matn ajratishidan foydalanadi; skanda matn bo‘lmasa xato qaytaradi. Lokal hujjat yo‘li rasm fayllarini qabul qilmaydi. Mavjud bulutli ekran imkoniyati bu cheklovni bartaraf etmaydi.

**Taklif:** skan sahifasini lokal OCR qilish, matnni asl sahifaga bog‘lash; rasm/skrinshotni imkoniyati mos lokal vision modeliga berish. Oddiy OCR uchun katta vision modelini majburlamaslik. Noto‘g‘ri aylantirilgan, xira va jadval sahifalari alohida sinovdan o‘tsin.

Tesseract rasmiy ro‘yxatida `uzb` va `uzb_cyrl` tillari mavjud. Bu tayyor nomzod, aniqlik natijasi emas. [Tesseract tillari](https://tesseract-ocr.github.io/tessdoc/Data-Files-in-different-versions.html). Ollama vision modeli matn bilan birga rasmlarni qabul qilishi mumkin; tanlangan model mosligi tekshirilsin. [Ollama vision](https://docs.ollama.com/capabilities/vision).

**Tayyorlik mezoni:** lotin/kirill o‘zbekcha va ruscha skanlar, sanalar/raqamlar va jadvallar. Manba bosilganda aynan o‘qilgan sahifa ko‘rinsin. Matnli PDF qayta OCR qilinmasin. Jarayon bekor qilinishi va ish hajmi chegaralanishi kerak.

**UI:** mavjud biriktirish joyi; skrinshot uchun foydalanuvchi tanlagan hudud. Sozlash va model tayyorlash Sozlamalarda.

## 4. Ollama uchun vositalar va tartibli natijalar

**Aniqlangan holat:** `core/ollama_chat.py:bounded_messages()` lokal yordamchida vositalar yo‘qligini aniq aytadi. Ilovaning boshqa provayderdagi amallari Ollama suhbatiga avtomatik ulanmagan.

**Taklif:** dastlab kalkulyator, tanlangan hujjatda qidirish va foydalanuvchi tanlagan faylni o‘qish. Keyin «hujjatdan vazifalar jadvali», «hisob-fakturadan maydonlar», JSON/CSV eksporti. Mavjud ruxsat va amallar siyosatini qayta ishlatish; modelning oddiy «bajardim» matni haqiqiy bajarilgan amal deb hisoblanmasin.

Ollama tool calling modeldan vosita chaqiruvini olish va natijani suhbatga qaytarishni qo‘llaydi. [Tool calling](https://docs.ollama.com/capabilities/tool-calling). JSON schema bilan tartibli chiqish olish va uni Python tarafida qayta tekshirish mumkin. Schema shaklni tekshiradi; faktlar to‘g‘riligini tasdiqlamaydi. [Structured outputs](https://docs.ollama.com/capabilities/structured-outputs).

**Tayyorlik mezoni:** faqat mos modelda ishga tushish, argumentlarni tekshirish, chaqiruvlar soni/vaqt chegarasi, bekor qilish va takroriy yozishni oldini olish. Fayl yaratishdan oldin aniq natija ko‘rinsin. Lokal fayl vazifasi internetga o‘tib ketmasin.

**UI:** natija chatdagi jadval/fayl kartasi va mavjud faoliyat ko‘rinishida; yana bitta parallel boshqaruv paneli ochilmasin.

## 5. Istalgan xabardan shoxlanish va javob versiyalari

**Aniqlangan holat:** `brave_conversation.py:branch_last()` faqat oxirgi user xabaridan nusxa suhbat yaratadi. `brave_history.py` chatlar orasida ota-shox munosabatini saqlamaydi.

**Taklif:** istalgan user xabarini tahrirlab yangi shox ochish; javob versiyalari orasida ixcham almashtirish; ikki javobni yonma-yon taqqoslash. Qaysi model/profil bilan olinganini versiyaga bog‘lash.

**Tayyorlik mezoni:** asl suhbat va manbalar saqlansin; shox o‘chirilsa boshqa shox buzilmasin; qayta javob kerakli prefixdan olinsin. Faol javob paytidagi almashish hozirgi himoyalar bilan mos ishlasin.

**UI:** xabarning kontekst menyusi va kichik versiya tanlagichi. Alohida katta «branch dashboard» zarur emas.

## 6. Aniq faktlar va qarorlar xotirasi

**Aniqlangan holat:** xotira mavjud; u mahkamlangan matn va erkin xulosadan iborat. `summary_plan()` kirishni 6000 belgi bilan kesadi. Juda uzun bitta almashinuv kesilgan bo‘lsa ham butun juftlikni qamrab olindi deb belgilashi mumkin. Bu ma’lumot yo‘qolishi uchun aniq tekshiriladigan holat.

**Taklif:** avval qamrov hisobini matnning haqiqiy ko‘rilgan qismiga moslashtirish. Keyin qaror, talab, ochiq savol va foydalanuvchi tasdiqlagan faktlarni manba xabari bilan ajratish. Zid yangi talab eski faktni yashirincha almashtirmasin; o‘chirilgan faktni qayta xulosadan tiriltirmaslik kerak.

**Tayyorlik mezoni:** katta xabar, ko‘p bosqichli xulosa, qarorni o‘zgartirish, o‘chirish va suhbat shoxida noto‘g‘ri xotira qaytmasligi. «Saqlangan tarix» va «modelga yuborilgan kontekst» farqi ko‘rinadigan bo‘lsin.

**UI:** hozirgi Suhbat xotirasi oynasi ichida; umumiy global xotiraga o‘z-o‘zidan qo‘shilmasin.

## 7. Offline ovozning ikkinchi bosqichi

**Aniqlangan holat:** hozir lokal yozish → to‘xtatish → transkriptni tekshirish → yuborish mavjud. Windows TTS o‘rnatilgan tizim ovozlariga tayanadi. Hozirgi mashinadagi inglizcha/ruscha ovozlar o‘zbekcha TTS tayyor degani emas.

**Taklif:** birinchi navbatda o‘zbekcha STT sifat to‘plami: oddiy gap, sheva, raqam, ism, shovqin va ruscha bilan aralash gaplar. Model hajmi/til tanlovi va natijani tuzatish qulayligi. Keyin gap tugashini aniqlash, qisman transkript va foydalanuvchi gapira boshlaganda o‘qishni to‘xtatish.

Sherpa-onnx offline STT/TTS, streaming va VAD uchun texnik nomzod. Bu loyiha mavjudligi aynan o‘zbekcha yaxshi TTS modeli borligini tasdiqlamaydi; ovoz modeli, litsenziyasi va sifatini alohida tekshirish kerak. [Loyihaning rasmiy repozitori](https://github.com/k2-fsa/sherpa-onnx).

**Tayyorlik mezoni:** inson tekshirgan transkriptlarda so‘z xatolari, raqam/ism xatolari, ovozdan yuborishgacha kechikish va bekor qilish. Har bir yangi yozishda mikrofonning tanlangan qurilmasi ishlasin. Fon indeksi ovoz vaqtida resursni band qilmasin.

**UI:** mavjud Offline ovoz oynasi; avtomatik yuborish keyinchalik ixtiyoriy sozlama bo‘lishi mumkin.

## 8. Katta suhbatlar tezligi va tarix bo‘yicha navigatsiya

**Aniqlangan holat:** `ConversationLog` alohida xabar widgetlari va `QScrollArea`dan foydalanadi. Chat tiklanganda `brave_features.py` ko‘rinishga oxirgi 300 xabarni oladi; shu bilan birga SQLite tarixini to‘liq o‘qiydi. Bu bor limit, lekin eski xabarlarni bosqichma-bosqich ko‘rish imkoniyati o‘rnini to‘liq bosmaydi.

**Taklif:** tarixni sahifalab o‘qish, yuqoriga aylantirganda oldingi qismini yuklash, ko‘rinmayotgan xabarlar uchun yengil saqlash. Suhbat ichida topilgan so‘zga va manba xabariga sakrash. Zarur bo‘lsa Qt model/view arxitekturasiga bosqichli o‘tish. Qt bu arxitekturada ma’lumotni ko‘rinishdan ajratadi; tezlik foydasi bizning chatda o‘lchanishi kerak. [Qt model/view](https://doc.qt.io/qt-6/model-view-programming.html).

**Tayyorlik mezoni:** 1000 va 10 000 xabarli sun’iy tarixda ochilish vaqti, xotira va scroll holatini o‘lchash; uzun kod, manba va nusxalash ishlashi. Ko‘rinishdan tushgan xabar SQLite’dan yo‘qolmasin. Foydalanuvchi yuqorida o‘qiyotganda oqim uni pastga tortmasin.

## 9. Tayyor Windows ilovasi va barqaror yangilash

**Aniqlangan holat:** repoda Python launcher, requirements va yetishmayotgan paketlarni o‘rnatuvchi `core/installer.py` bor. Bu tayyor Windows installer bilan bir xil emas; tekshirilgan qidiruvda paketlash `.spec` yoki dependency lock fayli topilmadi.

**Taklif:** PyQt6 uchun tekshirilgan PyInstaller build, aniq versiyali dependency lock, audio/document funksiyalari uchun alohida tayyorlash, birinchi ishga tushirish diagnostikasi. Modellar asosiy ilova paketidan alohida qolsin. Yangilashdan oldin DB migratsiyasi va ilova ma’lumotlarini tiklash yo‘li tayyorlansin. Mavjud fayl amallarini undo qilish butun ilova bazasini tiklashdan boshqa vazifa.

PyInstaller Qt binding hooklarini qo‘llaydi; bir build ichida bir nechta Qt binding yig‘ilishi rad etilishi hujjatlashtirilgan. Loyiha PyQt6 bo‘lgani uchun boshqa Qt bindingni tasodifan olib kirishdan saqlanish kerak. [PyInstaller hook sozlamalari](https://pyinstaller.org/en/stable/hooks-config.html).

**Tayyorlik mezoni:** Python o‘rnatilmagan toza Windows mashinada ochish, internetsiz qayta ishga tushirish, oldingi baza bilan yangilash va buzilgan yangilashdan tiklash. Installer va updater alohida tekshirilsin; bundlerning o‘zi rollback bermaydi deb rejalashtirilsin.

## Amalga oshirish tartibi

1. Hujjat qidiruvi uchun belgilangan sinov to‘plami va hozirgi natijani yozish; keyin semantik indeks va dalil yetishmasligi holati.
2. Resurs navbati va takrorlanadigan model benchmarki; undan keyingina avtomatik sozlash qoidalarini o‘zgartirish.
3. OCR/vision va cheklangan lokal vositalar; mavjud fayl/manba/ruxsat oqimlarini qayta ishlatish.
4. Haqiqiy foydalanishga qarab shoxlar, xotira aniqligi, ovoz, katta tarix va Windows tarqatmasi.

Tema faqat Sozlamalarda qoladi. Yangiliklar mavjud Markaz, chat menyusi, biriktirish yoki Sozlamalar ichiga joylashadi. Bosh oynaning asosiy vazifasi suhbat bo‘lib qoladi.
