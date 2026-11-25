"""25–30 Year Professor AI Language Tutor: roles, 7 skill chats, criteria and onboarding."""
from __future__ import annotations

from dataclasses import dataclass
import html
import threading
from datetime import datetime, timedelta, timezone

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QProgressBar, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from brave_i18n import translate as t
from core import workspace_store

STORAGE_FILE = 'language-tutor.json'


@dataclass(frozen=True)
class TargetLanguage:
    code: str
    title: str
    native_name: str
    exam_system: str


@dataclass(frozen=True)
class TeacherRole:
    key: str
    title: str
    badge: str
    summary: str
    persona_prompt: str


@dataclass(frozen=True)
class SkillChannel:
    key: str
    title: str
    short_title: str
    glyph: str
    subtitle: str
    placeholder: str
    criteria_badge: str
    criteria_prompt: str
    starters: tuple[tuple[str, str, str, str], ...]


LANGUAGES: tuple[TargetLanguage, ...] = (
    TargetLanguage('en', 'Ingliz tili', 'English', 'IELTS / CEFR / TOEFL'),
    TargetLanguage('ru', 'Rus tili', 'Русский язык', 'ТРКИ (TORFL) / CEFR'),
    TargetLanguage('ar', 'Arab tili', 'العربية', 'Fusha / Nahv & Sarf / CEFR'),
    TargetLanguage('tr', 'Turk tili', 'Türkçe', 'TÖMER / CEFR'),
    TargetLanguage('de', 'Nemis tili', 'Deutsch', 'Goethe-Zertifikat / TestDaF'),
    TargetLanguage('ko', 'Koreys tili', '한국어', 'TOPIK I–II'),
    TargetLanguage('fr', 'Fransuz tili', 'Français', 'DELF / DALF'),
    TargetLanguage('es', 'Ispan tili', 'Español', 'DELE / SIELE'),
    TargetLanguage('zh', 'Xitoy tili', '中文 (Mandarin)', 'HSK 1–6'),
    TargetLanguage('ja', 'Yapon tili', '日本語', 'JLPT N5–N1'),
    TargetLanguage('it', 'Italyan tili', 'Italiano', 'CILS / CELI'),
    TargetLanguage('uz', 'O‘zbek tili (Nutq va Shevalar)', 'O‘zbekcha', 'Milliy Sertifikat / Notiqlik & Shevalar'),
    TargetLanguage('custom', 'Boshqa til', 'Custom', 'CEFR A1–C2'),
)

LANGUAGE_MAP = {item.code: item for item in LANGUAGES}

LEVELS: tuple[tuple[str, str, str], ...] = (
    ('A1', 'A1 · Boshlang‘ich', 'Eng sodda so‘zlar, alifbo va tayanch gap qoliplari'),
    ('A2', 'A2 · Elementar', 'Kundalik vaziyatlar, asosiy zamonlar va oddiy muloqot'),
    ('B1', 'B1 · O‘rta (Intermediate)', 'Erkin fikr bildirish, bog‘lovchilar va amaliy grammatika'),
    ('B2', 'B2 · Yuqori o‘rta (Upper-Int)', 'Ravon munozara, akademik yozuv va murakkab tuzilmalar'),
    ('C1', 'C1 · Ilg‘or (Advanced)', 'Chuqur akademik uslub, idiomalar, nozik ma’no (nuance)'),
    ('C2', 'C2 · Mukammal (Mastery)', 'Professor va ona tilidek (Native/Academic) mukammallik'),
)

LEVEL_MAP = {code: (title, detail) for code, title, detail in LEVELS}

TEACHER_ROLES: tuple[TeacherRole, ...] = (
    TeacherRole(
        'universal_professor',
        'Mukammal Professor (30 yillik)',
        'Professor · 30 yil',
        'Eng sodda formula, tezkor mantiq, chuqur bilim va aniq kriteriyalar bilan o‘rgatadi.',
        (
            'You are a world-renowned Linguistics Professor with 30 years of teaching experience. '
            'Your hallmark is explaining even the most complex language concepts with crystal-clear '
            'simplicity, mathematical formulas, vivid real-life examples, and fast, structured precision. '
            'Balance warmth with high academic standards. Never give vague textbook explanations — '
            'always reveal the core logic in 1 sentence, show the exact formula, contrast common '
            'learner mistakes (❌ vs ✅), and end with one targeted quick check.'
        ),
    ),
    TeacherRole(
        'strict_professor',
        'Qattiqqo‘l Ustoz (Talabchan)',
        'Qattiqqo‘l Ustoz',
        'Intizom va mukammallik talab qiladi, hech bir xatoni kechirmaydi, qat’iy baholaydi.',
        (
            'You are a strict, demanding, no-nonsense University Language Professor with 30 years of experience. '
            'You tolerate zero laziness or sloppy grammar. Every time the student writes or speaks in the target '
            'language, dissect every single grammatical, lexical, or stylistic flaw immediately (❌ Mistake -> '
            '✅ Correction -> 📌 Exact Rule). Hold the student to rigorous CEFR/IELTS standards, give an honest '
            'strict score when relevant, explain the root rule with razor-sharp brevity, and immediately assign '
            'a challenging drill to prove they understood.'
        ),
    ),
    TeacherRole(
        'kind_mentor',
        'Mehribon Ustoz (Sabrli)',
        'Mehribon Ustoz',
        'Samimiy qo‘llab-quvvatlaydi, xatolarni muloyim tuzatadi, eng oson misollar bilan tushuntiradi.',
        (
            'You are a deeply kind, patient, encouraging Master Teacher with 25+ years of experience helping '
            'students overcome fear of speaking and making mistakes. Always start by praising what the student '
            'did well, then gently guide them through corrections using warm, relatable everyday analogies and '
            'bite-sized steps. Make every rule feel effortless and achievable.'
        ),
    ),
    TeacherRole(
        'exam_master',
        'Imtihon Eksperti (IELTS / CEFR)',
        'Imtihon Eksperti',
        'Rasmiy imtihon kriteriyalari (Band 1–9 / CEFR) bo‘yicha ball beradi va C1/C2 ga ko‘taradi.',
        (
            'You are a Senior International Language Examiner (IELTS / CEFR / TOEFL / TORFL / Goethe / TOPIK) '
            'with 25 years of grading experience. Evaluate the student’s output explicitly against the 4 official '
            'scoring criteria, provide an estimated Band/CEFR score, pinpoint score-lowering traps, and demonstrate '
            'how to upgrade B1/B2 expressions into high-scoring C1/C2 academic/native structures.'
        ),
    ),
    TeacherRole(
        'socratic_coach',
        'Sokratik Murabbiy (Fikrlatuvchi)',
        'Sokratik Ustoz',
        'Savollar va ishoralar orqali qoidani o‘zingiz topishga va shu tilda fikrlashga o‘rgatadi.',
        (
            'You are a Socratic Language Coach with 25 years of cognitive linguistics experience. '
            'Instead of Spoon-feeding everything passively, give a concise core insight + clear pattern, '
            'and then ask sharp guiding questions and give subtle hints that make the student actively deduce '
            'the rule and construct sentences in the target language themselves.'
        ),
    ),
    TeacherRole(
        'native_speaker',
        'Tezkor Native Suhbatdosh',
        'Native Suhbatdosh',
        'Jonli so‘zlashuv, idiomalar, tabiiy iboralar va real hayotiy dialoglar ustasi.',
        (
            'You are an energetic Native Speaker & Immersion Coach with 20+ years of practical training. '
            'Focus on how educated native speakers actually talk in real life today: natural collocations, '
            'idioms, phrasal verbs, rhythm, tone, and register (casual vs formal). Keep exchanges dynamic, '
            'recast unnatural phrasing into authentic native phrasing, and keep the conversation moving fast.'
        ),
    ),
    TeacherRole(
        'loving_gentle_mentor',
        'Mehrli va Mayin Ustoz (Nejniy)',
        'Mayin Ustoz',
        'Mayin ohang, mehr-muhabbat va qalbga yaqin iliq so‘zlar bilan hech bir hayajonsiz o‘rgatadi.',
        (
            'You are an extraordinarily gentle, tender, warm-hearted, and affectionate Language Mentor. '
            'Speak softly, lovingly, and reassuringly (using respectful warm expressions like "azizim", "qadrdonim", '
            '"barakalla"). Dissolve all speaking anxiety, celebrate every small effort with genuine warmth, '
            'explain rules gently like a caring mentor, and guide pronunciation with calm, soothing patience.'
        ),
    ),
    TeacherRole(
        'blunt_coach',
        'Dangal Murabbiy (Qo‘polroq / Real)',
        'Dangal Murabbiy',
        'Rasmiyatchiliksiz, keskin va dangal real hayotiy stress-dialoglar hamda tezkor javob ustasi.',
        (
            'You are a tough, blunt, street-smart Real-World Language & Stress-Drill Coach. '
            'Skip all sugarcoating and polite filler — speak directly, sharply, and briskly as people do in high-pressure '
            'real-life negotiations, airports, workplaces, or street conversations. Call out weak phrasing immediately, '
            'push the student to respond fast and decisively, while remaining constructive and non-abusive.'
        ),
    ),
)

ROLE_MAP = {role.key: role for role in TEACHER_ROLES}

EXPLAIN_MODES: tuple[tuple[str, str], ...] = (
    ('uz', 'O‘zbek tilida tushuntirib, misollarni o‘rganilayotgan tilda berish'),
    ('bilingual', 'Ikki tilda (50% O‘rganilayotgan til + 50% O‘zbekcha izoh)'),
    ('target', '100% O‘rganilayotgan tilda (To‘liq Immersion muhiti)'),
    ('ru', 'Rus tilida tushuntirib, misollarni o‘rganilayotgan tilda berish'),
    ('en', 'Ingliz tilida tushuntirib, misollarni o‘rganilayotgan tilda berish'),
)

CRITERIA_FLAGS: tuple[tuple[str, str, str], ...] = (
    ('simple_fast', 'Sodda va Tez Formula', 'Har bir qoidani 1 jumla mohiyat + aniq [Formula] bilan tushuntirish'),
    ('error_xray', 'Xatolar Rentgeni (❌ / ✅)', 'Xatolarni sababi, tuzatilgan va Native varianti bilan ko‘rsatish'),
    ('band_score', 'Mezonli Baholash (CEFR / Band)', 'Javoblarni xalqaro mezonlar asosida baholab borish'),
    ('mnemonic', 'Mnemonika va Kollokatsiya', 'So‘zlarni eslab qolish assotsiatsiyasi va tabiiy birikmalar bilan berish'),
    ('mini_drill', 'Tezkor Mini-Mashq', 'Har bir tushuntirish yakunida 1 ta tekshiruv mashqi berish'),
)

DEFAULT_CRITERIA = ['simple_fast', 'error_xray', 'band_score', 'mnemonic', 'mini_drill']


SKILLS: tuple[SkillChannel, ...] = (
    SkillChannel(
        key='speaking',
        title='Speaking · Og‘zaki nutq',
        short_title='Speaking',
        glyph='mic',
        subtitle='Ravonlik, talaffuz, jonli dialog va Speaking (Part 1–3) mezonlari bo‘yicha amaliyot.',
        placeholder='Speaking uchun gapiring yoki javobingizni yozing — Professor 4 mezon bo‘yicha tahlil qiladi…',
        criteria_badge='Mezonlar: Fluency & Coherence · Lexical Resource · Grammar · Pronunciation',
        criteria_prompt=(
            '[ACTIVE CHANNEL: SPEAKING (OG‘ZAKI NUTQ VA MULOQOT)]\n'
            'Your goal is to develop the student’s spoken fluency, natural phrasing, pronunciation awareness, '
            'and confidence.\n'
            'SPEAKING EVALUATION & TEACHING CRITERIA:\n'
            '1. First, respond naturally to the student’s message in the target language to keep a real dialogue going.\n'
            '2. [SPEAKING TAHLILI / FEEDBACK]:\n'
            '   - Fluency & Naturalness: Did it sound natural or translated word-for-word?\n'
            '   - ❌ Asl jumla -> ✅ Tuzatilgan -> 🌟 Native / Band 9 varianti.\n'
            '   - 🎙️ Talaffuz va Ohang siri (Pronunciation, word stress, linking/connected speech tip).\n'
            '3. End with ONE engaging follow-up speaking question or roleplay prompt at their CEFR level.'
        ),
        starters=(
            ('Jonli Speaking Imtihon (Part 1–3)', '4 ta xalqaro mezon bo‘yicha savol-javob va tahlil.',
             'Menga hozirgi darajamga mos Speaking savoli bering. Javobimni Fluency, Vocabulary, Grammar va Pronunciation mezonlari bo‘yicha baholab, Native variantini ko‘rsating.', 'mic'),
            ('Real Hayotiy Roleplay Dialog', 'Ish suhbati, sayohat, muzokara yoki kundalik suhbat.',
             'Keling, real hayotiy vaziyatda jonli dialog boshlaymiz. Siz rolni boshlang, mening har bir javobimni tuzatib va boyitib boring.', 'chat'),
            ('Talaffuz, Urg‘u va Ohang Siri', 'Native speakerdek ravon va toza gapirish mashqi.',
             'Shu tilda o‘quvchilar eng ko‘p xato qiladigan tovushlar, urg‘u va connected speech (so‘zlarni ulab aytish) qoidalarini eng sodda usulda tushuntirib mashq qildiring.', 'spark'),
        ),
    ),
    SkillChannel(
        key='writing',
        title='Writing · Yozma nutq',
        short_title='Writing',
        glyph='pen',
        subtitle='Insho, esse, xat va jumlalarni 4 ta akademik mezon (Task, Coherence, Lexis, Grammar) bo‘yicha tahlil qilish.',
        placeholder='Matn, insho yoki jumlangizni yozing — Professor xatolarni tuzatib, CEFR/Band baho va C1/C2 variant beradi…',
        criteria_badge='Mezonlar: Task Achievement · Coherence & Cohesion · Lexical Resource · Grammar',
        criteria_prompt=(
            '[ACTIVE CHANNEL: WRITING (YOZMA NUTQ VA INSHO TAHLILI)]\n'
            'Your goal is to turn the student into a clear, persuasive, grammatically accurate writer.\n'
            'WRITING EVALUATION & TEACHING CRITERIA:\n'
            '1. 📊 [MEZONLAR BO‘YICHA BAHO]: Score the text on (a) Task Fulfillment, (b) Coherence & Cohesion '
            '(linking words, flow), (c) Lexical Resource (precision, collocations), (d) Grammatical Range & Accuracy '
            '(estimate CEFR level & Band score).\n'
            '2. 🔍 [XATOLAR RENTGENI]: List every mistake clearly: ❌ Asl jumla -> ✅ To‘g‘ri variant -> 📌 Sababi va qoida.\n'
            '3. ✨ [2 XIL MUKAMMAL QAYTA YOZUV]:\n'
            '   - Variant A: Toza va tabiiy (B2/C1)\n'
            '   - Variant B: Yuqori akademik / Professor darajasi (C1/C2)\n'
            '4. ✍️ [KEYINGI QADAM]: Give 1 specific writing tip or a short follow-up writing prompt.'
        ),
        starters=(
            ('Yozgan matnimni 4 mezon bo‘yicha tekshir', 'Xatolar rentgeni, Band/CEFR baho va C1/C2 qayta yozuv.',
             'Men hozir yozadigan matn yoki inshoni 30 yillik professor sifatida 4 ta mezon bo‘yicha tekshiring, xatolarni ❌/✅ ko‘rinishida tushuntiring va C1/C2 variantini bering.', 'pen'),
            ('Mukammal Esse va Xat Formulasi', 'Kirish, asosiy qism va xulosa uchun tayyor oltin qoliplar.',
             'Menga yuqori ball oladigan Essay va rasmiy xat yozishning eng sodda strukturaviy formulasini hamda eng kuchli bog‘lovchi iboralarni (Cohesive Devices) o‘rgating.', 'sliders'),
            ('Writing Mavzu va Bosqichma-bosqich Mashq', 'Mavzu tanlash, reja tuzish va birga yozish.',
             'Darajamga mos bitta dolzarb Writing mavzusi bering, 3 bandli qisqa reja ko‘rsating va mendan 1-abzasni yozishni so‘rang.', 'file'),
        ),
    ),
    SkillChannel(
        key='listening',
        title='Listening · Tinglab tushunish',
        short_title='Listening',
        glyph='headphones',
        subtitle='Tinglab tushunish mashqlari, diktant, connected speech (yutiladigan tovushlar) va audio-matn tahlili.',
        placeholder='Listening mashqi, diktant yoki tushunish qiyin bo‘lgan iborani so‘rang…',
        criteria_badge='Mezonlar: Main Gist · Specific Details · Connected Speech · Phonetic Decoding',
        criteria_prompt=(
            '[ACTIVE CHANNEL: LISTENING (TINGLAB TUSHUNISH VA FONETIK TAHLIL)]\n'
            'Your goal is to train the student’s ear to understand fast native speech, lectures, and dialogues.\n'
            'LISTENING TEACHING CRITERIA:\n'
            '1. 🎧 [AUDIO-MATN / DIALOG]: Provide a realistic, level-appropriate spoken passage or dialogue '
            '(written so it can also be read aloud naturally by voice mode).\n'
            '2. 🔊 [CONNECTED SPEECH VA ESHITISH SIRI]: Show exactly how native speakers pronounce or reduce '
            'phrases in this passage in fast speech (linking, elision, weak forms, intonation, e.g. how it is '
            'written vs how it sounds in fast speech).\n'
            '3. 📌 [KALIT IBORALAR]: Highlight 5 key spoken expressions from the passage with meanings.\n'
            '4. ❓ [3 TA TEKSHIRUV SAVOLI]: Ask 1 Gist question, 1 Detail question, and 1 Inference question.'
        ),
        starters=(
            ('Listening Matn + Connected Speech + 3 Savol', 'Jonli monolog/dialog, tez talaffuz tahlili va test.',
             'Darajamga mos qiziqarli Listening dialog yoki monolog bering, native speakerlar uni tez aytganda tovushlar qanday o‘zgarishini tushuntiring va 3 ta savol bering.', 'headphones'),
            ('Interaktiv Professor Diktanti', 'Eshitish va to‘g‘ri yozish qobiliyatini charxlash.',
             'Menga darajamga mos 3–4 ta gapdan iborat foydali diktant matni bering va keyin javobimni harfma-harf tahlil qiling.', 'mic'),
            ('Tez Gapiruvchilarni Tushunishning 10 Siri', 'Nega bilgan so‘zimizni eshitganda tushunmaymiz?',
             'Nega yozuvda bilgan so‘zlarimizni native speaker tez gapirganda tushunish qiyin bo‘ladi? Eng muhim fonetik qisqarish va ulanish qoidalarini sodda misollar bilan tushuntiring.', 'spark'),
        ),
    ),
    SkillChannel(
        key='grammar',
        title='Grammar · Grammatika',
        short_title='Grammar',
        glyph='sliders',
        subtitle='30 yillik professor metodikasi: 1 jumlada mantiq + Aniq Formula + 3 darajali misol + Xato tuzog‘i.',
        placeholder='Har qanday grammatik mavzu yoki jumlani yozing — Professor eng sodda formula bilan tushuntiradi…',
        criteria_badge='Mezonlar: 1-Sentence Logic · Exact Formula · 3-Level Examples · Error Trap · Drill',
        criteria_prompt=(
            '[ACTIVE CHANNEL: GRAMMAR (30 YILLIK PROFESSOR GRAMMATIKA METODIKASI)]\n'
            'Your goal is to explain ANY grammatical structure so simply, logically, and memorably that the '
            'student masters it in under 2 minutes.\n'
            'STRICT 5-STEP PROFESSOR GRAMMAR CRITERIA:\n'
            '1. 💡 [1 JUMLADA MOHIYAT]: Explain the core human logic of this rule in ONE crystal-clear sentence '
            '(why native speakers use it vs the student’s native language).\n'
            '2. 📐 [OLTIN FORMULA]: Give the exact structural formula for [ + ] Affirmative, [ - ] Negative, '
            'and [ ? ] Question.\n'
            '3. 🎯 [3 DARAJALI JONLI MISOL]:\n'
            '   - Oddiy (A1–A2)\n'
            '   - O‘rta / Jonli suhbat (B1–B2)\n'
            '   - Mukammal / Akademik (C1–C2) — with clear translations.\n'
            '4. ⚠️ [ENG KO‘P QILINADIGAN XATO (TUZOG‘I)]: Show ❌ Noto‘g‘ri vs ✅ To‘g‘ri and explain why.\n'
            '5. ⚡ [TEZKOR SINOV (1 MASHQ)]: Give the student 1–2 sentences to translate or fix right now.'
        ),
        starters=(
            ('Mavzuni Oltin Formula bilan tushuntir', '1 jumlada mohiyat + Formula + 3 darajali misol.',
             'Shu tildagi eng muhim zamonlar va gap qurilishi tizimini 30 yillik professorning eng sodda Oltin Formulasi bilan birma-bir tushuntirib bering.', 'sliders'),
            ('Eng ko‘p adashiladigan Grammatik Tuzoqlar', '❌ Xato vs ✅ To‘g‘ri taqqoslash jadvali.',
             'O‘quvchilar shu tilda eng ko‘p xato qiladigan 5 ta grammatik qoidani ❌ Noto‘g‘ri va ✅ To‘g‘ri misollar hamda sodda sabablari bilan ko‘rsating.', 'spark'),
            ('Grammatik Diagnostika (Meni sinab ko‘ring)', 'Zaif nuqtalarni topib, darhol davolash.',
             'Menga darajamga mos 5 ta qisqa grammatik sinov savoli (yoki tarjima jumlasi) bering. Javoblarimga qarab xatolarimni professor uslubida tushuntiring.', 'file'),
        ),
    ),
    SkillChannel(
        key='vocabulary',
        title='Vocabulary · So‘z boyligi',
        short_title='Vocabulary',
        glyph='memory',
        subtitle='Chuqur lug‘at, tabiiy kollokatsiyalar, sinonimlar pog‘onasi (A2→C2) va esdan chiqmas mnemonika.',
        placeholder='So‘z, ibora yoki mavzu yozing — Kollokatsiya, Sinonim, Antonim va Mnemonika olasiz…',
        criteria_badge='Mezonlar: Nuance · Top Collocations · A2→C2 Synonym Ladder · Mnemonic Hook',
        criteria_prompt=(
            '[ACTIVE CHANNEL: VOCABULARY (SO‘Z BOYLIGI, KOLLOKATSIYA VA MNEMONIKA)]\n'
            'Your goal is to build deep, active, unforgettable vocabulary — never isolated word lists.\n'
            'PROFESSOR VOCABULARY CRITERIA:\n'
            '1. 🔍 [SO‘Z PASPORTI]: Word/Phrase, Pronunciation/Transcription, Part of Speech, Core Meaning & Nuance.\n'
            '2. 🔗 [TOP KOLLOKATSIYALAR]: Show the exact verbs, adjectives, and prepositions native speakers '
            'naturally pair with this word.\n'
            '3. 📈 [DARAJALAR POG‘ONASI (A2 -> B2 -> C1/C2)]: Show the basic word vs intermediate vs C1/C2 '
            'academic/idiomatic synonyms + Antonyms.\n'
            '4. 🧠 [ESLAB QOLISH SIRI (MNEMONIKA / ASSOTSIATSIYA)]: Give a vivid memory hook or etymology trick '
            'so the student never forgets it.\n'
            '5. 💬 [JONLI KONTEKST VA 1 FAOL MASHQ]: Show natural sentences and ask the student to use the word '
            'in 1 sentence of their own.'
        ),
        starters=(
            ('Kunlik 10 ta Oltin So‘z + Mnemonika', 'Transkripsiya, kollokatsiya va eslab qolish siri.',
             'Darajam uchun eng zarur 10 ta faol so‘z va iborani transkripsiyasi, kollokatsiyasi, eslab qolish mnemonikasi va jonli misollari bilan o‘rgating.', 'memory'),
            ('Oddiy so‘zlarni C1/C2 ga ko‘tarish (Upgrade)', 'B1/B2 so‘zlarni kuchli akademik sinonimlarga almashtirish.',
             'Nutq va yozuvda eng ko‘p ishlatiladigan 10 ta oddiy so‘zni C1/C2 darajadagi boy, ta’sirchan sinonim va kollokatsiyalarga almashtirish jadvalini bering.', 'spark'),
            ('Yaqin ma’noli so‘zlar farqi (Nuance)', 'Qaysi so‘z qaysi vaziyatda ishlatiladi?',
             'Shu tilda o‘quvchilar bir-biri bilan adashtiradigan eng muhim sinonim juftliklarni aniq farqi va misollari bilan tushuntirib bering.', 'sliders'),
        ),
    ),
    SkillChannel(
        key='reading',
        title='Reading · O‘qib tushunish',
        short_title='Reading',
        glyph='file',
        subtitle='Darajaga mos matnlar, uzun gaplarning sintaktik rentgeni, kontekstual lug‘at va Comprehension savollar.',
        placeholder='Matn tashlang yoki Reading mavzu so‘rang — Professor gapma-gap tahlil va savollar beradi…',
        criteria_badge='Mezonlar: Deep Comprehension · Sentence X-Ray · Academic Lexicon · Speed Strategy',
        criteria_prompt=(
            '[ACTIVE CHANNEL: READING (MATN TAHLILI, SINTAKSIS VA COMPREHENSION)]\n'
            'Your goal is to make the student read complex texts quickly and accurately with 100% comprehension.\n'
            'PROFESSOR READING CRITERIA:\n'
            '1. 📖 [MATN Yoki UMUMIY MAZMUN]: If the student asks for a reading practice, generate a rich, '
            'engaging passage at their CEFR level. If they paste a text, summarize its core thesis first.\n'
            '2. 🔬 [MURAKKAB GAPLAR RENTGENI (SYNTAX BREAKDOWN)]: Take the 2–3 hardest sentences, break them '
            'into clauses ([Ega/Subject] + [Kesim/Verb] + [Ergash gap/Modifier]), and show how to read them effortlessly.\n'
            '3. 💎 [MATNDAGI OLTIN IBORALAR]: Explain 5–7 key academic/contextual words from the text.\n'
            '4. ✅ [COMPREHENSION SAVOLLARI]: Ask 3 targeted questions (Main Idea, True/False/Not Given, Inference).'
        ),
        starters=(
            ('Darajamga mos Matn + Sintaktik Tahlil + Test', 'To‘liq Reading mashg‘uloti va savollar.',
             'Darajamga mos ilmiy-ommabop yoki hayotiy Reading matni yozib bering, ichidagi eng qiyin 2 ta gapni sintaktik bo‘laklab tushuntiring, lug‘atini bering va 3 ta savol so‘rang.', 'file'),
            ('Uzun va Murakkab Gaplarni Chaqish Siri', 'Qiyin gaplarni 5 soniyada tushunish texnikasi.',
             'Uzun va murakkab akademik gaplarni adashmasdan tez o‘qib tushunish uchun 30 yillik professorning "Gap rentgeni" usulini misollar bilan ko‘rsating.', 'sliders'),
            ('Men yuborgan matnni chuqur tahlil qil', 'Tarjima, grammatik izoh va muhim iboralar.',
             'Men hozir yuboradigan matnni ma’nosini, qiyin grammatik tuzilmalarini va ichidagi eng foydali iboralarni professor darajasida tahlil qilib bering.', 'spark'),
        ),
    ),
    SkillChannel(
        key='general',
        title='General · Erkin muloqot',
        short_title='General',
        glyph='chat',
        subtitle='Erkin suhbat — til, tarjima, imtihon strategiyasi yoki istalgan savolingizni chegarasiz so‘rang.',
        placeholder='General: Til bo‘yicha xohlagan savolingizni, tarjima yoki mavzuni bemalol yozing…',
        criteria_badge='Mezonlar: 30 Yillik Professor · Sodda · Tez · Mukammal · Erkin Savol-Javob',
        criteria_prompt=(
            '[ACTIVE CHANNEL: GENERAL (ERKIN MULOQOT VA UNIVERSAL PROFESSOR MASLAHATI)]\n'
            'In this General channel, the student may ask ANYTHING related to the target language, translation, '
            'study plans, cultural nuances, idioms, exam preparation, homework, or free conversation.\n'
            'Answer with the full wisdom of a 30-year Professor: crystal-clear, fast, deeply accurate, '
            'well-structured with examples, and immediately practical.'
        ),
        starters=(
            ('Shaxsiy Tezkor O‘quv Reja (0 dan C1/C2 gacha)', '30 yillik professorning aniq kunlik tizimi.',
             'Mening hozirgi darajamdan eng qisqa vaqtda C1/C2 darajaga chiqishim uchun 7 ta ko‘nikma (Speaking, Writing, Listening, Grammar, Vocabulary, Reading) bo‘yicha aniq kunlik reja tuzib bering.', 'chat'),
            ('Istalgan Jumla, Tarjima yoki Qoida Tahlili', 'Erkin savol — sodda, tez va mukammal javob.',
             'Men so‘ragan har qanday jumla, tarjima yoki til qoidasini eng sodda, tez va chuqur misollar bilan tushuntirib bering.', 'spark'),
            ('Darajamni Aniqlash (Tezkor Placement Test)', '5 ta savol bilan aniq CEFR darajani bilish.',
             'Menga ketma-ket 5 ta qisqa diagnostik savol berib, hozirgi til darajamni (A1–C2) va eng birinchi o‘rganishim kerak bo‘lgan mavzularni aniqlab bering.', 'sliders'),
        ),
    ),
)

