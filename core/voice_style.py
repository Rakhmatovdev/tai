"""Voice gender, Uzbek regional dialects, emotional delivery, and offline DSP prosody shaping."""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
import numpy as np

from core import workspace_store

STORAGE_FILE = 'voice-style.json'


@dataclass(frozen=True)
class VoiceGender:
    key: str
    title: str
    badge: str
    gemini_default: str
    pitch_ratio: float
    sapi_gender: str


@dataclass(frozen=True)
class UzbekDialect:
    key: str
    title: str
    badge: str
    region: str
    summary: str
    sample_phrase: str
    prompt_directive: str


@dataclass(frozen=True)
class EmotionTone:
    key: str
    title: str
    badge: str
    summary: str
    pitch_mult: float
    speed_mult: float
    warmth: float        # >0 softens highs (gentle/loving), <0 adds crisp edge (strict/rough)
    drive: float         # soft saturation / firmness
    pause_sec: float     # inter-sentence breathing pause
    gemini_female: str
    gemini_male: str
    sample_prefix: str
    prompt_directive: str


@dataclass(frozen=True)
class SpeechPace:
    key: str
    title: str
    badge: str
    speed: float
    sapi_rate: int
    prompt_directive: str


GENDERS: tuple[VoiceGender, ...] = (
    VoiceGender(
        key='female',
        title='Ayol ovozi (Mayin va tiniq)',
        badge='👩 Ayol',
        gemini_default='Aoede',
        pitch_ratio=1.00,
        sapi_gender='Female',
    ),
    VoiceGender(
        key='male',
        title='Erkak ovozi (Salobatli bariton)',
        badge='👨 Erkak',
        gemini_default='Charon',
        pitch_ratio=0.80,
        sapi_gender='Male',
    ),
)

GENDER_MAP = {g.key: g for g in GENDERS}


