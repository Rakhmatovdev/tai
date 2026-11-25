# Brave: local conversation features

The follow-up batch adds semantic knowledge, OCR/vision, local tools, conversation versions/facts, paged rendering, voice tests, measured comparisons and a Windows package. See [the current follow-up guide](NEXT_LOCAL_FEATURES.md) for entry points, evidence and limits. The sections below describe the original local batch.

These features extend the existing Settings, attachment picker and chat overflow menu. Themes remain only in Settings. No additional header toolbar was added.

## Conversation memory

Open the chat **… → Conversation memory**. Pin requirements (up to 1000 characters), inspect/edit the fallible local summary (up to 1600 characters), disable automatic summaries or clear the memory. Memory is scoped to a conversation in the local SQLite database.

Ollama retains complete exchanges in application memory while each generation still uses a bounded recent prompt. Before older exchanges fall outside that prompt, Brave can summarize them through the selected local model. Summary requests are hidden from the visible transcript and cancellable. A turn performs at most one summary batch with profile-bounded input, at most 256 output tokens and a 30-second deadline; further old material can be processed on later turns. This adds local inference work and can increase waiting time. Pinned requirements are useful for details that must remain explicit.

Coverage is tied to a hash of the source exchanges. Incompatible coverage is discarded after a changed transcript. Clearing memory advances its coverage through the currently loaded local history so the same old summary is not immediately recreated. Original messages remain in history. Existing summaries and pinned requirements are not automatically sent to Gemini when switching providers.

## Model downloads

Open **Settings → AI model → Download** beside the model picker. Verify the tag and start **Download / resume**. Downloading requires network permission and internet. No missing model is downloaded merely because a chat request was sent.

The dialog displays current-layer bytes/progress, preparation and verification phases. Unknown totals remain indeterminate. Layer progress is not presented as a guaranteed overall percentage. Local free disk space is an estimate: a separately configured Ollama server may store models elsewhere. Server-reported disk errors are shown. Cancel aborts Brave's connection; a pull shared with another Ollama client may continue on that server. A later pull can resume according to Ollama's behavior. On success the inventory refreshes; selection must still be saved explicitly.

Only the configured loopback address is contacted, without proxies or redirects. The pull API itself fetches model files from the library. Cloud model tags are rejected. Streams have an idle timeout, bounded frame size and overall deadline.

## Edit and regenerate

Open the chat **… → Edit last message** or **Regenerate reply**. These operations create a new conversation containing the prefix before the most recent user message. The original transcript remains intact.

Editing opens an unsent draft. Regeneration waits for the active backend to be ready and submits once; it never retries an uncertain network send. Changing the chat or draft cancels that pending submission. The original selected attachment paths are restored. If a file has moved or become unreadable, the normal validation preserves the draft and reports the issue. Source previews used in the copied prefix are independently copied so deleting the parent conversation does not break those citations. Text drafts are also retained when switching conversations during the current app session.

## Offline documents and sources

Use the existing attachment picker for PDF, DOCX and supported text/code formats. Reading occurs only when sending. File permission is required and checked again before generating a reply. Images, scanned PDFs requiring OCR and other unsupported formats receive an explanation; this release does not add local vision.

Retrieval is **local lexical ranking**, not an embedding/vector database. Extracted chunks are ranked against the question, and up to four bounded excerpts are supplied to Ollama. If there is no lexical match, leading excerpts can still be supplied for an overview question; this does not mean the complete document was read. The prompt asks the model to cite excerpts and say when evidence is missing. The UI also lists the excerpts actually provided. Citations do not guarantee that the answer accurately interprets them.

Click an **S1 / S2** source link to inspect its saved excerpt and filename/page label. Model-produced paths are not opened as local files. Source IDs resolve only through Brave's own registry. Excerpts, labels and selected paths are stored with local chat history; deleting the conversation removes its records. Branches retain their own source copies.

