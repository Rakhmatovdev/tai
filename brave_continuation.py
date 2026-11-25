"""Only an explicit click resumes a length-limited local answer."""
from brave_i18n import translate as t


def refresh(win):
    if not hasattr(win,'_features'):return
    from brave_chat import MessageCard
    cards=[row.findChild(MessageCard) for row in win._log._rows]
    for card in cards:
        if card and hasattr(card,'continue_button'):card.continue_button.hide()
    context=win._features.store.continuation(win._features.chat_id)
    if not context or win._active_provider!='ollama':return
    if win._features.page_offset+sum(bool(card and card.role in ('ai','you')) for card in cards)<win._features.store.count(win._features.chat_id):return
    for card in reversed(cards):
        if card and card.role=='ai' and card.answer_text==context['answer']:
            card.reply_seq=context['seq'];card.continue_button.show()
            card.continue_button.setEnabled(win._features.started is None and not getattr(win,'_send_pending',False))
            break


def continue_answer(win,seq=None):
    try:
        from brave_navigation import action_enabled
        if win._active_provider!='ollama':raise ValueError('Davom ettirish uchun Ollama rejimini tanlang.')
        runtime=getattr(win,'_local_chat',None)
        if not runtime or not action_enabled(win,'new-chat') or (win.can_send_text and not win.can_send_text()) or getattr(win,'_meeting_recording',False):
            raise ValueError('Avval joriy javob tugashini kuting.')
        context=win._features.store.continuation(win._features.chat_id)
        if not context or (seq is not None and seq!=context['seq']):raise ValueError('Davom ettiriladigan javob yo‘q.')
        from core.continuation import validate
        validate(context)
        win._continuation_submission=True
        try:
            win._log.append_log('You: Davom ettir')
            runtime.submit('Davom ettir',[],continuation=context)
        finally:win._continuation_submission=False
        return True
    except ValueError as error:win._log.append_log('ERR: '+t(str(error)));return False