DIALECTS: tuple[UzbekDialect, ...] = (
    UzbekDialect(
        key='adabiy',
        title='Adabiy o‘zbek tili (Standart)',
        badge='Adabiy',
        region='Umumo‘zbek adabiy me’yori',
        summary='Sof adabiy grammatika, aniq orfoepik talaffuz (-yapman, -moqda, siz).',
        sample_phrase='Assalomu alaykum! Bugun siz bilan yangi bilimlarni aniq va ravon usulda o‘rganamiz.',
        prompt_directive=(
            "UZBEK DIALECT: Speak in pure, polished Standard Literary Uzbek (Adabiy o'zbek tili) "
            "whenever speaking Uzbek — clear grammar (-yapman/-yapsiz), rich vocabulary, and refined pronunciation."
        ),
    ),
    UzbekDialect(
        key='toshkent',
        title='Toshkent shevasi',
        badge='Toshkentcha',
        region='Toshkent shahri va viloyati',
        summary='Jonli Toshkent ohangi: -votti / -vomman / -vosiz, «bo‘pti», «nima gapla», «aka/opa/ukam».',
        sample_phrase='Assalomu alaykum! Qalesiz, ishla bo‘vottimi? Keling, bugun darsni zo‘r qilib boshlavolamiz!',
        prompt_directive=(
            "UZBEK DIALECT: Whenever speaking Uzbek, naturally use authentic Tashkent dialect (Toshkent shevasi): "
            "present continuous endings '-votti / -vomman / -vosiz' (e.g., 'kevotti', 'qivomman', 'o'qivosiz', "
            "'etvomman'), warm Tashkent conversational expressions ('qalesiz', 'bo'pti', 'xo'p bo'ladi', "
            "'tushunvosizmi', 'aka/opa/ukam'), while keeping explanations crystal-clear and intelligent."
        ),
    ),
    UzbekDialect(
        key='fargona',
        title='Farg‘ona vodiysi shevasi',
        badge='Vodiy (Farg‘ona)',
        region='Farg‘ona · Andijon · Namangan',
        summary='Shirin, muloyim va ohangdor Vodiy nutqi: «yaxshimisizlar», «xo‘p bo‘ladi-da», samimiy lutf.',
        sample_phrase='Assalomu alaykum, yaxshimisiz, tan-joningiz sog‘mi? Keling-da, bugungi mavzuni birga o‘rganib olamiz!',
        prompt_directive=(
            "UZBEK DIALECT: Whenever speaking Uzbek, naturally use warm Fergana Valley dialect (Farg'ona/Andijon/Namangan "
            "vodiy shevasi): melodic, courteous phrasing, '-yapti / -utti' nuances, gentle emphatic particles "
            "('-da', '-ku', '-ya'), warm greetings ('yaxshimisiz, salomatmisiz', 'do'stim', 'xo'p bo'ladi-da'), "
            "and famously polite Valley hospitality."
        ),
    ),
    UzbekDialect(
        key='samarqand_buxoro',
        title='Samarqand–Buxoro shevasi',
        badge='Samarqand–Buxoro',
        region='Samarqand · Buxoro',
        summary='Qadimiy va shirali ohang: -opti / -omman / -opsiz, «nagzmi», «tinchmisiz», «jo‘ra / akajon».',
        sample_phrase='Assalomu alaykum, tinchmisiz, ishlar nagzmi? Keling, hozir bu qoidani bitta chiroyli misol bilan ko‘rib chiqoptik!',
        prompt_directive=(
            "UZBEK DIALECT: Whenever speaking Uzbek, naturally use authentic Samarkand-Bukhara dialect "
            "(Samarqand-Buxoro shevasi): characteristic verb endings '-opti / -omman / -opsiz' (e.g., 'kelopti', "
            "'qilomman', 'aytopsizu'), warm regional expressions ('tinchmisiz', 'nagzmi', 'jo'ra', 'akajon', "
            "'bemalol'), and wise, melodic cadence."
        ),
    ),
    UzbekDialect(
        key='xorazm',
        title='Xorazm (O‘g‘uz) shevasi',
        badge='Xorazmcha',
        region='Xorazm · Urganch · Xiva',
        summary='Jo‘shqin O‘g‘uz lahjasi: «gal», «bar», «nima gapla», -yabdi / -jak, «og‘a / birodar».',
        sample_phrase='Assalomu alaykum, yaxshimisizla, nima gapla? Galing, bugun shu mavzuni birgalashib zo‘r o‘rganjakmiz!',
        prompt_directive=(
            "UZBEK DIALECT: Whenever speaking Uzbek, naturally use authentic Khorezm Oghuz dialect (Xorazm shevasi): "
            "Oghuz verb & lexical forms ('gal/galing' for kel, 'bar' for bor, 'galyabdi', 'bo'lajak / o'rganjakmiz', "
            "'nima gapla', 'og'a / birodar', 'yaxshimisizla'), lively rhythm, and genuine Khorezmian warmth."
        ),
    ),
    UzbekDialect(
        key='qashqadaryo_surxon',
        title='Qashqadaryo–Surxondaryo shevasi',
        badge='Qashqadaryo–Surxon',
        region='Qarshi · Termiz · Janubiy voha',
        summary='Mardona va dangal janubiy nutq: keng unlilar, «bormisiz jo‘ra», -ayapti, xalqona iboralar.',
        sample_phrase='Assalomu alaykum, omonmisiz, bormisiz! Keling, hozir shu mavzuni mardona va lo‘nda qilib tushuntirib berayin!',
        prompt_directive=(
            "UZBEK DIALECT: Whenever speaking Uzbek, naturally use authentic Qashqadaryo-Surxondaryo southern dialect: "
            "hearty, spirited folk cadence, '-ayapti / -ayapsiz / -ayin' verb endings, warm southern greetings "
            "('omonmisiz', 'bormisiz', 'og'ayni / jo'ra'), vivid proverbs, and clear, direct explanations."
        ),
    ),
)