SKILL_MAP = {skill.key: skill for skill in SKILLS}
SKILL_KEYS = tuple(skill.key for skill in SKILLS)


# Windows SAPI language ids (hex LCID) for offline pronunciation.
_SAPI_LCID = {
    'en': '409', 'ru': '419', 'de': '407', 'fr': '40c', 'es': 'c0a', 'it': '410',
    'tr': '41f', 'ar': '401', 'zh': '804', 'ja': '411', 'ko': '412', 'uz': '443',
}


def _sapi_speak(word: str, lang: str, slow: bool = False) -> bool:
    """Speak ``word`` with local Uzbek neural TTS (for uz) or an installed Windows SAPI voice."""
    if lang == 'uz':
        try:
            import threading as _th
            from core import uzbek_tts
            from core.voice_style import load_voice_style
            if uzbek_tts.ready():
                st = dict(load_voice_style())
                if slow:
                    st['speed'] = 'very_slow'
                uzbek_tts.speak(word, _th.Event(), style=st)
                return True
        except Exception:
            pass
    try:
        import pythoncom
        import win32com.client
    except ImportError:
        return False
    pythoncom.CoInitialize()
    try:
        speaker = win32com.client.Dispatch('SAPI.SpVoice')
        lcid = _SAPI_LCID.get(lang)
        gender_pref = 'Female'
        base_rate = 0
        try:
            from core.voice_style import GENDER_MAP, SPEED_MAP, load_voice_style
            vs = load_voice_style()
            gender_pref = GENDER_MAP[vs['gender']].sapi_gender
            base_rate = SPEED_MAP[vs['speed']].sapi_rate
        except Exception:
            pass
        if lcid:
            try:
                voices = speaker.GetVoices(f'Language={lcid};Gender={gender_pref}')
                if not voices.Count:
                    voices = speaker.GetVoices(f'Language={lcid}')
                if voices.Count:
                    speaker.Voice = voices.Item(0)
            except Exception:
                try:
                    voices = speaker.GetVoices(f'Language={lcid}')
                    if voices.Count:
                        speaker.Voice = voices.Item(0)
                except Exception:
                    pass
        try:
            speaker.Rate = -5 if slow else base_rate
        except Exception:
            pass
        speaker.Speak(word)
        return True
    except Exception:
        return False
    finally:
        pythoncom.CoUninitialize()


def default_state() -> dict:
    return {
        'target_language': 'en',
        'custom_language': '',
        'level': 'B1',
        'teacher_role': 'universal_professor',
        'active_skill': 'general',
        'explain_language': 'uz',
        'criteria': list(DEFAULT_CRITERIA),
        'ask_on_startup': True,
        'onboarded': False,
        'skill_chats': {},
        'vocab_bank': [],
    }


PROFESSOR_STARTER_VOCAB: dict[str, list[dict[str, str]]] = {
    'en': [
        {'word': 'ubiquitous', 'meaning': 'hamma joyda uchraydigan (C1)', 'collocation': 'ubiquitous technology / presence', 'mnemonic': 'Ubi (qayerda) -> hamma yerda bor'},
        {'word': 'mitigate', 'meaning': 'yumshatmoq, xavfni kamaytirmoq (C1)', 'collocation': 'mitigate the risk / impact', 'mnemonic': 'Miti -> minusga tushirib yumshatish'},
        {'word': 'articulate', 'meaning': 'fikrini ravon va aniq ifodalaydigan (C1)', 'collocation': 'an articulate speaker', 'mnemonic': 'Artikul -> har bir bo‘g‘inni aniq aytish'},
        {'word': 'compelling', 'meaning': 'ishonarli, kuchli dalilli (B2/C1)', 'collocation': 'a compelling argument', 'mnemonic': 'Compel -> majbur qiladigan darajada kuchli'},
        {'word': 'meticulous', 'meaning': 'o‘ta sinchkov va e’tiborli (C1)', 'collocation': 'meticulous attention to detail', 'mnemonic': 'Metr + mikro -> millimetrigacha tekshiruvchi'},
        {'word': 'pragmatic', 'meaning': 'amaliy va real natijaga yo‘naltirilgan (C1)', 'collocation': 'a pragmatic approach / solution', 'mnemonic': 'Pragmatik -> quruq gap emas, amaliy ish'},
        {'word': 'exacerbate', 'meaning': 'muammoni yanada og‘irlashtirmoq (C1/C2)', 'collocation': 'exacerbate the crisis / inequality', 'mnemonic': 'Ex + acer (achchiq) -> vaziyatni yanada achchiqlashtirmoq'},
        {'word': 'resilient', 'meaning': 'bardoshli, qiyinchilikdan tez tiklanuvchi (B2/C1)', 'collocation': 'a resilient economy / mindset', 'mnemonic': 'Re-sili (sakrash) -> yiqilib yana tiklanuvchi'},
    ],
    'ru': [
        {'word': 'неотъемлемый', 'meaning': 'ajralmas, uzviy (C1)', 'collocation': 'неотъемлемая часть', 'mnemonic': 'Не отнять -> tortib olib bo‘lmaydigan'},
        {'word': 'способствовать', 'meaning': 'ko‘maklashmoq, turtki bo‘lmoq (B2)', 'collocation': 'способствовать развитию (+ дательный)', 'mnemonic': 'Способ -> yo‘l va imkon yaratish'},
        {'word': 'красноречивый', 'meaning': 'notiq, ta’sirchan gapiruvchi (C1)', 'collocation': 'красноречивый факт / оратор', 'mnemonic': 'Красная речь -> go‘zal nutq'},
        {'word': 'целесообразный', 'meaning': 'maqsadga muvofiq, oqilona (C1)', 'collocation': 'целесообразное решение', 'mnemonic': 'Цель (maqsad) + сообразный (mos)'},
        {'word': 'воплощать', 'meaning': 'amalga oshirmoq, hayotga tatbiq etmoq (B2/C1)', 'collocation': 'воплощать идею в жизнь', 'mnemonic': 'В + плоть -> g‘oyaga jon bag‘ishlamoq'},
        {'word': 'преодолевать', 'meaning': 'yengib o‘tmoq, bartaraf etmoq (B2)', 'collocation': 'преодолевать трудности / барьер', 'mnemonic': 'Пере + одолеть -> to‘siqdan oshib o‘tmoq'},
    ],
    'ar': [
        {'word': 'بَلَاغَة (Balag‘a)', 'meaning': 'notiqlik va fasohat (C1)', 'collocation': 'علم البلاغة', 'mnemonic': 'Balog‘atga yetgan mukammal nutq'},
        {'word': 'مُسْتَدَام (Mustadam)', 'meaning': 'barqaror, davomiy (B2)', 'collocation': 'تنمية مستدامة (barqaror rivojlanish)', 'mnemonic': 'Davom etuvchi (dama)'},
        {'word': 'جَوْهَرِيّ (Javhariy)', 'meaning': 'tub, asosiy, muhim (B2/C1)', 'collocation': 'فرق جوهري (tub farq)', 'mnemonic': 'Javhar — narsaning o‘zagi'},
        {'word': 'مِحْوَرِيّ (Mihwari)', 'meaning': 'markaziy, hal qiluvchi (C1)', 'collocation': 'دَوْر مِحْوَرِيّ (hal qiluvchi rol)', 'mnemonic': 'Mehvar -> atrofida hamma narsa aylanadigan o‘q'},
        {'word': 'تَعْزِيز (Ta‘ziz)', 'meaning': 'mustahkamlash, kuchaytirish (B2/C1)', 'collocation': 'تَعْزِيزُ التَّعَاوُنِ (hamkorlikni kuchaytirish)', 'mnemonic': 'Aziz -> qudratli va kuchli qilish'},
        {'word': 'مُقْتَضَى (Muqtada)', 'meaning': 'talab, taqozo, zarurat (C1)', 'collocation': 'بِمُقْتَضَى القَانُونِ (qonun talabiga ko‘ra)', 'mnemonic': 'Taqozo qilingan narsa'},
    ],
    'tr': [
        {'word': 'kapsamlı', 'meaning': 'keng qamrovli, mukammal (B2/C1)', 'collocation': 'kapsamlı bir araştırma', 'mnemonic': 'Kapsam -> hammasini qamrab olgan'},
        {'word': 'öngörmek', 'meaning': 'oldindan ko‘ra bilmoq (B2)', 'collocation': 'geleceği öngörmek', 'mnemonic': 'Ön (oldin) + görmek (ko‘rmoq)'},
        {'word': 'etkileyici', 'meaning': 'ta’sirchan, hayratlanarli (B1/B2)', 'collocation': 'etkileyici bir konuşma', 'mnemonic': 'Etki -> ta’sir o‘tkazuvchi'},
        {'word': 'vazgeçilmez', 'meaning': 'voz kechib bo‘lmaydigan, o‘ta zarur (B2/C1)', 'collocation': 'vazgeçilmez bir unsur', 'mnemonic': 'Vazgeç (voz kech) + ilmez (bo‘lmaydi)'},
        {'word': 'sürdürülebilir', 'meaning': 'barqaror, davomli (C1)', 'collocation': 'sürdürülebilir kalkınma', 'mnemonic': 'Sürdürmek (davom ettirish) + ebilir'},
        {'word': 'kavramak', 'meaning': 'chuqur anglamoq, tushunib yetmoq (B2)', 'collocation': 'konuyu derinlemesine kavramak', 'mnemonic': 'Aql bilan mahkam ushlab anglash'},
    ],
    'de': [
        {'word': 'nachhaltig', 'meaning': 'barqaror, uzoq muddatli (B2/C1)', 'collocation': 'nachhaltige Entwicklung', 'mnemonic': 'Nach + halten -> uzoq ushlab turuvchi'},
        {'word': 'unabdingbar', 'meaning': 'o‘ta zarur, muqarrar shart (C1)', 'collocation': 'eine unabdingbare Voraussetzung', 'mnemonic': 'Shartsiz kerakli'},
        {'word': 'nachvollziehen', 'meaning': 'mantiqan tushunib yetmoq (B2/C1)', 'collocation': 'etwas gut nachvollziehen können', 'mnemonic': 'Ortidan qadam-baqadam kuzatib anglash'},
        {'word': 'ausschlaggebend', 'meaning': 'hal qiluvchi, eng muhim (C1)', 'collocation': 'der ausschlaggebende Faktor', 'mnemonic': 'Tarozini og‘dirib hal qiluvchi'},
        {'word': 'gewährleisten', 'meaning': 'kafolatlamoq, ta’minlamoq (B2/C1)', 'collocation': 'Sicherheit gewährleisten', 'mnemonic': 'Gewähr (kafolat) + leisten (bajarmoq)'},
        {'word': 'unumgänglich', 'meaning': 'qochib bo‘lmaydigan, muqarrar (C1)', 'collocation': 'eine unumgängliche Maßnahme', 'mnemonic': 'Aylanib o‘tib (umgehen) bo‘lmaydigan'},
    ],
    'fr': [
        {'word': 'néanmoins', 'meaning': "shunga qaramasdan, baribir (B2/C1)", 'collocation': 'néanmoins important / néanmoins pertinent', 'mnemonic': "Ne + an + moins -> hech bo'lmasa, baribir"},
        {'word': 'épanouissement', 'meaning': 'kamolot, rivojlanish, gullanish (C1)', 'collocation': 'épanouissement personnel', 'mnemonic': "Épanoui -> gulga aylangan -> to'liq rivojlanish"},
        {'word': 'pertinent', 'meaning': "o'rinli, dolzarb, tegishli (B2)", 'collocation': 'une question pertinente', 'mnemonic': "Pertinent -> to'g'ridan-to'g'ri tegishli"},
        {'word': 'incontournable', 'meaning': 'chetlashib bo‘lmaydigan, muhim (C1)', 'collocation': 'un outil incontournable', 'mnemonic': 'Contour (aylanib o‘tish) + in (yo‘q)'},
        {'word': 'approfondir', 'meaning': 'chuqurlashtirmoq, batafsil o‘rganmoq (B2)', 'collocation': 'approfondir ses connaissances', 'mnemonic': 'Profond (chuqur) -> chuqurlashtirish'},
        {'word': 'préconiser', 'meaning': 'qat’iy tavsiya qilmoq, yoqlamoq (C1)', 'collocation': 'préconiser une réforme', 'mnemonic': 'Pre (oldindan) + kengashda tavsiya qilish'},
    ],
    'es': [
        {'word': 'imprescindible', 'meaning': "o'ta zarur, muqarrar (B2/C1)", 'collocation': 'es imprescindible + infinitivo', 'mnemonic': "Im-prescindible -> ayrilmaydigan, shart bo'lgan"},
        {'word': 'perspicaz', 'meaning': "ziyrak, o'tkir zehnli (C1)", 'collocation': 'una mente perspicaz', 'mnemonic': "Perspicaz -> perspektivani ko'ra oladigan"},
        {'word': 'contundente', 'meaning': 'ishonchli, kuchli, hal qiluvchi (B2/C1)', 'collocation': 'un argumento contundente', 'mnemonic': 'Contunde -> zarba beruvchi kuch'},
        {'word': 'fomentar', 'meaning': 'rag‘batlantirmoq, rivojlantirmoq (B2/C1)', 'collocation': 'fomentar el diálogo / la creatividad', 'mnemonic': 'Fomento -> olovga moy quyib kuchaytirish'},
        {'word': 'desencadenar', 'meaning': 'keltirib chiqarmoq, boshlab yubormoq (C1)', 'collocation': 'desencadenar una crisis / reacción', 'mnemonic': 'Des-encadenar -> zanjirni yechib yubormoq'},
        {'word': 'matizar', 'meaning': 'nozik farqini aniqlashtirmoq (C1/C2)', 'collocation': 'conviene matizar esta idea', 'mnemonic': 'Matiz (rang tuslari) -> nozik ma’no qo‘shish'},
    ],
    'zh': [
        {'word': '坚持不懈 (jiānchí bùxiè)', 'meaning': "qat'iyat bilan davom etmoq (HSK 5)", 'collocation': '坚持不懈地努力', 'mnemonic': "坚 (puxta) + 持 (ushlamoq) -> to'xtovsiz harakat"},
        {'word': '突破 (tūpò)', 'meaning': "to'siqni yengmoq, yutuq qozonmoq (HSK 4)", 'collocation': '取得突破 / 突破瓶颈', 'mnemonic': "突 (to'satdan) + 破 (sindirmoq) -> to'siqni yorib o‘tish"},
        {'word': '融合 (rónghé)', 'meaning': "qo'shilmoq, uyg'unlashmoq (HSK 5)", 'collocation': '文化融合 / 融合发展', 'mnemonic': "融 (eritmoq) + 合 (qo'shmoq) -> biriga uyg‘unlashish"},
        {'word': '不可或缺 (bù kě huò quē)', 'meaning': 'ajralmas, o‘ta zarur (HSK 5/6)', 'collocation': '不可或缺的一部分', 'mnemonic': 'Yo‘q bo‘lishi mumkin emas (缺 - yetishmaslik)'},
        {'word': '潜移默化 (qián yí mò huà)', 'meaning': 'sezilmas tarzda ta’sir qilmoq (HSK 6)', 'collocation': '潜移默化的影响', 'mnemonic': 'Jim va chuqur o‘zgartiruvchi ta’sir'},
        {'word': '相辅相成 (xiāng fǔ xiāng chéng)', 'meaning': 'bir-birini to‘ldirib kuchaytirmoq (HSK 6)', 'collocation': '两者相辅相成', 'mnemonic': 'Ikki tomon birgalikda yordam berib kamol topishi'},
    ],
    'ja': [
        {'word': '努力 (どりょく, doryoku)', 'meaning': "g'ayrat, mehnat qilmoq (JLPT N4)", 'collocation': '努力する / 努力が実る', 'mnemonic': '努 (harakat) + 力 (kuch) -> kuch sarflash'},
        {'word': '克服 (こくふく, kokufuku)', 'meaning': 'yengmoq, bartaraf etmoq (JLPT N2)', 'collocation': '困難を克服する', 'mnemonic': "克 (yengmoq) + 服 (bo'ysunmoq) -> qiyinlikni yengish"},
        {'word': '洞察力 (どうさつりょく, dōsatsuryoku)', 'meaning': 'ziyraklik, chuqur tushunish (JLPT N1)', 'collocation': '洞察力がある / 優れた洞察力', 'mnemonic': "洞 (ichiga kirish) + 察 (kuzatmoq) -> tubini ko‘rish"},
        {'word': '不可欠 (ふかけつ, fukaketsu)', 'meaning': 'ajralmas, mutlaqo zarur (JLPT N2)', 'collocation': '成功に不可欠な要素', 'mnemonic': '不 (yo‘q) + 可 (mumkin) + 欠 (kamaymoq)'},
        {'word': '臨機応変 (りんきおうへん, rinki ōhen)', 'meaning': 'vaziyatga moslashuvchanlik (JLPT N1)', 'collocation': '臨機応変に対応する', 'mnemonic': 'Vaziyat (機) ga qarab javob (応) berish'},
        {'word': '試行錯誤 (しこうさくご, shikō sakugo)', 'meaning': 'sinov va xato orqali o‘rganish (JLPT N2)', 'collocation': '試行錯誤を重ねる', 'mnemonic': 'Sinash (試) va xatolarni tahlil qilish'},
    ],
    'it': [
        {'word': 'impeccabile', 'meaning': "beg'ubor, mukammal, nuqsonsiz (C1)", 'collocation': "un'esecuzione impeccabile", 'mnemonic': 'Im-peccabile -> hech nuqsonsiz'},
        {'word': 'perspicace', 'meaning': "ziyrak, o'tkir zehnli (C1)", 'collocation': 'una mente perspicace', 'mnemonic': "Perspicace -> uzoqni ko'ra oladigan"},
        {'word': 'preponderante', 'meaning': 'ustunlik qiluvchi, asosiy (B2/C1)', 'collocation': 'il fattore preponderante', 'mnemonic': "Pre-ponderante -> og'ir bosadigan ustunlik"},
        {'word': 'imprescindibile', 'meaning': 'ajralmas, o‘ta zarur (B2/C1)', 'collocation': 'uno strumento imprescindibile', 'mnemonic': 'Shubhasiz shart bo‘lgan'},
        {'word': 'approfondire', 'meaning': 'chuqur o‘rganmoq, tadqiq qilmoq (B2)', 'collocation': 'approfondire un argomento', 'mnemonic': 'Profondo (chuqur) -> chuqurlashtirish'},
        {'word': 'consapevolezza', 'meaning': 'onglilik, chuqur xabardorlik (C1)', 'collocation': 'acquisire consapevolezza', 'mnemonic': 'Sapere (bilish) -> bilib anglash holati'},
    ],
    'ko': [
        {'word': '필수적인 (pilsujeogin)', 'meaning': 'eng zarur, majburiy (TOPIK 4)', 'collocation': '필수적인 요소', 'mnemonic': 'Pilsu -> birinchi navbatda zarur'},
        {'word': '효율적 (hyoyuljeok)', 'meaning': 'samarali, unumli (TOPIK 4)', 'collocation': '효율적인 방법', 'mnemonic': 'Foydasi yuqori usul'},
        {'word': '불가피하다 (bulgapihada)', 'meaning': 'muqarrar, qochib bo‘lmaydigan (TOPIK 5)', 'collocation': '불가피한 선택', 'mnemonic': 'Bul (yo‘q) + gapi (qochish) -> muqarrar'},
        {'word': '핵심적인 (haeksimjeogin)', 'meaning': 'markaziy, asosiy (TOPIK 4/5)', 'collocation': '핵심적인 역할', 'mnemonic': 'Haeksim -> yadro, o‘zak'},
        {'word': '극복하다 (geukbokhada)', 'meaning': 'yengib o‘tmoq (TOPIK 3/4)', 'collocation': '위기를 극복하다', 'mnemonic': 'Qiyinchilik ustidan g‘alaba qozonmoq'},
        {'word': '도입하다 (doiphada)', 'meaning': 'joriy qilmoq, kiritmoq (TOPIK 4/5)', 'collocation': '새로운 제도를 도입하다', 'mnemonic': 'Do (yo‘l) + ip (kirish) -> yangi tizim olib kirish'},
    ],
    'uz': [
        {'word': 'fasohat va balog‘at', 'meaning': 'nutqning tozaligi, ravonligi va ta’sirchanligi (C1/C2)', 'collocation': 'fasohat bilan so‘zlamoq', 'mnemonic': 'Fasohat = tiniq shakl, balog‘at = chuqur ma’no'},
        {'word': 'mushohada', 'meaning': 'chuqur mulohaza va tahliliy fikr yuritish (C1)', 'collocation': 'chuqur mushohada yuritmoq', 'mnemonic': 'Shohid bo‘lib aql bilan kuzatish'},
        {'word': 'muqarrar', 'meaning': 'shubhasiz sodir bo‘ladigan, qochib bo‘lmas (B2/C1)', 'collocation': 'muqarrar g‘alaba / natija', 'mnemonic': 'Qaror topgan, aniq narsa'},
        {'word': 'hamohang', 'meaning': 'uyg‘un, bir-biriga mos tushuvchi (B2)', 'collocation': 'zamon bilan hamohang bo‘lmoq', 'mnemonic': 'Ham (birga) + ohang -> bitta ohangda'},
        {'word': 'lahja va sheva', 'meaning': 'tilning hududiy talaffuz va grammatik tarmog‘i (Qarluq, Qipchoq, O‘g‘uz)', 'collocation': 'Toshkent, Farg‘ona, Xorazm, Samarqand shevalari', 'mnemonic': 'Uch yirik lahja: Qarluq (-yapti/-votti/-opti), Qipchoq (j-lovchi), O‘g‘uz (gal/bar)'},
        {'word': 'orfoepiya', 'meaning': 'adabiy talaffuz me’yorlari va urg‘u qoidalari (C1)', 'collocation': 'orfoepik me’yorga amal qilmoq', 'mnemonic': 'Orfo (to‘g‘ri) + epos (nutq) -> to‘g‘ri talaffuz'},
    ],
}


LANGUAGE_LINGUISTIC_GUIDES: dict[str, str] = {
    'en': (
        'ENGLISH PEDAGOGY: Enforce exact Tense-Aspect logic (Present Perfect vs Past Simple, Continuous vs Stative), '
        'article accuracy (a/an/the/zero), natural academic & phrasal collocations, C1/C2 inversions '
        '("Not only did...", "Had it not been..."), and explicit IELTS Band / CEFR descriptor alignment.'
    ),
    'ru': (
        'RUSSIAN PEDAGOGY: Explicitly mark Verb Aspect pairs (НСВ vs СВ: делать/сделать), Case governance '
        '(Падежи + предлоги), Verbs of Motion (идти/ходить, ехать/ездить), syllable stress marks (ударение, e.g. за́мок vs замо́к), '
        'and ТРКИ (TORFL) / CEFR standards.'
    ),
    'ar': (
        'ARABIC PEDAGOGY: Provide clear Harakat (تشكيل) on key/new words, explain the 3-letter Root & Pattern '
        '(الجذر والوزن / Sarf), show syntactic I‘rab / Nahv roles (مبتدأ، خبر، فاعل، مفعول), clarify Bab verb forms (I–X), '
        'and distinguish Modern Standard Arabic (Fusha) from spoken dialect.'
    ),
    'tr': (
        'TURKISH PEDAGOGY: Highlight Vowel Harmony (Büyük ve Küçük Ünlü Uyumu), Consonant Mutation (ünsüz yumuşaması: '
        'p/ç/t/k -> b/c/d/ğ), Agglutinative suffix order, and Turkish participle clauses (-dığı, -ecek, -en) per TÖMER / CEFR.'
    ),
    'de': (
        'GERMAN PEDAGOGY: ALWAYS present every German noun with its definite article and plural form '
        '(e.g. "der Fortschritt, -e", "die Entwicklung, -en"), specify Case governance (Kasusrektion: Dativ/Akkusativ/Genitiv), '
        'and teach V2 main clause vs Verb-final subordinate clause (Nebensatz mit weil/dass/obwohl) word order per Goethe/TestDaF.'
    ),
    'ko': (
        'KOREAN PEDAGOGY: Specify Speech Register (하십시오체, 해요체, 반말) for every dialogue/sentence, clarify '
        'topic vs subject markers (은/는 vs 이/가) and location particles (에 vs 에서), include Romanization for A1–A2 '
        'learners when helpful, and align grammar patterns to TOPIK I/II.'
    ),
    'fr': (
        'FRENCH PEDAGOGY: Always specify noun gender (un/une, le/la), contrast Passé composé vs Imparfait cleanly, '
        'highlight Subjonctif triggers (il faut que, bien que), explain liaison/elision & silent endings, and align with DELF/DALF.'
    ),
    'es': (
        'SPANISH PEDAGOGY: Clarify Ser vs Estar, Por vs Para, Pretérito indefinido vs Imperfecto, Subjuntivo triggers '
        '(espero que, aunque, para que), noun-adjective gender/number agreement, and DELE/SIELE standards.'
    ),
    'zh': (
        'CHINESE (MANDARIN) PEDAGOGY: ALWAYS include Pinyin with exact tone marks alongside Hanzi characters '
        '(e.g. 学习 xuéxí), specify Measure Words (量词: 个, 本, 张), clarify aspect particles (了, 过, 着) and 把/被 syntax, '
        'and align explanations with HSK standards.'
    ),
    'ja': (
        'JAPANESE PEDAGOGY: ALWAYS provide Furigana/reading in brackets alongside Kanji (e.g. 克服[こくふく, kokufuku]), '
        'clarify Register (丁寧語 ます/です vs 敬語 vs 普通体), core particles (は vs が, に vs で, を), and JLPT N5–N1 patterns.'
    ),
    'it': (
        'ITALIAN PEDAGOGY: Always specify noun gender & plural, Essere vs Avere auxiliaries in Passato prossimo, '
        'Imperfetto vs Passato prossimo, Congiuntivo triggers, articulated prepositions (del, nella, sul), and CILS/CELI standards.'
    ),
    'uz': (
        'UZBEK ELOQUENCE & DIALECTOLOGY PEDAGOGY: Teach pure Standard Literary Uzbek (Adabiy til, Milliy Sertifikat '
        'C1/C2, imlo va orfoepiya, qo‘shma gap sintaksisi, notiqlik san’ati) AND compare the 3 major Uzbek dialect groups '
        '(Qarluq: Toshkent -votti & Farg‘ona -yapti & Samarqand-Buxoro -opti; Qipchoq: Qashqadaryo-Surxondaryo j-lovchi; '
        'O‘g‘uz: Xorazm gal/bar/-yabdi) with clear pronunciation and stylistic contrast.'
    ),
    'default': (
        'UNIVERSAL LANGUAGE PEDAGOGY: Present script + pronunciation/phonetics for every new item, highlight '
        'sentence syntax formulas, core morphology, high-frequency collocations, and CEFR-calibrated examples.'
    ),
}


