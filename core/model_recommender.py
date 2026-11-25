"""Explainable recommendations among local Ollama models tailored to notebook hardware."""
from core.ollama_chat import OllamaClient
from core.ollama_resources import GIB, Resources, sample_resources, hardware_tier

KNOWN_MODELS = {
    'llama3.2:1b': {
        'display': 'Llama 3.2 (1B)', 'params': '1B', 'min_ram_gb': 2.0, 'rec_ram_gb': 4.0,
        'speed': 'ultra-fast', 'category': 'chat', 'quality': 55,
        'tag': 'tezkor',
        'desc': 'Juda yengil va tez. Har qanday noutbukda, hatto kuchsiz CPUda ham tez ishlaydi.'
    },
    'llama3.2:3b': {
        'display': 'Llama 3.2 (3B)', 'params': '3B', 'min_ram_gb': 3.5, 'rec_ram_gb': 6.0,
        'speed': 'fast', 'category': 'general', 'quality': 72,
        'tag': 'tavsiya',
        'desc': 'Oddiy va o‘rtacha noutbuklar uchun eng yaxshi tanlov. Tez va aqlli.'
    },
    'llama3.2': {
        'display': 'Llama 3.2 (3B)', 'params': '3B', 'min_ram_gb': 3.5, 'rec_ram_gb': 6.0,
        'speed': 'fast', 'category': 'general', 'quality': 72,
        'tag': 'tavsiya',
        'desc': 'Oddiy va o‘rtacha noutbuklar uchun eng yaxshi tanlov. Tez va aqlli.'
    },
    'llama3.1:8b': {
        'display': 'Llama 3.1 (8B)', 'params': '8B', 'min_ram_gb': 6.5, 'rec_ram_gb': 12.0,
        'speed': 'medium', 'category': 'general', 'quality': 85,
        'tag': 'sifatli',
        'desc': 'O‘rtacha va kuchli noutbuklar uchun oltin standart. Yuqori sifatli javoblar.'
    },
    'llama3.1': {
        'display': 'Llama 3.1 (8B)', 'params': '8B', 'min_ram_gb': 6.5, 'rec_ram_gb': 12.0,
        'speed': 'medium', 'category': 'general', 'quality': 85,
        'tag': 'sifatli',
        'desc': 'O‘rtacha va kuchli noutbuklar uchun oltin standart. Yuqori sifatli javoblar.'
    },
    'qwen2.5:0.5b': {
        'display': 'Qwen 2.5 (0.5B)', 'params': '0.5B', 'min_ram_gb': 1.0, 'rec_ram_gb': 2.0,
        'speed': 'ultra-fast', 'category': 'chat', 'quality': 45,
        'tag': 'ultra-yengil',
        'desc': 'Eng kam xotira sarflovchi model. Kuchsiz apparatlar uchun mos.'
    },
    'qwen2.5:1.5b': {
        'display': 'Qwen 2.5 (1.5B)', 'params': '1.5B', 'min_ram_gb': 2.5, 'rec_ram_gb': 4.0,
        'speed': 'ultra-fast', 'category': 'chat', 'quality': 62,
        'tag': 'tezkor',
        'desc': 'Ixcham, ko‘p tilli va tezkor model. Kam xotirali noutbuklarga mos.'
    },
    'qwen2.5:3b': {
        'display': 'Qwen 2.5 (3B)', 'params': '3B', 'min_ram_gb': 3.5, 'rec_ram_gb': 6.0,
        'speed': 'fast', 'category': 'general', 'quality': 74,
        'tag': 'tavsiya',
        'desc': 'Ajoyib mantiqiy fikrlash va ko‘p tilli qo‘llab-quvvatlash.'
    },
    'qwen2.5:7b': {
        'display': 'Qwen 2.5 (7B)', 'params': '7B', 'min_ram_gb': 6.5, 'rec_ram_gb': 12.0,
        'speed': 'medium', 'category': 'general', 'quality': 88,
        'tag': 'tavsiya',
        'desc': 'Hozirgi kundagi eng kuchli 7B model. O‘zbek tili va dasturlashda a’lo.'
    },
    'qwen2.5:14b': {
        'display': 'Qwen 2.5 (14B)', 'params': '14B', 'min_ram_gb': 12.0, 'rec_ram_gb': 24.0,
        'speed': 'slow', 'category': 'general', 'quality': 93,
        'tag': 'kuchli',
        'desc': 'Yuqori aniqlikdagi katta model. Kuchli apparat va 16GB+ RAM talab qiladi.'
    },
    'qwen2.5-coder:7b': {
        'display': 'Qwen 2.5 Coder (7B)', 'params': '7B', 'min_ram_gb': 6.5, 'rec_ram_gb': 12.0,
        'speed': 'medium', 'category': 'code', 'quality': 89,
        'tag': 'dasturlash',
        'desc': 'Dasturlash va kod yozish bo‘yicha dunyodagi eng ilg‘or 7B model.'
    },
    'gemma2:2b': {
        'display': 'Gemma 2 (2B)', 'params': '2B', 'min_ram_gb': 3.0, 'rec_ram_gb': 5.0,
        'speed': 'fast', 'category': 'chat', 'quality': 68,
        'tag': 'ixcham',
        'desc': 'Google modeli. Aniqligi yuqori va kam resurs talab qiladi.'
    },
    'gemma2:9b': {
        'display': 'Gemma 2 (9B)', 'params': '9B', 'min_ram_gb': 8.0, 'rec_ram_gb': 16.0,
        'speed': 'medium', 'category': 'general', 'quality': 86,
        'tag': 'sifatli',
        'desc': 'Google’ning eng ilg‘or 9B modeli. Bilim doirasi keng.'
    },
    'mistral:7b': {
        'display': 'Mistral (7B)', 'params': '7B', 'min_ram_gb': 6.0, 'rec_ram_gb': 12.0,
        'speed': 'medium', 'category': 'general', 'quality': 80,
        'tag': 'barqaror',
        'desc': 'Klassik va ishonchli 7B model. Tez va barqaror ishlaydi.'
    },
    'deepseek-r1:7b': {
        'display': 'DeepSeek R1 (7B)', 'params': '7B', 'min_ram_gb': 6.5, 'rec_ram_gb': 12.0,
        'speed': 'medium', 'category': 'reasoning', 'quality': 89,
        'tag': 'fikrlash',
        'desc': 'Fikrlash (reasoning) qobiliyatiga ega model. Murakkab mantiqiy tahlil uchun a’lo.'
    },
    'deepseek-r1:8b': {
        'display': 'DeepSeek R1 (8B)', 'params': '8B', 'min_ram_gb': 7.0, 'rec_ram_gb': 14.0,
        'speed': 'medium', 'category': 'reasoning', 'quality': 90,
        'tag': 'fikrlash',
        'desc': 'Chuqur mulohaza yurituvchi model. Qadamma-qadam tushuntirib beradi.'
    },
    'deepseek-r1:14b': {
        'display': 'DeepSeek R1 (14B)', 'params': '14B', 'min_ram_gb': 12.0, 'rec_ram_gb': 24.0,
        'speed': 'slow', 'category': 'reasoning', 'quality': 94,
        'tag': 'kuchli',
        'desc': 'Katta mulohazali model. Kuchli apparat va 24GB+ RAM talab qiladi.'
    },
    'codellama:7b': {
        'display': 'Code Llama (7B)', 'params': '7B', 'min_ram_gb': 6.0, 'rec_ram_gb': 12.0,
        'speed': 'medium', 'category': 'code', 'quality': 80,
        'tag': 'dasturlash',
        'desc': 'Dasturlash va kod tahlili uchun optimallashtirilgan model.'
    },
    'phi3:mini': {
        'display': 'Phi-3 Mini (3.8B)', 'params': '3.8B', 'min_ram_gb': 4.0, 'rec_ram_gb': 8.0,
        'speed': 'fast', 'category': 'reasoning', 'quality': 73,
        'tag': 'mantiq',
        'desc': 'Microsoft modeli. Matematika va mantiqiy savollar uchun juda kuchli.'
    },
    'phi3.5': {
        'display': 'Phi-3.5 Mini (3.8B)', 'params': '3.8B', 'min_ram_gb': 4.0, 'rec_ram_gb': 8.0,
        'speed': 'fast', 'category': 'reasoning', 'quality': 75,
        'tag': 'mantiq',
        'desc': 'Kengaytirilgan kontekst va yaxshilangan mulohaza yuritish.'
    },
}