DIALECT_MAP = {d.key: d for d in DIALECTS}


EMOTIONS: tuple[EmotionTone, ...] = (
    EmotionTone(
        key='neutral',
        title='Tabiiy va Ravon',
        badge='Tabiiy',
        summary='Muvozanatli, tiniq va professional suhbat ohangi.',
        pitch_mult=1.00,
        speed_mult=1.00,
        warmth=0.10,
        drive=1.05,
        pause_sec=0.11,
        gemini_female='Kore',
        gemini_male='Charon',
        sample_prefix='',
        prompt_directive='DELIVERY TONE: Natural, clear, articulate, and well-paced conversational tone.',
    ),
    EmotionTone(
        key='gentle',
        title='Mayin va Nozik (Nejniy)',
        badge='🌸 Mayin (Nejniy)',
        summary='Yumshoq, sokin, quloqqa yoqimli shivirga yaqin nafis va iliq ohang.',
        pitch_mult=1.04,
        speed_mult=0.92,
        warmth=0.58,
        drive=0.92,
        pause_sec=0.17,
        gemini_female='Aoede',
        gemini_male='Charon',
        sample_prefix='Mayin va sokin ohangda: ',
        prompt_directive=(
            "DELIVERY TONE (GENTLE / NEJNIY): Speak in a remarkably soft, tender, soothing, calm, and delicate voice. "
            "Use gentle transitions, soft comforting words, and never sound rushed, harsh, or abrupt."
        ),
    ),
    EmotionTone(
        key='loving',
        title='Mehr va Muhabbat bilan',
        badge='💖 Muhabbat bilan',
        summary='Samimiy, g‘amxo‘r, qalbga yaqin iliq so‘zlar va mehrli qo‘llab-quvvatlash.',
        pitch_mult=1.03,
        speed_mult=0.94,
        warmth=0.52,
        drive=0.96,
        pause_sec=0.16,
        gemini_female='Aoede',
        gemini_male='Puck',
        sample_prefix='Mehr va samimiyat bilan: ',
        prompt_directive=(
            "DELIVERY TONE (WARM & LOVING / MUHABBAT BILAN): Speak with deep affection, heartfelt care, warmth, "
            "and sincere encouragement (using warm respectful endearments like 'azizim', 'qadrdonim', 'jonim bilan', "
            "'barakalla'). Make the listener feel deeply valued, supported, and inspired."
        ),
    ),
    EmotionTone(
        key='cheerful',
        title='Jo‘shqin va Ko‘tarinki',
        badge='⚡ Jo‘shqin',
        summary='Yuqori energiya, xushchaqchaq kayfiyat va kuchli motivatsiya.',
        pitch_mult=1.06,
        speed_mult=1.07,
        warmth=-0.08,
        drive=1.15,
        pause_sec=0.08,
        gemini_female='Kore',
        gemini_male='Puck',
        sample_prefix='Ko‘tarinki ruhda: ',
        prompt_directive=(
            "DELIVERY TONE (ENERGETIC & UPBEAT): Speak with lively enthusiasm, bright energy, smile in the voice, "
            "and infectious motivation that keeps the user excited to continue."
        ),
    ),
    EmotionTone(
        key='polite_professor',
        title='Salobatli Professor (Vazmin)',
        badge='🎓 Professor',
        summary='Bosiq, dono, akademik salobatli va ishonch uyg‘otuvchi ohang.',
        pitch_mult=0.97,
        speed_mult=0.96,
        warmth=0.25,
        drive=1.08,
        pause_sec=0.14,
        gemini_female='Kore',
        gemini_male='Charon',
        sample_prefix='',
        prompt_directive=(
            "DELIVERY TONE (DISTINGUISHED PROFESSOR): Speak with calm authority, measured academic poise, "
            "deep wisdom, and dignified warmth."
        ),
    ),
    EmotionTone(
        key='strict',
        title='Qattiqqo‘l va Jiddiy',
        badge='🔥 Qattiqqo‘l',
        summary='Intizomli, keskin, talabchan va ortiqcha mulozamatsiz aniq ohang.',
        pitch_mult=0.94,
        speed_mult=1.04,
        warmth=-0.22,
        drive=1.28,
        pause_sec=0.08,
        gemini_female='Kore',
        gemini_male='Fenrir',
        sample_prefix='',
        prompt_directive=(
            "DELIVERY TONE (STRICT & DEMANDING): Speak in a firm, disciplined, no-nonsense, authoritative tone. "
            "Skip fluff, state facts and corrections sharply, and demand high standards."
        ),
    ),
    EmotionTone(
        key='rough',
        title='Qo‘pol / Dangal (Xarakterli)',
        badge='🪨 Dangal / Qo‘pol',
        summary='Rasmiyatchiliksiz, dag‘alroq, keskin va to‘g‘ridan-to‘g‘ri real hayotiy ohang.',
        pitch_mult=0.90,
        speed_mult=1.06,
        warmth=-0.35,
        drive=1.42,
        pause_sec=0.06,
        gemini_female='Fenrir',
        gemini_male='Fenrir',
        sample_prefix='',
        prompt_directive=(
            "DELIVERY TONE (BLUNT / ROUGH / UNFILTERED ROLEPLAY): Speak in a blunt, gruff, tough, street-smart, "
            "zero-sugarcoating tone (dangal/qo'polroq xarakter) without polite padding — direct, impatient with "
            "excuses, realistic for tough real-world roleplay while remaining non-abusive and helpful in substance."
        ),
    ),
)