LANGUAGE_GRAMMAR_CHEATSHEETS: dict[str, list[dict[str, str]]] = {
    'en': [
        {
            'title': 'C1 Inverted Conditionals (Band 8.0+ Shart Gaplari)',
            'formula': '[Had + S + V3] / [Were + S + to V1] / [Should + S + V1], S + would (have) + V',
            'example': 'Had governments acted earlier, the crisis would have been mitigated.',
            'trap': '❌ Had governments acted earlier, the crisis would mitigated. -> ✅ would have been mitigated.',
            'practice_prompt': 'Menga Inverted Conditionals (Had / Were / Should) mavzusida 3 ta mashq va C1 Writing misolini bering.',
        },
        {
            'title': 'Negative Inversion (Akademik Urg‘u)',
            'formula': '[Not only / Seldom / Scarcely] + Auxiliary (do/did/had/have) + S + V',
            'example': 'Not only did the policy boost productivity, but it also reduced waste.',
            'trap': '❌ Not only the policy boosted... -> ✅ Not only did the policy boost...',
            'practice_prompt': 'Negative Inversion (Not only, Seldom, Hardly) formulasini 5 qadamli usulda tushuntirib mashq qildiring.',
        },
        {
            'title': 'Participle Clauses (Gaplarni ixcham C1 qilish)',
            'formula': '[V-ing / V3 / Having + V3], Main Clause (bir xil ega!)',
            'example': 'Having analyzed the data, the researchers proposed a pragmatic framework.',
            'trap': '❌ Having analyzed the data, the problem became clear. (Egalar mos emas!)',
            'practice_prompt': 'Participle Clauses bilan oddiy gaplarni C1 akademik gaplarga aylantirishni mashq qildir.',
        },
        {
            'title': 'C1/C2 Cohesive Devices (Insho Bog‘lovchilari)',
            'formula': 'Notwithstanding + Noun | Consequently | Conversely | In light of + Noun',
            'example': 'Notwithstanding the budget constraints, innovation remained ubiquitous.',
            'trap': '❌ Despite of the constraints -> ✅ Despite the constraints / Notwithstanding the constraints.',
            'practice_prompt': 'IELTS Writing Task 2 uchun eng kuchli 10 ta C1 bog‘lovchi iboralarni misollar bilan o‘rgating.',
        },
    ],
    'ru': [
        {
            'title': 'Виды глагола: НСВ vs СВ (Tugallanganlik)',
            'formula': 'НСВ (jarayon / takror) vs СВ (aniq natija / bir marta)',
            'example': 'Я долго решал (НСВ) задачу и наконец решил (СВ) её.',
            'trap': '❌ Вчера я долго решил эту задачу. -> ✅ Вчера я долго решал (jarayon) и решил (natija).',
            'practice_prompt': 'Rus tilida НСВ va СВ fe’l turlarini eng sodda formula va 5 ta juftlik bilan tushuntirib mashq qildir.',
        },
        {
            'title': '6 Падежей — Oltin Savollar Jadvali',
            'formula': 'Им.(кто/что) · Род.(кого/чего) · Дат.(кому/чему) · Вин.(кого/что) · Твор.(кем/чем) · Пред.(о ком/чём)',
            'example': 'Благодаря упорному труду (Дат.) она добилась успеха (Род.).',
            'trap': '❌ Благодаря упорного труда -> ✅ Благодаря + Дательный падеж (упорному труду)!',
            'practice_prompt': 'Rus tilidagi 6 kelishik (Падежи) va eng ko‘p ishlatiladigan predloglarni jadvalda o‘rgating.',
        },
        {
            'title': 'Глаголы движения (Harakat fe’llari)',
            'formula': 'Идти/Ехать (bir yo‘nalish, hozir) vs Ходить/Ездить (borib-kelish / odat)',
            'example': 'Сейчас я иду на урок, хотя обычно хожу туда утром.',
            'trap': '❌ Каждый день я иду на работу. -> ✅ Каждый день я хожу (takror) на работу.',
            'practice_prompt': 'Идти/Ходить va Прийти/Приходить farqini misollar bilan tushuntiring.',
        },
    ],
    'ar': [
        {
            'title': 'الجملة الاسمية والفعلية (Ismiy va Fe’liy gap)',
            'formula': 'Ismiy: [المبتدأ (Marfu‘) + الخبر (Marfu‘)] | Fe’liy: [الفعل + الفاعل (Marfu‘) + المفعول (Mansub)]',
            'example': 'العِلْمُ نُورٌ (Ilm nurdir) | يَقْرَأُ الطَّالِبُ الكِتَابَ (Talaba kitob o‘qiyapti).',
            'trap': '❌ يقرأُ الطالبَ الكتابُ -> ✅ الفاعل (الطالبُ) doim Marfu‘ (-u), المفعول (الكتابَ) Mansub (-a)!',
            'practice_prompt': 'Arab tilida Mubtado-Xabar va Fe’l-Foil-Maf‘ul gap qoliplarini harakatlari bilan tushuntiring.',
        },
        {
            'title': 'الإضافة (Izofa birikmasi)',
            'formula': '[المضاف (AL yo‘q, tanvin yo‘q)] + [المضاف إليه (Majrur -i/-in)]',
            'example': 'كِتَابُ الطَّالِبِ (Talabaning kitobi) · بَابُ المَدْرَسَةِ (Maktab eshigi).',
            'trap': '❌ الكِتَابُ الطَّالِبِ -> ✅ Mudofga hech qachon "ال" (AL) qo‘yilmaydi!',
            'practice_prompt': 'Izofa birikmasi qoidalarini 5 ta zamonaviy arabcha misol bilan mashq qildiring.',
        },
        {
            'title': 'إنَّ وأخواتها vs كان وأخواتها',
            'formula': 'إنَّ + [Ism Mansub (-a)] + [Xabar Marfu‘ (-u)] | كَانَ + [Ism Marfu‘ (-u)] + [Xabar Mansub (-a)]',
            'example': 'إنَّ الدَّرْسَ مُفِيدٌ | كَانَ الدَّرْسُ مُفِيدًا.',
            'trap': '❌ إنَّ الدرسُ مفيدٌ -> ✅ "إنَّ" birinchi so‘zni Mansub (الدرسَ) qiladi!',
            'practice_prompt': 'Inna va Kana opa-singillari qoidasini qisqa taqqoslash formulasida tushuntiring.',
        },
    ],
    'tr': [
        {
            'title': 'Büyük ve Küçük Ünlü Uyumu (Unlilar Uyg‘unligi)',
            'formula': 'Kalın (a, ı, o, u) -> -lar/-da/-a | İnce (e, i, ö, ü) -> -ler/-de/-e',
            'example': 'kitap-lar-da (kitoblarda) | ev-ler-de (uylarda) | göz-lük-çü (ko‘zoynakchi).',
            'trap': '❌ evde değil "evda" emas! İnce unli (e) -> -de qo‘shimchasini oladi.',
            'practice_prompt': 'Turk tilida unlilar uyg‘unligi va ünsüz yumuşaması qoidalarini mashq qildiring.',
        },
        {
            'title': 'Sıfat-Fiil (-dığı / -ecek) Ergash Gaplari',
            'formula': '[Ega (-in)] + [Fe’l + -dık/-ecek + Egalik] + [Kelishik]',
            'example': 'Senin söylediğin sözü çok beğendim (Sen aytgan so‘z menga juda yoqdi).',
            'trap': '❌ Sen söylediğin söz -> ✅ Ko‘pincha egalik kelishigi + egalik qo‘shimchasi (-in ... -in) mos keladi.',
            'practice_prompt': 'Turk tilida "-dığı" va "-eceği" qo‘shimchalari bilan murakkab gap tuzishni o‘rgating.',
        },
    ],
    'de': [
        {
            'title': 'Verbposition: Hauptsatz (V2) vs Nebensatz (Verb-Ende)',
            'formula': 'Hauptsatz: [Pos.1 + V2 (tusalgan) + ... ] | Nebensatz: [weil/dass/obwohl + S + ... + V_Ende]',
            'example': 'Ich lerne Deutsch, weil ich in Berlin studieren möchte.',
            'trap': '❌ ...weil ich möchte in Berlin studieren. -> ✅ ...weil ich in Berlin studieren möchte.',
            'practice_prompt': 'Nemis tilida V2 va Nebensatz (weil, dass, obwohl, wenn) so‘z tartibini mashq qildiring.',
        },
        {
            'title': '4 Kasus: Nominativ · Genitiv · Dativ · Akkusativ',
            'formula': 'Dativ-Präp: aus, bei, mit, nach, seit, von, zu | Akkusativ: für, ohne, gegen, um, durch',
            'example': 'Ich fahre mit dem Zug (Dativ) in die Stadt (Akkusativ).',
            'trap': '❌ mit den Zug -> ✅ "mit" doim Dativ talab qiladi: mit dem Zug!',
            'practice_prompt': 'Nemis tilida Dativ va Akkusativ predloglari bo‘yicha 5 ta misol va sinov bering.',
        },
    ],
    'ko': [
        {
            'title': '은/는 (Mavzu) vs 이/가 (Subyekt/Yangi ma’lumot)',
            'formula': '[Undosh + 은 / Unli + 는] (taqqoslash, mavzu) | [Undosh + 이 / Unli + 가] (aniq ega)',
            'example': '저는 학생입니다 (Men esa talabaman) | 누가 왔어요? 민수가 왔어요 (Kim keldi? Minsu keldi).',
            'trap': '❌ 누구는 왔어요? -> ✅ "Kim?" (누구) so‘rog‘iga doim 이/가 (누가) qo‘shiladi.',
            'practice_prompt': 'Koreys tilida 은/는 va 이/가 hamda 에 vs 에서 farqini 5 ta hayotiy misolda o‘rgating.',
        },
        {
            'title': 'Sabab va Ziddiyat Bog‘lovchilari (-아/어서 vs -지만)',
            'formula': 'Fe’l/Sifat negizi + [-아/어서 (sabab, buyruq bilan ishlamaydi!)] / [-(으)니까] / [-지만 (lekin)]',
            'example': '비가 와서 집에 있어요 (Yomg‘ir yog‘ayotgani uchun uydaman).',
            'trap': '❌ 시간이 없어서 빨리 가세요! -> ✅ Buyruq (-세요) bilan -(으)니까 ishlatiladi: 시간이 없으니까!',
            'practice_prompt': 'Koreys tilida -아/어서, -(으)니까 va -기 때문에 farqini formula bilan tushuntiring.',
        },
    ],
    'fr': [
        {
            'title': 'Passé composé vs Imparfait',
            'formula': 'Passé composé: [avoir/être + V3] (aniq voqea) | Imparfait: [-ais/-ais/-ait] (fon, odat)',
            'example': 'Il pleuvait (Imparfait — fon) quand je suis sorti (Passé composé — aniq harakat).',
            'trap': '❌ Quand je suis entré, il a dormi -> ✅ Il dormait (fon davom etayotgan edi).',
            'practice_prompt': 'Fransuz tilida Passé composé va Imparfait o‘rtasidagi farqni 5 ta misol bilan mashq qildiring.',
        },
        {
            'title': 'Le Subjonctif (Istak, Zarurat va His-tuyg‘u)',
            'formula': '[Il faut que / Bien que / Je veux que] + S + Verbe au Subjonctif (-e, -es, -e, -ions, -iez, -ent)',
            'example': 'Bien qu’il soit tard, nous continuons à travailler.',
            'trap': '❌ Il faut que tu viens -> ✅ Il faut que tu viennes!',
            'practice_prompt': 'Fransuz Subjonctif triggers va eng muhim noto‘g‘ri fe’llarni jadvalda bering.',
        },
    ],
    'es': [
        {
            'title': 'Ser vs Estar (Oltin Formula)',
            'formula': 'SER (DOCTOR: ta’rif, kasb, vaqt, kelib chiqish) vs ESTAR (PLACE: joy, holat, kayfiyat)',
            'example': 'Ella es inteligente (doimiy xususiyat), pero hoy está cansada (hozirgi holat).',
            'trap': '❌ Madrid es en España -> ✅ Joylashuv uchun doim ESTAR: Madrid está en España!',
            'practice_prompt': 'Ispan tilida Ser va Estar bilan ma’nosi o‘zgaradigan sifatlar (listo, aburrido, rico) ni mashq qildir.',
        },
        {
            'title': 'Subjuntivo (WEIRDO Qoidasi)',
            'formula': '[Espero que / Dudo que / Es imprescindible que] + S + Subjuntivo (-ar->-e, -er/-ir->-a)',
            'example': 'Es imprescindible que domines el vocabulario académico.',
            'trap': '❌ Espero que tienes éxito -> ✅ Espero que tengas éxito!',
            'practice_prompt': 'Ispan Subjuntivo WEIRDO formulasini misollar bilan tushuntirib mashq qildiring.',
        },
    ],
    'zh': [
        {
            'title': '把字句 (Bǎ strukturasi — Natija va Ta’sir)',
            'formula': '[Ega] + 把 + [Aniq Obyekt] + [Fe’l + Natija/Yo‘nalish/了]',
            'example': '我把作业做完了 (Wǒ bǎ zuòyè zuòwán le — Vazifamni bajarib tugatdim).',
            'trap': '❌ 我把书看 (tugallanmagan fe’l yolg‘iz kelmaydi!) -> ✅ 我把书看完了 (o‘qib tugatdim).',
            'practice_prompt': 'Xitoy tilida 把 (bǎ) va 被 (bèi) gap qoliplarini Pinyin va ohanglari bilan o‘rgating.',
        },
        {
            'title': 'Aspect Particles: 了 (le) · 过 (guò) · 着 (zhe)',
            'formula': '了 (yakun / o‘zgarish) | 过 (hayotiy tajriba "...ganman") | 着 (davomiy holat)',
            'example': '我去过北京 (Wǒ qù guo Běijīng — Pekinda bo‘lganman).',
            'trap': '❌ 昨天我去了了 -> ✅ Tugallangan aniq harakat uchun fe’ldan keyin bitta 了 yetarli.',
            'practice_prompt': '了, 过 va 着 yuklamalarining farqini HSK 4–5 misollari bilan tushuntiring.',
        },
    ],
    'ja': [
        {
            'title': 'Yapon Partikllari: は vs が · に vs で',
            'formula': 'は (mavzu "haqida") | が (yangi subyekt / "kim/nima?") | で (harakat joyi) | に (bo‘lish joyi / maqsad)',
            'example': '図書館[としょかん]で本[ほん]を読[よ]みます (Kutubxonada kitob o‘qiyman).',
            'trap': '❌ 図書館に勉強します -> ✅ Harakat sodir bo‘layotgan joy uchun で: 図書館で勉強します!',
            'practice_prompt': 'Yapon tilida は vs が va に vs で partikllarini 5 ta JLPT misoli bilan mashq qildiring.',
        },
        {
            'title': 'て-forma va N2 Sabab/Ziddiyat Qoliplari',
            'formula': '[V-て + います (davomiy)] / [V-て + みます (sinab ko‘rmoq)] / [N + にもかかわらず (...ga qaramasdan)]',
            'example': '困難[こんなん]にもかかわらず、挑戦[ちょうせん]し続[つづ]けました。',
            'trap': '❌ 雨だにもかかわらず -> ✅ Ot / Na-sifatga to‘g‘ridan-to‘g‘ri ulanadi: 雨にもかかわらず!',
            'practice_prompt': 'て-forma va JLPT N3/N2 bog‘lovchi qoliplarini Furigana bilan o‘rgating.',
        },
    ],
    'it': [
        {
            'title': 'Passato prossimo: Essere vs Avere',
            'formula': 'Harakat va holat o‘zgarishi (andare, venire, nascere) -> ESSERE (+ jins/son moslashuvi!) | Boshqalar -> AVERE',
            'example': 'Maria è partita ieri (a tugaydi!) | Marco ha studiato italiano.',
            'trap': '❌ Maria è partito ieri -> ✅ Essere bilan sifatdosh jinsga moslashadi: Maria è partita!',
            'practice_prompt': 'Italyan tilida Essere va Avere yordamchi fe’llari hamda moslashuv qoidasini mashq qildiring.',
        },
        {
            'title': 'Il Congiuntivo (Penso che / Sebbene)',
            'formula': '[Penso che / Credo che / Sebbene / Affinché] + S + Congiuntivo',
            'example': 'Sebbene sia difficile, continuo a migliorare ogni giorno.',
            'trap': '❌ Penso che lui è bravo -> ✅ Penso che lui sia bravo!',
            'practice_prompt': 'Italyan tilida Congiuntivo presente qoidalarini 5 ta CILS misoli bilan o‘rgating.',
        },
    ],
    'uz': [
        {
            'title': 'O‘zbek Tilining 3 Yirik Lahjasi va Hozirgi Zamon Qo‘shimchalari',
            'formula': 'Adabiy [-yapman/-moqda] | Toshkent [-vomman/-votti] | Samarqand-Buxoro [-omman/-opti] | Xorazm [-yabman/-yabdi]',
            'example': 'Adabiy: U kelyapti -> Toshkent: U kevotti -> Samarqand: U kelopti -> Xorazm: U galyabdi.',
            'trap': '❌ Rasmiy inshoda sheva qo‘shimchalarini aralashtirish -> ✅ Rasmiy yozuvda adabiy me’yor, jonli suhbatda tabiiy sheva!',
            'practice_prompt': 'O‘zbek tilining Qarluq, Qipchoq va O‘g‘uz lahjalari hamda hududiy shevalarining talaffuz farqlarini jadval va jonli dialoglar bilan o‘rgating.',
        },
        {
            'title': 'Orfoepiya va Notiqlik: Q vs G‘, X vs H va Urg‘u Me’yori',
            'formula': 'Chuqur til orqa [q / g‘ / x] vs Bo‘g‘iz [h] | Urg‘u odatda oxirgi bo‘g‘inga tushadi (istisno: hózir, álbaytta, hámma)',
            'example': 'Xol (yuzdagi xol) vs Hol (ahvol); Shox (daraxt shoxi) vs Shoh (podshoh).',
            'trap': '❌ «Hozirgina keldim»da x/h va urg‘uni adashtirish -> ✅ Ma’no farqlovchi paronim tovushlarni aniq talaffuz qilish!',
            'practice_prompt': 'O‘zbek adabiy talaffuzi (orfoepiya), X va H farqi hamda notiqlik ohangini (mayin, salobatli, tez va sekin) mashq qildiring.',
        },
    ],
    'default': [
        {
            'title': 'Universal 5-Qadamli Professor Grammatika Formulasi',
            'formula': '1 Jumla Mohiyat -> [+ / - / ?] Formula -> 3 Darajali Misol -> ❌/✅ Tuzoq -> Mini-Mashq',
            'example': 'Har qanday yangi mavzuni avval formula qolipiga soling, so‘ng 3 ta shaxsiy gap tuzing.',
            'trap': '❌ Qoidani yodlab gap tuzmaslik -> ✅ Darhol jonli nutqda 1 marta qo‘llash.',
            'practice_prompt': 'Hozirgi tilim bo‘yicha eng asosiy 5 ta gap tuzish formulasini jadval qilib bering.',
        },
    ],
}


