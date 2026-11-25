# Brave: keyingi rivojlantirish uchun tadqiqot

Tekshiruv sanasi: 2026-10-16. Asos: joriy loyiha kodi va quyida berilgan rasmiy manbalar. Bu hujjat tavsiyalarni beradi; ilovaga yangi imkoniyatlar hali qo‘shilmadi. Ushbu tadqiqot davomida yangi tezlik benchmarki yoki ovoz sifati sinovi o‘tkazilmadi.

Keyingi amalga oshirish holati: foydalanuvchining «go add» topshirig‘idan so‘ng 1-banddagi model mosligi va 2-banddagi tezlik diagnostikasi qo‘shildi; 119 ta test o‘tdi. Avtomatik profilning tezlikka qarab o‘zini sozlashi keyingi ish bo‘lib qoladi. Quyidagi «koddagi holat» yozuvlari tadqiqot vaqtidagi boshlang‘ich holatni tasvirlaydi. Bajarilgan o‘zgarishlar va sinovlar `readme.md` hamda `design-preview/appearance/README.md`da yozilgan.

«All add» topshirig‘idan keyin suhbat xotirasi, model yuklash, oxirgi xabarni tahrirlash/qayta javob, manbali offline hujjatlar, restart talab qilmaydigan provayder almashishi va Windows offline ovozi qo‘shildi. 143 ta test o‘tdi. Hujjat qidiruvi hozir lokal so‘zlar asosida; semantik embedding indeksi va o‘zbekcha ovoz sifati bo‘yicha benchmark keyingi ish bo‘lib qoladi. Ishlatish va tekshiruvlar: `LOCAL_FEATURES.md`.

**Tavsiya:** birinchi navbatda model mosligini aniqlash va tezlikni o‘lchashni qo‘shish. Keyin suhbat konteksti va model yuklashni yaxshilash. Bular keyingi offline fayl, rasm va ovoz imkoniyatlariga tayanch bo‘ladi.

## Hozir mavjud bo‘lgan asos

- Ollama orqali lokal matnli chat, model tanlash va qidirish, oqimli javob, bekor qilish, xizmatni avtomatik ishga tushirish.
- Avtomatik / Tejamkor / Muvozanatli / Sifat profillari, bo‘sh RAM va NVIDIA GPU xotirasini hisobga olish.
- Chat tarixi, eksport, loyiha konteksti, buyruqlar qidiruvi, fokus rejimi, UZ/EN/RU va uchta tema.
- Tema va AI boshqaruvlari Sozlamalarda jamlangan.

Model tanlash, yana bir tema yoki takroriy boshqaruv paneli keyingi asosiy ehtiyoj emas. Tekshiruvda foydalanuvchining ishiga ko‘proq ta’sir qiladigan quyidagi bo‘shliqlar aniqlandi.

| Navbat | Taklif | Natija | Nisbiy murakkablik |
|---|---|---|---|
| 1 | Model imkoniyatiga mos so‘rov | Mos kelmaydigan model va parametrlar oldindan aniqlanadi | O‘rta |
| 2 | Tezlik diagnostikasi va resurs profilini aniqlashtirish | Nima sekinligi va qaysi profil foydaliligi o‘lchanadi | O‘rta |
| 3 | Uzun suhbat uchun boshqariladigan xotira | Eski qarorlar kontekstdan chiqib ketganda yo‘qolmaydi | O‘rta–katta |
| 4 | Ilova ichida model yuklash | Terminalga o‘tmasdan lokal model tayyorlanadi | O‘rta |
| 5 | Offline hujjatlar va mos modelda rasm tahlili | Foydalanuvchining fayllari bilan amaliy ish | Katta |
| 6 | Qayta ochmasdan Gemini / Ollama almashish | Ish jarayoni uzilmaydi | Katta |
| 7 | Offline ovozli suhbat | Internetsiz mikrofon orqali foydalanish | Katta |

Murakkablik baholari koddagi bog‘liqliklardan chiqarilgan muhandislik taxmini. Ular bajarish muddati yoki unumdorlik kafolati emas.

## 1. Model imkoniyatiga mos ishlash

**Koddagi holat:** `ChatRequest.shown()` model mavjudligi va remote metama’lumotini tekshiradi. `capabilities` va `thinking` imkoniyatlari ishlatilmaydi. So‘rovlarga doim `think=False` yoziladi. `chunk()` faqat `message.content`ni oladi; `done_reason`ni ajratmaydi.