EMOTION_MAP = {e.key: e for e in EMOTIONS}


SPEEDS: tuple[SpeechPace, ...] = (
    SpeechPace(
        key='very_slow',
        title='Juda sekin (0.70× · Bo‘g‘inlab talaffuz)',
        badge='🐢 0.70×',
        speed=0.70,
        sapi_rate=-4,
        prompt_directive='SPEAKING PACE: Speak very slowly and distinctly, articulating every syllable clearly with pauses.',
    ),
    SpeechPace(
        key='slow',
        title='Sekin va Dona-dona (0.85×)',
        badge='0.85×',
        speed=0.85,
        sapi_rate=-2,
        prompt_directive='SPEAKING PACE: Speak at a relaxed, slow, easy-to-follow pace.',
    ),
    SpeechPace(
        key='normal',
        title='Me’yoriy (1.0× · Tabiiy)',
        badge='1.0×',
        speed=1.00,
        sapi_rate=0,
        prompt_directive='SPEAKING PACE: Speak at a natural, balanced everyday pace.',
    ),
    SpeechPace(
        key='fast',
        title='Tez (1.20× · Jonli)',
        badge='⚡ 1.20×',
        speed=1.20,
        sapi_rate=3,
        prompt_directive='SPEAKING PACE: Speak briskly and dynamically at a fast native conversational speed.',
    ),
    SpeechPace(
        key='very_fast',
        title='Juda tez (1.40× · Native Tezkor)',
        badge='🚀 1.40×',
        speed=1.40,
        sapi_rate=5,
        prompt_directive='SPEAKING PACE: Speak rapidly at high-speed fluent native tempo for advanced listening practice.',
    ),
)

SPEED_MAP = {s.key: s for s in SPEEDS}


def default_voice_style() -> dict:
    return {
        'gender': 'female',
        'dialect': 'adabiy',
        'emotion': 'neutral',
        'speed': 'normal',
        'phonetic_dialect_tts': True,
        'auto_sync_gemini_voice': True,
    }