PROFESSOR_QUIZ_BANK: dict[str, list[dict]] = {
    'en': [
        {
            'question': '[Grammar Formula] Choose the C1 Inverted Conditional equivalent of: "If you had informed me earlier, I would have helped."',
            'options': [
                'Had you informed me earlier, I would have helped.',
                'Did you inform me earlier, I would have helped.',
                'Were you to inform me earlier, I would have helped.',
                'Have you informed me earlier, I would help.',
            ],
            'answer': 'Had you informed me earlier, I would have helped.',
            'note': 'Professor Formula: Type 3 Inversion -> [Had + Subject + V3, Subject + would have + V3].',
        },
        {
            'question': '[Vocabulary Collocation] Which verb naturally collocates with "a problem / risk" at IELTS Band 8.0+ level to mean "reduce severity"?',
            'options': [
                'mitigate',
                'manufacture',
                'exaggerate',
                'procrastinate',
            ],
            'answer': 'mitigate',
            'note': 'Collocation: "mitigate a risk / mitigate the negative impact" (xavf yoki salbiy ta’sirni yumshatmoq).',
        },
        {
            'question': '[Writing Coherence] Which linker introduces a contrasting concession before a strong main clause?',
            'options': [
                'Notwithstanding the initial challenges, the project succeeded.',
                'Consequently the initial challenges, the project succeeded.',
                'Furthermore the initial challenges, the project succeeded.',
                'Because of the initial challenges, the project succeeded.',
            ],
            'answer': 'Notwithstanding the initial challenges, the project succeeded.',
            'note': '"Notwithstanding + Noun Phrase" = "...ga qaramasdan" (C1/C2 Academic Writing).',
        },
        {
            'question': '[Speaking Idiom] In natural fluent English, what does "hit the nail on the head" mean?',
            'options': [
                'To describe the exact core truth of a situation',
                'To make a careless grammatical mistake',
                'To work physically hard all day',
                'To postpone an important decision',
            ],
            'answer': 'To describe the exact core truth of a situation',
            'note': 'Nishonga aniq urmoq — muammoning eng aniq nuqtasini topib aytmoq.',
        },
        {
            'question': '[Error X-Ray] Find the 100% grammatically correct sentence:',
            'options': [
                'Scarcely had the lecture begun when the lights went out.',
                'Scarcely the lecture had begun than the lights went out.',
                'Scarcely had the lecture began when the lights went out.',
                'Scarcely did the lecture begun when the lights went out.',
            ],
            'answer': 'Scarcely had the lecture begun when the lights went out.',
            'note': 'Formula: [Scarcely/Hardly + had + S + V3 + when + S + V2].',
        },
    ],
    'ru': [
        {
            'question': "[Grammatika Formulasi] «Несмотря на то, что» iborasining qisqa C1 muqobili qaysi?",
            'options': ['Несмотря на + существительное', 'Хотя + глагол', 'Потому что', 'Всё же + глагол'],
            'answer': 'Несмотря на + существительное',
            'note': "Formula: «Несмотря на усталость, он продолжал» = «Charchoqqa qaramasdan, u davom etdi» (C1 qisqartma).",
        },
        {
            'question': "[Kollokatsiya] «способствовать» fe'li bilan eng tabiiy birikma va kelishik qaysi?",
            'options': ['способствовать развитию (Дат.)', 'способствовать стол (Им.)', 'способствовать быстро (Наречие)', 'способствовать книгу (Вин.)'],
            'answer': 'способствовать развитию (Дат.)',
            'note': "«Способствовать + Дательный падеж» -> rivojlanishga ko'maklashmoq.",
        },
        {
            'question': "[Writing Coherence] «Благодаря» predlogidan keyin qaysi kelishik ishlatiladi?",
            'options': ['Дательный падеж (кому? чему?)', 'Родительный падеж (кого? чего?)', 'Винительный падеж (кого? что?)', 'Именительный падеж'],
            'answer': 'Дательный падеж (кому? чему?)',
            'note': "To‘g‘ri: Благодаря упорному труду (Дат.), emas «благодаря труда»!",
        },
        {
            'question': "[Speaking Idiom] «Воплощать в жизнь» iborasining aniq ma’nosi nima?",
            'options': ["G‘oyani amalda ro‘yobga chiqarmoq", "Vaqtinchalik orqaga surmoq", "Xatoni yashirmoq", "Shunchaki orzu qilmoq"],
            'answer': "G‘oyani amalda ro‘yobga chiqarmoq",
            'note': "Воплощать + Вин. + в жизнь = orzu yoki rejani hayotga tatbiq etmoq.",
        },
        {
            'question': "[Error X-Ray] Qaysi gapda НСВ / СВ (fe’l turi) 100% to‘g‘ri ishlatilgan?",
            'options': [
                'Вчера я долго решал задачу и наконец решил её.',
                'Вчера я долго решил задачу и наконец решал её.',
                'Он всегда прочёл эту книгу каждый вечер.',
                'Завтра я долго напишу это письмо два часа.',
            ],
            'answer': 'Вчера я долго решал задачу и наконец решил её.',
            'note': "«Долго» (jarayon) -> НСВ (решал); «наконец» (natija) -> СВ (решил).",
        },
    ],
    'ar': [
        {
            'question': "[Grammatika Formulasi] «إنَّ» yuklamasidan keyin keluvchi Ism qaysi holatda (I‘rab) bo‘ladi?",
            'options': ['Mansub (فَتحة -a)', 'Marfu‘ (ضَمّة -u)', 'Majrur (كَسرة -i)', 'Majzum (سُكون)'],
            'answer': 'Mansub (فَتحة -a)',
            'note': 'Formula: إنَّ + [Ism Mansub (-a)] + [Xabar Marfu‘ (-u)]. Masalan: إنَّ العِلْمَ نُورٌ.',
        },
        {
            'question': "[Vocabulary Collocation] «بَرْقَرور rivojlanish» ma’nosini beruvchi rasmiy arabcha kollokatsiya qaysi?",
            'options': ['تَنْمِيَة مُسْتَدَامَة', 'فَرْق صَغِير', 'مَاء بَارِد', 'يَوْم جَدِيد'],
            'answer': 'تَنْمِيَة مُسْتَدَامَة',
            'note': 'Tanmiya Mustadama (تنمية مستدامة) — xalqaro akademik va iqtisodiy atama.',
        },
        {
            'question': "[Writing Coherence] «Shunga qaramasdan» ma’nosini beruvchi rasmiy bog‘lovchi qaysi?",
            'options': ['عَلَى الرَّغْمِ مِنْ ذَلِكَ', 'بِسَبَبِ ذَلِكَ', 'أَوَّلاً وَقَبْلَ كُلِّ شَيْء', 'فِي الحَقِيقَةِ فَقَطْ'],
            'answer': 'عَلَى الرَّغْمِ مِنْ ذَلِكَ',
            'note': '«عَلَى الرَّغْمِ مِنْ (+ Majrur)» = "...ga qaramasdan / shunga qaramasdan".',
        },
        {
            'question': "[Speaking Idiom] «دَوْر مِحْوَرِيّ» iborasining ma’nosi nima?",
            'options': ['Hal qiluvchi, markaziy rol', 'Kichik va sezilmas vazifa', 'Tashqi ko‘rinish', 'Tasodifiy uchrashuv'],
            'answer': 'Hal qiluvchi, markaziy rol',
            'note': 'Mihwari (محوري) = o‘zak/mehvar bo‘lgan, hal qiluvchi.',
        },
        {
            'question': "[Error X-Ray] Qaysi Izofa (الإضافة) birikmasi 100% to‘g‘ri yozilgan?",
            'options': ['كِتَابُ الطَّالِبِ', 'الكِتَابُ الطَّالِبِ', 'كِتَابٌ الطَّالِبُ', 'كِتَابُ الطَّالِبَ'],
            'answer': 'كِتَابُ الطَّالِبِ',
            'note': 'Izofa qoidasi: Mudofda (كِتَابُ) AL va tanvin bo‘lmaydi, Mudof ilayhi (الطَّالِبِ) esa Majrur (-i) bo‘ladi.',
        },
    ],
    'tr': [
        {
            'question': "[Grammatika Formulasi] «Gidiyorum» so‘zida «git-» ildizidagi t -> d o‘zgarishi qaysi qoidaga kiradi?",
            'options': ['Ünsüz yumuşaması (Undosh yumshashi)', 'Büyük ünlü uyumu', 'Ünlü düşmesi', 'Kaynak harfi'],
            'answer': 'Ünsüz yumuşaması (Undosh yumshashi)',
            'note': 'p/ç/t/k bilan tugagan so‘z unli bilan boshlanuvchi qo‘shimcha olsa, b/c/d/ğ ga yumshaydi (git+iyor -> gidiyor).',
        },
        {
            'question': "[Vocabulary Collocation] «Kapsamlı bir araştırma» birikmasining aniq tarjimasi nima?",
            'options': ['Keng qamrovli tadqiqot', 'Qisqa muddatli sayohat', 'Yuzaki fikr', 'Oddiy topshiriq'],
            'answer': 'Keng qamrovli tadqiqot',
            'note': 'Kapsamlı (keng qamrovli) + araştırma (tadqiqot) — TÖMER C1 kollokatsiyasi.',
        },
        {
            'question': "[Writing Coherence] Rasmiy matnda «Biroq / Shunga qaramay» ma’nosini beruvchi C1 bog‘lovchi qaysi?",
            'options': ['Buna rağmen / Ancak', 'Bu yüzden', 'İlk olarak', 'Özetle'],
            'answer': 'Buna rağmen / Ancak',
            'note': '«-e rağmen» (dativ + rağmen) = "...ga qaramasdan".',
        },
        {
            'question': "[Speaking Idiom] «Vazgeçilmez» sifati qaysi ma’noda ishlatiladi?",
            'options': ['Voz kechib bo‘lmaydigan, o‘ta zarur', 'Tez unutiladigan', 'Foydasiz va ortiqcha', 'Oson almashtiriladigan'],
            'answer': 'Voz kechib bo‘lmaydigan, o‘ta zarur',
            'note': '«Zamanımızda yabancı dil öğrenmek vazgeçilmezdir.»',
        },
        {
            'question': "[Error X-Ray] Unlilar uyg‘unligi (Ünlü uyumu) bo‘yicha 100% to‘g‘ri variant qaysi?",
            'options': [
                'Öğrenciler kütüphanede ders çalışıyorlar.',
                'Öğrencilar kütüphanada ders çalışıyorlar.',
                'Öğrenciler kütüphaneda ders çalışıyorler.',
                'Öğrencilar kütüphanede ders çalışıyörlar.',
            ],
            'answer': 'Öğrenciler kütüphanede ders çalışıyorlar.',
            'note': 'İnce unlilar (öğrenci, kütüphane) -> -ler/-de oladi; çalış-iyor esa kalın -yor/-lar bilan uyg‘unlashadi.',
        },
    ],
    'de': [
        {
            'question': "[Grammatika Formulasi] «Ich bleibe zu Hause, _____ es stark regnet.» (Sabab bog‘lovchisi) — to‘g‘ri davomi qaysi?",
            'options': ['weil es stark regnet', 'weil regnet es stark', 'weil stark regnet es', 'denn es regnet stark nicht'],
            'answer': 'weil es stark regnet',
            'note': 'Formula: Nebensatz mit «weil / dass / obwohl» -> tusalgan fe’l (regnet) gapning ENG OXIRIDA keladi.',
        },
        {
            'question': "[Vocabulary Collocation] Nemis tilida «Sicherheit gewährleisten» nimani anglatadi?",
            'options': ['Xavfsizlikni kafolatlamoq / ta’minlamoq', 'Xavfni oshirmoq', 'Shartnomani bekor qilmoq', 'Vaqtni boy bermoq'],
            'answer': 'Xavfsizlikni kafolatlamoq / ta’minlamoq',
            'note': 'Gewährleisten — B2/C1 rasmiy va biznes uslubidagi kuchli fe’l.',
        },
        {
            'question': "[Writing Coherence] C1 inshoda «Shunga qaramasdan» ma’nosini beruvchi inversiya bog‘lovchisi qaysi?",
            'options': ['Dennoch (+ Verb an Position 2)', 'Deshalb (+ Verb an Position 2)', 'Darüber hinaus', 'Zunächst einmal'],
            'answer': 'Dennoch (+ Verb an Position 2)',
            'note': '«Es ist schwer; dennoch lohnt es sich.» (Dennoch 1-o‘rinda, fe’l 2-o‘rinda!).',
        },
        {
            'question': "[Speaking Idiom] «Der ausschlaggebende Faktor» iborasi nimani bildiradi?",
            'options': ['Hal qiluvchi omil', 'Ikkinchi darajali detal', 'Tasodifiy xato', 'Boshlang‘ich taxmin'],
            'answer': 'Hal qiluvchi omil',
            'note': 'Ausschlaggebend = tarozi pallasini bosuvchi, hal qiluvchi.',
        },
        {
            'question': "[Error X-Ray] Predlog va kelishik (Kasus) jihatidan 100% to‘g‘ri gap qaysi?",
            'options': [
                'Ich fahre jeden Morgen mit dem Bus zur Arbeit.',
                'Ich fahre jeden Morgen mit den Bus zur Arbeit.',
                'Ich fahre jeden Morgen mit der Bus zu Arbeit.',
                'Ich fahre jeden Morgen für dem Bus zur Arbeit.',
            ],
            'answer': 'Ich fahre jeden Morgen mit dem Bus zur Arbeit.',
            'note': '«mit» doim Dativ talab qiladi: der Bus -> mit dem Bus; die Arbeit -> zu + der = zur Arbeit.',
        },
    ],
    'ko': [
        {
            'question': "[Grammatika Formulasi] Buyruq (-세요) yoki taklif (-읍시다) bilan qaysi sabab qo‘shimchasi ishlatiladi?",
            'options': ['-(으)니까', '-아/어서', '-지만', '-거나'],
            'answer': '-(으)니까',
            'note': 'Qoida: -아/어서 buyruq/taklif bilan ishlamaydi! «시간이 없으니까 빨리 가세요.»',
        },
        {
            'question': "[Vocabulary Collocation] «위기를 극복하다» birikmasining ma’nosi nima?",
            'options': ['Inqirozni / qiyinchilikni yengib o‘tmoq', 'Yangi muammo yaratmoq', 'Vaziyatdan qochmoq', 'Ishni keyinga qoldirmoq'],
            'answer': 'Inqirozni / qiyinchilikni yengib o‘tmoq',
            'note': '위기 (inqiroz) + 극복하다 (yengib o‘tmoq) — TOPIK II eng faol kollokatsiyasi.',
        },
        {
            'question': "[Writing Coherence] Akademik inshoda «Nafaqat A, balki B ham» konstruksiyasi qaysi?",
            'options': ['-(으)ㄹ 뿐만 아니라', '-기 때문에', '-(으)므로', '-는 반면에'],
            'answer': '-(으)ㄹ 뿐만 아니라',
            'note': '«지식뿐만 아니라 경험도 중요하다» = Nafaqat bilim, balki tajriba ham muhim.',
        },
        {
            'question': "[Speaking Idiom] «필수적인 요소» iborasi nimani bildiradi?",
            'options': ['Eng zarur / ajralmas unsur', 'Keraksiz qo‘shimcha', 'Tasodifiy natija', 'Oddiy misol'],
            'answer': 'Eng zarur / ajralmas unsur',
            'note': '필수적이다 (zaruriy) + 요소 (unsur/omil).',
        },
        {
            'question': "[Error X-Ray] Harakat sodir bo‘layotgan joy partikli (에 vs 에서) to‘g‘ri ishlatilgan gap qaysi?",
            'options': [
                '도서관에서 한국어를 공부해요.',
                '도서관에 한국어를 공부해요.',
                '집에서 가요.',
                '학교에서 있어요.',
            ],
            'answer': '도서관에서 한국어를 공부해요.',
            'note': 'Faol harakat joyi (o‘qish, ishlash) -> 에서; joylashuv/borish yo‘nalishi -> 에.',
        },
    ],
    'fr': [
        {
            'question': "[Grammaire C1] Qaysi gapda «Subjonctif» to'g'ri ishlatilgan?",
            'options': [
                'Il faut que tu viennes maintenant.',
                'Il faut que tu viens maintenant.',
                'Je sais que tu viennes.',
                'Il pense que tu puisses.',
            ],
            'answer': 'Il faut que tu viennes maintenant.',
            'note': '«Il faut que» -> Subjonctif talab qiladi: venir -> vienne/viennes.',
        },
        {
            'question': "[Vocabulaire B2] «Néanmoins» so'zi qaysi ma'noni bildiradi?",
            'options': ['Shunga qaramasdan, baribir', 'Shuning uchun', 'Demak, xulosa qilib', 'Avvalo, birinchi navbatda'],
            'answer': 'Shunga qaramasdan, baribir',
            'note': "«Néanmoins» = nevertheless -> ziddiyatni ifodalovchi C1 bog'lovchi.",
        },
        {
            'question': "[Writing Coherence] «Bien que» (Garchi ... bo‘lsa ham) bog‘lovchisidan keyin qaysi mayl ishlatiladi?",
            'options': ['Le Subjonctif', 'Le Futur simple', 'L’Impératif', 'Le Conditionnel passé'],
            'answer': 'Le Subjonctif',
            'note': '«Bien que ce soit difficile, nous réussirons.» — DELF B2/C1 oltin qoidasi.',
        },
        {
            'question': "[Speaking Idiom] «Un outil incontournable» iborasining ma’nosi nima?",
            'options': ['Chetlashib bo‘lmaydigan, o‘ta zarur vosita', 'Eskirgan asbob', 'Taqiqlangan narsa', 'Foydasiz buyum'],
            'answer': 'Chetlashib bo‘lmaydigan, o‘ta zarur vosita',
            'note': 'Incontournable — zamonaviy fransuz matbuotida eng ko‘p uchraydigan C1 sifat.',
        },
        {
            'question': "[Error X-Ray] Passé composé bilan «être» yordamchi fe’li moslashuvi to‘g‘ri berilgan gap qaysi?",
            'options': [
                'Marie est partie tôt ce matin.',
                'Marie est parti tôt ce matin.',
                'Marie a partie tôt ce matin.',
                'Marie est partis tôt ce matin.',
            ],
            'answer': 'Marie est partie tôt ce matin.',
            'note': '«être» bilan kelgan sifatdosh ega (Marie — jenskiy rod) bilan jins va sonda moslashadi (-e).',
        },
    ],
    'es': [
        {
            'question': "[Gramática C1] «Si hubiera estudiado más, habría aprobado» — bu qaysi conditional?",
            'options': ['Condicional Perfecto (Type 3)', 'Condicional Simple (Type 2)', 'Presente de Subjuntivo', 'Futuro Perfecto'],
            'answer': 'Condicional Perfecto (Type 3)',
            'note': "Formula: Si + hubiera/hubiese + V3 -> habría + V3 (o'tmishdagi imkonsiz shart).",
        },
        {
            'question': "[Vocabulary Collocation] «Un argumento contundente» nimani bildiradi?",
            'options': ['Kuchli, ishonchli va hal qiluvchi dalil', 'Shubhali gumon', 'Qisqa savol', 'Noto‘g‘ri xulosa'],
            'answer': 'Kuchli, ishonchli va hal qiluvchi dalil',
            'note': 'Contundente — DELE B2/C1 munozaralarida eng yuqori baholanadigan kollokatsiya.',
        },
        {
            'question': "[Writing Coherence] «Por consiguiente» bog‘lovchisining aniq vazifasi nima?",
            'options': ['Natija va xulosa bildirish (shuning uchun)', 'Ziddiyat bildirish', 'Misol keltirish', 'Vaqt tartibini ko‘rsatish'],
            'answer': 'Natija va xulosa bildirish (shuning uchun)',
            'note': '«Por consiguiente / En consecuencia» = C1 akademik natija bog‘lovchisi.',
        },
        {
            'question': "[Speaking Idiom] «Es imprescindible + infinitivo» iborasining ma’nosi nima?",
            'options': ['Mutlaqo zarur / shart', 'Mutlaqo taqiqlangan', 'Ehtimoldan yiroq', 'Shunchaki qo‘shimcha'],
            'answer': 'Mutlaqo zarur / shart',
            'note': '«Es imprescindible practicar todos los días.»',
        },
        {
            'question': "[Error X-Ray] Ser vs Estar qoidasi bo‘yicha 100% to‘g‘ri gap qaysi?",
            'options': [
                'El museo está en el centro de la ciudad.',
                'El museo es en el centro de la ciudad.',
                'Hoy yo soy muy cansado.',
                'Madrid es en España.',
            ],
            'answer': 'El museo está en el centro de la ciudad.',
            'note': 'Joylashuv (qayerda?) uchun doim ESTAR, hozirgi charchoq holati uchun ham ESTAR (estoy cansado).',
        },
    ],
    'zh': [
        {
            'question': "[语法 HSK5] «虽然…但是…» konstruksiyasining ingliz tilidagi muqobili qaysi?",
            'options': ['Although… nevertheless…', 'Because… therefore…', 'If… then…', 'Not only… but also…'],
            'answer': 'Although… nevertheless…',
            'note': "虽然 (garchi) + 但是 (lekin/ammo) -> ziddiyat bog'lovchisi. «虽然很难，但是值得。»",
        },
        {
            'question': "[Vocabulary HSK5] «坚持不懈 (jiānchí bùxiè)» iborasining ma’nosi nima?",
            'options': ['Qat’iyat va sabr bilan to‘xtovsiz harakat qilmoq', 'Bir kunda voz kechmoq', 'Tasodifan yutib olmoq', 'Shoshilib xato qilmoq'],
            'answer': 'Qat’iyat va sabr bilan to‘xtovsiz harakat qilmoq',
            'note': '坚持不懈地努力 = uzluksiz matonat bilan harakat qilish.',
        },
        {
            'question': "[Writing Coherence] Rasmiy matnda «Nafaqat..., balki...» qolipi qaysi?",
            'options': ['不仅…而且… (bùjǐn… érqiě…)', '如果…就…', '只有…才…', '一边…一边…'],
            'answer': '不仅…而且… (bùjǐn… érqiě…)',
            'note': '不仅 (nafaqat) + 而且 (balki / yana) — HSK 4–6 yozuvining asosiy qolipi.',
        },
        {
            'question': "[Speaking Idiom] «相辅相成 (xiāng fǔ xiāng chéng)» chengyu iborasi nimani bildiradi?",
            'options': ['Ikki narsa bir-birini to‘ldirib kuchaytirishi', 'Bir-biriga qarshi chiqishi', 'Alohida-alohida yo‘qolishi', 'Hech qanday aloqasi yo‘qligi'],
            'answer': 'Ikki narsa bir-birini to‘ldirib kuchaytirishi',
            'note': 'Masalan: 理论和实践相辅相成 (Nazariya va amaliyot bir-birini to‘ldiradi).',
        },
        {
            'question': "[Error X-Ray] 把 (bǎ) konstruksiyasi grammatik jihatdan 100% to‘g‘ri tuzilgan gap qaysi?",
            'options': [
                '我把作业做完了。',
                '我把作业做。',
                '我做了把作业。',
                '我把作业不知道。',
            ],
            'answer': '我把作业做完了。',
            'note': 'Formula: S + 把 + O + Fe’l + Natija/了 (做完 — bajarib tugatmoq). Yolg‘iz fe’l bilan tugamaydi!',
        },
    ],
    'ja': [
        {
            'question': "[文法 JLPT N2] «〜にもかかわらず» iborasining ma'nosi nima?",
            'options': ['...ga qaramasdan (despite)', '...sababli (because)', '...uchun (in order to)', '...kabi (as if)'],
            'answer': '...ga qaramasdan (despite)',
            'note': "「雨にもかかわらず出かけた」= Yomg'irga qaramasdan chiqib ketdi. C1/N2 darajasi.",
        },
        {
            'question': "[Vocabulary Collocation] «困難を克服する (konnan wo kokufuku suru)» nimani bildiradi?",
            'options': ['Qiyinchilikni yengib o‘tmoq', 'Qiyinchilikdan qochmoq', 'Ishni to‘xtatmoq', 'Shunchaki kuzatmoq'],
            'answer': 'Qiyinchilikni yengib o‘tmoq',
            'note': '克服 (kokufuku) = yengish; JLPT N2 akademik lug‘at.',
        },
        {
            'question': "[Writing Coherence] Yapon matnida «Bir tomondan..., boshqa tomondan...» (qarama-qarshi jihat) qolipi qaysi?",
            'options': ['一方で (ippō de)', 'なぜなら (nazenara)', 'たとえば (tatoeba)', 'つまり (tsumari)'],
            'answer': '一方で (ippō de)',
            'note': 'A のメリットがある一方で、B という課題もある (Bir tomondan foydasi bor, ikkinchi tomondan muammo ham bor).',
        },
        {
            'question': "[Speaking Idiom] «臨機応変 (rinki ōhen)» iborasi qaysi xislatni anglatadi?",
            'options': ['Vaziyatga qarab tez va oqilona moslashish', 'Qoidalarga ko‘r-ko‘rona ergashish', 'Hech qachon qaror qilmaslik', 'Faqat o‘tmishni eslash'],
            'answer': 'Vaziyatga qarab tez va oqilona moslashish',
            'note': '臨機応変に対応する = vaziyatga mos tarzda harakat qilish (JLPT N1).',
        },
        {
            'question': "[Error X-Ray] Harakat joyi partikli (で vs に) 100% to‘g‘ri qo‘yilgan gap qaysi?",
            'options': [
                '図書館で日本語を勉強します。',
                '図書館に日本語を勉強します。',
                '図書館が日本語を勉強します。',
                '東京へ住んでいます。',
            ],
            'answer': '図書館で日本語を勉強します。',
            'note': 'Harakat sodir bo‘ladigan joy (勉強します — o‘qiyman) bilan で ishlatiladi!',
        },
    ],
    'it': [
        {
            'question': "[Grammatica C1] «Sebbene / Benché» bog‘lovchilaridan keyin qaysi fe’l mayli ishlatiladi?",
            'options': ['Il Congiuntivo', 'L’Indicativo futuro', 'L’Imperativo', 'Il Gerundio'],
            'answer': 'Il Congiuntivo',
            'note': '«Sebbene sia tardi, studio ancora.» — CILS B2/C1 oltin qoidasi.',
        },
        {
            'question': "[Vocabulary Collocation] «Un’esecuzione impeccabile» iborasining ma’nosi nima?",
            'options': ['Beg‘ubor va nuqsonsiz ijro', 'Shoshilinch va xato ish', 'Oddiy mashq', 'Kechikkan natija'],
            'answer': 'Beg‘ubor va nuqsonsiz ijro',
            'note': 'Impeccabile — hech qanday nuqsoni yo‘q mukammal daraja (C1).',
        },
        {
            'question': "[Writing Coherence] Akademik matnda «Xulosa qilib aytganda / Natijada» ma’nosidagi ibora qaysi?",
            'options': ['Di conseguenza / Pertanto', 'Al contrario', 'Nonostante ciò', 'Inizialmente'],
            'answer': 'Di conseguenza / Pertanto',
            'note': 'Pertanto = shuning uchun, natijada (rasmiy C1 bog‘lovchi).',
        },
        {
            'question': "[Speaking Idiom] «Acquisire consapevolezza» nimani anglatadi?",
            'options': ['Chuqur ongli tushuncha va xabardorlik hosil qilish', 'Barcha ma’lumotni unutish', 'Vaqtni behuda sarflash', 'Bahsdan qochish'],
            'answer': 'Chuqur ongli tushuncha va xabardorlik hosil qilish',
            'note': 'Consapevolezza = onglilik, anglab yetish.',
        },
        {
            'question': "[Error X-Ray] Passato prossimo va Essere moslashuvi to‘g‘ri berilgan gap qaysi?",
            'options': [
                'Giulia è arrivata in orario.',
                'Giulia è arrivato in orario.',
                'Giulia ha arrivata in orario.',
                'Giulia è arrivate in orario.',
            ],
            'answer': 'Giulia è arrivata in orario.',
            'note': '«arrivare» (kelmoq) Essere bilan tuslanadi va Giulia (ayol jinsi, birlik) uchun «arrivata» bo‘ladi!',
        },
    ],
    'uz': [
        {
            'question': '[Shevashunoslik] Xorazm (O‘g‘uz) lahjasida «Kelinglar, birga o‘rganamiz» jumlasi tabiiy qanday aytiladi?',
            'options': [
                'Galingla, birgalashib o‘rganjakmiz',
                'Kevottila, birga o‘qivomiz',
                'Keloptila, birga o‘qioptik',
                'Kelayaptilar, o‘qimoqdamiz',
            ],
            'answer': 'Galingla, birgalashib o‘rganjakmiz',
            'note': 'O‘g‘uz lahjasida so‘z boshidagi k -> g (kel -> gal) va kelasi zamon -jak/-ajak qo‘shimchasi faol qo‘llanadi.',
        },
        {
            'question': '[Hududiy Shevalar] Fe’lning «kelopti, boropti, aytopti» shakli qaysi hudud shevasiga xos?',
            'options': [
                'Samarqand–Buxoro shevasiga',
                'Xorazm shevasiga',
                'Faqat rasmiy hujjat uslubiga',
                'Qoraqalpoq tiliga',
            ],
            'answer': 'Samarqand–Buxoro shevasiga',
            'note': 'Samarqand va Buxoro qarluq shevalarida hozirgi zamon davom fe’li «-opti / -omman / -opsiz» shaklida aytiladi.',
        },
        {
            'question': '[Orfoepiya va Imlo] Qaysi qatorda X va H undoshlari ma’no farqlagan (paronim) juftlik to‘g‘ri berilgan?',
            'options': [
                'Shox (daraxt shoxi) — Shoh (podshoh)',
                'Xamma — Hamma (ikkalasi bir xil ma’no)',
                'Xozir — Hozir (ikkalasi to‘g‘ri imlo)',
                'Baxt — Baht (ikkalasi adabiy imlo)',
            ],
            'answer': 'Shox (daraxt shoxi) — Shoh (podshoh)',
            'note': 'Shox (novda) — chuqur til orqa X; Shoh (hukmdor) — bo‘g‘iz undoshi H bilan yoziladi va talaffuz qilinadi.',
        },
        {
            'question': '[Notiqlik va Uslub] «Fasohat bilan so‘zlamoq» iborasi nimani anglatadi?',
            'options': [
                'Tiniq, ravon, til me’yorlariga mos va ta’sirchan gapirmoq',
                'Juda baland ovozda baqirib gapirmoq',
                'Faqat chet so‘zlarni aralashtirib gapirmoq',
                'Jumlalarni yarim chala qoldirmoq',
            ],
            'answer': 'Tiniq, ravon, til me’yorlariga mos va ta’sirchan gapirmoq',
            'note': 'Fasohat — nutqning sofligi, ravonligi va go‘zal talaffuzi demakdir.',
        },
        {
            'question': '[Toshkent shevasi vs Adabiy til] Toshkent so‘zlashuv nutqidagi «Nima qivosiz?» so‘rog‘ining sof adabiy shakli qaysi?',
            'options': [
                'Nima qilyapsiz? (yoki Nima qilmoqdasiz?)',
                'Nima qilopsiz?',
                'Nima qilyabsiz?',
                'Nima qiljakmiz?',
            ],
            'answer': 'Nima qilyapsiz? (yoki Nima qilmoqdasiz?)',
            'note': 'Toshkent shevasidagi «-vosiz / -vomman / -votti» adabiy tilda «-yapsiz / -yapman / -yapti» me’yoriga to‘g‘ri keladi.',
        },
    ],
    'default': [
        {
            'question': '[30-Yillik Professor Metodikasi] Grammatik qoidani 2 daqiqada mukammal eslab qolishning oltin tartibi qaysi?',
            'options': [
                '1 jumlada mantiq -> [+ / - / ?] Oltin Formula -> 3 darajali jonli misol (A1-C2)',
                'Faqat uzun nazariy qoidalarni yodlash',
                'Lug‘atni kontekstsiz va misolsiz o‘qish',
                'Xatolarni tahlil qilmasdan keyingi mavzuga o‘tish',
            ],
            'answer': '1 jumlada mantiq -> [+ / - / ?] Oltin Formula -> 3 darajali jonli misol (A1-C2)',
            'note': 'Professor oltin qoidasi: Mantiq + Formula + Jonli kontekst!',
        },
        {
            'question': '[Vocabulary & Mnemonika] Yangi so‘zni uzoq muddatli xotiraga muhrlash uchun nima eng muhim?',
            'options': [
                'Tabiiy birikma (kollokatsiya) + yorqin assotsiatsiya (mnemonika) + jonli jumla',
                'So‘zni yolg‘iz o‘zini 50 marta ko‘chirib yozish',
                'Faqat tarjimasini ko‘rib chiqish',
                'Talaffuziga e’tibor bermaslik',
            ],
            'answer': 'Tabiiy birikma (kollokatsiya) + yorqin assotsiatsiya (mnemonika) + jonli jumla',
            'note': 'Ona tilida so‘zlar yakka emas, kollokatsiya (birikma) holida yashaydi.',
        },
        {
            'question': '[Speaking & Listening] "Shadowing" texnikasining asosiy vazifasi nima?',
            'options': [
                'Spikerning ohangi, urg‘usi va bog‘lama talaffuzini (connected speech) birga-bir qaytarib o‘zlashtirish',
                'Matnni ovozsiz ichida o‘qish',
                'Faqat grammatik test yechish',
                'So‘zlarni alifbo tartibida yodlash',
            ],
            'answer': 'Spikerning ohangi, urg‘usi va bog‘lama talaffuzini (connected speech) birga-bir qaytarib o‘zlashtirish',
            'note': 'Shadowing — eshitish va ravon talaffuzni bir vaqtda C1 darajaga olib chiqadi.',
        },
        {
            'question': '[Writing Coherence] Inshoning "Coherence & Cohesion" mezonini keskin oshiradigan usul qaysi?',
            'options': [
                'Har bir abzasni bitta aniq g‘oya (Topic Sentence), mantiqiy bog‘lovchilar va dalil bilan qurish',
                'Barcha fikrlarni bitta uzun abzasga yozish',
                'Mavzudan chetga chiqib, murakkab lekin ma’nosiz so‘zlar terish',
                'Xulosa qismini yozmaslik',
            ],
            'answer': 'Har bir abzasni bitta aniq g‘oya (Topic Sentence), mantiqiy bog‘lovchilar va dalil bilan qurish',
            'note': 'Topic Sentence + Evidence + Linker = Band 8.0+ abzas strukturasi.',
        },
        {
            'question': '[Error X-Ray] Xatolarni tuzatishning eng samarali usuli qaysi?',
            'options': [
                '❌ Asl xato -> ✅ To‘g‘ri variant -> 🌟 Native/C1 muqobil + 1 qator qoidani solishtirish',
                'Xatoni umuman e’tiborsiz qoldirish',
                'Sababini bilmasdan faqat to‘g‘ri javobni ko‘chirish',
                'Xato qilishdan qo‘rqib gapirmaslik',
            ],
            'answer': '❌ Asl xato -> ✅ To‘g‘ri variant -> 🌟 Native/C1 muqobil + 1 qator qoidani solishtirish',
            'note': 'Har bir xato — eng tez o‘sish nuqtasi!',
        },
    ],
}


