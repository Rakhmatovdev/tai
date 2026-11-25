# Oltita yangi lokal AI oqimi

Keyingi yangilanish `/` menyu, uchrashuv avto-saqlashi, aniqroq nutq rejimi, crop/redact, ko‘p faylli kod va test runner, hamda o‘lchangan routingni qo‘shdi: [joriy qo‘llanma](SLASH_AND_RELIABILITY.md). Quyidagi dastlabki sinovlar tarixiy dalil sifatida saqlangan.

Kirish: **Chat → … → AI Studio** yoki **Ctrl+K → AI Studio**. Asosiy oynalar UZ/EN/RU va Dark/Light/Hacker mavzulariga mos. Manba `start.ps1` orqali ishlaydi; oldingi `dist/` EXE bu o‘zgarishlar bilan qayta yig‘ilmagan.

## Ekranni tushunish

**Ekran tahlili**da monitorni tanlang va **Ekranni olish · 1 soniya**ni bosing. Brave oynalari vaqtincha yashiriladi, tanlangan monitorning bitta rasmi olinadi va oynalar qaytadi. Ekran ruxsati kerak. Bu avtomatik kuzatuv yoki takroriy capture emas.

Rasmni tekshiring, savol yozing va **Ekranni lokal AI bilan tahlil qilish**ni bosing. Faqat shu bosqichda rasm lokal Ollama Vision modeliga beriladi. O‘rnatilgan mos model avtomatik tanlanadi; default model sozlamasi o‘zgarmaydi. Rasm matni buyruq sifatida bajarilmaydi. Tugma bosish yoki ilovani boshqarish bu tahlilning vazifasi emas. Rasm RAM’da, eng katta tomoni 2048 piksel; **Rasmni tozalash** yoki oynani yopish uni tozalaydi.

## Jonli uchrashuv va vazifalar

**Uchrashuv → Jonli uchrashuvni boshlash** mikrofonni yoqadi. O‘rnatilgan lokal Whisper modeli kerak; tahlil paytida model yuklanmaydi. Matn odatda 8 soniyalik qismlar tanilgach yangilanadi; haqiqiy kechikish model va inference navbatiga bog‘liq. Bu so‘zma-so‘z streaming STT emas. Mikrofon chat yozuvi bilan bir vaqtda ochilmaydi.

**Jonli vazifalarni yangilash** yozuv davomida joriy transkript nusxasidan qaror va vazifalarni chiqaradi. Qaydlar oxirgi yangilangan nusxaga tegishli; yangi gaplardan keyin yana bosing. **Yozuvni tugatish** mikrofonni yopadi va oxirgi nutqni tanib tugatadi. **Bekor qilish** kutayotgan ishlarni bekor qiladi. Transkriptni tekshiring, keyin yakuniy **Xulosa va vazifalar** va eksportdan foydalaning.

Faqat mikrofon olinadi, kompyuterning system audio oqimi olinmaydi. Audio faylga yozilmaydi. 2 soat, 160 ming belgi va ko‘pi bilan 60 soniyalik navbat chegaralari bor. Tanib olish ortda qolsa, audio yashirin tashlanmaydi: yozuv to‘xtaydi va xato ko‘rsatiladi. Mikrofon ruxsati olib tashlansa capture yopiladi. Yozuv/recognition fon oqimlarida ishlaydi.

## Gapiruvchilarni ajratish

**Gapiruvchi modelini tayyorlash · 26.5 MB** rasmiy WeSpeaker ONNX modelini bir marta yuklaydi. Yuklash internet ruxsatini talab qiladi, bekor qilinadi va SHA-256 tekshiriladi. Model `%LOCALAPPDATA%/Brave/speaker-models/`ga saqlanadi. Ushbu kompyuterda model tayyorlandi. **Gapiruvchilarni ajratish** checkbox’i audio import va jonli yozuvga qo‘llanadi.

Silero VAD nutq qismlarini topadi; 3 soniyagacha bo‘lgan qismlardan Kaldi-compatible 80-bin fbank va WeSpeaker 256 o‘lchamli embedding olinadi. Normalangan vektorlar online cosine threshold 0.55 bilan, ko‘pi bilan 8 ta markazga ajratiladi. Yetarli o‘xshashlik bo‘lmasa limitdan keyin `Speaker ?` chiqadi. Yorliqlar shu yozuv ichida saqlanadi; boshqa uchrashuvda qayta boshlanadi. Bu shaxsni tanish emas. Qisqa gaplar, shovqin va ustma-ust nutqda xato bo‘lishi mumkin. Model inglizcha VoxCeleb ma’lumotida tayyorlangan; o‘zbekcha diarizatsiya aniqligi bu ishda baholanmadi.