def normalize_voice_style(raw: dict | None) -> dict:
    state = default_voice_style()
    if not isinstance(raw, dict):
        return state
    gender = str(raw.get('gender') or 'female').strip().lower()
    if gender in GENDER_MAP:
        state['gender'] = gender
    dialect = str(raw.get('dialect') or 'adabiy').strip().lower()
    if dialect in DIALECT_MAP:
        state['dialect'] = dialect
    emotion = str(raw.get('emotion') or 'neutral').strip().lower()
    if emotion in EMOTION_MAP:
        state['emotion'] = emotion
    speed = str(raw.get('speed') or 'normal').strip().lower()
    if speed in SPEED_MAP:
        state['speed'] = speed
    state['phonetic_dialect_tts'] = bool(raw.get('phonetic_dialect_tts', True))
    state['auto_sync_gemini_voice'] = bool(raw.get('auto_sync_gemini_voice', True))
    return state


def load_voice_style() -> dict:
    raw = workspace_store.read(STORAGE_FILE, {})
    return normalize_voice_style(raw)


def save_voice_style(changes: dict) -> dict:
    current = load_voice_style()
    current.update(changes or {})
    clean = normalize_voice_style(current)
    try:
        workspace_store.write(STORAGE_FILE, clean)
    except OSError:
        pass
    return clean


def recommended_gemini_voice(style: dict | None = None) -> str:
    style = normalize_voice_style(style or load_voice_style())
    emotion = EMOTION_MAP[style['emotion']]
    if style['gender'] == 'male':
        return emotion.gemini_male
    return emotion.gemini_female


def style_badge_summary(style: dict | None = None) -> str:
    style = normalize_voice_style(style or load_voice_style())
    g = GENDER_MAP[style['gender']]
    d = DIALECT_MAP[style['dialect']]
    e = EMOTION_MAP[style['emotion']]
    s = SPEED_MAP[style['speed']]
    parts = [g.badge, d.badge]
    if e.key != 'neutral':
        parts.append(e.badge)
    if s.key != 'normal':
        parts.append(s.badge)
    return ' · '.join(parts)


def preview_sentence(style: dict | None = None) -> str:
    """Return a rich Uzbek preview sentence reflecting the selected dialect and emotional tone."""
    style = normalize_voice_style(style or load_voice_style())
    dialect = DIALECT_MAP[style['dialect']]
    emotion = EMOTION_MAP[style['emotion']]
    key = (dialect.key, emotion.key)
    custom_samples = {
        ('toshkent', 'gentle'): 'Assalomu alaykum, yaxshimisiz? Keling, shoshmasdan, mayin ohangda birga o‘rganvomiz.',
        ('toshkent', 'loving'): 'Assalomu alaykum, azizim! Siz bilan dars qilish menga juda yoqvotti, jonim bilan yordam beraman!',
        ('toshkent', 'rough'): 'Qarang, bahonani yig‘ishtiramiz! Hozir nima qivotgan bo‘lsak, oxirigacha aniq bajaramiz, bo‘ptimi?',
        ('fargona', 'loving'): 'Assalomu alaykum, qadrdonim, omonmisiz? Keling-da, mehr bilan bugungi mavzuni chiroyli o‘rganib olamiz!',
        ('xorazm', 'cheerful'): 'Assalomu alaykum birodar, nima gapla! Galing, bugun g‘ayrat bilan zo‘r natija ko‘rsatjakmiz!',
        ('samarqand_buxoro', 'gentle'): 'Assalomu alaykum, tinchmisiz? Keling, bosiqlik va mayinlik bilan yangi so‘zlarni o‘rganoptik.',
        ('qashqadaryo_surxon', 'strict'): 'Diqqat qiling jo‘ra! Har bitta qoidani aniq va xatosiz aytishingiz shart, dangasalik ketmaydi!',
    }
    if key in custom_samples:
        return custom_samples[key]
    if emotion.key == 'loving':
        return f"Aziz qadrdonim, jonim bilan yordam beraman! {dialect.sample_phrase}"
    if emotion.key == 'gentle':
        return f"Xotirjam va mayin tinglang. {dialect.sample_phrase}"
    if emotion.key == 'strict':
        return f"Diqqatni jamlang va aniq takrorlang! {dialect.sample_phrase}"
    if emotion.key == 'rough':
        return f"Gapni cho‘zmaymiz, dangal ishga o‘tamiz! {dialect.sample_phrase}"
    return dialect.sample_phrase


