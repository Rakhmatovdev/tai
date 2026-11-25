# Brave local AI: next implementation batch

Implemented from the 2026-10-16 research. Themes remain exclusively in Settings.

| Entry point | Feature |
|---|---|
| Center → Knowledge library | Persistent local index, semantic/keyword search, remove/reindex, attach selected files |
| Settings → AI model → Local AI options | Repeated model comparison, OCR settings, app backup and restore |
| Settings → AI model | Enable read-only local tools, then use the existing Save button |
| Chat → … → Local analysis | Image understanding, schema-validated field extraction, JSON/CSV export, arithmetic |
| Chat → … → Conversation versions and facts | Branch from any user message, compare related chats, source-backed confirmed notes |
| Chat → … → Offline voice | Model size, partial transcription, optional silence stop, audio quality test |
| Main transcript/history | Message pages; conversation search and jump in the inspector |

## Knowledge and evidence

The library stores an explicit selection of files in local SQLite outside the checkout. It does not scan the computer automatically. File hashes, index version and known embedding-model digests prevent reuse of stale data. Changing a known model digest requires reindexing. A cancelled file keeps its previous index; previously completed files remain usable.

The initial embedding model field is `embeddinggemma`. It must already be installed in Ollama; prepare it using the existing download dialog. Leave the field empty for keyword-only indexing. Inference never starts a download. EmbeddingGemma was prepared on this development machine during the explicit implementation request.

Search covers selected documents, or the first ten listed documents if none are selected. **Attach to chat** reuses existing attachment chips. Changed files are read from current content and should be reindexed to restore semantic retrieval. Existing file count, size and parsing bounds still apply.

Ranking combines keyword and semantic ranks. Zero keyword evidence no longer returns arbitrary leading paragraphs. Semantic similarity ranks candidates; it is not a calibrated probability or proof of a claim. Source previews show the supplied excerpts. The model is instructed to acknowledge absent evidence. Synthetic cross-language retrieval passed with an Uzbek question about English text; a broad Uzbek retrieval benchmark remains future evaluation work.

Chat, embeddings and speech recognition share a cancellable inference gate. Indexing releases it between embedding batches. Embedding transport is loopback-only with no proxy or redirect following, a 120-second deadline, a 4 MiB response bound and cancellation polling. A real cold-load timeout exposed the need for this longer cancellable path.

## OCR and image understanding

Digital PDFs use text extraction. Empty PDF pages and supported images can use local Tesseract OCR, with PDFium rasterization. Input pixels and subprocess time are bounded; cancellation stops OCR. Attachment preparation has a 120-second deadline. Large scans can exceed it; preindexing helps repeated use.

Portable Tesseract was prepared under `LocalAppData/Brave/ocr/tesseract`, with English, Russian, Uzbek Latin, Uzbek Cyrillic and orientation data. The system installer was not run and registry settings were not changed. Settings can select another existing executable and language list. The package build includes the prepared runtime when available; other developers must prepare it or supply Tesseract separately.

**Local analysis → Explain an image** sends one selected image to a capable local Ollama model. Capability and pixel checks run before generation. Ordinary image attachments use OCR; visual interpretation is an explicit analysis action. Text-only models receive a compatibility error.

Real synthetic image OCR and scanned-PDF OCR passed. `gemma4:12b` read the number 42 from an image. That cold request took about 97 seconds on this machine, so this demonstrates functionality rather than fast vision.

## Local tools and structured extraction

The optional tool loop exposes bounded arithmetic and searching only the supplied document excerpts. It does not expose Python eval, shell, arbitrary file paths or a browser. Source search checks file permission; Ask mode requests approval inside the app. Unknown tools, invalid arguments and more than three rounds are rejected. Only the final answer is persisted.

Extraction accepts 1–8 field names, supplies a JSON schema to Ollama and separately validates exact keys and string/null values before export. Only bounded leading excerpts are used. Schema validity is not factual verification; check the original document. CSV export protects formula-like values. Real `llama3.2` schema extraction and a calculator tool round passed using synthetic inputs.

## Versions, notes and long conversations

The inspector pages through a conversation and branches from any selected user message. The original remains intact. Attachment paths and independent source previews survive branching. Related chats can be compared using their recent messages. Completed local branches record their model/profile.

Confirmed facts, decisions, requirements and open questions have a source-message index. These are user-written/confirmed notes rather than automatically asserted facts. Replace a note by deleting and re-adding it. Branches copy notes only from their retained prefix. Parent deletion preserves the child. Notes enter the local prompt within a conservative budget and are not automatically sent to Gemini.