def model_fit_details(name: str, size: int, resources: Resources) -> dict:
    """Detailed evaluation of how a model fits into the notebook's hardware."""
    estimated = size * 1.3 + 0.5 * GIB
    gpu_budget = resources.gpu_free or resources.gpu_total or 0
    ram_budget = resources.ram_free or 0
    total_budget = resources.ram_total or 0

    vram_fit = bool(gpu_budget and size and estimated <= gpu_budget * 0.9)
    ram_fit = bool(ram_budget and size and estimated <= ram_budget * 0.9)
    fits = vram_fit or ram_fit

    known = KNOWN_MODELS.get(name) or KNOWN_MODELS.get(name.partition(':')[0]) or {}
    display = known.get('display', name)

    if vram_fit:
        badge = "⚡ GPU Tezkor · Tavsiya etiladi"
        fit_level = 'perfect'
        reason = f"Ushbu model GPU xotirasiga ({gpu_budget/GIB:.1f} GB) to‘liq sig‘adi va offline chaqmoqdek tez ishlaydi."
    elif ram_fit:
        badge = "✅ Mos keladi"
        fit_level = 'good'
        reason = f"Ushbu model noutbukingiz RAM xotirasiga ({ram_budget/GIB:.1f} GB bo‘sh) mos keladi va ravon ishlaydi."
    elif total_budget and size and estimated <= total_budget * 0.8:
        badge = "⚠️ Og‘ir model"
        fit_level = 'tight'
        reason = "Model xotira chegarasiga yaqin. Ishlash jarayonida noutbuk biroz sekinlashishi mumkin."
    else:
        badge = "❌ Xotira yetarli emas"
        fit_level = 'exceeds'
        reason = f"Model ishlashi uchun kamida {estimated/GIB:.1f} GB xotira talab qilinadi."

    return {
        'fits': fits,
        'fit_level': fit_level,
        'badge': badge,
        'reason': reason,
        'vram_fit': vram_fit,
        'estimated_gib': round(estimated / GIB, 1),
        'display': display,
        'known': known
    }