# ── Uzbek Dialect Phonetic & Lexical Colouring for Offline TTS ───────────────
_DIALECT_RULES: dict[str, tuple[tuple[str, str], ...]] = {
    'adabiy': (),
    'toshkent': (
        (r'\bkelyapman\b', 'kevomman'),
        (r'\bkelyapsiz\b', 'kevosiz'),
        (r'\bkelyapti\b', 'kevotti'),
        (r'\bboryapman\b', 'borvomman'),
        (r'\bboryapsiz\b', 'borvosiz'),
        (r'\bboryapti\b', 'borvotti'),
        (r'\bqilyapman\b', 'qivomman'),
        (r'\bqilyapsiz\b', 'qivosiz'),
        (r'\bqilyapti\b', 'qivotti'),
        (r'\baytyapman\b', 'etvomman'),
        (r'\baytyapti\b', 'etvotti'),
        (r'yapman\b', 'vomman'),
        (r'yapsiz\b', 'vosiz'),
        (r'yapsan\b', 'vosan'),
        (r'yapti\b', 'votti'),
        (r'\bbo‘ldi\b', "bo'pti"),
        (r"\bbo'ldi\b", "bo'pti"),
    ),
    'fargona': (
        (r'yapman\b', 'yapman'),
        (r'\bkeling\b', 'keling-da'),
        (r'\byaxshimisiz\b', 'yaxshimisiz, salomatmisiz'),
    ),
    'samarqand_buxoro': (
        (r'\bkelyapti\b', 'kelopti'),
        (r'\bboryapti\b', 'boropti'),
        (r'\bqilyapti\b', 'qilopti'),
        (r'yapman\b', 'omman'),
        (r'yapsiz\b', 'opsiz'),
        (r'yapti\b', 'opti'),
        (r'\byaxshimisiz\b', 'tinchmisiz, nagzmi'),
    ),
    'xorazm': (
        (r'\bkelinglar\b', 'galingla'),
        (r'\bkeling\b', 'galing'),
        (r'\bkelyapti\b', 'galyabdi'),
        (r'\bboryapti\b', 'baryabdi'),
        (r'yapti\b', 'yabdi'),
        (r'yapman\b', 'yabman'),
        (r'yapsiz\b', 'yabsiz'),
        (r'\bnima gaplar\b', 'nima gapla'),
    ),
    'qashqadaryo_surxon': (
        (r'\bkelyapti\b', 'kelayapti'),
        (r'\bboryapti\b', 'borayapti'),
        (r'\bqilyapti\b', 'qilayapti'),
        (r'([^aeiouo‘])\byapti\b', r'\1ayapti'),
    ),
}


def apply_uzbek_dialect_text(text: str, dialect_key: str = 'adabiy') -> str:
    """Apply subtle, natural morphological dialect shifts for offline Uzbek TTS speech."""
    if not text or dialect_key not in _DIALECT_RULES or dialect_key == 'adabiy':
        return text
    out = text
    for pattern, repl in _DIALECT_RULES[dialect_key]:
        def _match_case(m: re.Match, replacement: str = repl) -> str:
            src = m.group(0)
            if src.isupper():
                return replacement.upper()
            if src[:1].isupper():
                return replacement[:1].upper() + replacement[1:]
            return replacement
        out = re.sub(pattern, _match_case, out, flags=re.IGNORECASE)
    return out