Attribution: [WeSpeaker ResNet34-LM](https://huggingface.co/Wespeaker/wespeaker-voxceleb-resnet34-LM), **CC BY 4.0**, revision `f0c48c298fd835726c27956a5d617bad7115627e`. Model o‘zgartirilmagan. Frontend rasmiy [WeSpeaker inference](https://github.com/wenet-e2e/wespeaker/blob/master/wespeaker/cli/speaker.py) shakliga asoslangan. Model inference’i faqat lokal ONNX Runtime CPU orqali, Torch’siz bajariladi.

## Kod tuzatishini qo‘llash va qaytarish

**Kod tahlili**da alohida kod faylini tanlang. Talabni yozib **AI tuzatish tayyorlash**ni bosing. Kichik faylning to‘liq almashtirish taklifi diff oynasida ochiladi. Tugallanmagan/token chegarasiga yetgan javob qo‘llash oynasiga o‘tmaydi. Kirish profilga sig‘masa Sifat profilini yoki **Diff bilan tahrirlash**ni tanlang. Qo‘lda diff bilan tahrirlash 180 KB’gacha UTF-8 faylda ishlaydi.

Oynada yangi matnni tahrirlash va diffni ko‘rish mumkin. **Diffni tasdiqlab qo‘llash**gina aynan tanlangan faylni yozadi. Symlink/junction yo‘li, ma’lum maxfiy nom/qiymatlar va keyin o‘zgargan fayl qabul qilinmaydi. BOM va mavjud CRLF odati saqlanadi. Dastlab zaxira olinadi, so‘ng vaqtinchalik fayl atomik almashtiriladi. Asl fayl hash’i qo‘llashdan oldin yana tekshiriladi.

**Oxirgi tuzatishni qaytarish** zaxirani tiklaydi; shu o‘zgarish umumiy Undo stekiga ham yoziladi. Fayl keyin tashqaridan o‘zgargan bo‘lsa tiklash uni bosib ketmaydi. Zaxiralar mavjud file-backup registrida diskka saqlanadi. Git tahlili hanuz o‘qish rejimida; ko‘p faylli avtomatik patch yoki testlarni bajarish qo‘shilmagan.

## Vazifaga qarab model tanlash

**Model tavsiyasi → Vazifaga qarab modelni avtomatik tanlash → AI sozlamalarini saqlash**. Odatda o‘chiq. Faqat o‘rnatilgan lokal completion modellari ishlatiladi. Kod kalit so‘zlari/markdown kod bloki → code, rasm → vision, qolganlari → text. Bu klassifikator oddiy qoida, AI sifat benchmark’i emas.

Oldingi tavsiya reytingi va taxminiy xotira mosligi ishlatiladi. Tools yoqilgan chat uchun tools imkoniyati ham talab qilinadi. Metadata 60 soniya keshlanadi; bu modelni preload yoki download qilmaydi. Tanlov faqat joriy so‘rovga tegishli: saqlangan default model/provider o‘zgarmaydi. Asosiy chat, matn amallari, Studio tahlili va kod takliflari ulanadi. Screen tahlili aniq rasm amali bo‘lgani uchun o‘rnatilgan Vision modelini o‘zi tanlaydi. Model nomi chat vazifa paneli va tahlil yakunida ko‘rinadi.

## Rasm bo‘yicha keyingi savol

Vision bilan muvaffaqiyatli javob olingach, keyingi savolda rasmni qayta biriktirish shart emas. Oxirgi rasm to‘plami faqat shu chat uchun ishlatiladi; yangi rasm eski to‘plamni almashtiradi. Xatoli/bekor qilingan so‘rov rasmni saqlamaydi. Keyingi xabarga hozirgi rasm piksellari qayta beriladi; rasm tarixiy matn xulosasi bilan taxmin qilinmaydi.

Chegara: har chatda 3 rasm, encoded to‘plam 24 MB, eng ko‘pi 4 ta chatning oxirgi rasmlari RAM’da. Piksellar SQLite yoki boshqa disk fayliga yozilmaydi. App/backend yopilganda unutiladi. **Suhbatdagi oxirgi rasmni eslab turish**ni o‘chiring yoki **Rasm kontekstini unutish**ni bosing. Davom etayotgan so‘rov tugasa ham unutilgan rasm qayta saqlanmaydi. Fayl ruxsati kerak. Matnli default model bilan davom ettirish uchun Vision modelini tanlang yoki avtomatik routingni yoqing.

## Tekshiruv dalillari

Yangi xulq-atvor tekshiruvlari `tests/test_ai_extensions.py`da: rasm/chat izolyatsiyasi va unutish, kech retention, routing/capabilities, diff/apply/undo/conflict, permission revoke, yarim kod javobi, capture-preview-analysis, mikrofon yopilishi, oxirgi audio drain va yozuv davomidagi vazifalar. `tests/test_ai_studio.py` 6 tab × 3 mavzu × 3 tilni tekshiradi.

Haqiqiy modellar bilan foydalanuvchi ma’lumotlarisiz sinov (`scripts/smoke_ai_extensions.py`):

| Sinov | Natija |
| --- | --- |
| 27.51 s sun’iy Irina/Zira ovozi, simulated microphone transport | 4.02 s processing; navbatlashgan Speaker 1/2 yorliqlari qaytdi |
| Kod routing | `qwen2.5-coder:7b`, saqlangan `llama3.2:latest` o‘zgarmadi |
| Nolga bo‘lish uchun to‘liq kod taklifi | 3.91 s; ValueError tekshiruvi diffda, qo‘llash va baytma-bayt tiklash ishladi |
| Sun’iy ekran rasmini tushuntirish | 26.20 s sovuq model bilan; ZeroDivisionError to‘g‘ri aniqlandi |
| Qizil rasm va biriktirmasiz keyingi savol | `qwen3.5:9b` ikkala safar `red` dedi |

Bu vaqtlar umumiy tezlik/aniqlik benchmark’i emas. Mikrofon transporti sun’iy oqim bilan, STT, VAD va embedding esa haqiqiy lokal modellar bilan tekshirildi. Transkriptda bir raqam `$42` o‘rniga `$1.2` deb tanildi; raqam, ism va vazifalarni audio/manba bilan tekshirish kerak. Odamlar bilan jonli uchrashuv sifati baholanmadi.

Yangi oqimlar uchun **19 test**, to‘liq to‘plamda **254 test — OK (113.541 s)**. `pip check` — buzilgan talab topilmadi. **54** Studio ko‘rinishi (6 tab × 3 mavzu × 3 til) tekshirildi; qorong‘i mavzudagi ScrollArea oq fon muammosi tuzatildi.

Dalillar: `logs/extensions-real-smoke.json`, `logs/extensions-real-run.log`, `logs/extensions-final-tests.log`, `design-preview/ai-studio/`.