def load_state() -> dict:
    raw = workspace_store.read(STORAGE_FILE, {})
    state = default_state()
    if not isinstance(raw, dict):
        return state
    lang = str(raw.get('target_language') or 'en').strip()
    state['target_language'] = lang if lang in LANGUAGE_MAP else 'en'
    state['custom_language'] = str(raw.get('custom_language') or '').strip()[:60]
    level = str(raw.get('level') or 'B1').strip().upper()
    state['level'] = level if level in LEVEL_MAP else 'B1'
    role = str(raw.get('teacher_role') or 'universal_professor').strip()
    state['teacher_role'] = role if role in ROLE_MAP else 'universal_professor'
    skill = str(raw.get('active_skill') or 'general').strip().lower()
    state['active_skill'] = skill if skill in SKILL_MAP else 'general'
    explain = str(raw.get('explain_language') or 'uz').strip()
    state['explain_language'] = explain if any(explain == k for k, _ in EXPLAIN_MODES) else 'uz'
    criteria = raw.get('criteria')
    if isinstance(criteria, list):
        valid = [k for k, _, _ in CRITERIA_FLAGS if k in criteria]
        state['criteria'] = valid or list(DEFAULT_CRITERIA)
    state['ask_on_startup'] = bool(raw.get('ask_on_startup', True))
    state['onboarded'] = bool(raw.get('onboarded', False))
    chats = raw.get('skill_chats')
    if isinstance(chats, dict):
        state['skill_chats'] = {
            str(k): str(v) for k, v in chats.items()
            if isinstance(k, str) and isinstance(v, str) and 1 <= len(v) <= 64
        }
    vocab = raw.get('vocab_bank')
    if isinstance(vocab, list):
        clean_vocab = []
        for item in vocab[:200]:
            if isinstance(item, dict) and item.get('word'):
                clean_vocab.append({
                    'word': str(item.get('word', '')).strip()[:80],
                    'meaning': str(item.get('meaning', '')).strip()[:120],
                    'collocation': str(item.get('collocation', '')).strip()[:120],
                    'mnemonic': str(item.get('mnemonic', '')).strip()[:140],
                    'lang': str(item.get('lang', state['target_language'])).strip()[:16],
                    'mastered': bool(item.get('mastered', False)),
                    'review_count': int(item.get('review_count', 0) if isinstance(item.get('review_count'), int) else 0),
                })
        state['vocab_bank'] = clean_vocab
    return state


def save_state(state: dict) -> dict:
    clean = default_state()
    clean.update(state or {})
    try:
        workspace_store.write(STORAGE_FILE, clean)
    except OSError:
        pass
    return clean


def language_display_name(state: dict | None = None) -> str:
    state = state or load_state()
    code = state.get('target_language', 'en')
    if code == 'custom' and state.get('custom_language'):
        return state['custom_language']
    item = LANGUAGE_MAP.get(code, LANGUAGES[0])
    return t(item.title)


def role_display(state: dict | None = None) -> TeacherRole:
    state = state or load_state()
    return ROLE_MAP.get(state.get('teacher_role', 'universal_professor'), TEACHER_ROLES[0])


def skill_display(state: dict | None = None) -> SkillChannel:
    state = state or load_state()
    return SKILL_MAP.get(state.get('active_skill', 'general'), SKILLS[-1])


def build_professor_system_prompt(state: dict | None = None) -> str:
    """Construct the complete 30-year Professor system prompt for Ollama and Gemini Live."""
    state = state or load_state()
    lang_code = state.get('target_language', 'en')
    lang_item = LANGUAGE_MAP.get(lang_code, LANGUAGES[0])
    target_name = (
        state['custom_language']
        if lang_code == 'custom' and state.get('custom_language')
        else f"{lang_item.title} ({lang_item.native_name})"
    )
    level = state.get('level', 'B1')
    level_title, level_desc = LEVEL_MAP.get(level, LEVEL_MAP['B1'])
    role = role_display(state)
    skill = skill_display(state)
    explain_mode = state.get('explain_language', 'uz')
    explain_instructions = {
        'uz': (
            "Explain rules, feedback, and meta-commentary clearly in Uzbek (O'zbek tili), "
            f"while providing all target examples, dialogues, and practice in {target_name}."
        ),
        'bilingual': (
            f"Write responses 50% in {target_name} and 50% with concise Uzbek explanations "
            "so the student both immerses and understands 100%."
        ),
        'target': (
            f"Conduct the entire lesson 100% in {target_name} (Full Immersion), "
            f"adapting vocabulary to level {level}, unless the student explicitly asks for a translation."
        ),
        'ru': (
            "Explain rules, feedback, and meta-commentary clearly in Russian (Русский язык), "
            f"while providing all target examples, dialogues, and practice in {target_name}."
        ),
        'en': (
            "Explain rules, feedback, and meta-commentary clearly in English, "
            f"while providing all target examples, dialogues, and practice in {target_name}."
        ),
    }.get(explain_mode, "Explain clearly in the user's preferred language with target language examples.")

    active_criteria = set(state.get('criteria') or DEFAULT_CRITERIA)
    criteria_lines = []
    if 'simple_fast' in active_criteria:
        criteria_lines.append(
            "- SODDA VA TEZ FORMULA (SIMPLE & FAST): Explain every concept with 1-sentence core logic "
            "+ an explicit structural [Formula] so the student grasps it immediately."
        )
    if 'error_xray' in active_criteria:
        criteria_lines.append(
            "- XATOLAR RENTGENI (ERROR X-RAY): Whenever the student makes a mistake in the target language, "
            "show: ❌ Student version -> ✅ Corrected version -> 🌟 Native/Professor version + 1-line why."
        )
    if 'band_score' in active_criteria:
        criteria_lines.append(
            f"- MEZONLI BAHOLASH (CRITERIA SCORING): Evaluate performance using {lang_item.exam_system} "
            f"and CEFR ({level}) criteria."
        )
    if 'mnemonic' in active_criteria:
        criteria_lines.append(
            "- MNEMONIKA VA KOLLOKATSIYA: Always pair new words with natural collocations and a vivid "
            "memory association (mnemonic) so the student never forgets."
        )
    if 'mini_drill' in active_criteria:
        criteria_lines.append(
            "- FAOL MINI-MASHQ: End every teaching explanation with 1 short, interactive practice question "
            "or sentence for the student to try right away."
        )

    criteria_block = '\n'.join(criteria_lines)
    linguistic_guide = LANGUAGE_LINGUISTIC_GUIDES.get(lang_code, LANGUAGE_LINGUISTIC_GUIDES['default'])
    if lang_code == 'custom' and state.get('custom_language'):
        linguistic_guide = (
            f"LANGUAGE-SPECIFIC PEDAGOGY ({state['custom_language']}): "
            + LANGUAGE_LINGUISTIC_GUIDES['default']
        )
    return (
        "\n\n=== 🎓 AI LANGUAGE PROFESSOR & 7-SKILL ACADEMY PROTOCOL ===\n"
        f"TARGET LANGUAGE TO TEACH: {target_name} ({lang_item.exam_system})\n"
        f"STUDENT CURRENT LEVEL: {level_title} — {level_desc}\n"
        f"ACTIVE TEACHER PERSONA: {role.title}\n"
        f"PERSONA DIRECTIVE: {role.persona_prompt}\n"
        f"EXPLANATION LANGUAGE MODE: {explain_instructions}\n"
        f"{linguistic_guide}\n\n"
        f"{skill.criteria_prompt}\n\n"
        "CORE 30-YEAR PROFESSOR PEDAGOGICAL CRITERIA:\n"
        f"{criteria_block}\n"
        "=== END OF LANGUAGE PROFESSOR PROTOCOL ===\n"
    )


def extract_vocab_from_reply(text: str) -> list[dict[str, str]]:
    """Extract structured vocabulary items (word, meaning, collocation, mnemonic) from AI reply markdown."""
    import re
    if not text or not text.strip():
        return []
    candidates: list[dict[str, str]] = []
    seen: set[str] = set()
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    # Pattern 1: Bold or plain bullet items like "- **ubiquitous** — hamma joyda uchraydigan" or "1. mitigate: yumshatmoq"
    bullet_re = re.compile(
        r'^(?:[-*•🔹📌💎]\s*|\d+[.)]\s*)?(?:\*\*|`)?([^*\n`—–:|]{2,60}?)(?:\*\*|`)?\s*(?:—|–|:|\s-\s)\s*(.+)$'
    )
    skip_headers = {
        'so‘z pasporti', 'soz pasporti', 'top kollokatsiyalar', 'darajalar pog‘onasi',
        'eslab qolish siri', 'jonli kontekst', 'xatolar rentgeni', 'mezonlar bo‘yicha baho',
        '1 jumlada mohiyat', 'oltin formula', 'faol bo‘lim', 'kalit iboralar',
        'sababi va qoida', 'natija', 'tasdiq', 'muammo', 'variant a', 'variant b',
    }
    for ln in lines:
        m = bullet_re.match(ln)
        if not m:
            continue
        raw_word = m.group(1).strip().strip('"\'[]()')
        raw_rest = m.group(2).strip()
        if not raw_word or raw_word.casefold() in skip_headers or raw_word.startswith(('[', '❌', '✅', '🌟', '###')):
            continue
        if len(raw_word.split()) > 6:
            continue
        colloc = ''
        mnem = ''
        meaning = raw_rest
        if '|' in raw_rest:
            parts = [p.strip() for p in raw_rest.split('|') if p.strip()]
            meaning = parts[0]
            for extra in parts[1:]:
                low = extra.casefold()
                if low.startswith(('mnemon', '💡', 'eslab')):
                    mnem = re.sub(r'^(?:mnemonika\s*:|💡)\s*', '', extra, flags=re.IGNORECASE).strip()
                else:
                    colloc = re.sub(r'^(?:kollokatsiya\s*:|🔗)\s*', '', extra, flags=re.IGNORECASE).strip()
        key = raw_word.casefold()
        if key not in seen and meaning:
            seen.add(key)
            candidates.append({
                'word': raw_word[:80],
                'meaning': meaning[:120],
                'collocation': colloc[:120],
                'mnemonic': mnem[:140],
            })
        if len(candidates) >= 12:
            break

    # Pattern 2: Upgrade/correction pairs like "❌ mistake -> ✅ corrected -> 🌟 native"
    if not candidates:
        upgrade_re = re.compile(r'🌟\s*(?:Native[^:]*:\s*)?([^\n]+)')
        for ln in lines:
            um = upgrade_re.search(ln)
            if um:
                phrase = um.group(1).strip().strip('"\'')
                if 2 <= len(phrase) <= 80 and phrase.casefold() not in seen:
                    seen.add(phrase.casefold())
                    candidates.append({
                        'word': phrase,
                        'meaning': 'C1 / Native ibora (chatdan saqlangan)',
                        'collocation': '',
                        'mnemonic': '',
                    })
                    if len(candidates) >= 5:
                        break
    return candidates


def build_study_report_markdown(
    state: dict | None = None,
    streak_stats: dict | None = None,
    skill_counts: dict[str, int] | None = None,
) -> str:
    """Generate a comprehensive Markdown learning & CEFR progress report for the learner."""
    state = state or load_state()
    lang_code = state.get('target_language', 'en')
    lang_item = LANGUAGE_MAP.get(lang_code, LANGUAGES[0])
    lang_name = language_display_name(state)
    level = state.get('level', 'B1')
    role = role_display(state)
    streak_stats = streak_stats or {}
    skill_counts = skill_counts or {}

    items = [v for v in (state.get('vocab_bank') or []) if v.get('lang', lang_code) == lang_code]
    total_vocab = len(items)
    mastered = [v for v in items if v.get('mastered')]
    review_needed = [v for v in items if not v.get('mastered')]
    pct = int(round(len(mastered) / total_vocab * 100)) if total_vocab else 0
    total_msgs = sum(int(skill_counts.get(s.key, 0)) for s in SKILLS)

    lines = [
        f"# 🎓 TAI Akademiya — Shaxsiy O‘quv Hisoboti ({lang_name})",
        "",
        f"- **Maqsad til:** {lang_name} (`{lang_item.exam_system}`)",
        f"- **Joriy CEFR darajasi:** `{level}`",
        f"- **Faol AI Ustoz:** {t(role.title)}",
        f"- **Kunlik streak:** {streak_stats.get('streak', 0)} kun (Jami faol kunlar: {streak_stats.get('total_days', 0)})",
        f"- **Shaxsiy lug‘at:** {total_vocab} ta so‘z · Yodlangan: {len(mastered)} ({pct}%) · Takrorlash kerak: {len(review_needed)}",
        f"- **Jami amaliy xabarlar:** {total_msgs} ta",
        "",
        "## 📊 7 Ta Ko‘nikma Bo‘yicha Faollik",
        "| Ko‘nikma | Xabarlar soni | Imtihon mezonlari |",
        "| --- | ---: | --- |",
    ]
    for skill in SKILLS:
        cnt = int(skill_counts.get(skill.key, 0))
        lines.append(f"| {skill.short_title} | {cnt} | {skill.criteria_badge} |")

    lines.append("")
    lines.append("## 📚 Shaxsiy Lug‘at va Holati")
    if not items:
        lines.append("_Hozircha saqlangan so‘zlar yo‘q._")
    else:
        lines.append("| So‘z / Ibora | Ma’nosi | Kollokatsiya | Holati |")
        lines.append("| --- | --- | --- | --- |")
        for v in items[:100]:
            status = "🌟 Yodlangan" if v.get('mastered') else "⏳ Takrorlash"
            w = str(v.get('word', '')).replace('|', '/')
            m = str(v.get('meaning', '')).replace('|', '/')
            col = str(v.get('collocation', '')).replace('|', '/') or '—'
            lines.append(f"| **{w}** | {m} | {col} | {status} |")

    # Identify weakest skill channel to recommend next action
    practice_skills = [s for s in SKILLS if s.key != 'general']
    weakest = min(practice_skills, key=lambda s: int(skill_counts.get(s.key, 0)))
    lines.extend([
        "",
        "## 🎯 Professor Tavsiyasi (Keyingi Qadam)",
        f"1. **Eng kam mashq qilingan bo‘lim:** `{weakest.title}` ({int(skill_counts.get(weakest.key, 0))} xabar) — bugun shu bo‘limda 10 daqiqa mashq qiling.",
        f"2. **Lug‘at takrorlash:** Hozir {len(review_needed)} ta so‘z takrorlash navbatida turibdi — `🗂 Flashcard` tugmasi orqali mustahkamlang.",
        "3. **Kundalik formula:** Har kuni 1 ta `📐 Oltin Formula` va 1 ta `🎯 5-Savollik Sinov` topshirish natijani barqaror oshiradi.",
        "",
    ])
    return "\n".join(lines)