Limits: at most 10 files, 25 MB each and 50 MB total; PDF extraction is capped at 200 pages, and extracted text at about 2 million characters per file. Expanded DOCX ZIP data is bounded. Prompt excerpts use the selected resource budget. Truncation is reported. Existing secret filename/key exclusions apply. Parsing and retrieval run outside the GUI thread; cancelled/obsolete work cannot submit a late model request.

## Switch providers without restart

Save **Gemini / Ollama** in Settings. Finish or cancel the current response/action first. Brave disables sends during transition, stops the old runtime, closes its asynchronous session/audio tasks and then starts the new runtime. Draft and visible history remain. Old backend callbacks are guarded and cannot write after deactivation. A failed cloud startup stops with an error and allows returning to Ollama, rather than launching repeatedly.

Switching to Gemini does **not** automatically seed that cloud session with the displayed local transcript or local summary. Explicit history resume remains a separate action that can send conversation context in Gemini mode. Switching back to Ollama restores complete saved exchanges locally. Updating the Gemini key rebuilds the runtime and refreshes its auxiliary key cache. Live Gemini availability and real cloud audio were not exercised in the local tests below.

## Offline voice on Windows

In Ollama mode, click the main **Speak / F4** microphone button and speak. Recording stops after a pause, another click, or 30 seconds; the cached speech model transcribes locally and sends the text to the selected local Ollama model. Esc cancels without sending. A draft typed or attachment added during recognition is preserved. **Voice + text / Text only** controls local reply playback and saves independently of Gemini's reply mode. Internet permission can remain off for the complete local conversation.

Open the chat **… → Offline voice**. Choose a local speech model folder, recognition language and installed system voice. **Download speech model** explicitly prepares multilingual faster-whisper `base` once; inference then requires local model files. The package is included in requirements, with PyAV constrained below 19 for the decoder API used by faster-whisper 1.2.x. Runtime transcription never installs packages, removes offline flags or downloads missing weights.

**Record** opens the selected microphone only for that recording, up to 30 seconds. Stop to transcribe locally with CPU INT8. Review/correct the transcript and press Send. An existing composer draft is preserved rather than overwritten. Microphone permission is honored, and cancelled transcription results cannot send a request or enter history.

Enable **Read replies with local speech** and Save for local playback after Ollama replies. Windows SAPI uses the installed voices and system output routing. Stop/Esc cancels playback. Text is sent to SAPI as plain text rather than XML/SSML, and Markdown links/code are simplified. This path does not use EdgeTTS or a cloud TTS provider.

On the checked machine, installed voices were Microsoft Irina (Russian) and Microsoft Zira (English). An Uzbek recognition language is selectable, but Uzbek recognition accuracy and Uzbek speech quality were not benchmarked. An Uzbek Windows system voice is not supplied by this implementation. Closing a voice dialog cancels recording/transcription/playback; an explicitly started model preparation may finish in the background and populate its cache.

## Verification

The automated suite covers memory isolation/coverage, cancelled summaries, local PDF/DOCX/text extraction, persisted sources, branch independence, file restoration, protocol progress/cancellation/errors, provider lifecycle/failure recovery, draft preservation and stale voice/backend results. UI previews cover all three themes and UZ/EN/RU for model download, offline voice, memory and source dialogs. Fixtures replace cloud calls and microphone recording.

Real local checks on 2026-10-16:

- `llama3.2:latest` summarized older exchanges, stored coverage through 14 messages and answered a temporary document question with project code HORIZON, budget 42 and working source IDs.
- The multilingual base speech model was downloaded to Brave's local speech cache. Windows SAPI synthesized an English WAV file, and the cached model transcribed: “The project starts on Monday. Please remember the blue folder.”
- No real microphone recording or live Gemini request was performed for these checks. This is functional verification, not an Uzbek quality or performance benchmark.

Relevant primary documentation: [Ollama pull API](https://github.com/ollama/ollama/blob/main/docs/api.md#pull-a-model), [Ollama chat](https://docs.ollama.com/api/chat), [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [sounddevice streams](https://python-sounddevice.readthedocs.io/en/latest/api/streams.html), [Windows SAPI Speak](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ms723609(v=vs.85)).