Summary coverage now tracks an offset inside a long source message. A clipped segment is no longer marked as a fully summarized exchange. Summaries remain fallible/editable, and at most three batches run per turn. Context budgets are conservative character budgets, not exact tokenizer counts.

Rendering uses bounded pages, older/newer navigation and search in the inspector. A synthetic 10,000-message history was checked. LocalChat still retains complete exchanges in RAM for its summary planner; pagination bounds rendering rather than all backend history memory.

## Voice

Choose tiny/base/small/medium, then explicitly prepare it or select an existing local directory. Selecting a size changes its directory without downloading. Optional previews decode a recent recording window about every three seconds; the stopped recording supplies the editable full transcript. These are periodic partial results rather than a stateful streaming ASR engine. Starting a recording cancels local playback.

Optional silence stop uses an energy threshold after speech detection. It is off by default and may need manual stopping in noisy rooms or long pauses. **Test speech quality** accepts a WAV up to 30 seconds and a reference transcript, then reports word error rate for that sample. This does not establish overall Uzbek accuracy. Windows TTS still uses installed system voices; an Uzbek TTS voice is not bundled.

## Measured model comparison

Choose up to four installed models and a prompt. Each model runs three times, optionally as cold/warm pairs. Cold testing explicitly unloads the selected model and can affect other clients using that shared Ollama server. Benchmark requests retain the model for five minutes so warm samples can reuse it, including when the normal chat profile would unload immediately.

The table records observed residency, first-response and total time, tokens/second and system RAM/VRAM in use at sample completion. Memory is a system snapshot, not model-only or peak memory. Medians and ranges are grouped by observed state; missing information stays unknown. Answer samples support manual quality comparison. Durable records exclude prompt/answer text; explicit JSON export includes answer samples. Auto profile's existing RAM/VRAM heuristics remain conservative.

An actual `llama3.2` comparison completed three cold/warm pairs: observed cold TTFT was 2.89–3.95 seconds and warm TTFT 0.13–0.16 seconds on this machine with one synthetic Uzbek prompt. These are local sample results, not a general speedup guarantee or overall quality score.

## App snapshots

Backups use SQLite's backup API and a checksummed versioned ZIP. They contain chat/memory/source state, knowledge index, selected small registries and allowlisted local preferences. API keys, executable paths, model weights and binary file-undo archives are excluded. Existing file undo remains separate.

Restore validates names, hashes, size, JSON shape and SQLite integrity, then stages the archive for startup before settings are read or chat storage opens. It retains a `before-restore-*.zip` copy. Keep other Brave instances closed during restoration. Credentials remain in place. No automatic backup schedule or cloud sync was added.

## Windows package

`packaging/Brave.spec` builds a PyQt6 folder containing `Brave.exe`. `packaging/requirements-windows.lock` records exact dependency versions from this environment. Run `powershell -ExecutionPolicy Bypass -File packaging/build.ps1` after preparing the environment and installing PyInstaller.

Keep `dist/Install-Brave.vbs`, `Install-Brave.ps1` and the `Brave` folder together. The VBS launcher runs installation without a console. The installer creates a versioned copy under `LocalAppData/Programs/BraveAssistant` and a Start menu shortcut. New versions preserve the previous copy. `Install-Brave.ps1 -Rollback` restores the previous shortcut target. Updates are explicit packages; there is no silent release download.

Frozen configuration lives in `LocalAppData/Brave/config` across versions. Project API configuration, user databases and Ollama weights are excluded. Frozen builds skip pip auto-installation. The build excludes an incompatible Conda/Poppler ICU discovered on PATH so Qt uses the Windows ICU API.

The executable was tested on this development Windows machine with isolated configuration, not on a clean VM or every hardware configuration. Installer update/rollback tests use a temporary folder and leave the user's Start menu untouched. Ollama remains a separate prerequisite.

## Evidence

- `tests/test_next_local.py`: retrieval/cache/model changes, cancellable worker transport, gates, arithmetic/tools, schema/vision checks, summary offsets, facts/branches/pages, snapshots and installer update/rollback.
- `design-preview/appearance/local-real-smoke.json`: actual synthetic OCR, scanned PDF, embeddings, structured output, calculator tool and vision checks.
- `design-preview/appearance/package-smoke.json`: executable opening the main window and new dialogs.
- `design-preview/appearance/real-model-comparison.json`: repeated local model comparison when generated by the integration check.
- New dialog previews cover three themes and three languages.