def suggest_downloads(resources: Resources) -> list[dict]:
    """Suggest top models to download based on the notebook's hardware specs."""
    tier = hardware_tier(resources)
    suggestions = []

    if tier == 'high':
        suggestions.append({
            'name': 'qwen2.5:7b',
            'display': 'Qwen 2.5 (7B)',
            'size_str': '4.7 GB',
            'tag': '⭐ Tavsiya etiladi',
            'reason': 'Eng kuchli intellekt, mukammal o‘zbek tili va dasturlash. GPU xotirangizga to‘liq sig‘adi.'
        })
        suggestions.append({
            'name': 'llama3.1:8b',
            'display': 'Llama 3.1 (8B)',
            'size_str': '4.7 GB',
            'tag': 'Oltin standart',
            'reason': 'Meta kompaniyasining eng ommabop 8B modeli. Bilim doirasi juda keng va tezkor.'
        })
        suggestions.append({
            'name': 'deepseek-r1:8b',
            'display': 'DeepSeek R1 (8B)',
            'size_str': '4.9 GB',
            'tag': 'Mantiqiy tahlil',
            'reason': 'Chuqur fikrlash va qadamma-qadam isbotlash qobiliyatiga ega yetakchi model.'
        })
        suggestions.append({
            'name': 'llama3.2:3b',
            'display': 'Llama 3.2 (3B)',
            'size_str': '2.0 GB',
            'tag': 'Tezkor rejim',
            'reason': 'Lahzalik javob beruvchi yengil model. Resurslarni mutlaqo tejaydi.'
        })
    elif tier == 'mid':
        suggestions.append({
            'name': 'llama3.2:3b',
            'display': 'Llama 3.2 (3B)',
            'size_str': '2.0 GB',
            'tag': '⭐ Tavsiya etiladi',
            'reason': 'Noutbukingiz uchun ideal muvozanat: yuqori tezlik, kam xotira sarfi va aqlli javoblar.'
        })
        suggestions.append({
            'name': 'qwen2.5:7b',
            'display': 'Qwen 2.5 (7B)',
            'size_str': '4.7 GB',
            'tag': 'Sifatli',
            'reason': 'O‘zbek tili va chuqurroq tahlil uchun ajoyib tanlov.'
        })
        suggestions.append({
            'name': 'phi3:mini',
            'display': 'Phi-3 Mini (3.8B)',
            'size_str': '2.2 GB',
            'tag': 'Mantiqiy',
            'reason': 'Microsoft modeli: matematika va mantiqiy savollar uchun juda qulay.'
        })
    else:
        suggestions.append({
            'name': 'llama3.2:1b',
            'display': 'Llama 3.2 (1B)',
            'size_str': '1.3 GB',
            'tag': '⭐ Tavsiya etiladi',
            'reason': 'Har qanday noutbukda, hatto kuchsiz CPUda ham chaqqon ishlaydi.'
        })
        suggestions.append({
            'name': 'llama3.2:3b',
            'display': 'Llama 3.2 (3B)',
            'size_str': '2.0 GB',
            'tag': 'Muvozanatli',
            'reason': 'Kichik hajmda maksimal sifat. Ta’lim va suhbat uchun a’lo.'
        })
        suggestions.append({
            'name': 'qwen2.5:1.5b',
            'display': 'Qwen 2.5 (1.5B)',
            'size_str': '1.0 GB',
            'tag': 'Tezkor',
            'reason': 'Ko‘p tilli va ultra-yengil model. Xotirani deyarli band qilmaydi.'
        })

    return suggestions