**Qo‘shiladigan ish:** `/api/show` orqali modelning chat, thinking, vision va tool imkoniyatlarini aniqlash; mavjud maydonlar asosida mos so‘rov qurish. Faqat embedding ishlab chiqaradigan model chat uchun tanlansa, tushunarli izoh berish. Eski server metama’lumot bermasa, konservativ moslik yo‘lini ishlatish. Server versiyasini ham diagnostikada saqlash.

Thinking holatida kelayotgan faol oqimni javobsiz qolish bilan adashtirmaslik kerak: hozir matn kelgandagina idle timer yangilanadi. Holat matni faol bosqichni ko‘rsatsin; ichki reasoning matnini asosiy chatga chiqarish shart emas. Yakunlanish sababi javob limiti bo‘lsa, uni oddiy tugallangan javobdan ajratish kerak.

Rasmiy API model imkoniyatlari va thinking sozlamalarini e’lon qiladi. Thinking qiymatlari modelga qarab farqlanadi. Bu barcha modellarga bir xil sozlama berish o‘rniga metama’lumotga tayangan moslashtirishni asoslaydi. [Model ma’lumoti](https://docs.ollama.com/api-reference/show-model-details), [thinking](https://docs.ollama.com/capabilities/thinking).

**Tayyorlik mezoni:** oddiy chat modeli, embedding modeli, thinking modeli va eski server javobi bilan tekshiruv; noto‘g‘ri tanlov foydalanuvchi xabarini yo‘qotmasin; bekor qilingan yoki kechikkan oqim yangi chatga yozilmasin. Model almashganda kesh yangilansin.

**UI:** mavjud Sozlamalar → AI modeli ichidagi model ma’lumotiga ixcham imkoniyatlar izohi. Thinking boshqaruvi faqat uni qo‘llovchi modelda ko‘rinsin.

## 2. O‘lchanadigan optimizatsiya

**Koddagi holat:** avtomatik profil bo‘sh RAM/VRAM chegaralariga tayanadi. Tanlangan modelning xotiradagi holati va o‘lchangan tezligi siyosatga kiritilmagan. Transport yakuniy javob statistikasini saqlamaydi. Tejamkor profil `keep_alive=0` bilan har javobdan so‘ng modelni bo‘shatadi.

**Qo‘shiladigan o‘lchovlar:**

- Foydalanuvchi yuborganidan birinchi ko‘rinadigan javobgacha vaqt; tayyorlash va so‘rov vaqtlarini alohida yozish.
- Modelni yuklash vaqti, kirish/chiqish tokenlari va generatsiya tezligi.
- Tanlangan va amalda ishlatilgan profil, model/tag, server versiyasi, xato yoki yakunlanish sababi.
- Birinchi so‘rov va model xotirada turgan keyingi so‘rov natijalarini alohida ko‘rsatish.

Ollama chat API yakuniy javobda token sonlari va vaqtlarni beradi. Generatsiya tezligini `eval_count / eval_duration * 1e9` bilan hisoblash mumkin; bu to‘liq foydalanuvchi kutish vaqtiga teng emas. Nol yoki yo‘q davomiylikda ko‘rsatkichni noma’lum deb belgilash kerak. [Chat API](https://docs.ollama.com/api/chat).

**Keyingi siyosat:** xotirada allaqachon turgan modelni ham hisobga olish. Past bo‘sh VRAMning o‘zi har doim boshqa dastur bosimi degani emas. `/api/ps` tanlangan modelning mavjudligi, VRAM hajmi va kontekstini beradi; bu model yuklanishining foizi emas. [Ishlayotgan modellar](https://docs.ollama.com/api/ps).

Xotirani tejash va keyingi javobning tez boshlanishi alohida maqsadlar. `keep_alive=0` bo‘shatishni so‘raydi; uni har doim «eng tez profil» deb ko‘rsatish to‘g‘ri emas. Ushbu farqni o‘lchangan natijalar bilan tushuntirish lozim. [Rasmiy API, modelni bo‘shatish](https://github.com/ollama/ollama/blob/main/docs/api.md#unload-a-model).

**Tayyorlik mezoni:** bir xil model, kontekst va javob limiti bilan kamida uch marta takrorlangan taqqoslash; boshlang‘ich va xotiradagi model natijalari aralashtirilmasin. Loglarda prompt, fayl mazmuni yoki API kaliti bo‘lmasin. Muayyan tezlashuv foizi sinovsiz va’da qilinmasin.

**UI:** mavjud Diagnostika ichida tafsilotlar. Asosiy oynaga doimiy grafik va yangi tugmalar qo‘shish kerak emas.

## 3. Uzun suhbat xotirasi

**Koddagi holat:** `bounded_messages()` profilga qarab 1200/2800/6000 belgilik budjetdan foydalanadi. `LocalChat` operativ tarixni oxirgi 20 xabar bilan cheklaydi. To‘liq SQLite tarixi saqlanishi model hammasini ko‘rayotganini anglatmaydi.

**Taklif:** yaqindagi suhbat + eski qismlarning qisqa lokal xulosasi + foydalanuvchi mahkamlagan aniq faktlar. Masalan, loyiha talablari yoki kelishilgan nom suhbat boshida qolib ketmasin. Xulosani ko‘rish, tuzatish va o‘chirish mumkin bo‘lsin; u model yaratgan hosila ekanligi ma’lum bo‘lsin. Xotira chatlar orasida o‘z-o‘zidan aralashmasin.

Token budjeti model va javob uchun ajratilgan joyni hisobga olsin. Belgi sonini aniq token soni deb ko‘rsatmaslik kerak. Kontekstni shunchaki maksimal qilish xotira sarfini oshiradi. [Kontekst uzunligi](https://docs.ollama.com/context-length).

**Tayyorlik mezoni:** oldindan ma’lum faktlar uzoq suhbat oxirida ham topilsin; foydalanuvchi o‘chirgan fakt qayta qaytmasin; xulosa bekor qilinsa yoki yaratilmasa, tarix buzilmasin. Xulosa model xatolarini ham saqlab qolishi mumkinligi sababli uni tahrirlash zarur.

## 4. Model yuklash menejeri

**Koddagi holat:** o‘rnatilgan modellar tanlanadi; yetishmayotgan modelni Brave ichidan yuklash yo‘q.

**Taklif:** Sozlamalar → AI modeli ichida «Model yuklash» orqali aniq nom/tag, hajm ma’lum bo‘lsa disk tekshiruvi, yuklangan baytlar, to‘xtatish va qayta urinish. Dastlab hajm noma’lum bo‘lishi mumkin; bunday holatda soxta foiz chiqmasin. Yakuniy tekshiruv tugagachgina model tayyor deb belgilansin.

Rasmiy `/api/pull` oqimi qatlam digestini hamda `total`/`completed` maydonlarini beradi; hujjatda uzilgan yuklashni davom ettirish tasvirlangan. Qatlam foizini umumiy model foizi deb noto‘g‘ri ko‘rsatmaslik kerak. [Pull API tafsilotlari](https://github.com/ollama/ollama/blob/main/docs/api.md#pull-a-model).

Bu amal internet orqali model fayllarini oladi. U foydalanuvchi boshlagan alohida yuklash bo‘lsin; oddiy offline xabar yuborish avtomatik download boshlamasin. O‘rnatish tugagach mavjud model ro‘yxati yangilansin.

**Tayyorlik mezoni:** internet uzilishi, disk yetishmasligi, takroriy bosish va Sozlamalar yopilishi sinovdan o‘tsin. Brave oynasi oqimni yopishi serverdagi boshqa mijoz yuklashini ham bekor qilishi kafolati sifatida ko‘rsatilmasin.

## 5. Offline fayllar, manbali javoblar va rasm

Loyihada tanlangan loyiha fayllaridan kontekst yaratish mavjud. Ammo `LocalChat.submit()` barcha biriktirmalarni rad etadi. Shuning uchun lokal hujjatlar bilan ishlashni alohida ulash kerak.

**Birinchi bosqich:** tanlangan kichik TXT/Markdown/kod faylidan cheklangan matn yuborish; kesilgan joyni aniq bildirish. **Keyingi bosqich:** PDF/DOCX matnini ajratish, bo‘laklash, lokal indekslash, kerakli parchalarni qidirish va javobda fayl/sahifa manbasini ochish. Skan qilingan PDF uchun OCR alohida ish hisoblanadi.

Ollama embeddings API lokal semantik qidiruv uchun asos beradi; indeks va savol uchun bir xil embedding modelini ishlatish kerak. RAG javobning to‘g‘riligini o‘zi kafolatlamaydi: mos parcha yo‘q bo‘lsa «topilmadi» deyish va manba bilan tekshirish zarur. [Embeddings](https://docs.ollama.com/capabilities/embeddings).

Rasm tahlili boshqa yo‘l: vision qo‘llovchi modelga foydalanuvchi tanlagan rasm yuboriladi. Bu PDF matnini qidirish bilan bir imkoniyat emas. [Vision](https://docs.ollama.com/capabilities/vision).

**Tayyorlik mezoni:** manba havolasi aynan ishlatilgan parchani ochsin; o‘chirilgan hujjat indeksdan chiqsin; hujjatdagi buyruq matnlari tizim ko‘rsatmasi sifatida bajarilmasin. Katta indekslash GUI oqimini band qilmasin.

## 6. Provayderni qayta ochmasdan almashtirish

**Koddagi holat:** `start_backend()` ishga tushishda bir marta provayderni tanlaydi. Model/profilni yangilash bilan Gemini ↔ Ollama almashishi turli hayot sikllari.

**Taklif:** boshqariladigan backend holati: joriy ishni tugatish yoki bekor qilish → audio/tarmoq resurslarini yopish → eski callbacklarni chetlatish → yangi backendni tayyorlash. Draft va tarix saqlansin. Lokal suhbat tarixi bulutga avtomatik ko‘chirilmasin; yuboriladigan kontekst aniq boshqarilsin.

Bu tavsiya rasmiy API imkoniyatidan ko‘ra loyiha arxitekturasidan kelib chiqqan xulosa.

**Tayyorlik mezoni:** oqim paytida, voice paytida va tayyorlash bosqichida almashtirish; takroriy mikrofon oqimi, eski javob yoki ochiq qolgan socket bo‘lmasin. Boshqaruv Sozlamalarda qolsin.

## 7. Offline ovoz

**Koddagi holat:** `core/stt.py` ichida faster-whisper/Vosk, `core/tts.py` ichida Kokoro va boshqa TTS adapterlari bor. Ular lokal chat yo‘liga ulanmagan. STT/TTS eski kodida offline cheklovlarni olib tashlab model yuklashga urinish va TTS yordamchi kodida paket yangilashga urinish bor; yangi qat’iy offline yo‘lga buni o‘zgartirmasdan ulash yaramaydi.

**Taklif:** avval push-to-talk → lokal transkripsiya → Ollama → lokal ovoz. Model fayllarini alohida tayyorlash bosqichi va aniq «offline tayyor» holati bo‘lsin. CPU/GPU ulashishni LLM bilan birgalikda rejalash kerak. Keyin VAD va gapni bo‘lib o‘qish orqali kechikishni kamaytirish mumkin.

Faster-whisper CPU/GPU inferensiyasi, INT8 va VAD imkoniyatlarini hujjatlashtiradi; GPU yo‘li uchun kutubxona mosligi talab qilinadi. Boshqa qurilmalardagi benchmark bizdagi kechikishni isbotlamaydi. [faster-whisper](https://github.com/SYSTRAN/faster-whisper).

O‘zbekcha STT va TTS sifati alohida sinov talab qiladi. Ovoz dvigateli mavjudligi yaxshi o‘zbekcha talaffuz borligini anglatmaydi. O‘zbekcha lotin/kirill, ruscha aralash nutq, ism va raqamlar bilan foydalanuvchi yozuvlari kerak.

**Tayyorlik mezoni:** model fayllari tayyorlangach internet o‘chiq holatda to‘liq suhbat; yozuvni bekor qilish, mikrofon almashishi va ovoz chiqayotgan paytda to‘xtatish ishlasin. Yashirin download yoki cloud fallback bo‘lmasin.

## Sifatni tekshirish va UI tartibi

Har bosqichda kichik, takrorlanadigan baholash to‘plami kerak: UZ/EN/RU savollar, kod, uzun kontekst, noma’lum javob va offline cheklovlar. Model nomi/tagi, profil va o‘lchov sharoiti qayd etilsin. Funksional testlar javobning mazmuniy sifati benchmarkiga teng emas.

- Sozlamalar → AI modeli: model mosligi, yuklash, profil va provayder.
- Mavjud Diagnostika: tezlik, yuklash vaqti, amaldagi profil va server ma’lumoti.
- Mavjud chat menyusi: keyinchalik qayta javob olish yoki xabarni tahrirlab yuborish.
- Mavjud biriktirish oqimi: fayl va rasm; modelga mos bo‘lmaganda tushunarli izoh.
- Tema faqat Sozlamalarda qoladi; yangi tema yoki takroriy panel rejalashtirilmaydi.

Offline tool calling keyingi alohida bosqich bo‘lishi mumkin. Ollama buni qo‘llovchi modellarda tool chaqiruvlarini beradi, ammo amallarni dastur bajaradi. Mavjud ruxsat siyosati, argument tekshiruvi, vaqt/son chegaralari qayta ishlatilishi kerak. Birinchi bosqichni faqat o‘qish amallari bilan cheklash qulay. [Tool calling](https://docs.ollama.com/capabilities/tool-calling).

**Birinchi amalga oshirish paketi:** 1 va 2. Foydalanuvchi darhol modelning mosligini tushunadi, ishlab chiquvchi esa keyingi optimizatsiyani o‘lchangan dalil bilan tanlaydi. So‘ng 3 va 4 kundalik foydalanishni yaxshilaydi; 5–7 funksional imkoniyatlarni kengaytiradi.