def build_voice_style_prompt(style: dict | None = None) -> str:
    """Build system instruction block for Gemini Live and Ollama so both text and speech match user's style."""
    style = normalize_voice_style(style or load_voice_style())
    gender = GENDER_MAP[style['gender']]
    dialect = DIALECT_MAP[style['dialect']]
    emotion = EMOTION_MAP[style['emotion']]
    pace = SPEED_MAP[style['speed']]
    return (
        "\n[VOICE, UZBEK DIALECT & PROSODY PROFILE]\n"
        f"- SPEAKER PERSONA GENDER: {gender.title}\n"
        f"- {dialect.prompt_directive}\n"
        f"- {emotion.prompt_directive}\n"
        f"- {pace.prompt_directive}\n"
        "- IMPORTANT: When teaching a foreign target language (English, Arabic, Russian, etc.), keep target-language "
        "examples and pronunciation 100% authentic to native speakers of that target language, while applying the "
        "Uzbek dialect above to your Uzbek explanations and conversational remarks.\n"
    )


# ── Pure-NumPy WSOLA Time-Stretching & Pitch/Timbre Prosody Engine ───────────

def is_neutral_dsp(style: dict | None) -> bool:
    """True when no pitch, speed, or timbre alteration is needed on female 1.0x audio."""
    s = normalize_voice_style(style or default_voice_style())
    return (
        s['gender'] == 'female'
        and s['emotion'] == 'neutral'
        and s['speed'] == 'normal'
    )


def _wsola_stretch(audio: np.ndarray, speed: float, sr: int) -> np.ndarray:
    """Waveform Similarity Overlap-Add (WSOLA) time-scale modification without pitch change.

    ``speed > 1.0`` makes speech faster (shorter output);
    ``speed < 1.0`` makes speech slower (longer output, preserving vocal pitch).
    """
    x = np.asarray(audio, dtype=np.float32).reshape(-1)
    n = x.size
    if n < 256 or abs(speed - 1.0) < 0.02:
        return x.copy()

    speed = float(max(0.50, min(2.00, speed)))
    win_len = max(128, int(round(sr * 0.030)))   # 30 ms Hann window
    if win_len % 2 == 1:
        win_len += 1
    if n <= win_len * 2:
        out_len = max(1, int(round(n / speed)))
        grid = np.linspace(0, n - 1, out_len, dtype=np.float32)
        return np.interp(grid, np.arange(n, dtype=np.float32), x).astype(np.float32)

    hs = win_len // 2                            # 50% synthesis overlap
    ha = float(hs) * speed                       # average analysis hop
    tol = max(16, int(round(sr * 0.007)))        # ±7 ms pitch-period alignment search
    win = np.hanning(win_len).astype(np.float32)

    out_len = max(win_len + hs, int(math.ceil(n / speed)) + win_len)
    y = np.zeros(out_len, dtype=np.float32)
    norm = np.zeros(out_len, dtype=np.float32)

    # First frame anchored at 0
    y[:win_len] += x[:win_len] * win
    norm[:win_len] += win * win
    prev_pos = 0
    out_pos = hs
    frame_idx = 1

    while out_pos + win_len <= out_len:
        nominal = int(round(frame_idx * ha))
        if nominal + win_len >= n:
            break
        # Expected natural continuation from previous chosen frame
        natural_ref_pos = prev_pos + hs
        best_pos = nominal
        if natural_ref_pos + win_len <= n:
            ref = x[natural_ref_pos:natural_ref_pos + win_len]
            ref_energy = float(np.dot(ref, ref))
            if ref_energy > 1e-6:
                lo = max(0, nominal - tol)
                hi = min(n - win_len, nominal + tol)
                if hi > lo:
                    # Coarse-to-fine step=2 for <2ms CPU cost
                    candidates = range(lo, hi + 1, 2)
                    best_corr = -1e30
                    for cand in candidates:
                        seg = x[cand:cand + win_len]
                        score = float(np.dot(ref, seg)) / (math.sqrt(float(np.dot(seg, seg)) * ref_energy) + 1e-8)
                        if score > best_corr:
                            best_corr = score
                            best_pos = cand

        y[out_pos:out_pos + win_len] += x[best_pos:best_pos + win_len] * win
        norm[out_pos:out_pos + win_len] += win * win
        prev_pos = best_pos
        out_pos += hs
        frame_idx += 1

    valid_end = min(out_len, out_pos + hs)
    y = y[:valid_end]
    norm = norm[:valid_end]
    mask = norm > 1e-4
    y[mask] /= norm[mask]
    return y.astype(np.float32)