def rank(catalog, descriptions, task, resources):
    """Rank installed models by hardware fit, task suitability, and capabilities."""
    if task not in ('text', 'code', 'vision'):
        raise ValueError('Vazifa turi noto‘g‘ri.')
    rows = []
    for item in catalog:
        info = descriptions.get(item['name'])
        if not info:
            continue
        caps = info.get('capabilities') or []
        if 'completion' not in caps:
            continue
        if task == 'vision' and 'vision' not in caps:
            continue

        size = item.get('size', 0)
        estimated = size * 1.3 + 0.5 * GIB
        budget = max(resources.gpu_total or 0, resources.ram_free or 0)
        fits = bool(budget and size and estimated < budget * 0.9)
        code = any(word in item['name'].casefold() for word in ('coder', 'code', 'starcoder'))

        fit_eval = model_fit_details(item['name'], size, resources)

        # Baseline score strictly preserves test-expected priorities
        score = (100 if fits else 0) + (40 if task == 'code' and code else 0) - size / GIB

        rows.append(dict(
            item,
            capabilities=caps,
            fits_estimate=fits,
            thinking_values=info.get('thinking_values', []),
            estimated_gib=round(estimated / GIB, 1),
            code_name=code,
            score=score,
            fit_level=fit_eval['fit_level'],
            badge=fit_eval['badge'],
            fit_reason=fit_eval['reason'],
            vram_fit=fit_eval['vram_fit'],
            display_name=fit_eval['display']
        ))
    return sorted(rows, key=lambda row: (-row['score'], row['name']))


def best_installed_model(catalog, descriptions, resources, task='text'):
    """Return the single best installed model for the notebook, or None."""
    ranked = rank(catalog, descriptions, task, resources)
    return ranked[0] if ranked else None


_FIT_ORDER = {'perfect': 3, 'good': 2, 'tight': 1, 'exceeds': 0}
_NON_CHAT_HINTS = ('embed', 'bge-', 'minilm', 'rerank')


def pick_best_for_hardware(catalog, resources, descriptions=None):
    """Choose the highest-quality installed chat model that still runs smoothly.

    Unlike ``rank`` (which favours small models for snappy task routing), this
    prefers the strongest model that fits: GPU fit > RAM fit, then known quality,
    then parameter size. Models that would exceed memory are never chosen.
    Works without ``/api/show`` metadata by skipping obvious embedding models.
    """
    descriptions = descriptions or {}
    best, best_key = None, None
    for item in catalog:
        name = item.get('name') or ''
        info = descriptions.get(name)
        if info is not None:
            caps = info.get('capabilities') or []
            if caps and 'completion' not in caps:
                continue
        elif any(hint in name.casefold() for hint in _NON_CHAT_HINTS):
            continue
        size = item.get('size', 0) or 0
        if not size:
            continue
        fit = model_fit_details(name, size, resources)
        if fit['fit_level'] not in ('perfect', 'good'):
            continue
        quality = fit['known'].get('quality', 0)
        key = (_FIT_ORDER[fit['fit_level']], quality, size)
        if best_key is None or key > best_key:
            best_key = key
            best = dict(item, fit_level=fit['fit_level'], badge=fit['badge'],
                        fit_reason=fit['reason'], display_name=fit['display'])
    return best


def recommend(settings, task, cancelled, progress=lambda text: None):
    client = OllamaClient(settings)
    try:
        catalog = client.catalog()
        descriptions = {}
        # Bound metadata work; no inference, downloads or model preloading.
        for i, row in enumerate(catalog[:32]):
            if cancelled.is_set():
                return []
            progress(f'{i+1}/{min(32,len(catalog))} · ' + row['name'])
            client.settings = type(settings)(settings.url, row['name'], settings.profile, settings.autostart, settings.thinking)
            try:
                descriptions[row['name']] = client.describe()
            except (ValueError, RuntimeError):
                pass
        return rank(catalog, descriptions, task, sample_resources())
    finally:
        client.close()
