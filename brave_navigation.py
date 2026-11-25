"""Shared, local navigation metadata. Searching never invokes an action."""
from dataclasses import dataclass
import unicodedata

from brave_i18n import translate as t


@dataclass(frozen=True)
class Entry:
    key: str
    title: str
    detail: str
    section: str
    glyph: str = 'sliders'
    keywords: str = ''
    shortcut: str = ''


SECTIONS = (
    ('appearance', 'Ko‘rinish', 'palette'),
    ('profile', 'Shaxsiylashtirish', 'spark'),
    ('ai', 'AI modeli', 'spark'),
    ('audio', 'Audio qurilmalar', 'mic'),
    ('plugins', 'Plaginlar', 'settings'),
    ('system', 'Tizim', 'sliders'),
)

SETTINGS = (
    Entry('ai', 'AI modeli', 'Gemini yoki Ollama va lokal model resurslarini sozlang.', 'ai', 'spark', 'ollama offline local model gemini optimization performance cpu gpu ram lokal oflayn optimizatsiya модель офлайн'),
    Entry('appearance', 'Ko‘rinish', 'Standart, Och yoki Hacker mavzusini tanlang.', 'appearance', 'palette', 'theme skin dark light hacker tema mavzu rang color оформление тема'),
    Entry('language', 'Til', 'Interfeys tilini tanlang.', 'appearance', 'chat', 'language english russian uzbek uz en ru til язык'),
    Entry('profile', 'Shaxsiylashtirish', 'Yordamchi nomi, ovozi va aksent rangi.', 'profile', 'spark', 'name voice accent rang nom ism ovoz голос имя цвет'),
    Entry('audio', 'Audio qurilmalar', 'Mikrofon va javob ovozi uchun qurilmalar.', 'audio', 'mic', 'microphone speaker headset mikrofon karnay микрофон наушники звук'),
    Entry('plugins', 'Plaginlar', 'O‘rnatilgan plaginlarni boshqaring.', 'plugins', 'settings', 'plugin extension plagin kengaytma плагин расширение'),
    Entry('plugin-settings', 'Plagin sozlamalari', 'Plaginlarning ulanish va ish parametrlarini sozlang.', 'plugins', 'sliders', 'plugin configuration settings sozlama настройка'),
    Entry('autostart', 'Avtomatik ishga tushirish', 'Kompyuter yoqilganda Brave ishga tushishi.', 'system', 'sliders', 'startup boot autostart avtomatik автозапуск'),
    Entry('desktop', 'Ish stoliga yorliq', 'Brave uchun ish stoli yorlig‘ini yarating.', 'system', 'file', 'desktop shortcut yorliq ярлык'),
    Entry('remote', 'Telefon orqali boshqarish', 'Telefon ulanishi va masofaviy boshqaruv.', 'system', 'chat', 'phone remote telefon masofaviy телефон удаленный'),
    Entry('layout', 'Joylashuv', 'Oyna o‘lchami, joyi va fokus ko‘rinishini boshqaring.', 'system', 'sliders', 'layout window remember reset default focus joylashuv oyna saqlash eslab fokus расположение окно запомнить сброс'),
)