def transform_waveform(audio: np.ndarray, sr: int, style: dict | None = None) -> np.ndarray:
    """Apply gender pitch-shift, speaking speed, and emotional timbre shaping to a float32 waveform."""
    x = np.asarray(audio, dtype=np.float32).reshape(-1)
    if x.size == 0:
        return x
    s = normalize_voice_style(style or load_voice_style())
    if is_neutral_dsp(s):
        return x

    gender = GENDER_MAP[s['gender']]
    emotion = EMOTION_MAP[s['emotion']]
    pace = SPEED_MAP[s['speed']]

    target_pitch = float(gender.pitch_ratio * emotion.pitch_mult)
    target_speed = float(pace.speed * emotion.speed_mult)

    # Resampling by 1/target_pitch shifts both pitch and speed by target_pitch.
    # Pre-stretching by (target_speed / target_pitch) yields independent pitch & speed!
    wsola_rate = target_speed / max(0.55, target_pitch)
    stretched = _wsola_stretch(x, wsola_rate, sr)

    if abs(target_pitch - 1.0) >= 0.015 and stretched.size > 4:
        resampled_len = max(1, int(round(stretched.size / target_pitch)))
        src_idx = np.linspace(0, stretched.size - 1, resampled_len, dtype=np.float32)
        y = np.interp(src_idx, np.arange(stretched.size, dtype=np.float32), stretched).astype(np.float32)
    else:
        y = stretched

    # Timbre & emotional envelope shaping
    warmth = emotion.warmth + (0.20 if gender.key == 'male' else 0.0)
    if warmth > 0.05 and y.size > 2:
        # Warm low-pass blend (softens sibilance for gentle/loving/baritone)
        alpha = min(0.72, warmth)
        lp = np.empty_like(y)
        lp[0] = y[0]
        # Fast 2-tap + 3-tap moving warmth approximation (vectorized, <0.2ms)
        lp[1:] = 0.55 * y[1:] + 0.45 * y[:-1]
        if y.size > 3:
            lp[2:] = 0.45 * lp[2:] + 0.35 * y[1:-1] + 0.20 * y[:-2]
        y = ((1.0 - alpha) * y + alpha * lp).astype(np.float32)
    elif warmth < -0.05 and y.size > 2:
        # Crisp edge / presence boost for strict & rough styles
        edge_gain = min(0.45, -warmth)
        hp = np.empty_like(y)
        hp[0] = y[0]
        hp[1:] = y[1:] - 0.85 * y[:-1]
        y = (y + edge_gain * hp).astype(np.float32)

    drive = emotion.drive
    if abs(drive - 1.0) > 0.03:
        denom = float(math.tanh(drive)) or 1.0
        y = (np.tanh(y * drive) / denom).astype(np.float32)
        if emotion.key in ('gentle', 'loving'):
            y *= 0.90  # slightly softer, intimate loudness

    return np.clip(y, -1.0, 1.0).astype(np.float32)


def pause_duration_seconds(style: dict | None = None) -> float:
    s = normalize_voice_style(style or load_voice_style())
    emotion = EMOTION_MAP[s['emotion']]
    pace = SPEED_MAP[s['speed']]
    return max(0.04, min(0.35, emotion.pause_sec / max(0.65, pace.speed)))