class LanguageTutorDialog(QDialog):
    """Interactive onboarding & configuration dialog for choosing Target Language, Teacher Role, Level, and Skill."""

    def __init__(self, controller: TutorController):
        super().__init__(controller.win)
        from brave_ui import button_style, colors, font
        from brave_control_center import style_dialog

        self.controller = controller
        self.state = dict(controller.state)
        c = colors()
        self.setWindowTitle(t('Til Akademiyasi · Ustoz va Tilni Tanlash'))
        self.setFont(font(10))
        screen = controller.win.screen().availableGeometry()
        self.resize(min(860, screen.width() - 48), min(720, screen.height() - 64))
        style_dialog(self, 'Til Akademiyasi · Ustoz va Tilni Tanlash')

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)

        header = QFrame()
        header.setStyleSheet(
            f'QFrame {{background:{c.PRI_GHO};border:1px solid {c.PRI_DIM};border-radius:12px;}}'
        )
        h_lay = QVBoxLayout(header)
        h_lay.setContentsMargins(14, 10, 14, 10)
        h_lay.setSpacing(4)
        title = QLabel(t('🎓 30 Yillik Professor AI — Til O‘rganish Akademiyasi'))
        title.setFont(font(13, True))
        title.setStyleSheet(f'color:{c.PRI};border:none;background:transparent;')
        subtitle = QLabel(t(
            'Qaysi tilni o‘rganmoqchisiz va AI sizga qanday ustoz rolida dars o‘tsin? '
            'Tanlovingiz 7 ta maxsus chat (Speaking, Writing, Listening, Grammar, Vocabulary, Reading, General) uchun darhol qo‘llanadi.'
        ))
        subtitle.setWordWrap(True)
        subtitle.setFont(font(9))
        subtitle.setStyleSheet(f'color:{c.TEXT};border:none;background:transparent;')
        h_lay.addWidget(title)
        h_lay.addWidget(subtitle)
        root.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet('QScrollArea {background:transparent;border:none;}')
        body = QWidget()
        body.setStyleSheet('background:transparent;')
        form = QVBoxLayout(body)
        form.setContentsMargins(2, 2, 8, 2)
        form.setSpacing(12)

        # 1. Target Language + Level row
        lang_card = QFrame()
        lang_card.setStyleSheet(f'QFrame {{background:{c.PANEL2};border:1px solid {c.BORDER};border-radius:12px;}}')
        lc_lay = QVBoxLayout(lang_card)
        lc_lay.setContentsMargins(14, 12, 14, 12)
        lc_lay.setSpacing(8)
        lc_title = QLabel(t('1. Qaysi tilni va qaysi darajada o‘rganmoqchisiz?'))
        lc_title.setFont(font(10, True))
        lc_title.setStyleSheet(f'color:{c.WHITE};border:none;background:transparent;')
        lc_lay.addWidget(lc_title)

        grid = QGridLayout()
        grid.setSpacing(8)
        lbl_lang = QLabel(t('O‘rganiladigan til:'))
        lbl_lang.setFont(font(9, True))
        lbl_lang.setStyleSheet(f'color:{c.TEXT_MED};border:none;')
        self.lang_combo = QComboBox()
        self.lang_combo.setMinimumHeight(34)
        for item in LANGUAGES:
            self.lang_combo.addItem(f"{t(item.title)} · {item.native_name} ({item.exam_system})", item.code)
        idx = self.lang_combo.findData(self.state.get('target_language', 'en'))
        self.lang_combo.setCurrentIndex(max(0, idx))

        self.custom_lang_input = QLineEdit(self.state.get('custom_language', ''))
        self.custom_lang_input.setPlaceholderText(t('Til nomini kiriting (masalan: Polsha tili, Fors tili)…'))
        self.custom_lang_input.setMinimumHeight(32)
        self.custom_lang_input.setVisible(self.lang_combo.currentData() == 'custom')
        self.lang_combo.currentIndexChanged.connect(
            lambda: self.custom_lang_input.setVisible(self.lang_combo.currentData() == 'custom')
        )

        lbl_level = QLabel(t('Hozirgi darajangiz (CEFR):'))
        lbl_level.setFont(font(9, True))
        lbl_level.setStyleSheet(f'color:{c.TEXT_MED};border:none;')
        self.level_combo = QComboBox()
        self.level_combo.setMinimumHeight(34)
        for code, l_title, l_desc in LEVELS:
            self.level_combo.addItem(f"{t(l_title)} — {t(l_desc)}", code)
        l_idx = self.level_combo.findData(self.state.get('level', 'B1'))
        self.level_combo.setCurrentIndex(max(0, l_idx))

        lbl_explain = QLabel(t('Tushuntirish tili:'))
        lbl_explain.setFont(font(9, True))
        lbl_explain.setStyleSheet(f'color:{c.TEXT_MED};border:none;')
        self.explain_combo = QComboBox()
        self.explain_combo.setMinimumHeight(34)
        for mode_key, mode_title in EXPLAIN_MODES:
            self.explain_combo.addItem(t(mode_title), mode_key)
        e_idx = self.explain_combo.findData(self.state.get('explain_language', 'uz'))
        self.explain_combo.setCurrentIndex(max(0, e_idx))

        grid.addWidget(lbl_lang, 0, 0)
        grid.addWidget(self.lang_combo, 0, 1)
        grid.addWidget(self.custom_lang_input, 1, 1)
        grid.addWidget(lbl_level, 2, 0)
        grid.addWidget(self.level_combo, 2, 1)
        grid.addWidget(lbl_explain, 3, 0)
        grid.addWidget(self.explain_combo, 3, 1)
        grid.setColumnStretch(1, 1)
        lc_lay.addLayout(grid)
        form.addWidget(lang_card)

        # 2. AI Teacher Persona Cards
        role_card = QFrame()
        role_card.setStyleSheet(f'QFrame {{background:{c.PANEL2};border:1px solid {c.BORDER};border-radius:12px;}}')
        rc_lay = QVBoxLayout(role_card)
        rc_lay.setContentsMargins(14, 12, 14, 12)
        rc_lay.setSpacing(8)
        rc_title = QLabel(t('2. AI Ustoz Rolini Tanlang (Har xil xarakter va metodika):'))
        rc_title.setFont(font(10, True))
        rc_title.setStyleSheet(f'color:{c.WHITE};border:none;background:transparent;')
        rc_lay.addWidget(rc_title)

        self.role_buttons: dict[str, QPushButton] = {}
        role_grid = QGridLayout()
        role_grid.setSpacing(8)
        current_role = self.state.get('teacher_role', 'universal_professor')
        for index, role in enumerate(TEACHER_ROLES):
            btn = QPushButton()
            btn.setCheckable(True)
            btn.setChecked(role.key == current_role)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(74)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            b_lay = QVBoxLayout(btn)
            b_lay.setContentsMargins(10, 8, 10, 8)
            b_lay.setSpacing(3)
            r_head = QLabel(t(role.title))
            r_head.setFont(font(9, True))
            r_head.setStyleSheet(f'color:{c.WHITE};background:transparent;border:none;')
            r_desc = QLabel(t(role.summary))
            r_desc.setWordWrap(True)
            r_desc.setFont(font(8))
            r_desc.setStyleSheet(f'color:{c.TEXT_DIM};background:transparent;border:none;')
            for child in (r_head, r_desc):
                child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                b_lay.addWidget(child)
            btn.clicked.connect(lambda checked=False, k=role.key: self._select_role(k))
            self.role_buttons[role.key] = btn
            role_grid.addWidget(btn, index // 2, index % 2)
        self._style_role_buttons()
        rc_lay.addLayout(role_grid)
        form.addWidget(role_card)

        # 3. 7 Skill Channel Quick Start Selection
        skill_card = QFrame()
        skill_card.setStyleSheet(f'QFrame {{background:{c.PANEL2};border:1px solid {c.BORDER};border-radius:12px;}}')
        sc_lay = QVBoxLayout(skill_card)
        sc_lay.setContentsMargins(14, 12, 14, 12)
        sc_lay.setSpacing(8)
        sc_title = QLabel(t('3. Qaysi Chat Bo‘limidan boshlaymiz? (Yonboshda 7 ta maxsus chat):'))
        sc_title.setFont(font(10, True))
        sc_title.setStyleSheet(f'color:{c.WHITE};border:none;background:transparent;')
        sc_lay.addWidget(sc_title)

        self.skill_buttons: dict[str, QPushButton] = {}
        skill_row = QGridLayout()
        skill_row.setSpacing(6)
        current_skill = self.state.get('active_skill', 'general')
        for index, skill in enumerate(SKILLS):
            s_btn = QPushButton(f"{skill.short_title}")
            s_btn.setToolTip(t(skill.subtitle))
            s_btn.setCheckable(True)
            s_btn.setChecked(skill.key == current_skill)
            s_btn.setMinimumHeight(34)
            s_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            s_btn.clicked.connect(lambda checked=False, k=skill.key: self._select_skill(k))
            self.skill_buttons[skill.key] = s_btn
            skill_row.addWidget(s_btn, index // 4, index % 4)
        self._style_skill_buttons()
        sc_lay.addLayout(skill_row)
        form.addWidget(skill_card)

        # 4. Professor Pedagogical Criteria Checkboxes
        crit_card = QFrame()
        crit_card.setStyleSheet(f'QFrame {{background:{c.PANEL2};border:1px solid {c.BORDER};border-radius:12px;}}')
        cc_lay = QVBoxLayout(crit_card)
        cc_lay.setContentsMargins(14, 12, 14, 12)
        cc_lay.setSpacing(6)
        cc_title = QLabel(t('4. 30 Yillik Professor O‘qitish Kriteriyalari:'))
        cc_title.setFont(font(10, True))
        cc_title.setStyleSheet(f'color:{c.WHITE};border:none;background:transparent;')
        cc_lay.addWidget(cc_title)

        self.criteria_checks: dict[str, QCheckBox] = {}
        enabled_crit = set(self.state.get('criteria') or DEFAULT_CRITERIA)
        for key, c_title, c_desc in CRITERIA_FLAGS:
            chk = QCheckBox(f"{t(c_title)} — {t(c_desc)}")
            chk.setChecked(key in enabled_crit)
            chk.setFont(font(9))
            chk.setStyleSheet(f'color:{c.TEXT};background:transparent;border:none;')
            self.criteria_checks[key] = chk
            cc_lay.addWidget(chk)

        self.startup_check = QCheckBox(t('Har safar dasturga kirganda til va ustoz rolini so‘rash'))
        self.startup_check.setChecked(bool(self.state.get('ask_on_startup', True)))
        self.startup_check.setFont(font(9))
        self.startup_check.setStyleSheet(f'color:{c.PRI};background:transparent;border:none;margin-top:4px;')
        cc_lay.addWidget(self.startup_check)
        form.addWidget(crit_card)

        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        footer = QHBoxLayout()
        voice_studio_btn = QPushButton(t('🎙️ Ovoz, Sheva va Ohang Studiyasi…'))
        voice_studio_btn.setMinimumHeight(36)
        voice_studio_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        voice_studio_btn.setStyleSheet(button_style())
        voice_studio_btn.clicked.connect(lambda: self.controller.open_voice_dialect_studio(parent=self))
        footer.addWidget(voice_studio_btn)
        footer.addStretch(1)
        cancel_btn = QPushButton(t('Yopish'))
        cancel_btn.setMinimumHeight(36)
        cancel_btn.setStyleSheet(button_style())
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton(t('Darsni Boshlash · Saqlash'))
        save_btn.setMinimumHeight(36)
        save_btn.setStyleSheet(button_style(True) + 'QPushButton {padding: 6px 18px; font-weight: 600;}')
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self.apply_and_start)
        footer.addWidget(cancel_btn)
        footer.addWidget(save_btn)
        root.addLayout(footer)

    def _select_role(self, role_key: str):
        self.state['teacher_role'] = role_key
        for key, btn in self.role_buttons.items():
            btn.setChecked(key == role_key)
        self._style_role_buttons()

    def _style_role_buttons(self):
        from brave_ui import colors
        c = colors()
        for key, btn in self.role_buttons.items():
            active = btn.isChecked()
            btn.setStyleSheet(
                f'QPushButton {{background:{c.PRI_GHO if active else c.BG};'
                f'border:1px solid {c.PRI if active else c.BORDER};border-radius:10px;text-align:left;}}'
                f'QPushButton:hover {{border-color:{c.PRI_DIM};}}'
            )

    def _select_skill(self, skill_key: str):
        self.state['active_skill'] = skill_key
        for key, btn in self.skill_buttons.items():
            btn.setChecked(key == skill_key)
        self._style_skill_buttons()

    def _style_skill_buttons(self):
        from brave_ui import button_style
        for key, btn in self.skill_buttons.items():
            btn.setStyleSheet(button_style(btn.isChecked()))

    def apply_and_start(self):
        selected_crit = [k for k, chk in self.criteria_checks.items() if chk.isChecked()]
        self.state['target_language'] = self.lang_combo.currentData() or 'en'
        self.state['custom_language'] = self.custom_lang_input.text().strip()[:60]
        self.state['level'] = self.level_combo.currentData() or 'B1'
        self.state['explain_language'] = self.explain_combo.currentData() or 'uz'
        self.state['criteria'] = selected_crit or list(DEFAULT_CRITERIA)
        self.state['ask_on_startup'] = self.startup_check.isChecked()
        self.state['onboarded'] = True
        self.controller.apply_state(self.state, announce=True)
        self.accept()


class TutorController:
    """Manages the 7 language learning chats, teacher personas, and professor system prompt."""

    def __init__(self, win):
        self.win = win
        self.state = load_state()
        self._syncing_bar = False

    def ensure_skill_chat_id(self, skill_key: str, lang_code: str | None = None, force_new: bool = False) -> str:
        from brave_history import HistoryStore
        lang_code = lang_code or self.state.get('target_language', 'en')
        slot = f"{lang_code}:{skill_key}"
        chats = dict(self.state.get('skill_chats') or {})
        chat_id = chats.get(slot)
        if not chat_id or force_new:
            chat_id = HistoryStore.new_id()
            chats[slot] = chat_id
            self.state['skill_chats'] = chats
            save_state(self.state)
        return chat_id

    def switch_skill(self, skill_key: str, force: bool = False) -> bool:
        if skill_key not in SKILL_MAP:
            return False
        features = getattr(self.win, '_features', None)
        if features is not None and not force:
            if features.started is not None or (self.win.can_change_chat and not self.win.can_change_chat()):
                self.win._log.append_log('ERR: ' + t('Avval joriy javob yoki vazifa tugashini kuting.'))
                self.refresh_sidebar()
                return False
        self.state['active_skill'] = skill_key
        chat_id = self.ensure_skill_chat_id(skill_key)
        save_state(self.state)
        if features is not None and features.chat_id != chat_id:
            if not features.switch_chat(chat_id):
                return False
        else:
            self.win._log.retheme()
        self.refresh_ui()
        return True

    def on_new_chat_started(self, new_chat_id: str):
        """Bind a newly created chat to the currently active language + skill channel."""
        lang_code = self.state.get('target_language', 'en')
        skill_key = self.state.get('active_skill', 'general')
        chats = dict(self.state.get('skill_chats') or {})
        chats[f"{lang_code}:{skill_key}"] = new_chat_id
        self.state['skill_chats'] = chats
        save_state(self.state)
        self.refresh_ui()

    def apply_state(self, new_state: dict, announce: bool = False):
        old_lang = self.state.get('target_language', 'en')
        old_skill = self.state.get('active_skill', 'general')
        self.state.update(new_state or {})
        save_state(self.state)
        new_lang = self.state.get('target_language', 'en')
        new_skill = self.state.get('active_skill', 'general')
        target_chat_id = self.ensure_skill_chat_id(new_skill, new_lang)
        features = getattr(self.win, '_features', None)
        switched = False
        if features is not None and (old_lang != new_lang or old_skill != new_skill or features.chat_id != target_chat_id):
            if features.started is None and (self.win.can_change_chat is None or self.win.can_change_chat()):
                switched = features.switch_chat(target_chat_id)
        if not switched and hasattr(self.win, '_log'):
            self.win._log.retheme()
        self.refresh_ui()
        if announce and hasattr(self.win, '_log'):
            lang_name = language_display_name(self.state)
            role = role_display(self.state)
            skill = skill_display(self.state)
            level = self.state.get('level', 'B1')
            self.win._log.append_log(
                f"SYS: {lang_name} ({level}) · {t(role.title)} · {skill.short_title} {t('bo‘limi faollashtirildi.')}"
            )
            if features is not None and features.store.count(features.chat_id) == 0 and not self.win._log._history:
                greeting = self.welcome_professor_message()
                stamp = datetime.now(timezone(timedelta(hours=5))).strftime('%H:%M')
                self.win._log._enqueue(f"{self.win._assistant_name}: {greeting}")

    def welcome_professor_message(self) -> str:
        lang_name = language_display_name(self.state)
        level = self.state.get('level', 'B1')
        role = role_display(self.state)
        skill = skill_display(self.state)
        role_intro = {
            'strict_professor': (
                f"Men sizning **{lang_name}** bo‘yicha 30 yillik **Qattiqqo‘l Professor** ustozi bo‘laman. "
                "Darsimizda intizom, aniqlik va yuqori natija birinchi o‘rinda — xatolaringizni ayamasdan "
                "tahlil qilaman va sizni eng yuqori darajaga olib chiqaman."
            ),
            'kind_mentor': (
                f"Xush kelibsiz! Men sizning **{lang_name}** bo‘yicha **Mehribon va Sabrli Ustozingizman**. "
                "Xato qilishdan aslo qo‘rqmang — har bir qoidani eng sodda, hayotiy misollar bilan birga o‘rganamiz."
            ),
            'exam_master': (
                f"Salom! Men **{lang_name}** bo‘yicha xalqaro **Imtihon Ekspertiman**. "
                "Har bir javobingizni rasmiy CEFR/Band mezonlari asosida baholab, C1/C2 darajaga ko‘tarish sirlarini ko‘rsataman."
            ),
            'socratic_coach': (
                f"Salom! Men sizning **Sokratik Murabbiyingizman**. **{lang_name}**da tayyor qoliplarni yodlatmayman — "
                "savollar va mantiqiy kalitlar orqali shu tilda mustaqil fikrlashga o‘rgataman."
            ),
            'native_speaker': (
                f"Salom! Men sizning **Tezkor Native Suhbatdoshingizman**. **{lang_name}**ni kitobiy emas, "
                "real hayotdagi jonli iboralar, idiomalar va tabiiy dialoglar orqali o‘rganamiz!"
            ),
            'loving_gentle_mentor': (
                f"Assalomu alaykum, aziz qadrdonim! Men sizning **{lang_name}** bo‘yicha **Mehrli va Mayin Ustozingizman**. "
                "Hech qanday hayajonlanmang — har bir so‘z va talaffuzni mehr bilan, shoshmasdan, eng mayin va oson usulda o‘rganamiz!"
            ),
            'blunt_coach': (
                f"Salom! Men **{lang_name}** bo‘yicha **Dangal Murabbiyingizman**. Ortiqcha mulozamat yo‘q — "
                "xuddi real hayotdagi keskin vaziyatlardek tez, aniq va dangal gapirishga chiniqtiraman!"
            ),
        }.get(
            role.key,
            f"Assalomu alaykum! Men **{lang_name}** bo‘yicha 30 yillik tajribaga ega **Professor Ustozingizman**. "
            "Har bir mavzuni eng sodda formula, tezkor mantiq va aniq kriteriyalar asosida tushuntiraman."
        )
        return (
            f"### 🎓 {lang_name} ({level}) · {t(role.title)}\n"
            f"**Faol bo‘lim:** `{skill.title}`\n\n"
            f"{role_intro}\n\n"
            f"**{skill.short_title} bo‘limi mezonlari:** *{skill.criteria_badge}*\n\n"
            f"👉 Quyida savolingizni, jumlangizni yoki o‘rganmoqchi bo‘lgan mavzungizni yozing (yoki mikrofon orqali gapiring)!"
        )

    def system_prompt(self) -> str:
        return build_professor_system_prompt(self.state)

    def open_dialog(self):
        dialog = LanguageTutorDialog(self)
        self.win._tutor_dialog = dialog
        dialog.exec()
        return dialog

    def open_academy_hub(self):
        dialog = AcademyHubDialog(self)
        self.win._academy_hub_dialog = dialog
        dialog.exec()
        return dialog

    def open_voice_dialect_studio(self, parent=None):
        from brave_voice_dialect import open_voice_dialect_studio
        return open_voice_dialect_studio(self.win, parent=parent)

    def add_vocab_entry(self, word: str, meaning: str, collocation: str = '', mnemonic: str = '') -> bool:
        word = (word or '').strip()[:80]
        meaning = (meaning or '').strip()[:120]
        if not word or not meaning:
            return False
        bank = list(self.state.get('vocab_bank') or [])
        lang = self.state.get('target_language', 'en')
        bank = [item for item in bank if not (item.get('word', '').lower() == word.lower() and item.get('lang') == lang)]
        bank.insert(0, {
            'word': word,
            'meaning': meaning,
            'collocation': (collocation or '').strip()[:120],
            'mnemonic': (mnemonic or '').strip()[:140],
            'lang': lang,
        })
        self.state['vocab_bank'] = bank[:200]
        save_state(self.state)
        self.refresh_ui()
        return True

    def update_vocab_progress(self, word: str, mastered: bool) -> None:
        """Update review count and mastery status for a vocabulary item."""
        bank = list(self.state.get('vocab_bank') or [])
        lang = self.state.get('target_language', 'en')
        for item in bank:
            if item.get('word', '').lower() == (word or '').strip().lower() and item.get('lang', lang) == lang:
                item['review_count'] = int(item.get('review_count', 0)) + 1
                item['mastered'] = bool(mastered)
                break
        self.state['vocab_bank'] = bank
        save_state(self.state)
        self.refresh_ui()

    def vocab_mastery_stats(self) -> dict:
        """Return total, mastered count and percentage for current language."""
        lang = self.state.get('target_language', 'en')
        items = [v for v in (self.state.get('vocab_bank') or []) if v.get('lang', lang) == lang]
        total = len(items)
        mastered = sum(1 for v in items if v.get('mastered'))
        pct = int(round(mastered / total * 100)) if total else 0
        return {'total': total, 'mastered': mastered, 'percent': pct}

    def delete_vocab_entry(self, word: str) -> bool:
        """Remove a word from the current language vocab bank."""
        word = (word or '').strip().lower()
        if not word:
            return False
        bank = list(self.state.get('vocab_bank') or [])
        lang = self.state.get('target_language', 'en')
        initial_len = len(bank)
        bank = [item for item in bank if not (item.get('word', '').lower() == word and item.get('lang', lang) == lang)]
        if len(bank) < initial_len:
            self.state['vocab_bank'] = bank
            save_state(self.state)
            self.refresh_ui()
            return True
        return False

    def speak_word(self, word: str, *, slow: bool = False) -> None:
        """Pronounce the word using local TTS or native Windows speech in a background thread."""
        word = (word or '').strip()
        if not word:
            return
        # The Uzbek chat voice would mispronounce foreign words, so use an
        # offline Windows voice matching the target language when available.
        lang = self.state.get('target_language', 'en')
        args = (word, lang, True) if slow else (word, lang)
        threading.Thread(target=_sapi_speak, args=args, daemon=True,
                         name='tutor-speak-word').start()

    def load_starter_vocab_pack(self) -> int:
        lang = self.state.get('target_language', 'en')
        pack = PROFESSOR_STARTER_VOCAB.get(lang, PROFESSOR_STARTER_VOCAB['en'])
        added = 0
        for row in reversed(pack):
            if self.add_vocab_entry(row['word'], row['meaning'], row.get('collocation', ''), row.get('mnemonic', '')):
                added += 1
        return added

    def skill_message_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        features = getattr(self.win, '_features', None)
        store = getattr(features, 'store', None) if features is not None else None
        lang_code = self.state.get('target_language', 'en')
        chats = dict(self.state.get('skill_chats') or {})
        for skill in SKILLS:
            chat_id = chats.get(f"{lang_code}:{skill.key}")
            if store is not None and chat_id:
                try:
                    counts[skill.key] = int(store.count(chat_id))
                except Exception:
                    counts[skill.key] = 0
            else:
                counts[skill.key] = 0
        return counts

    def launch_skill_quiz(self):
        """Open an interactive 30-Year Professor CEFR Quiz on the center HUD board."""
        self.record_study_session()
        lang_code = self.state.get('target_language', 'en')
        lang_name = language_display_name(self.state)
        level = self.state.get('level', 'B1')
        skill = skill_display(self.state)
        base_questions = list(PROFESSOR_QUIZ_BANK.get(lang_code, PROFESSOR_QUIZ_BANK['default']))
        # Also include any personal vocab_bank items as dynamic quiz questions
        vocab_items = [
            v for v in (self.state.get('vocab_bank') or [])
            if v.get('lang', lang_code) == lang_code and v.get('word') and v.get('meaning')
        ]
        all_meanings = [v['meaning'] for v in vocab_items] + [
            'noto‘g‘ri talaffuz qilmoq', 'kechiktirmoq, orqaga surmoq', 'umuman aloqasi yo‘q tushuncha'
        ]
        for v in vocab_items[:3]:
            distractors = [m for m in all_meanings if m != v['meaning']][:3]
            opts = [v['meaning']] + distractors
            base_questions.insert(0, {
                'question': f"[Shaxsiy Lug‘at · {level}] '{v['word']}' so‘zining aniq ma’nosi qaysi? ({v.get('collocation', '')})",
                'options': opts,
                'answer': v['meaning'],
                'note': f"Mnemonika: {v.get('mnemonic') or v.get('collocation') or v['word']}",
            })

        def _grader(q: dict, given: str) -> bool:
            expected = str(q.get('answer', '')).strip().casefold()
            actual = str(given or '').strip().casefold()
            is_ok = (actual == expected)
            note = q.get('note', '')
            if hasattr(self.win, '_quiz_note_lbl') and note:
                prefix = '✅ Professor tasdig‘i: ' if is_ok else '❌ Professor izohi: '
                self.win._quiz_note_lbl.setText(prefix + note)
                self.win._quiz_note_lbl.show()
            return is_ok

        topic_title = f"TAI · {lang_name} ({level}) · {skill.short_title} Sinovi"
        if hasattr(self.win, '_show_quiz'):
            self.win._show_quiz(topic_title, base_questions[:5], grader=_grader)
            if hasattr(self.win, '_log'):
                self.win._log.append_log(f"SYS: 🎯 Markaziy ekranda '{topic_title}' interaktiv testi boshlandi!")

    def trigger_professor_action(self, action_key: str):
        """Populate or transform the chat input with a 30-year Professor specialized prompt."""
        self.record_study_session()
        if not hasattr(self.win, '_input'):
            return
        lang_name = language_display_name(self.state)
        level = self.state.get('level', 'B1')
        skill = skill_display(self.state)
        draft = self.win._input.text().strip()
        if action_key == 'xray':
            if draft:
                prompt = (
                    f"[XATOLAR RENTGENI · {lang_name} {level}]: Quyidagi jumlamni 30 yillik professor mezonida "
                    f"(❌ Xato -> ✅ To‘g‘ri -> 🌟 C1/Native variant + 1 qator qoida) tahlil qilib ber: \"{draft}\""
                )
            else:
                prompt = (
                    f"Men yozgan jumlani {lang_name} ({level}) bo‘yicha Xatolar Rentgeni "
                    "(❌ Xato -> ✅ To‘g‘ri -> 🌟 Native/C1 variant + qoida) usulida tekshirib ber: "
                )
        elif action_key == 'formula':
            if draft:
                prompt = (
                    f"[OLTIN FORMULA · {lang_name} {level}]: \"{draft}\" mavzusini 30 yillik professorning "
                    "5-qadamli Oltin Formulasi (1 jumlada mohiyat + [+ / - / ?] Formula + 3 darajali misol + Xato tuzog‘i + 1 sinov) bilan tushuntirib ber."
                )
            else:
                prompt = (
                    f"{lang_name} ({level} · {skill.short_title}) bo‘yicha eng muhim mavzuni "
                    "1 jumlada mantiq + [+ / - / ?] Oltin Formula + 3 darajali misol bilan tushuntirib ber."
                )
        else:  # roadmap / drill
            prompt = (
                f"Menga {lang_name} ({level}) bo‘yicha {skill.short_title} yo‘nalishida 30 yillik professorning "
                "5 daqiqalik intensiv mini-darsi va 3 bosqichli amaliy mashqini boshla!"
            )
        self.win._input.setText(prompt)
        self.win._input.setFocus()

    def maybe_prompt_on_startup(self):
        import os
        import sys
        if os.environ.get('QT_QPA_PLATFORM') == 'offscreen' or 'unittest' in sys.modules:
            return
        try:
            if not self.win.isVisible() or not getattr(self.win, '_ready', False):
                return
        except RuntimeError:
            return
        if not self.state.get('onboarded', False) or self.state.get('ask_on_startup', True):
            self.open_dialog()

    def refresh_sidebar(self):
        from brave_ui import button_style, colors, set_icon
        c = colors()
        active_skill = self.state.get('active_skill', 'general')
        lang_name = language_display_name(self.state)
        level = self.state.get('level', 'B1')
        role = role_display(self.state)

        if hasattr(self.win, '_tutor_role_btn'):
            self.win._tutor_role_btn.setText(f"{lang_name} · {level} · {t(role.badge)}")
            self.win._tutor_role_btn.setToolTip(
                f"{t('Til va Ustoz Roli')}: {lang_name} ({level}) — {t(role.title)}"
            )
            self.win._tutor_role_btn.setStyleSheet(
                button_style() +
                f"QPushButton {{background:{c.PRI_GHO};color:{c.PRI};border:1px solid {c.PRI_DIM};"
                f"text-align:left;padding:4px 10px;font-size:12px;font-weight:600;}}"
            )
            set_icon(self.win._tutor_role_btn, 'spark', 'PRI')

        if hasattr(self.win, '_header_academy_btn'):
            skill_obj = skill_display(self.state)
            self.win._header_academy_btn.setText(
                f"🎓 {lang_name} ({level}) · {t(role.badge)} · {skill_obj.short_title}"
            )
            self.win._header_academy_btn.setStyleSheet(
                button_style() +
                f"QPushButton {{color:{c.PRI};background:{c.PRI_GHO};border:1px solid {c.PRI_DIM};"
                f"border-radius:12px;padding:5px 12px;font-weight:600;}}"
            )

        counts = self.skill_message_counts()
        buttons = getattr(self.win, '_skill_buttons', {})
        for key, button in buttons.items():
            skill = SKILL_MAP[key]
            is_active = key == active_skill
            msg_count = counts.get(key, 0)
            label_txt = f"{skill.short_title}  ·  {msg_count}" if msg_count > 0 else skill.short_title
            button.setText(label_txt)
            button.setCheckable(True)
            button.setChecked(is_active)
            set_icon(button, skill.glyph, 'PRI' if is_active else 'TEXT_MED')
            base = (
                button_style() +
                f"QPushButton {{text-align: left; padding: 4px 10px; font-size: 12px; "
                f"border: 1px solid transparent; background: transparent;}} "
                f"QPushButton:hover {{background: {c.PANEL2}; border-color: {c.BORDER};}} "
                f"QPushButton:focus {{border-color: {c.PRI};}}"
            )
            if is_active:
                base += f"QPushButton {{background: {c.PRI_GHO}; color: {c.PRI}; border-left: 2px solid {c.PRI}; font-weight: 600;}}"
            button.setStyleSheet(base)

    def refresh_chat_bar(self):
        from brave_ui import button_style, colors
        c = colors()
        skill = skill_display(self.state)
        lang_name = language_display_name(self.state)
        level = self.state.get('level', 'B1')
        role = role_display(self.state)
        vocab_count = len([
            v for v in (self.state.get('vocab_bank') or [])
            if v.get('lang', self.state.get('target_language', 'en')) == self.state.get('target_language', 'en')
        ])

        if hasattr(self.win, '_chat_heading_lbl'):
            self.win._chat_heading_lbl.setText(f"{skill.short_title} · {lang_name} ({level})")
        if hasattr(self.win, '_tutor_criteria_lbl'):
            self.win._tutor_criteria_lbl.setText(f"🎓 {t(role.badge)} · {skill.criteria_badge}")
            self.win._tutor_criteria_lbl.setToolTip(f"{t(role.title)} — {skill.criteria_badge}")
            self.win._tutor_criteria_lbl.setStyleSheet(
                f"color:{c.PRI};background:{c.PRI_GHO};border:1px solid {c.BORDER};"
                f"border-radius:7px;padding:2px 7px;"
            )
        if hasattr(self.win, '_tutor_vocab_btn'):
            streak_stats = self.get_streak_stats()
            streak_days = streak_stats.get('streak', 0)
            vocab_text = f"📚 {vocab_count}" if vocab_count else "📚 Lug‘at"
            if streak_days:
                vocab_text += f" · 🔥 {streak_days}k"
            self.win._tutor_vocab_btn.setText(vocab_text)
            self.win._tutor_vocab_btn.setStyleSheet(button_style() + 'QPushButton {padding:3px 6px;font-size:11px;}')
        if hasattr(self.win, '_tutor_quiz_btn'):
            self.win._tutor_quiz_btn.setStyleSheet(button_style() + 'QPushButton {padding:3px 6px;font-size:11px;}')
        if hasattr(self.win, '_tutor_flashcard_btn'):
            self.win._tutor_flashcard_btn.setStyleSheet(button_style() + 'QPushButton {padding:3px 6px;font-size:11px;}')
        if hasattr(self.win, '_tutor_voice_btn'):
            try:
                from core.voice_style import DIALECT_MAP, EMOTION_MAP, GENDER_MAP, load_voice_style, style_badge_summary
                vs = load_voice_style()
                g_icon = '👩' if vs['gender'] == 'female' else '👨'
                d_badge = DIALECT_MAP[vs['dialect']].badge
                self.win._tutor_voice_btn.setText(f"🎙️ {g_icon} {d_badge}")
                self.win._tutor_voice_btn.setToolTip(
                    f"Ovoz, Sheva va Hissiy Ohang Studiyasi: {style_badge_summary(vs)}"
                )
            except Exception:
                self.win._tutor_voice_btn.setText("🎙️ Sheva")
            self.win._tutor_voice_btn.setStyleSheet(
                button_style() +
                f"QPushButton {{padding:2px 6px;font-size:10px;border-radius:7px;color:{c.PRI};border-color:{c.PRI_DIM};}}"
            )
        for attr in ('_tutor_xray_btn', '_tutor_formula_btn', '_tutor_drill_btn'):
            btn = getattr(self.win, attr, None)
            if btn is not None:
                btn.setStyleSheet(
                    button_style() +
                    f"QPushButton {{padding:2px 6px;font-size:10px;border-radius:7px;color:{c.TEXT_MED};}}"
                    f"QPushButton:hover {{color:{c.PRI};border-color:{c.PRI_DIM};}}"
                )
        if hasattr(self.win, '_input'):
            self.win._input.setPlaceholderText(t(skill.placeholder))

        self._syncing_bar = True
        try:
            if hasattr(self.win, '_tutor_lang_box'):
                idx = self.win._tutor_lang_box.findData(self.state.get('target_language', 'en'))
                if idx >= 0:
                    self.win._tutor_lang_box.setCurrentIndex(idx)
            if hasattr(self.win, '_tutor_level_box'):
                idx = self.win._tutor_level_box.findData(self.state.get('level', 'B1'))
                if idx >= 0:
                    self.win._tutor_level_box.setCurrentIndex(idx)
            if hasattr(self.win, '_tutor_role_box'):
                idx = self.win._tutor_role_box.findData(self.state.get('teacher_role', 'universal_professor'))
                if idx >= 0:
                    self.win._tutor_role_box.setCurrentIndex(idx)
            if hasattr(self.win, '_tutor_setup_btn'):
                self.win._tutor_setup_btn.setStyleSheet(button_style() + 'QPushButton {padding:3px 7px;font-size:11px;}')
        finally:
            self._syncing_bar = False

    def refresh_ui(self):
        self.refresh_sidebar()
        self.refresh_chat_bar()
        if hasattr(self.win, '_log') and getattr(self.win._log, 'welcome', None) is not None:
            self.win._log.welcome.refresh_for_tutor(self.state)
        if hasattr(self.win, 'hud'):
            self.win.hud.update()

    def export_vocab_csv(self) -> str:
        """Export the current language vocab bank as a UTF-8 CSV string."""
        import io
        import csv as csv_module
        lang_code = self.state.get('target_language', 'en')
        items = [
            v for v in (self.state.get('vocab_bank') or [])
            if v.get('lang', lang_code) == lang_code
        ]
        buffer = io.StringIO()
        writer = csv_module.writer(buffer)
        writer.writerow(["So'z", "Ma'nosi", 'Kollokatsiya', 'Mnemonika', 'Til'])
        for item in items:
            writer.writerow([
                item.get('word', ''),
                item.get('meaning', ''),
                item.get('collocation', ''),
                item.get('mnemonic', ''),
                item.get('lang', lang_code),
            ])
        return buffer.getvalue()

    def export_vocab_anki(self) -> str:
        """Export the current language vocab bank as Anki-ready TSV string."""
        lang_code = self.state.get('target_language', 'en')
        items = [
            v for v in (self.state.get('vocab_bank') or [])
            if v.get('lang', lang_code) == lang_code
        ]
        lines = ["#separator:tab\n#html:true\n#tags column:3\n"]
        for item in items:
            # Anki imports with #html:true, so escape user text and strip
            # separators that would split the row.
            def clean(value):
                return html.escape(str(value or '').replace('\t', ' ').replace('\n', ' '))
            word = clean(item.get('word'))
            meaning = clean(item.get('meaning'))
            colloc = clean(item.get('collocation'))
            mnem = clean(item.get('mnemonic'))
            back_parts = [f"<b>{meaning}</b>"]
            if colloc:
                back_parts.append(f"🔗 <i>{colloc}</i>")
            if mnem:
                back_parts.append(f"<small>💡 {mnem}</small>")
            back = "<br>".join(back_parts)
            tag = f"tai-{lang_code}"
            lines.append(f"{word}\t{back}\t{tag}\n")
        return "".join(lines)

    def record_study_session(self) -> None:
        """Record today's study session for streak tracking."""
        from datetime import date
        today = date.today().isoformat()
        stats = workspace_store.read('tutor-streak.json', {})
        if not isinstance(stats, dict):
            stats = {}
        lang = self.state.get('target_language', 'en')
        lang_stats = stats.get(lang, {'streak': 0, 'last_date': '', 'total_days': 0, 'sessions': []})
        sessions = lang_stats.get('sessions', [])
        if today not in sessions:
            sessions.append(today)
            sessions = sessions[-365:]
            last_date = lang_stats.get('last_date', '')
            streak = lang_stats.get('streak', 0)
            total_days = lang_stats.get('total_days', 0)
            from datetime import date as date_cls, timedelta
            try:
                last = date_cls.fromisoformat(last_date) if last_date else None
            except ValueError:
                last = None
            today_date = date_cls.today()
            if last is None or (today_date - last).days > 1:
                streak = 1
            elif (today_date - last).days == 1:
                streak += 1
            total_days += 1
            lang_stats = {
                'streak': streak,
                'last_date': today,
                'total_days': total_days,
                'sessions': sessions,
            }
            stats[lang] = lang_stats
            workspace_store.write('tutor-streak.json', stats)

    def get_streak_stats(self) -> dict:
        """Return streak statistics for the current language."""
        lang = self.state.get('target_language', 'en')
        stats = workspace_store.read('tutor-streak.json', {})
        if not isinstance(stats, dict):
            return {'streak': 0, 'total_days': 0, 'last_date': ''}
        return stats.get(lang, {'streak': 0, 'total_days': 0, 'last_date': ''})

    def open_flashcards(self):
        """Open interactive spaced-repetition FlashcardDialog."""
        dialog = FlashcardDialog(self, self.win)
        self.win._flashcard_dialog = dialog
        dialog.exec()
        return dialog

    def open_grammar_formulas(self):
        """Open offline Golden Grammar & Exam Formula reference sheet for active language."""
        dialog = GrammarFormulaDialog(self, self.win)
        self.win._grammar_formula_dialog = dialog
        dialog.exec()
        return dialog

    def start_professor_quiz(self):
        """Alias for launch_skill_quiz for Command Palette and shortcuts."""
        return self.launch_skill_quiz()

    def extract_vocab_candidates(self, text: str) -> list[dict[str, str]]:
        """Extract candidate vocabulary entries from an AI reply or arbitrary text."""
        return extract_vocab_from_reply(text)

    def save_extracted_vocab(self, text: str) -> list[dict[str, str]]:
        """Parse vocabulary entries from text and save them into vocab_bank."""
        candidates = extract_vocab_from_reply(text)
        saved: list[dict[str, str]] = []
        for item in reversed(candidates):
            if self.add_vocab_entry(
                item['word'],
                item['meaning'],
                item.get('collocation', ''),
                item.get('mnemonic', ''),
            ):
                saved.append(item)
        return saved

    def quick_save_from_message(self, text: str, interactive: bool = True) -> int:
        """Save vocabulary from an AI reply card with 1 click."""
        saved = self.save_extracted_vocab(text)
        if saved:
            if hasattr(self.win, '_log'):
                words_preview = ', '.join(item['word'] for item in saved[:3])
                more = f" (+{len(saved) - 3})" if len(saved) > 3 else ""
                self.win._log.append_log(
                    f"SYS: 📚 Lug‘atga {len(saved)} ta so‘z/ibora saqlandi: {words_preview}{more}"
                )
            return len(saved)

        lines = [ln.strip() for ln in (text or '').splitlines() if ln.strip()]
        snippet = (lines[0] if lines else (text or '').strip())[:60].strip('•*-#` ')
        if not interactive:
            if snippet and self.add_vocab_entry(snippet, 'Chatdan saqlangan ibora'):
                return 1
            return 0

        from PyQt6.QtWidgets import QInputDialog
        word, ok1 = QInputDialog.getText(
            self.win,
            "📚 Lug‘atga saqlash",
            "So‘z yoki ibora:",
            text=snippet,
        )
        if not ok1 or not word.strip():
            return 0
        meaning, ok2 = QInputDialog.getText(
            self.win,
            "📚 Ma’nosi",
            f"«{word.strip()}» so‘zining ma’nosi (O‘zbekcha):",
        )
        if not ok2 or not meaning.strip():
            return 0
        if self.add_vocab_entry(word.strip(), meaning.strip()):
            if hasattr(self.win, '_log'):
                self.win._log.append_log(f"SYS: 📚 Lug‘atga saqlandi: {word.strip()}")
            return 1
        return 0

    def export_study_report_markdown(self) -> str:
        """Return a Markdown study progress report for the active language."""
        return build_study_report_markdown(
            self.state,
            streak_stats=self.get_streak_stats(),
            skill_counts=self.skill_message_counts(),
        )

    def launch_placement_diagnostic(self) -> None:
        """Prepare a 7-skill CEFR & exam placement diagnostic prompt in General chat."""
        self.record_study_session()
        lang_name = language_display_name(self.state)
        level = self.state.get('level', 'B1')
        self.switch_skill('general')
        if hasattr(self.win, '_input'):
            self.win._input.setText(
                f"[CEFR & IMTIHON DIAGNOSTIKASI · {lang_name} · Joriy tanlov: {level}]: "
                "Menga ketma-ket 5 ta bosqichli savol (Grammatika, Leksika, Sintaksis, Yozma uslub va Muloqot) berib, "
                "hozirgi aniq CEFR darajamni hamda 7 ta ko‘nikma bo‘yicha shaxsiy kuchaytirish rejamni tuzib bering. "
                "Birinchi savoldan boshlang!"
            )
            self.win._input.setFocus()


class GrammarFormulaDialog(QDialog):
    """Offline Oltin Grammatika va Imtihon Formulalari qo‘llanmasi."""

    def __init__(self, controller: TutorController, parent=None):
        super().__init__(parent or controller.win)
        self.controller = controller
        from brave_ui import button_style, colors, font
        from brave_control_center import style_dialog

        c = colors()
        lang_code = controller.state.get('target_language', 'en')
        lang_name = language_display_name(controller.state)
        level = controller.state.get('level', 'B1')
        title_txt = f"📐 Oltin Formulalar · {lang_name} ({level})"
        self.setWindowTitle(title_txt)
        self.setFont(font(10))
        screen = controller.win.screen().availableGeometry()
        self.resize(min(760, screen.width() - 60), min(600, screen.height() - 80))
        style_dialog(self, title_txt)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)

        banner = QFrame()
        banner.setStyleSheet(f'QFrame {{background:{c.PRI_GHO};border:1px solid {c.PRI_DIM};border-radius:10px;}}')
        b_lay = QVBoxLayout(banner)
        b_lay.setContentsMargins(12, 8, 12, 8)
        b_lay.setSpacing(3)
        head = QLabel(f"🎓 {lang_name} — Eng muhim Formula va Xato Tuzoqlari")
        head.setFont(font(11, True))
        head.setStyleSheet(f'color:{c.PRI};border:none;background:transparent;')
        guide = LANGUAGE_LINGUISTIC_GUIDES.get(lang_code, LANGUAGE_LINGUISTIC_GUIDES['default'])
        sub = QLabel(guide)
        sub.setWordWrap(True)
        sub.setFont(font(8))
        sub.setStyleSheet(f'color:{c.TEXT};border:none;background:transparent;')
        b_lay.addWidget(head)
        b_lay.addWidget(sub)
        root.addWidget(banner)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        host = QWidget()
        lay = QVBoxLayout(host)
        lay.setContentsMargins(2, 2, 6, 2)
        lay.setSpacing(8)

        cards = LANGUAGE_GRAMMAR_CHEATSHEETS.get(lang_code, LANGUAGE_GRAMMAR_CHEATSHEETS['default'])
        for row in cards:
            card = QFrame()
            card.setStyleSheet(f'QFrame {{background:{c.PANEL2};border:1px solid {c.BORDER};border-radius:10px;}}')
            cl = QVBoxLayout(card)
            cl.setContentsMargins(12, 10, 12, 10)
            cl.setSpacing(4)
            t_lbl = QLabel(f"📐 {row['title']}")
            t_lbl.setFont(font(10, True))
            t_lbl.setStyleSheet(f'color:{c.WHITE};border:none;background:transparent;')
            f_lbl = QLabel(f"Formula: {row['formula']}")
            f_lbl.setWordWrap(True)
            f_lbl.setFont(font(9, True))
            f_lbl.setStyleSheet(f'color:{c.PRI};border:none;background:transparent;')
            e_lbl = QLabel(f"✅ Misol: {row['example']}")
            e_lbl.setWordWrap(True)
            e_lbl.setFont(font(9))
            e_lbl.setStyleSheet(f'color:{c.TEXT};border:none;background:transparent;')
            trap_lbl = QLabel(f"⚠️ Tuzoq: {row['trap']}")
            trap_lbl.setWordWrap(True)
            trap_lbl.setFont(font(8))
            trap_lbl.setStyleSheet(f'color:{c.TEXT_MED};border:none;background:transparent;')
            cl.addWidget(t_lbl)
            cl.addWidget(f_lbl)
            cl.addWidget(e_lbl)
            cl.addWidget(trap_lbl)

            btn_row = QHBoxLayout()
            btn_row.addStretch()
            practice_btn = QPushButton("💬 Chatda mashq qilish →")
            practice_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            practice_btn.setStyleSheet(button_style(True) + 'QPushButton {padding:4px 10px;font-size:11px;}')
            practice_btn.clicked.connect(lambda _=False, p=row['practice_prompt']: self._practice(p))
            btn_row.addWidget(practice_btn)
            cl.addLayout(btn_row)
            lay.addWidget(card)
        lay.addStretch()
        scroll.setWidget(host)
        root.addWidget(scroll, 1)

        footer = QHBoxLayout()
        footer.addStretch()
        close_btn = QPushButton("Yopish")
        close_btn.setStyleSheet(button_style())
        close_btn.clicked.connect(self.accept)
        footer.addWidget(close_btn)
        root.addLayout(footer)

    def _practice(self, prompt_text: str):
        self.controller.record_study_session()
        self.controller.switch_skill('grammar')
        if hasattr(self.controller.win, '_input'):
            self.controller.win._input.setText(prompt_text)
            self.controller.win._input.setFocus()
        self.accept()


