# Ollama lokal tezlik tekshiruvi — 2026-10-19

Tekshiruv foydalanuvchi aytgan Ollama javoblarining sekinligiga qaratildi. Real lokal API, Qt interfeysi, resurslar, eski loglar va avtomatik testlar tekshirildi. Barcha yangi chat sinovlarida sun’iy ma’lumot va vaqtinchalik tarix ishlatildi.

## Topilmalar va tuzatishlar

1. **Javobdan oldingi yashirin generatsiyalar.** `brave_local_chat.py` uzun tarixni ketma-ket uch marta xulosalashi mumkin edi. Har bir xulosa oddiy profilning to‘liq javob limitidan foydalanardi: Quality holatida har safar 1024 tokengacha. Endi bir foydalanuvchi xabari oldidan ko‘pi bilan bitta xulosa olinadi, chiqish 256 token bilan cheklanadi, kirish faol profilga mos keladi. Qolgan tarix keyingi xabarlarda qayta ishlanadi; xulosalanmagan qism bajarilgan deb belgilanmaydi. Xulosa 30 soniyada tugamasa, mavjud kontekst bilan javob davom etadi.

2. **Yordamchi diagnostika javobni ushlab turishi.** `/api/version` va `/api/ps` ketma-ket 8 soniyadan kutishi mumkin edi. Ular endi har biri 250 ms bilan cheklangan. Kechiksa, model versiyasi yoki xotiradagi holat noma’lum deb olinib, generatsiya davom etadi. Majburiy model tekshiruvlarining 8 soniyalik limiti saqlandi.

3. **Economy rejimida oraliq model tushirilishi.** Yashirin xulosa tugagach `keep_alive=0` modelni bo‘shatib, darhol keyingi asosiy javob uchun qayta yuklashga olib kelardi. Xulosa modelni vaqtincha saqlaydi; foydalanuvchiga beriladigan javob Economy’ning odatiy bo‘shatish siyosatini ishlatadi.

4. **Vosita chaqiruvidan keyingi javob.** Tugagan HTTP javobining callback’i yangi vosita davomiyligini o‘chirib yuborishi mumkin bo‘lgan holat tuzatildi. Oxirgi JSON satri yangi qatorsiz kelishi ham tekshirildi. Bu tezlikdan tashqari lokal vositalar ishonchliligini yaxshilaydi.

5. **Amaldagi lokal sozlama.** Tekshiruv boshida asosiy provider `gemini`, Ollama profili `quality` edi. Endi provider `ollama`, profil `balanced`; model `llama3.2:latest`, avtomatik server ishga tushishi va thinking=off saqlandi. Boshqa sozlamalar tengligi dasturiy tekshirildi. Avvalgi tanlangan maydonlar kalitlarsiz `logs/local-settings-before.json` faylida saqlandi. Modelga yangi yuklab olish qilinmadi.

## Haqiqiy o‘lchovlar

Muhit: Windows, Python 3.12.13, Ollama 0.33.2, 31,8 GiB RAM, RTX 4060 Laptop GPU 8 GiB. `ollama ps` sinovlarda tanlangan modellar uchun **100% GPU** ko‘rsatdi. Tekshiruv boshida Ollama serveri ishlamayotgan edi; mavjud o‘rnatilgan server loyiha mexanizmi orqali ishga tushirildi.

| Sinov | Birinchi javob matni | Umumiy vaqt | Izoh |
| --- | ---: | ---: | --- |
| Llama, Quality, dastlabki sovuq sinov | 4,718 s | 5,000 s | Model yuklash 4,224 s |
| Llama, Quality, xotirada tayyor | 0,093 s | 0,171 s | Qisqa sun’iy savol |
| Llama, Balanced, dastlabki sovuq sinov | 2,547 s | 2,657 s | Model yuklash 2,316 s |
| Llama, Balanced, tuzatishdan keyingi sovuq sinov | 3,781 s | 4,062 s | Sovuq yuklash vaqti o‘zgaruvchan |
| Llama, Balanced, tuzatishdan keyin xotirada tayyor | 0,078 s | 0,328 s | Taxminan 104 token/s |
| To‘liq Qt chat, 24 ta uzun sun’iy tarix xabari | 1,000 s | 1,312 s | Bitta yashirin xulosa va asosiy javob |