ACTIONS = (
    Entry('voice-dialect', 'Ovoz, sheva va talaffuz studiyasi', 'Ayol/erkak ovozi, o‘zbek shevalari, hissiy ohang (nejniy, muhabbat bilan, qo‘pol) va nutq tezligi', 'action', 'mic', 'voice dialect sheva ovoz ayol erkak nejniy mayin muhabbat sekin tez qopol toshkent xorazm samarqand fargona talaffuz голос диалект произношение'),
    Entry('tutor-setup', 'Til akademiyasi: Til, daraja va ustoz roli', 'AI til ustozi, CEFR daraja va ko‘nikmani sozlash', 'action', 'spark', 'tutor language professor role cefr level til ustoz daraja роль язык'),
    Entry('academy-hub', 'Til akademiyasi: Shaxsiy lug‘at va Oltin formulalar', 'Lug‘at bazasi, Anki eksport va grammatika qoliplari', 'action', 'memory', 'academy vocab dictionary anki formulas lugat akademiya словарь формулы'),
    Entry('tutor-flashcards', 'Til akademiyasi: 3D Flashcard mashg‘uloti', 'Saqlangan so‘zlarni interaktiv kartochkalarda yodlash', 'action', 'file', 'flashcard spaced repetition memory cards kartochka повторение'),
    Entry('tutor-quiz', 'Til akademiyasi: 5-savollik CEFR sinov testi', 'Faol til bo‘yicha tezkor daraja va grammatika testi', 'action', 'sliders', 'quiz test cefr ielts exam sinov test тест экзамен'),
    Entry('model-duel', 'Ikki modelni taqqoslash', 'Ikki modelni taqqoslash', 'action', 'spark', 'duel compare models taqqoslash сравнение модели'),
    Entry('chat-folders', 'Chat papkalari va teglar', 'Chat papkalari va teglar', 'action', 'file', 'folder tags pinned papka teg папки теги закрепленные'),
    Entry('continue-answer', 'Davom ettir', 'Chegarada to‘xtagan javobni davom ettirish', 'action', 'chat', 'continue length truncated davom продолжить'),
    Entry('chat-search', 'Suhbat ichida qidirish', 'Joriy suhbat ichida qidirish', 'action', 'search', 'find chat message text code qidiruv поиск сообщение код', 'Ctrl+F'),
    Entry('task-queue', 'AI vazifalar navbati', 'AI vazifalar navbati', 'action', 'sliders', 'queue tasks batch navbat очередь задачи'),
    Entry('custom-commands', 'Shaxsiy slash buyruqlar', 'Shaxsiy slash buyruqlar', 'action', 'spark', 'custom slash prompt buyruq команда шаблон'),
    Entry('slash-help', 'Slash buyruqlar', 'Barcha slash buyruqlar', 'action', 'spark', 'slash commands buyruqlar prompt snippets команды шаблоны'),
    Entry('settings', 'Sozlamalar', 'Brave sozlamalarini oching.', 'action', 'settings', 'settings preferences nastroyka настройки'),
    Entry('focus-input', 'Xabar maydoniga o‘tish', 'Suhbatda yozishni davom ettiring.', 'action', 'chat', 'input composer yozish chat', 'Ctrl+L'),
    Entry('new-chat', 'Yangi suhbat', 'Yangi suhbat boshlang.', 'action', 'plus', 'new chat conversation yangi новый'),
    Entry('history', 'Suhbatlar tarixi', 'Saqlangan suhbatlarni ko‘ring.', 'action', 'memory', 'history chat suhbat tarix история'),
    Entry('export', 'Suhbatni eksport qilish', 'Suhbatni Markdown fayliga saqlang.', 'action', 'download', 'export save markdown saqlash eksport сохранить', 'Ctrl+Shift+E'),
    Entry('chat-focus', 'Fokus rejimi', 'Chat va ish maydoni ko‘rinishini almashtiring.', 'action', 'expand', 'expand focus portrait chat portret fokus фокус', 'Ctrl+Shift+F'),
    Entry('center', 'Brave markazi', 'Xotira, loyihalar va ruxsatlarni boshqaring.', 'action', 'sliders', 'center memory security project permissions xotira loyiha ruxsat память доступ'),
    Entry('diagnostics', 'Diagnostika', 'Ulanish va qurilmalar holatini tekshiring.', 'action', 'sliders', 'diagnostics connection internet status diagnostika ulanish диагностика'),
    Entry('ai-actions', 'AI amallari', 'Matnni xulosalash, tarjima qilish va yaxshilash.', 'action', 'spark', 'ai summarize translate rewrite explain xulosa tarjima tahrir перевод резюме объяснить'),
    Entry('ai-studio', 'AI Studio', 'Model, offline amallar, uchrashuv, kod va lug‘at.', 'action', 'spark', 'models recommend route offline screen screenshot ekran meeting live speakers audio code review diff undo dictionary lugat uchrashuv kod модель экран встреча словарь'),
    Entry('mini', 'Mini oyna', 'Ixcham suhbat oynasini oching.', 'action', 'chat', 'mini window oyna окно', 'Ctrl+Alt+F8'),
    Entry('mute', 'Mikrofonni yoqish / o‘chirish', 'Mikrofon holatini almashtiring.', 'action', 'mic', 'mute unmute microphone mikrofon микрофон', 'F4'),
    Entry('fullscreen', 'To‘liq ekran', 'To‘liq ekran rejimini almashtiring.', 'action', 'expand', 'fullscreen ekran полный экран', 'F11'),
    Entry('help', 'Klaviatura yordami', 'Klaviatura yorliqlarini ko‘ring.', 'action', 'file', 'help shortcuts hotkey yordam помощь', 'F1'),
)