class FlashcardDialog(QDialog):
    """Interval takrorlash (Spaced Repetition) interaktiv Flashcard darsi."""

    def __init__(self, controller: TutorController, parent=None):
        super().__init__(parent or controller.win)
        self.controller = controller
        from brave_ui import button_style, colors, font
        from brave_control_center import style_dialog
        c = colors()
        lang_name = language_display_name(controller.state)
        level = controller.state.get('level', 'B1')
        self.setWindowTitle(f"TAI Flashcard · {lang_name} ({level})")
        self.setFont(font(10))
        self.resize(560, 420)
        style_dialog(self, f"TAI Flashcard · {lang_name} ({level})")

        lang_code = controller.state.get('target_language', 'en')
        self.items = [
            v for v in (controller.state.get('vocab_bank') or [])
            if v.get('lang', lang_code) == lang_code
        ]
        self.queue = list(self.items)
        self.current_idx = 0
        self.flipped = False
        self.reviewed_count = 0
        self.mastered_in_session = 0

        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(20, 16, 20, 16)
        self.root.setSpacing(10)

        # Top Bar: Progress and counter
        top_bar = QHBoxLayout()
        self.title_lbl = QLabel(f"🗂 Flashcard · {lang_name} ({level})")
        self.title_lbl.setFont(font(11, True))
        self.title_lbl.setStyleSheet(f"color:{c.PRI};border:none;background:transparent;")
        self.counter_lbl = QLabel(f"Kartochka 1 / {max(1, len(self.queue))}")
        self.counter_lbl.setFont(font(9))
        self.counter_lbl.setStyleSheet(f"color:{c.TEXT_MED};border:none;background:transparent;")
        top_bar.addWidget(self.title_lbl)
        top_bar.addStretch()
        top_bar.addWidget(self.counter_lbl)
        self.root.addLayout(top_bar)

        self.prog_bar = QProgressBar()
        self.prog_bar.setRange(0, max(1, len(self.queue)))
        self.prog_bar.setValue(0)
        self.prog_bar.setTextVisible(False)
        self.prog_bar.setFixedHeight(5)
        self.prog_bar.setStyleSheet(
            f"QProgressBar {{background:{c.BORDER};border-radius:2px;border:none;}}"
            f"QProgressBar::chunk {{background:{c.PRI};border-radius:2px;}}"
        )
        self.root.addWidget(self.prog_bar)

        # Flip Card Container
        self.card = QFrame()
        self.card.setCursor(Qt.CursorShape.PointingHandCursor)
        self.card.setStyleSheet(
            f"QFrame {{background:{c.PANEL2};border:2px solid {c.BORDER};border-radius:14px;}}"
            f"QFrame:hover {{border-color:{c.PRI_DIM};}}"
        )
        self.card.mousePressEvent = lambda e: self._toggle_flip()
        self.card_layout = QVBoxLayout(self.card)
        self.card_layout.setContentsMargins(22, 18, 22, 18)
        self.card_layout.setSpacing(8)

        self.side_badge = QLabel("OLD TOMON · SO‘Z")
        self.side_badge.setFont(font(8, True))
        self.side_badge.setStyleSheet(f"color:{c.TEXT_DIM};border:none;background:transparent;")
        self.card_layout.addWidget(self.side_badge, 0, Qt.AlignmentFlag.AlignHCenter)

        self.word_lbl = QLabel("")
        self.word_lbl.setFont(font(20, True))
        self.word_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.word_lbl.setWordWrap(True)
        self.word_lbl.setStyleSheet(f"color:{c.WHITE};border:none;background:transparent;margin-top:6px;")
        self.card_layout.addWidget(self.word_lbl)

        speak_row = QHBoxLayout()
        speak_row.setSpacing(6)
        speak_row.addStretch()
        self.speak_btn = QPushButton("🔊 Talaffuz")
        self.speak_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.speak_btn.setStyleSheet(button_style() + f"QPushButton {{padding:3px 10px;font-size:11px;color:{c.PRI};}}")
        self.speak_btn.clicked.connect(lambda: self._speak_current(slow=False))
        self.slow_speak_btn = QPushButton("🐢 Sekin (0.7×)")
        self.slow_speak_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.slow_speak_btn.setToolTip("Bo‘g‘inlab sekin talaffuz qilish")
        self.slow_speak_btn.setStyleSheet(button_style() + f"QPushButton {{padding:3px 9px;font-size:11px;color:{c.TEXT_MED};}}")
        self.slow_speak_btn.clicked.connect(lambda: self._speak_current(slow=True))
        speak_row.addWidget(self.speak_btn)
        speak_row.addWidget(self.slow_speak_btn)
        speak_row.addStretch()
        self.card_layout.addLayout(speak_row)

        self.back_container = QWidget()
        back_lay = QVBoxLayout(self.back_container)
        back_lay.setContentsMargins(0, 4, 0, 0)
        back_lay.setSpacing(6)

        self.meaning_lbl = QLabel("")
        self.meaning_lbl.setFont(font(13, True))
        self.meaning_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.meaning_lbl.setWordWrap(True)
        self.meaning_lbl.setStyleSheet(f"color:{c.PRI};border:none;background:transparent;")
        back_lay.addWidget(self.meaning_lbl)

        self.colloc_lbl = QLabel("")
        self.colloc_lbl.setFont(font(10))
        self.colloc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.colloc_lbl.setWordWrap(True)
        self.colloc_lbl.setStyleSheet(f"color:{c.TEXT};border:none;background:transparent;")
        back_lay.addWidget(self.colloc_lbl)

        self.mnem_lbl = QLabel("")
        self.mnem_lbl.setFont(font(9))
        self.mnem_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mnem_lbl.setWordWrap(True)
        self.mnem_lbl.setStyleSheet(f"color:{c.TEXT_MED};border:none;background:transparent;")
        back_lay.addWidget(self.mnem_lbl)

        self.card_layout.addWidget(self.back_container)
        self.back_container.hide()

        self.card_layout.addStretch()

        self.hint_lbl = QLabel("💡 Kartani ag‘darish uchun bosing yoki Space tugmasini bosing")
        self.hint_lbl.setFont(font(8))
        self.hint_lbl.setStyleSheet(f"color:{c.TEXT_DIM};border:none;background:transparent;")
        self.card_layout.addWidget(self.hint_lbl, 0, Qt.AlignmentFlag.AlignHCenter)

        self.root.addWidget(self.card, 1)

        # Bottom Controls
        self.bottom_box = QHBoxLayout()
        self.flip_btn = QPushButton("🔄 Javobni Ko‘rish (Space)")
        self.flip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.flip_btn.setStyleSheet(button_style(True) + "QPushButton {padding:7px 16px;font-size:12px;font-weight:600;}")
        self.flip_btn.clicked.connect(self._toggle_flip)
        self.bottom_box.addWidget(self.flip_btn)

        self.rate_hard_btn = QPushButton("❌ Qiyin [1]")
        self.rate_hard_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rate_hard_btn.setStyleSheet(button_style() + "QPushButton {padding:7px 12px;font-size:11px;color:#ff6b6b;border-color:#ff6b6b;}")
        self.rate_hard_btn.clicked.connect(lambda: self._rate('hard'))

        self.rate_good_btn = QPushButton("⚡ Yaxshi [2]")
        self.rate_good_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rate_good_btn.setStyleSheet(button_style(True) + "QPushButton {padding:7px 14px;font-size:11px;}")
        self.rate_good_btn.clicked.connect(lambda: self._rate('good'))

        self.rate_easy_btn = QPushButton("🌟 Oson [3]")
        self.rate_easy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rate_easy_btn.setStyleSheet(button_style() + "QPushButton {padding:7px 12px;font-size:11px;color:#51cf66;border-color:#51cf66;}")
        self.rate_easy_btn.clicked.connect(lambda: self._rate('easy'))

        self.bottom_box.addWidget(self.rate_hard_btn)
        self.bottom_box.addWidget(self.rate_good_btn)
        self.bottom_box.addWidget(self.rate_easy_btn)

        self.rate_hard_btn.hide()
        self.rate_good_btn.hide()
        self.rate_easy_btn.hide()

        self.root.addLayout(self.bottom_box)

        if not self.queue:
            self._show_empty()
        else:
            self._show_card()

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key.Key_Space, Qt.Key.Key_Return):
            if not self.flipped:
                self._toggle_flip()
            else:
                self._rate('good')
        elif key == Qt.Key.Key_1 and self.flipped:
            self._rate('hard')
        elif key == Qt.Key.Key_2 and self.flipped:
            self._rate('good')
        elif key == Qt.Key.Key_3 and self.flipped:
            self._rate('easy')
        elif key == Qt.Key.Key_Escape:
            self.accept()
        else:
            super().keyPressEvent(event)

    def _show_card(self):
        from brave_ui import colors
        c = colors()
        self.flipped = False
        current = self.queue[self.current_idx]
        self.side_badge.setText("OLD TOMON · SO‘Z")
        self.side_badge.setStyleSheet(f"color:{c.TEXT_DIM};border:none;background:transparent;")
        self.word_lbl.setText(current.get('word', ''))
        self.meaning_lbl.setText(current.get('meaning', ''))
        self.colloc_lbl.setText(f"🔗 {current.get('collocation', '')}" if current.get('collocation') else "")
        self.mnem_lbl.setText(f"💡 {current.get('mnemonic', '')}" if current.get('mnemonic') else "")
        self.back_container.hide()
        self.counter_lbl.setText(f"Kartochka {self.current_idx + 1} / {len(self.queue)}")
        self.hint_lbl.setText("💡 Kartani ag‘darish uchun bosing yoki Space tugmasini bosing")

        self.flip_btn.show()
        self.rate_hard_btn.hide()
        self.rate_good_btn.hide()
        self.rate_easy_btn.hide()

    def _toggle_flip(self):
        if not self.queue or self.side_badge.text() in ("NATIJA", "LUG‘AT BO‘SH"):
            return
        from brave_ui import colors
        c = colors()
        self.flipped = not self.flipped
        if self.flipped:
            self.side_badge.setText("ORQA TOMON · TARJIMA VA MNEMONIKA")
            self.side_badge.setStyleSheet(f"color:{c.PRI};border:none;background:transparent;")
            self.back_container.show()
            self.hint_lbl.setText("Natijangizni baholang: 1 (Qiyin), 2 (Yaxshi), 3 (Oson)")
            self.flip_btn.hide()
            self.rate_hard_btn.show()
            self.rate_good_btn.show()
            self.rate_easy_btn.show()
        else:
            self.side_badge.setText("OLD TOMON · SO‘Z")
            self.side_badge.setStyleSheet(f"color:{c.TEXT_DIM};border:none;background:transparent;")
            self.back_container.hide()
            self.hint_lbl.setText("💡 Kartani ag‘darish uchun bosing yoki Space tugmasini bosing")
            self.flip_btn.show()
            self.rate_hard_btn.hide()
            self.rate_good_btn.hide()
            self.rate_easy_btn.hide()

    def _speak_current(self, slow: bool = False):
        if self.queue:
            word = self.queue[self.current_idx].get('word', '')
            self.controller.speak_word(word, slow=slow)

    def _rate(self, rating: str):
        if not self.queue:
            return
        current = self.queue[self.current_idx]
        word = current.get('word', '')
        self.reviewed_count += 1
        self.controller.record_study_session()

        if rating == 'easy':
            self.mastered_in_session += 1
            self.controller.update_vocab_progress(word, mastered=True)
            self.queue.pop(self.current_idx)
        elif rating == 'good':
            self.controller.update_vocab_progress(word, mastered=True)
            self.queue.pop(self.current_idx)
        else:
            self.controller.update_vocab_progress(word, mastered=False)
            card = self.queue.pop(self.current_idx)
            self.queue.append(card)

        self.prog_bar.setValue(min(self.reviewed_count, self.prog_bar.maximum()))
        if not self.queue:
            self._show_summary()
        else:
            if self.current_idx >= len(self.queue):
                self.current_idx = 0
            self._show_card()

    def _show_summary(self):
        from brave_ui import colors, font, button_style
        c = colors()
        self.prog_bar.setValue(self.prog_bar.maximum())
        self.side_badge.setText("NATIJA")
        self.word_lbl.setText("🎉 Mashg‘ulot yakunlandi!")
        self.speak_btn.hide()
        self.slow_speak_btn.hide()
        self.back_container.show()
        self.meaning_lbl.setText(f"Takrorlangan so‘zlar: {self.reviewed_count} ta")
        self.colloc_lbl.setText("🔥 O‘quv streak saqlandi va xotirangiz mustahkamlandi!")
        self.mnem_lbl.setText("💡 Interval takrorlash har kuni 5 daqiqa davom ettirilsa, so‘zlar uzoq muddatli xotiraga aylanadi.")
        self.hint_lbl.setText("Ertaga yana takrorlashni unutmang!")

        self.flip_btn.hide()
        self.rate_hard_btn.hide()
        self.rate_good_btn.hide()
        self.rate_easy_btn.hide()

        restart_btn = QPushButton("🔄 Qayta Boshlash")
        restart_btn.setStyleSheet(button_style(True) + "QPushButton {padding:7px 16px;}")
        restart_btn.clicked.connect(self._restart)
        close_btn = QPushButton("Yopish")
        close_btn.setStyleSheet(button_style() + "QPushButton {padding:7px 16px;}")
        close_btn.clicked.connect(self.accept)
        self.bottom_box.addWidget(restart_btn)
        self.bottom_box.addWidget(close_btn)

    def _show_empty(self):
        from brave_ui import button_style
        self.side_badge.setText("LUG‘AT BO‘SH")
        self.word_lbl.setText("Hozircha so‘zlar mavjud emas")
        self.speak_btn.hide()
        self.slow_speak_btn.hide()
        self.back_container.show()
        self.meaning_lbl.setText("O‘rganish uchun avval so‘zlar paketini yuklang")
        self.colloc_lbl.setText("")
        self.mnem_lbl.setText("")
        self.hint_lbl.setText("")
        self.flip_btn.hide()
        load_btn = QPushButton("⚡ Professor C1 So‘zlarini Yuklash va Boshlash")
        load_btn.setStyleSheet(button_style(True) + "QPushButton {padding:8px 16px;font-weight:600;}")
        load_btn.clicked.connect(self._load_pack_and_start)
        self.bottom_box.addWidget(load_btn)

    def _load_pack_and_start(self):
        self.controller.load_starter_vocab_pack()
        lang_code = self.controller.state.get('target_language', 'en')
        self.items = [v for v in (self.controller.state.get('vocab_bank') or []) if v.get('lang', lang_code) == lang_code]
        self.queue = list(self.items)
        while self.bottom_box.count():
            it = self.bottom_box.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self.bottom_box.addWidget(self.flip_btn)
        self.bottom_box.addWidget(self.rate_hard_btn)
        self.bottom_box.addWidget(self.rate_good_btn)
        self.bottom_box.addWidget(self.rate_easy_btn)
        self.prog_bar.setRange(0, max(1, len(self.queue)))
        self.speak_btn.show()
        self.slow_speak_btn.show()
        self._show_card()

    def _restart(self):
        lang_code = self.controller.state.get('target_language', 'en')
        self.items = [v for v in (self.controller.state.get('vocab_bank') or []) if v.get('lang', lang_code) == lang_code]
        self.queue = list(self.items)
        self.current_idx = 0
        self.reviewed_count = 0
        self.mastered_in_session = 0
        while self.bottom_box.count():
            it = self.bottom_box.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self.bottom_box.addWidget(self.flip_btn)
        self.bottom_box.addWidget(self.rate_hard_btn)
        self.bottom_box.addWidget(self.rate_good_btn)
        self.bottom_box.addWidget(self.rate_easy_btn)
        self.prog_bar.setValue(0)
        self.speak_btn.show()
        self.slow_speak_btn.show()
        self._show_card()