To‘liq UI sinovida yangi user/assistant juftligi bir marta saqlandi, keyin yozilgan qoralama saqlandi, 20 ms tekshiruv taymerining eng katta oralig‘i 47 ms bo‘ldi. Skrinshot: `logs/ollama-ui-after.png`.

Bu kichik miqdordagi sun’iy sinovlar: 0,093 → 0,078 s farqni universal tezlashish foizi deb hisoblash mumkin emas. Sovuq model yuklashini kod tuzatishi yo‘qotmaydi. Asosiy tuzatishlar uzoq yashirin ish va nosog‘lom diagnostika kutishlarini chegaralaydi.

`qwen2.5-coder:7b` ham mavjud o‘rnatilgan model sifatida tekshirildi: birinchi sovuq yuklash 13,07 s, xotirada birinchi javob 0,109 s, generatsiya taxminan 56 token/s. Shu oddiy o‘zbekcha savolda Qwen javoblari ravonroq chiqdi; Llama ayrim javoblarda gap mazmunini noto‘g‘ri ifodaladi. Bu til sifati bo‘yicha umumiy benchmark emas. Tezlik ustuvorligi sabab kichik Llama modeli saqlandi. Kod optimizatsiyasi modelning o‘zbekcha bilimini o‘zgartirmaydi.

## Tasdiqlash va qayta tekshirish

- Boshlang‘ich to‘plam: **181 test — OK**.
- Tuzatishlardan keyin: **185 test — OK**, 79,28 s. Yangi tekshiruvlar yordamchi timeout, yangi qatorsiz vosita javobi, chiqish token limiti, bitta chegaralangan xulosa va Economy’da qayta yuklashni oldini olishni qamrab oladi.
- `python -m pip check`: **No broken requirements found**.
- Haqiqiy model va Qt integratsiyasi: muvaffaqiyatli, suhbat tarixi vaqtinchalik katalogda.

PowerShell, loyiha papkasida:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts\benchmark_ollama.py --profiles balanced --output logs\ollama-check.json
.\.venv\Scripts\python.exe scripts\smoke_ollama_ui.py --long-history --output logs\ollama-ui-check.json
```

`benchmark_ollama.py --cold` tanlangan modelni avval xotiradan chiqaradi. Oddiy tekshiruvda boshqa mijoz ishlatayotgan modelni tushirmaslik uchun `--cold` kerak emas. `--model` faqat allaqachon o‘rnatilgan lokal modelni sinaydi. `profile_local.py` serverga generatsiya yubormasdan UI chizilishi va sun’iy oqim xarajatini o‘lchaydi.

Xom natijalar: `logs/ollama-before.json`, `logs/ollama-after.json`, `logs/ollama-qwen7b.json`, `logs/ollama-ui-after.json`; test logi: `logs/local-fix-tests.log`. Lokal manba o‘zgartirildi; oldin yig‘ilgan `dist/` EXE qayta yig‘ilmadi. Yangilangan kodni `start.ps1` orqali ochish mumkin.

## Rasmiy manbalar

- [Ollama FAQ](https://docs.ollama.com/faq): GPU/CPU joylashuvi, modelni saqlash va yuklash.
- [Ollama usage metrics](https://docs.ollama.com/api/usage): yuklash, prompt va chiqish tokenlari vaqtini ajratish.
- [Ollama context length](https://docs.ollama.com/context-length): kontekst va resurslar munosabati.

O‘lchovlar ushbu loyihaning real testlaridan olindi; manbalar API parametrlarini talqin qilish uchun ishlatildi.