def normalized(text):
    text = unicodedata.normalize('NFKC', text).casefold()
    for apostrophe in ('‘', '’', 'ʻ', 'ʼ', '`', "'"):
        text = text.replace(apostrophe, '')
    return ' '.join(text.split())


def search_entries(entries, query):
    terms = normalized(query).split()
    ranked = []
    for position, entry in enumerate(entries):
        titles = [normalized(t(entry.title, lang)) for lang in ('uz', 'en', 'ru')]
        haystack = normalized(' '.join([entry.key, entry.keywords,
                                       *titles, *[t(entry.detail, lang) for lang in ('uz', 'en', 'ru')]]))
        if all(term in haystack for term in terms):
            rank = 0 if normalized(query) in titles else 1 if any(title.startswith(normalized(query)) for title in titles) else 2
            ranked.append((rank, position, entry))
    return [entry for _, _, entry in sorted(ranked)]


def action_enabled(win, key):
    if key=='continue-answer':
        return win._active_provider=='ollama' and action_enabled(win,'new-chat') and bool(win._features.store.continuation(win._features.chat_id))
    if key == 'new-chat':
        return win._features.started is None and (win.can_change_chat is None or win.can_change_chat())
    if key == 'mute':
        return not win._text_only and win._capabilities.policy['permissions']['microphone']
    if key == 'export':
        return bool(win._features.store.messages(win._features.chat_id))
    return True


def invoke(win, key):
    """Called only after deliberate activation; use the existing guarded handlers."""
    if not action_enabled(win, key):
        return
    tutor = getattr(win, '_language_tutor', None) or getattr(win, '_tutor_controller', None)
    if key == 'voice-dialect':
        from brave_voice_dialect import open_voice_dialect_studio
        return open_voice_dialect_studio(win)
    if key == 'tutor-setup' and tutor is not None:
        return tutor.open_dialog()
    if key == 'academy-hub' and tutor is not None:
        return tutor.open_academy_hub()
    if key == 'tutor-flashcards' and tutor is not None:
        return tutor.open_flashcards()
    if key == 'tutor-quiz' and tutor is not None:
        return tutor.start_professor_quiz()
    if key=='model-duel':
        from brave_model_duel import open_duel
        return open_duel(win)
    if key=='chat-folders':return win._features.history()
    if key=='continue-answer':
        from brave_continuation import continue_answer
        return continue_answer(win)
    if key=='chat-search':
        from brave_chat_search import open_search
        return open_search(win)
    if key=='task-queue':
        from brave_task_queue import open_queue
        return open_queue(win)
    if key=='custom-commands':
        from brave_custom_commands import open_commands
        return open_commands(win)
    if key == 'slash-help':
        from brave_command_library import open_library
        return open_library(win)
    if any(entry.key == key for entry in SETTINGS):
        from brave_settings import open_settings
        return open_settings(win, next(entry.section for entry in SETTINGS if entry.key == key), key)
    if key == 'settings':
        from brave_settings import open_settings
        return open_settings(win)
    if key == 'focus-input': return win._input.setFocus()
    if key == 'new-chat': return win._features.switch_chat()
    if key == 'history': return win._features.history()
    if key == 'export':
        from brave_chat_tools import export_chat
        return export_chat(win)
    if key == 'chat-focus':
        from brave_chat import toggle_chat_focus
        return toggle_chat_focus(win)
    if key == 'center': return win._capabilities.open()
    if key == 'diagnostics':
        from brave_diagnostics import open_diagnostics
        return open_diagnostics(win)
    if key == 'mini': return win._capabilities.open_mini()
    if key == 'ai-actions':
        from brave_text_actions import open_text_actions
        return open_text_actions(win, win._input.text())
    if key == 'ai-studio':
        from brave_ai_studio import open_studio
        return open_studio(win)
    if key == 'mute': return win._toggle_mute()
    if key == 'fullscreen': return win._toggle_fullscreen()
    if key == 'help':
        from brave_chat_tools import shortcut_help
        return shortcut_help(win)


def preview_chat(win, chat_id, query):
    # Selecting a search result previews history. Resuming remains a separate
    # explicit action in the existing history dialog, with its busy-task guard.
    from brave_features import HistoryDialog
    dialog = HistoryDialog(win._features)
    dialog.search.setText(query)
    dialog.timer.stop()
    dialog.refresh()
    from PyQt6.QtCore import Qt
    for index in range(dialog.list.count()):
        item = dialog.list.item(index)
        if item.data(Qt.ItemDataRole.UserRole) == chat_id:
            dialog.list.setCurrentItem(item)
            break
    dialog.exec()