class AcademyHubDialog(QDialog):
    """TAI Akademiya Markazi: Shaxsiy Lug‘at (Word Bank & Mnemonics), 7-Bo‘lim Statistikasi va Tezkor Sinov."""

    def __init__(self, controller: TutorController):
        super().__init__(controller.win)
        from brave_ui import button_style, colors, font
        from brave_control_center import style_dialog

        self.controller = controller
        c = colors()
        lang_name = language_display_name(controller.state)
        level = controller.state.get('level', 'B1')
        self.setWindowTitle(f"TAI Akademiya Markazi · {lang_name} ({level})")
        self.setFont(font(10))
        screen = controller.win.screen().availableGeometry()
        self.resize(min(820, screen.width() - 48), min(660, screen.height() - 64))
        style_dialog(self, f"TAI Akademiya Markazi · {lang_name} ({level})")

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)

        # 1. 7-Skill Progress Summary Banner
        stats_card = QFrame()
        stats_card.setStyleSheet(f'QFrame {{background:{c.PANEL2};border:1px solid {c.BORDER};border-radius:12px;}}')
        sc_lay = QVBoxLayout(stats_card)
        sc_lay.setContentsMargins(14, 10, 14, 10)
        sc_lay.setSpacing(6)
        sc_title = QLabel(f"📊 7 O‘quv Chat Bo‘yicha Faollik ({lang_name} · {level})")
        sc_title.setFont(font(10, True))
        sc_title.setStyleSheet(f'color:{c.PRI};border:none;background:transparent;')
        sc_lay.addWidget(sc_title)

        counts = controller.skill_message_counts()
        grid = QGridLayout()
        grid.setSpacing(6)
        for idx, skill in enumerate(SKILLS):
            cnt = counts.get(skill.key, 0)
            pill = QPushButton(f"{skill.short_title}: {cnt} xabar")
            pill.setCursor(Qt.CursorShape.PointingHandCursor)
            pill.setStyleSheet(button_style(skill.key == controller.state.get('active_skill')))
            pill.clicked.connect(lambda _=False, k=skill.key: (controller.switch_skill(k), self.accept()))
            grid.addWidget(pill, idx // 4, idx % 4)
        sc_lay.addLayout(grid)
        root.addWidget(stats_card)

        # 2. Add New Word / Collocation / Mnemonic Form
        add_card = QFrame()
        add_card.setStyleSheet(f'QFrame {{background:{c.PANEL2};border:1px solid {c.BORDER};border-radius:12px;}}')
        ac_lay = QVBoxLayout(add_card)
        ac_lay.setContentsMargins(14, 10, 14, 10)
        ac_lay.setSpacing(6)
        ac_head = QHBoxLayout()
        ac_title = QLabel("📚 Shaxsiy Professor Lug‘ati (So‘z + Kollokatsiya + Mnemonika)")
        ac_title.setFont(font(10, True))
        ac_title.setStyleSheet(f'color:{c.WHITE};border:none;background:transparent;')
        ac_head.addWidget(ac_title)
        ac_head.addStretch()
        pack_btn = QPushButton("⚡ Professor C1 So‘zlar Paketini Yuklash")
        pack_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        pack_btn.setStyleSheet(button_style(True) + 'QPushButton {padding:4px 10px;font-size:11px;}')
        pack_btn.clicked.connect(self._load_pack)
        ac_head.addWidget(pack_btn)
        ac_lay.addLayout(ac_head)

        row1 = QHBoxLayout()
        self.word_in = QLineEdit()
        self.word_in.setPlaceholderText("So‘z yoki ibora (masalan: ubiquitous)")
        self.meaning_in = QLineEdit()
        self.meaning_in.setPlaceholderText("Ma’nosi va darajasi (masalan: hamma joyda uchraydigan · C1)")
        row1.addWidget(self.word_in, 1)
        row1.addWidget(self.meaning_in, 1)
        ac_lay.addLayout(row1)

        row2 = QHBoxLayout()
        self.colloc_in = QLineEdit()
        self.colloc_in.setPlaceholderText("Tabiiy birikma / Kollokatsiya (masalan: ubiquitous technology)")
        self.mnem_in = QLineEdit()
        self.mnem_in.setPlaceholderText("Mnemonika / eslab qolish kaliti")
        add_btn = QPushButton("＋ Lug‘atga Qo‘shish")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setStyleSheet(button_style(True) + 'QPushButton {padding:5px 12px;font-weight:600;}')
        add_btn.clicked.connect(self._add_word)
        row2.addWidget(self.colloc_in, 1)
        row2.addWidget(self.mnem_in, 1)
        row2.addWidget(add_btn)
        ac_lay.addLayout(row2)
        root.addWidget(add_card)

        # 3. Search and Filter Bar
        search_box = QHBoxLayout()
        self.search_in = QLineEdit()
        self.search_in.setPlaceholderText("🔍 Lug‘atdan qidirish (so‘z, ma’no yoki kollokatsiya bo‘yicha)...")
        self.search_in.textChanged.connect(lambda: self._render_vocab_list())
        self.filter_combo = QComboBox()
        self.filter_combo.addItem("Barchasi", "all")
        self.filter_combo.addItem("⏳ Takrorlash kerak", "review")
        self.filter_combo.addItem("🌟 Yodlangan", "mastered")
        self.filter_combo.setMinimumWidth(155)
        self.filter_combo.currentIndexChanged.connect(lambda: self._render_vocab_list())
        search_box.addWidget(self.search_in, 1)
        search_box.addWidget(self.filter_combo)
        root.addLayout(search_box)

        # 4. Scrollable Vocabulary Cards List
        self.list_scroll = QScrollArea()
        self.list_scroll.setWidgetResizable(True)
        self.list_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.list_host = QWidget()
        self.list_layout = QVBoxLayout(self.list_host)
        self.list_layout.setContentsMargins(2, 2, 6, 2)
        self.list_layout.setSpacing(6)
        self.list_scroll.setWidget(self.list_host)
        root.addWidget(self.list_scroll, 1)

        # Streak and study stats banner
        streak_stats = controller.get_streak_stats()
        streak_val = streak_stats.get('streak', 0)
        total_val = streak_stats.get('total_days', 0)
        mastery = controller.vocab_mastery_stats()
        streak_card = QFrame()
        streak_card.setStyleSheet(f'QFrame {{background:{c.PRI_GHO};border:1px solid {c.PRI_DIM};border-radius:10px;}}')
        sk_lay = QHBoxLayout(streak_card)
        sk_lay.setContentsMargins(14, 8, 14, 8)
        flame_lbl = QLabel(f"🔥 Streak: {streak_val} kun" if streak_val else "📅 Hali streak yo'q — bugun o'rganishni boshlang!")
        flame_lbl.setFont(font(10, True))
        flame_lbl.setStyleSheet(f'color:{c.PRI};border:none;background:transparent;')
        self.mastered_lbl = QLabel(f"🏆 Yodlangan: {mastery['mastered']}/{mastery['total']} ({mastery['percent']}%)")
        self.mastered_lbl.setFont(font(9, True))
        self.mastered_lbl.setStyleSheet(f'color:{c.WHITE};border:none;background:transparent;')
        total_lbl = QLabel(f"📊 Jami: {total_val} o'quv kuni")
        total_lbl.setFont(font(9))
        total_lbl.setStyleSheet(f'color:{c.TEXT};border:none;background:transparent;')
        sk_lay.addWidget(flame_lbl)
        sk_lay.addStretch()
        sk_lay.addWidget(self.mastered_lbl)
        sk_lay.addStretch()
        sk_lay.addWidget(total_lbl)
        root.addWidget(streak_card)

        footer = QHBoxLayout()
        footer.setSpacing(6)
        flashcard_btn = QPushButton("🗂 Flashcard")
        flashcard_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        flashcard_btn.setStyleSheet(button_style(True) + 'QPushButton {padding:6px 12px;font-weight:600;}')
        flashcard_btn.setToolTip("Interval takrorlash kartochkalari bilan so‘zlarni yodlash")
        flashcard_btn.clicked.connect(self._open_flashcards)

        formulas_btn = QPushButton("📐 Oltin Formulalar")
        formulas_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        formulas_btn.setStyleSheet(button_style() + 'QPushButton {padding:6px 10px;}')
        formulas_btn.setToolTip("Faol til bo‘yicha grammatika formulalari va xato tuzoqlari")
        formulas_btn.clicked.connect(lambda: GrammarFormulaDialog(controller, self).exec())

        quiz_btn = QPushButton("🎯 Sinov")
        quiz_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        quiz_btn.setStyleSheet(button_style() + 'QPushButton {padding:6px 10px;}')
        quiz_btn.setToolTip("5-savollik interaktiv CEFR sinovi")
        quiz_btn.clicked.connect(lambda: (self.accept(), controller.launch_skill_quiz()))

        diag_btn = QPushButton("🎓 Diagnostika")
        diag_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        diag_btn.setStyleSheet(button_style() + 'QPushButton {padding:6px 10px;}')
        diag_btn.setToolTip("CEFR daraja diagnostikasi va 7 ko‘nikma bo‘yicha shaxsiy reja")
        diag_btn.clicked.connect(lambda: (self.accept(), controller.launch_placement_diagnostic()))

        csv_btn = QPushButton("📥 CSV/Anki")
        csv_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        csv_btn.setStyleSheet(button_style() + 'QPushButton {padding:6px 10px;}')
        csv_btn.setToolTip("Shaxsiy lug'atni CSV yoki Anki kartalari sifatida saqlash")
        csv_btn.clicked.connect(lambda: self._export_csv(controller))

        report_btn = QPushButton("📊 Hisobot (.md)")
        report_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        report_btn.setStyleSheet(button_style() + 'QPushButton {padding:6px 10px;}')
        report_btn.setToolTip("To‘liq o‘quv hisoboti va tavsiyalarni Markdown faylida eksport qilish")
        report_btn.clicked.connect(lambda: self._export_study_report(controller))

        close_btn = QPushButton("Yopish")
        close_btn.setStyleSheet(button_style())
        close_btn.clicked.connect(self.accept)
        footer.addWidget(flashcard_btn)
        footer.addWidget(formulas_btn)
        footer.addWidget(quiz_btn)
        footer.addWidget(diag_btn)
        footer.addWidget(csv_btn)
        footer.addWidget(report_btn)
        footer.addStretch()
        footer.addWidget(close_btn)
        root.addLayout(footer)

        self._render_vocab_list()

    def _add_word(self):
        if self.controller.add_vocab_entry(
            self.word_in.text(),
            self.meaning_in.text(),
            self.colloc_in.text(),
            self.mnem_in.text(),
        ):
            self.word_in.clear()
            self.meaning_in.clear()
            self.colloc_in.clear()
            self.mnem_in.clear()
            self._render_vocab_list()
            self._refresh_mastery_label()

    def _refresh_mastery_label(self):
        mastery = self.controller.vocab_mastery_stats()
        if hasattr(self, 'mastered_lbl'):
            self.mastered_lbl.setText(f"🏆 Yodlangan: {mastery['mastered']}/{mastery['total']} ({mastery['percent']}%)")

    def _open_flashcards(self):
        FlashcardDialog(self.controller, self).exec()
        self._render_vocab_list()
        self._refresh_mastery_label()

    def _load_pack(self):
        self.controller.load_starter_vocab_pack()
        self._render_vocab_list()
        self._refresh_mastery_label()

    def _toggle_mastered(self, word: str, current_mastered: bool):
        self.controller.update_vocab_progress(word, mastered=not current_mastered)
        self._render_vocab_list()
        self._refresh_mastery_label()

    def _practice_word_in_chat(self, word: str):
        self.controller.record_study_session()
        self.controller.switch_skill('vocabulary')
        if hasattr(self.controller.win, '_input'):
            self.controller.win._input.setText(
                f"\"{word}\" so‘zini 30 yillik professor metodikasi bo‘yicha (etimologiya, 5 ta kollokatsiya, "
                "mnemonika va A2/B2/C1 darajali jonli gaplar bilan) chuqur tahlil qilib ber."
            )
        self.accept()

    def _delete_word(self, word: str):
        if self.controller.delete_vocab_entry(word):
            self._render_vocab_list()
            self._refresh_mastery_label()

    def _render_vocab_list(self):
        from brave_ui import button_style, colors, font
        c = colors()
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        lang_code = self.controller.state.get('target_language', 'en')
        items = [
            v for v in (self.controller.state.get('vocab_bank') or [])
            if v.get('lang', lang_code) == lang_code
        ]
        filter_mode = self.filter_combo.currentData() if hasattr(self, 'filter_combo') else 'all'
        if filter_mode == 'mastered':
            items = [v for v in items if v.get('mastered')]
        elif filter_mode == 'review':
            items = [v for v in items if not v.get('mastered')]

        query = self.search_in.text().strip().lower() if hasattr(self, 'search_in') else ''
        if query:
            items = [
                v for v in items
                if query in v.get('word', '').lower()
                or query in v.get('meaning', '').lower()
                or query in v.get('collocation', '').lower()
                or query in v.get('mnemonic', '').lower()
            ]
        if not items:
            msg = "Mos keladigan so‘z topilmadi." if (query or filter_mode != 'all') else (
                "Hozircha bu tilda saqlangan so‘zlar yo‘q. Yuqoridagi '⚡ Professor C1 So‘zlar Paketini Yuklash' "
                "tugmasini bosing yoki o‘z so‘zingizni qo‘shing!"
            )
            empty = QLabel(msg)
            empty.setWordWrap(True)
            empty.setFont(font(9))
            empty.setStyleSheet(f'color:{c.TEXT_DIM};padding:12px;')
            self.list_layout.addWidget(empty)
            self.list_layout.addStretch()
            return
        for row in items:
            card = QFrame()
            card.setStyleSheet(f'QFrame {{background:{c.BG};border:1px solid {c.BORDER};border-radius:10px;}}')
            lay = QHBoxLayout(card)
            lay.setContentsMargins(12, 8, 12, 8)
            lay.setSpacing(8)
            info = QVBoxLayout()
            head = QLabel(f"🔹 {row['word']}  —  {row['meaning']}")
            head.setFont(font(10, True))
            head.setStyleSheet(f'color:{c.WHITE};border:none;')
            sub_parts = []
            if row.get('collocation'):
                sub_parts.append(f"🔗 Kollokatsiya: {row['collocation']}")
            if row.get('mnemonic'):
                sub_parts.append(f"💡 Mnemonika: {row['mnemonic']}")
            sub = QLabel("   |   ".join(sub_parts) if sub_parts else "")
            sub.setFont(font(8))
            sub.setStyleSheet(f'color:{c.PRI};border:none;')
            info.addWidget(head)
            if sub_parts:
                info.addWidget(sub)
            lay.addLayout(info, 1)

            is_mastered = bool(row.get('mastered'))
            toggle_btn = QPushButton("🌟 Yodlangan" if is_mastered else "⏳ Takrorlash")
            toggle_btn.setToolTip("Yodlangan / Takrorlash holatini almashtirish")
            toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            toggle_btn.setStyleSheet(
                button_style() + (
                    "QPushButton {padding:4px 8px;font-size:10px;color:#51cf66;border-color:#51cf66;}"
                    if is_mastered else
                    f"QPushButton {{padding:4px 8px;font-size:10px;color:{c.TEXT_MED};}}"
                )
            )
            toggle_btn.clicked.connect(lambda _=False, w=row['word'], m=is_mastered: self._toggle_mastered(w, m))
            lay.addWidget(toggle_btn)

            speak_btn = QPushButton("🔊")
            speak_btn.setToolTip("Tabiiy tezlikda talaffuzni eshitish")
            speak_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            speak_btn.setStyleSheet(button_style() + f'QPushButton {{padding:4px 8px;font-size:12px;color:{c.PRI};}}')
            speak_btn.clicked.connect(lambda _=False, w=row['word']: self.controller.speak_word(w))
            lay.addWidget(speak_btn)

            slow_btn = QPushButton("🐢")
            slow_btn.setToolTip("Sekin va bo‘g‘inlab talaffuzni eshitish (0.70×)")
            slow_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            slow_btn.setStyleSheet(button_style() + f'QPushButton {{padding:4px 7px;font-size:11px;color:{c.TEXT_MED};}}')
            slow_btn.clicked.connect(lambda _=False, w=row['word']: self.controller.speak_word(w, slow=True))
            lay.addWidget(slow_btn)

            ask_btn = QPushButton("Professor Tahlili →")
            ask_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            ask_btn.setStyleSheet(button_style() + 'QPushButton {padding:4px 8px;font-size:11px;}')
            ask_btn.clicked.connect(lambda _=False, w=row['word']: self._practice_word_in_chat(w))
            lay.addWidget(ask_btn)

            del_btn = QPushButton("✕")
            del_btn.setToolTip("Lug‘atdan o‘chirish")
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_btn.setStyleSheet(button_style() + f'QPushButton {{padding:4px 8px;font-size:11px;color:{c.TEXT_DIM};}} QPushButton:hover {{color:#ff5555;}}')
            del_btn.clicked.connect(lambda _=False, w=row['word']: self._delete_word(w))
            lay.addWidget(del_btn)

            self.list_layout.addWidget(card)
        self.list_layout.addStretch()

    def _export_csv(self, controller: 'TutorController'):
        from PyQt6.QtWidgets import QFileDialog
        lang_name = language_display_name(controller.state)
        lang_code = controller.state.get('target_language', 'en')
        path, selected_filter = QFileDialog.getSaveFileName(
            self, f"Lug'atni eksport qilish — {lang_name}",
            f"tai_vocab_{lang_code}.csv",
            "CSV fayl (*.csv);;Anki Flashcards TSV (*.tsv *.txt)",
        )
        if not path:
            return
        try:
            from pathlib import Path
            if path.endswith(('.tsv', '.txt')) or 'Anki' in selected_filter:
                text_content = controller.export_vocab_anki()
            else:
                text_content = controller.export_vocab_csv()
            Path(path).write_text(text_content, encoding='utf-8-sig')
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Eksport muvaffaqiyatli", f"Lug'at saqlandi:\n{path}")
        except OSError as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Xato", f"Saqlashda xato: {e}")

    def _export_study_report(self, controller: 'TutorController'):
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        lang_name = language_display_name(controller.state)
        lang_code = controller.state.get('target_language', 'en')
        path, _ = QFileDialog.getSaveFileName(
            self, f"O‘quv hisobotini saqlash — {lang_name}",
            f"tai_hisobot_{lang_code}.md",
            "Markdown fayl (*.md);;Matn fayl (*.txt)",
        )
        if not path:
            return
        try:
            from pathlib import Path
            Path(path).write_text(controller.export_study_report_markdown(), encoding='utf-8')
            QMessageBox.information(self, "Hisobot saqlandi", f"Shaxsiy o‘quv hisoboti saqlandi:\n{path}")
        except OSError as e:
            QMessageBox.warning(self, "Xato", f"Saqlashda xato: {e}")


def build_tutor_chat_bar(win, layout: QVBoxLayout):
    """Compact interactive bar at the top of the Chat panel for instant Language, Level, Role, Quiz, and Professor Tools."""
    from pathlib import Path
    from brave_ui import button_style, colors, font, set_icon

    c = colors()
    if not hasattr(win, '_language_tutor'):
        win._language_tutor = TutorController(win)
    tutor = win._language_tutor

    bar = QFrame()
    bar.setObjectName('BraveTutorBar')
    bar.setStyleSheet(
        f'QFrame#BraveTutorBar {{background:{c.PANEL2};border:1px solid {c.BORDER};border-radius:10px;}}'
    )
    bar_layout = QHBoxLayout(bar)
    bar_layout.setContentsMargins(8, 4, 8, 4)
    bar_layout.setSpacing(5)

    arrow = (Path(__file__).resolve().parent / 'assets' / 'chevron.svg').as_posix()
    combo_style = (
        f'QComboBox {{color:{c.TEXT};background:{c.BG};border:1px solid {c.BORDER};'
        f'border-radius:7px;padding:3px 16px 3px 6px;}}'
        f'QComboBox::drop-down {{width:14px;border:none;background:transparent;}}'
        f'QComboBox::down-arrow {{image:url("{arrow}");width:8px;height:8px;}}'
        f'QComboBox QAbstractItemView {{color:{c.TEXT};background:{c.PANEL2};selection-background-color:{c.PRI_GHO};}}'
    )

    win._tutor_lang_box = QComboBox()
    win._tutor_lang_box.setFont(font(8, True))
    win._tutor_lang_box.setToolTip(t('O‘rganiladigan tilni tanlang'))
    win._tutor_lang_box.setProperty('brave_literal_text', True)
    for item in LANGUAGES:
        win._tutor_lang_box.addItem(t(item.title), item.code)
    win._tutor_lang_box.setStyleSheet(combo_style)

    win._tutor_level_box = QComboBox()
    win._tutor_level_box.setFont(font(8, True))
    win._tutor_level_box.setToolTip(t('Til darajasi (CEFR A1–C2)'))
    win._tutor_level_box.setProperty('brave_literal_text', True)
    for code, _, _ in LEVELS:
        win._tutor_level_box.addItem(code, code)
    win._tutor_level_box.setFixedWidth(52)
    win._tutor_level_box.setStyleSheet(combo_style)

    win._tutor_role_box = QComboBox()
    win._tutor_role_box.setFont(font(8))
    win._tutor_role_box.setToolTip(t('AI Ustoz Rolini tanlang (Qattiqqo‘l, Mehribon, Professor va h.k.)'))
    win._tutor_role_box.setProperty('brave_literal_text', True)
    for role in TEACHER_ROLES:
        win._tutor_role_box.addItem(t(role.badge), role.key)
    win._tutor_role_box.setStyleSheet(combo_style)

    win._tutor_quiz_btn = QPushButton("🎯 Sinov")
    win._tutor_quiz_btn.setProperty('brave_literal_text', True)
    win._tutor_quiz_btn.setFixedHeight(25)
    win._tutor_quiz_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    win._tutor_quiz_btn.setToolTip("Markaziy ekranda 5 savollik CEFR sinov testini boshlash")
    win._tutor_quiz_btn.clicked.connect(tutor.launch_skill_quiz)

    win._tutor_vocab_btn = QPushButton("📚 Lug‘at")
    win._tutor_vocab_btn.setProperty('brave_literal_text', True)
    win._tutor_vocab_btn.setFixedHeight(25)
    win._tutor_vocab_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    win._tutor_vocab_btn.setToolTip("Shaxsiy Professor Lug‘ati, Kollokatsiyalar va 7-Bo‘lim Statistikasi")
    win._tutor_vocab_btn.clicked.connect(tutor.open_academy_hub)

    win._tutor_flashcard_btn = QPushButton("🗂")
    win._tutor_flashcard_btn.setProperty('brave_literal_text', True)
    win._tutor_flashcard_btn.setFixedHeight(25)
    win._tutor_flashcard_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    win._tutor_flashcard_btn.setToolTip("3D Flashcard interval takrorlash mashg‘ulotini boshlash")
    win._tutor_flashcard_btn.clicked.connect(tutor.open_flashcards)

    win._tutor_setup_btn = QPushButton(t('Ustoz'))
    set_icon(win._tutor_setup_btn, 'spark', 'PRI')
    win._tutor_setup_btn.setFixedHeight(25)
    win._tutor_setup_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    win._tutor_setup_btn.setToolTip(t('Til, Ustoz roli va Professor kriteriyalarini sozlash'))
    win._tutor_setup_btn.clicked.connect(tutor.open_dialog)

    def _on_quick_change():
        if tutor._syncing_bar:
            return
        lang_code = win._tutor_lang_box.currentData() or 'en'
        if lang_code == 'custom' and not tutor.state.get('custom_language'):
            tutor.open_dialog()
            return
        tutor.apply_state({
            'target_language': lang_code,
            'level': win._tutor_level_box.currentData() or 'B1',
            'teacher_role': win._tutor_role_box.currentData() or 'universal_professor',
        })

    win._tutor_lang_box.currentIndexChanged.connect(_on_quick_change)
    win._tutor_level_box.currentIndexChanged.connect(_on_quick_change)
    win._tutor_role_box.currentIndexChanged.connect(_on_quick_change)

    bar_layout.addWidget(win._tutor_lang_box, 2)
    bar_layout.addWidget(win._tutor_level_box, 0)
    bar_layout.addWidget(win._tutor_role_box, 2)
    bar_layout.addWidget(win._tutor_quiz_btn, 0)
    bar_layout.addWidget(win._tutor_vocab_btn, 0)
    bar_layout.addWidget(win._tutor_flashcard_btn, 0)
    bar_layout.addWidget(win._tutor_setup_btn, 0)
    layout.addWidget(bar)

    # Second compact row: Criteria badge + 1-click Professor Tools (X-Ray, Formula, Drill)
    sub_row = QHBoxLayout()
    sub_row.setContentsMargins(0, 0, 0, 0)
    sub_row.setSpacing(4)

    win._tutor_criteria_lbl = QLabel()
    win._tutor_criteria_lbl.setProperty('brave_literal_text', True)
    win._tutor_criteria_lbl.setFont(font(8, True))
    win._tutor_criteria_lbl.setFixedHeight(22)
    sub_row.addWidget(win._tutor_criteria_lbl, 1)

    win._tutor_voice_btn = QPushButton("🎙️ Sheva")
    win._tutor_voice_btn.setProperty('brave_literal_text', True)
    win._tutor_voice_btn.setFixedHeight(22)
    win._tutor_voice_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    win._tutor_voice_btn.setToolTip("Ovoz jinsi (ayol/erkak), O‘zbek shevalari, hissiy ohang (nejniy, muhabbat bilan, qo‘pol) va tezlik")
    win._tutor_voice_btn.clicked.connect(lambda: tutor.open_voice_dialect_studio())
    sub_row.addWidget(win._tutor_voice_btn, 0)

    for attr, text, tip, key in [
        ('_tutor_xray_btn', '⚡ Rentgen', 'Yozgan jumlangizni Xatolar Rentgeni (❌ -> ✅ -> 🌟) usulida tekshirish', 'xray'),
        ('_tutor_formula_btn', '📐 Formula', 'Mavzuni 5-qadamli Professor Oltin Formulasi bilan tushuntirish', 'formula'),
        ('_tutor_drill_btn', '🎓 Mashq', 'Hozirgi bo‘lim va daraja bo‘yicha intensiv professor mashqini boshlash', 'drill'),
    ]:
        btn = QPushButton(text)
        btn.setProperty('brave_literal_text', True)
        btn.setFixedHeight(22)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip(tip)
        btn.clicked.connect(lambda _=False, k=key: tutor.trigger_professor_action(k))
        setattr(win, attr, btn)
        sub_row.addWidget(btn, 0)

    win._tutor_lock_btn = QPushButton("🛡️ Cheklov: YouTube")
    win._tutor_lock_btn.setProperty('brave_literal_text', True)
    win._tutor_lock_btn.setFixedHeight(22)
    win._tutor_lock_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    win._tutor_lock_btn.setToolTip("Ta'limiy Cheklov Rejimi: Faqat YouTube va ta'limiy manbalarga (Cambridge, Oxford, BBC, TED) ruxsat berilgan. Tizim va erkin kod cheklangan.")
    win._tutor_lock_btn.setStyleSheet(
        f"QPushButton {{background:{c.PRI_GHO};color:{c.PRI};border:1px solid {c.BORDER};"
        f"border-radius:7px;padding:1px 6px;font-size:10px;font-weight:600;}}"
        f"QPushButton:hover {{border-color:{c.PRI};}}"
    )
    win._tutor_lock_btn.clicked.connect(lambda: getattr(win, '_capabilities', None) and win._capabilities.open())
    sub_row.addWidget(win._tutor_lock_btn, 0)

    layout.addLayout(sub_row)
    tutor.refresh_chat_bar()
