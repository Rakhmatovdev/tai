# Brave

Model comparisons now keep the **latest 20 saved results** across restarts, with explicit reopen/delete and backup support. Chat organization drafts survive chat/filter changes and warn before discard. Completed `/queue` results export to Markdown or UTF-8 text. See [saved results and draft protection](docs/SAVED_RESULTS.md).

Type **/** in the chat composer for **66 built-in commands**, with multilingual search, categories, favorites, recent usage and examples. `/duel` compares two installed Ollama models side by side using the same prompt/profile and sequential inference. Length-limited local replies offer **Continue** or `/continue`, preserving the draft and original response model/profile. `/folders` adds folders, tags, pinning and filtered chat history. See [comparison, continuation and chat folders](docs/COMPARE_CONTINUE_FOLDERS.md).

`/commands` creates personal slash commands with prompt templates and request-specific Ollama model/profile choices. `/queue` runs explicit local AI and file-to-text tasks sequentially, with pause/cancel, saved results and interrupted-job recovery. **Ctrl+F** or `/find text` searches the whole current chat and jumps to a matching message. See [custom commands, queue and chat search](docs/PRODUCTIVITY_WORKFLOWS.md).

Other commands include `/debug`, `/fix`, `/refactor`, `/tests`, `/table`, `/extract`, `/email`, `/teach`, `/history`, `/copy` and `/settings`. `/shorten @last` transforms the last completed answer; `/snippets` saves local prompt templates; `/help` opens the searchable catalog. See the [complete command guide](docs/COMMAND_LIBRARY.md). Meeting drafts save and restore locally; speech has a pause-aware accuracy mode; screenshots support crop/redaction; code edits support multiple selected files and a reviewed test command; model routing can use repeated measured timings. See [slash commands and reliability improvements](docs/SLASH_AND_RELIABILITY.md).

**AI Studio** includes screen understanding, live microphone meeting transcripts and action items, anonymous speaker labels, code changes with diff approval/backup/undo, optional task-based model routing, and session image follow-ups. It also retains installed-model advice, offline desktop actions, audio import, code/Git review and a personal speech dictionary. Open **Chat → … → AI Studio** or **Ctrl+K → AI Studio**. See [the six new workflows and verification](docs/AI_EXTENSIONS.md) and [AI Studio guide](docs/AI_STUDIO.md).

The main chat now supports explicit **OCR / Vision** image modes. Attach an image and choose **Understand image · Vision** to ask the selected local vision model about it. Each completed answer also has **AI actions** for summarizing, translating, simplifying and improving text. Review results before copying or inserting them into the composer. See [new AI actions and image chat](docs/AI_ACTIONS_AND_VISION.md).

The latest local AI batch adds a semantic knowledge library, scanned-document OCR, local image analysis, validated JSON/CSV extraction, read-only Ollama tools, conversation versions and confirmed facts, paged history, voice quality tests, repeated model comparisons and recoverable app snapshots. Entry points, verified behavior and limits are in [Local AI guide](docs/NEXT_LOCAL_FEATURES.md). A native Windows build and per-user installer are provided through [packaging/build.ps1](packaging/build.ps1).

## Offline chat with Ollama

When internet connectivity is lost in Gemini mode, a native **Switch to offline mode?** dialog appears. **Switch offline** checks the configured local Ollama server and installed chat model, stops the cloud runtime and keeps the current conversation and draft. **Not now** leaves the provider unchanged. The dialog appears once per outage; internet recovery dismisses it without switching providers automatically. Missing local models show an error and Retry instead of downloading anything. See [offline fallback behavior and checks](docs/OFFLINE_FALLBACK.md).

The chat **…** menu now includes per-conversation local memory, editing the last user message, regeneration into a preserved-history branch, and offline voice. Settings includes an explicit model download/resume dialog. See [Local features](docs/LOCAL_FEATURES.md) for usage, limits and verification.

Open **Settings → AI model**, select **Ollama · Offline**, and choose an installed model from the automatically loaded picker. Type to search its names, or use **Refresh** beside the picker to reload the inventory. The selected model shows its disk size, parameter count and quantization when Ollama supplies them; disk size is not peak RAM usage. Refresh never changes the saved choice or generates a reply. **Check connection** verifies the selected model. Click **Save** to use that model on the next message without restarting. Switching between Gemini and Ollama is applied by Save without restarting; finish the active response or action first. The visible draft/history stays, and the local transcript is not automatically sent to Gemini. The first-run setup also has **Start offline with Ollama**; a Gemini key is not required for local mode. Gemini remains the default for existing installations, and its saved key is preserved.

**Start Ollama automatically** is enabled by default in the same Settings page. Brave reuses a responding server; otherwise it starts the installed `ollama serve` in the background for `localhost:11434` or `127.0.0.1:11434`. Startup checks run off the UI thread, share one launch lock, and wait up to about 15 seconds. A missing installation or failed startup produces an actionable message. No installer or model download runs automatically. Custom ports and IPv6-only addresses remain user-managed. Turning the checkbox off prevents future automatic launches; it does not stop an already running service.

A newly launched service is bound to `127.0.0.1:11434` with `OLLAMA_NO_CLOUD=1` in that process's environment. Existing services, global environment variables, firewall settings and startup entries are not modified. Windows launches without a console window. The service remains available after Brave closes, so other Ollama clients are not interrupted; model retention still follows the request's resource profile. The default address is `http://localhost:11434`; only loopback HTTP addresses are accepted. To download a model once, use Ollama's UI or, for example, `ollama pull llama3.2`. Downloading needs internet; an installed local model can then answer offline. Brave does not fall back to cloud inference. Cloud-tagged models and model metadata pointing to a remote host are rejected. Local HTTP requests bypass environment proxies and do not follow redirects.

This mode supports **text and explicit voice conversations** with streaming replies, local history, explicit history resume, new chats, export, and cancellation. Starting local mode does not start Gemini Live, microphone capture, tool/plugin discovery or the dashboard server. Press the main **Speak / F4** microphone button to record one turn. A pause or another press stops recording, then local speech recognition sends the transcript to Ollama. **Voice + text** enables installed Windows system speech for replies; **Text only** disables playback. Speech model, recognition language and voice selection remain in **… → Offline voice**. PDF/DOCX/text attachments use local retrieval with source previews. Unsupported attachments and oversized messages leave the composer intact. Completed replies are stored once; partial, failed and cancelled replies are not saved or reused as model context. Chat uses Qt's asynchronous network API: **Cancel / Esc** aborts the active socket without waiting for headers or another token, hides the partial answer, and immediately allows a new chat/message. Stale response signals cannot write into a new conversation. Server-side compute termination depends on Ollama noticing that disconnect. Startup does not preload a model.

The existing task panel shows **Checking resources**, **Starting Ollama** when needed, **Checking Ollama**, **Waiting for model load**, **Waiting for first reply**, and **Receiving reply**, together with the requested model name and elapsed time. The cold/warm distinction is inferred from one `/api/ps` snapshot; it is not a live load percentage. There are no invented progress percentages. Preparation has a 20-second cap. Once the chat transport starts, required model metadata has an 8-second limit; advisory `/api/version` and `/api/ps` checks each have a 250 ms limit and continue with unknown diagnostics on timeout. First stream activity has a 120-second limit, active text/thinking chunks a 45-second idle limit, and that transport a 5-minute cap. Timeouts abort the request, preserve a newer draft, and exclude incomplete answers from context. Cancel also interrupts preparation immediately in the UI and prevents generation after a late startup result. No automatic generation retry is performed.

Long conversations summarize at most one older segment before each reply, with input bounded by the active profile and output capped at 256 tokens. Remaining older text is deferred to later turns. A summary has a 30-second deadline and falls back to existing context if it fails. In Economy, the summary temporarily retains the model for one minute so it is not unloaded immediately before the visible answer; the visible answer still uses Economy's normal unload policy. Reproduction scripts, measurements and limitations are in [Local performance audit](docs/LOCAL_PERFORMANCE_2026-10-19.md).

Choose a **Resource profile** in the same settings page:

The selected model's capabilities and context limit are discovered through `/api/show` in the background. A model advertised without text completion (for example an embedding model) is rejected before inference, preserving the prompt. Unknown metadata from older servers remains usable. **Thinking mode** appears only for models advertising usable thinking controls; the picker offers Model default and the model's supported boolean or named levels. The saved preference is sent only when supported; otherwise the model default is used. Capability labels describe the model. Local text documents and Windows offline speech use their existing attachment/chat-menu entry points. Main-chat image analysis is available through the explicit Vision attachment mode; optional allowlisted desktop actions are configured in AI Studio. The effective context limit is capped by both the resource profile and the model's advertised maximum.

| Profile | Context / output token limits | Idle model retention |
| --- | --- | --- |
| Automatic | Chooses Economy or Balanced from available memory | Follows the selected budget |
| Economy | 2048 / 256 | Unload after the response |
| Balanced | 4096 / 512 | 5 minutes |
| Quality | 8192 / 1024 | 10 minutes |

**Automatic** is the default when no resource profile has been saved. An existing manual selection stays manual. Resource sampling happens in background workers at startup and before an automatic request. It uses available system RAM and optional NVIDIA NVML free VRAM; unsupported GPUs fall back to RAM. It selects Economy if available RAM is unknown, below 4 GiB, below 15% of total, or a detected GPU has less than 1 GiB / 10% available memory; otherwise it selects Balanced. Quality stays an explicit manual option. Under pressure it lowers the budget immediately; upgrading waits 60 seconds after the last observed pressure sample to avoid rapid changes. The configured value remains `auto` on disk. The Settings summary is a snapshot recommendation; actual request budgets are rechecked before sending. Manual budgets are not overridden. Optional AI Studio task routing can choose another installed model for a request without changing the saved default. These conservative heuristics do not guarantee that a particular model fits in memory or becomes faster.

Conversation context uses the newest complete exchanges, at most 20 messages and 1200 / 2800 / 6000 characters respectively, without deleting older saved history. These are conservative character budgets, not a tokenizer measurement. Thinking prefers Off when the model supports that value; unsupported preferences fall back to the model default. Thinking chunks update the existing task stage and idle timer without displaying or retaining reasoning text. A stopped stream still times out, and the overall deadline remains enforced. Ollama manages CPU/GPU placement; Brave does not force all layers into VRAM. The local portrait timer runs at 20 Hz in Economy and about 30 Hz otherwise. **Unload model** explicitly releases an idle selected model; it is blocked during a local reply. Local model, thinking and profile changes apply to the next request. Profile limits and idle unloading reduce resource budgets; actual latency depends on model, hardware and load, and is not guaranteed to improve.

In Ollama mode, **Diagnostics** checks only the local server/model and does not probe Gemini or enumerate audio devices. It displays the configured/effective resource profile and the latest request's model, server version, context, completion/cancellation/error status and pre-request model residency. Performance measurements include time from submission to the first visible answer, total elapsed time including preparation, preparation time, server-reported model loading time, input/output token counts and generation tokens/second. The generation rate excludes model loading and is not the user's complete waiting time. Missing metrics display as unknown, and zero durations are never divided by. Measurements are volatile metadata for the latest request, without prompts, answers, reasoning or keys. They do not trigger inference, automatic retries or automatic speed tuning. Replies that reach their length limit are kept with an explicit continuation notice. The Internet permission applies to remote Gemini traffic; local text inference remains usable when that permission is off. The provider, model, address, profile, thinking and service-start preference are saved in `config/api_keys.json` under `chat_provider`, `ollama_model`, `ollama_url`, `ollama_profile`, `ollama_thinking`, `ollama_autostart`. Existing `llm_provider` settings belong to the older auxiliary client and do not silently change the main conversation provider.

API behavior follows the official [Ollama chat API](https://docs.ollama.com/api/chat) and [model retention documentation](https://docs.ollama.com/faq#how-do-i-keep-a-model-loaded-in-memory-or-make-it-unload-immediately).

Brave is a native desktop AI companion with a voice-reactive 3D portrait.

## Brave desktop interface

- Switch between **English, Uzbek and Russian** under **Settings → Appearance → Language**. This changes interface copy; conversations continue in the language you speak.
- The header groups status and controls around a fixed-width **HH:MM:SS** clock with a localized date. It updates every second in Tashkent time (UTC+5); the clock and date stay visible in compact windows.
- Open **Settings → Appearance / Sozlamalar → Ko‘rinish / Настройки → Оформление** to compare three native previews: **Default** (graphite and copper), **Light** (warm white), and **Hacker** (midnight green, terminal details, a wireframe portrait and matching branding). Appearance is available only in Settings. Selection applies immediately and survives a restart; choose **Default** to return to the ordinary interface. Existing custom accent colours are retained for Default and Light; Hacker uses its own green palette.
- The gear opens one **searchable Settings window** with Appearance, Personalize, Audio devices, Plugins and System sections. Theme, language, profile and audio forms stay inside that window. Search matches Uzbek, English and Russian labels and keywords regardless of the active interface language. Profile and audio changes require **Save**; closing Settings cancels an unsaved accent preview. Plugin tools and remote control reuse their existing specialized panels. Memory is managed under **Center → Memory**. The sidebar keeps conversation navigation and diagnostics; repeated settings shortcuts and the duplicate export icon have been removed.
- **Ctrl+K** opens local quick search for settings, actions and saved conversations. Use **↑ / ↓**, **Enter**, or a click to choose; **Esc** closes it and keeps your draft. Typing never runs an action. Busy-task and microphone availability checks still apply. Selecting a conversation opens its history preview; **Continue** is still required to resume it and send that context to Gemini. Search itself does not send data to Gemini. History search supports case-insensitive Cyrillic as well as Latin text.
- **Focus mode** shows only the conversation, hiding the portrait, statistics, header and footer. Use the existing expand/collapse button in the chat title, **Ctrl+Shift+F**, or **Ctrl+K → Focus mode** to enter or leave. The draft, messages and attachments stay in place, and Ctrl+K remains available while focused.
- **Settings → System → Layout** controls **Remember layout** (enabled by default), focus mode and **Reset layout**. Window size, position, maximized state and the focus view are saved locally in `%LOCALAPPDATA%/Brave/ui-layout.json` and restored on the next launch. Saved bounds are adjusted to available monitors; F11 fullscreen remains a session control. Disabling remembrance clears the saved geometry and view while retaining the disabled preference.
- The human portrait follows voice activity, with the existing facial movement and lip-sync pipeline. Controls offer a shaded portrait or a wireframe portrait.
- Use the conversation panel for messages and files. **F4** toggles the microphone, **Esc** interrupts a response, and **F11** switches fullscreen.
- Start with `./start.ps1` from PowerShell, or `.venv/Scripts/python.exe main.py`.
- On Windows, double-click the **Brave** desktop shortcut or `launch_brave.vbs` to open the app without a terminal. The launcher uses the real GUI Python interpreter with the existing virtual environment; repeat launches focus the running instance. Startup logs remain under `logs/`.

In Gemini mode, microphone audio is sent to Google Gemini. In Ollama mode, text, speech recognition and reply playback run locally with or without internet. Microphone recording starts only after an explicit Speak / F4 press. Remote control remains disabled by default.

Interface source: `brave_ui.py`, settings: `brave_settings.py`, quick search: `brave_commands.py`, shared navigation: `brave_navigation.py`, theme previews: `brave_appearance.py`, translations: `brave_i18n.py`, application wiring: `ui.py`. Preview images are in `design-preview/`; current theme comparisons are in `design-preview/appearance/`. Navigation has a clear active indicator, starter cards separate titles from supporting text, and the composer highlights keyboard focus. Smaller windows use compact starter cards. Theme changes preserve conversations, attachments and unsent drafts.

Offline UI checks: `.venv/Scripts/python.exe -m unittest discover -s tests -v`. Tests use a temporary configuration and never start Gemini or microphone capture. Set `BRAVE_UI_PREVIEWS=design-preview/appearance` to regenerate the three themes in Uzbek, English and Russian at 1440×900 and 1040×700.

The conversation view uses readable message cards, Markdown answers, code blocks and a copy action. Starter ideas fill a draft without sending it. The multiline composer sends with **Enter**, inserts a line with **Shift+Enter**, and keeps the draft when Brave is disconnected. Attach a file with the paperclip or drop it into the conversation. The expand/collapse button in the chat header switches focus mode. System messages stay in the expandable **Activity** section. Incoming replies do not move the page while you are reading older messages.

Use **⋯ → Export conversation** in the chat toolbar, or **Ctrl+Shift+E**, to save the current conversation as a local Markdown file. It exports stored user and assistant messages; internal activity and errors are excluded. Failed text sends restore an empty composer without overwriting a newer draft. They are never retried automatically. An unavailable microphone or speaker no longer disconnects Gemini: text chat continues while audio retries. Sleeping and connecting have distinct status labels.

**History** searches saved conversations by title or message text, supports renaming/deleting, and resumes a selected chat. **New** starts a fresh conversation with the active provider. History is stored outside the project, under `%LOCALAPPDATA%/Brave/chat-history.sqlite3`; only user and assistant messages are saved. Browsing is local. In Gemini mode, resuming explicitly sends up to 20 recent messages, bounded to 24,000 characters, to Gemini as conversation context. Ollama mode uses the bounded local context described above. Older messages remain available in the local history viewer.

**Text only** disables microphone streaming and audible reply playback; replies appear in the chat. Gemini Live still generates audio with transcription internally. The mode is saved across restarts. The task panel shows thinking, executing and responding stages plus elapsed time. **Cancel** stops queued speech and prevents remaining tool calls in that response; an external action already running may still finish and cannot be undone by cancellation. Conversation switching is disabled until the current response/task has finished.

**Diagnostics** in the sidebar checks the Gemini HTTPS route, the actual Live connection, microphone/speaker stream readiness and automatic device monitoring. It does not record audio or display/send the API key. A saved key alone is reported as unconfirmed until the Live connection succeeds. **Refresh audio** safely reopens local streams; **Choose device** opens the existing audio picker.

On Windows, active endpoints, system default devices and microphone permission changes are checked every two seconds using native device metadata. A change must appear in two consecutive observations before audio is refreshed. Both streams finish and close before PortAudio is reinitialized; stale audio is discarded, the current Gemini session remains open, and chat stays available. The saved device preference is retained, with the existing fallback when a selected device is missing. Playback may pause briefly during a change. Other platforms use the available PortAudio device inventory as a best-effort monitor.

## Brave Center and Turbo

Open **Center / Markaz** in the header. Security offers **Ask permission**, **Approve for me** (default: read-only actions run automatically; risky actions require a preview and human approval), and **Full access**. Internet, microphone, screen, camera, files, code execution and computer control have individual grants. These are enforced at tool dispatch, not only displayed in the interface. Full access approves actions automatically, including actions that previously used the irreversible-action banner. Turning off a permission leaves Full/Turbo mode. Changing permissions does not grant OS administrator rights; generated code runs with the current user's privileges, without an OS sandbox. Installed plugin imports remain trusted executable code.

**Turbo** grants every permission, selects Full access, requests high media resolution and automatic thinking where supported, and raises the code/build repair budget to 20 passes. All registered tools remain available. Gemini model support, quotas, context sizes, subprocess timeouts and OS permissions still apply. Build loops check cancellation between steps. Turning Turbo off restores the prior profile and media/thinking preferences. Permission settings survive restart; action audits store tool names and decisions locally without arguments or credentials.

The **Project** tab indexes a selected folder locally. Select files and write a question to explicitly send their text to the current chat. Cache/build folders and common secret files are excluded; recognizable credentials are redacted. This is a heuristic, not a guarantee that a file has no sensitive content. File context is bounded to 24,000 characters normally and 60,000 in Turbo; this does not restrict the existing explicit file tools.

The **Reminders** tab uses Windows Task Scheduler, so a registered reminder can fire while Brave is closed. Dates are entered in Tashkent time (UTC+5) and converted to the host scheduler's local time. The panel lists and cancels registered reminders. Notification scripts use a windowless launcher. **Ctrl+Alt+F8** toggles a mini composer globally on Windows, or within Brave on other platforms; it shares the main draft and shows the latest reply.

The original implementation and license attribution are retained below.

---

### The Ultimate Cross-Platform Personal AI Assistant — By FatihMakes

> 📺 **[Watch the full setup video on YouTube](https://www.youtube.com/@FatihMakes)**

A real-time voice AI that can hear, see, speak, and control your computer — on any OS. Supports Windows, macOS, and Linux. Built on the Gemini Live API for native audio streaming, delivering zero subscriptions and total digital autonomy.

---

## ✨ Overview

Mark LIV gave the assistant a face. **Mark LV gives it a screen — and the stamina to keep working when a model goes down.**

Say "play the new Dune trailer" and the video appears **where the avatar was**, in the HUD itself, muted until you ask for sound. A YouTube link, a local file, a direct URL or just a description to search for: they all land in the same place, and BRAVE tells you it is coming *before* the picture arrives instead of going quiet for five seconds.

Underneath, every Gemini call in the app now goes through **one ladder of nine models**, ordered by measured response time rather than guesswork. When a model hits its quota, times out or disappears, the next rung takes the call and the dead one is put on a cooldown so nobody pays for it twice. Before this release, sixteen files named their own model, twenty-six times, with **no timeout at all** — one unwell alias could hang a request forever.

The release also draws a line through the bundled skill list. **Everything BRAVE ships with now drives the computer** — applications, files, the browser, the desktop, the screen. Five skills that served one hobby or one trade left the list, which is a thousand tokens the model no longer reads on every connection, and five fewer wrong tools for it to reach for.

It's not just an assistant — it's an extension of your digital life.

---

## 🚀 Capabilities

### Core Features
| Feature | Description |
|---|---|
| 🧑‍🎤 Holographic Avatar | An animated human head in the HUD — real facial geometry, lit and drawn in software, no GPU or extra packages |
| 👄 Real Lip-Sync | ~50 mouth shapes a second from the audio's formants **and** the transcript — closures, spreads and rounds, not a volume meter |
| 🌍 Language-Free Mouth | Articulation is derived by Unicode reduction, so Latin, Cyrillic and Greek scripts all work from one rule set — and scripts that hide pronunciation fall back cleanly |
| 🙂 Facial Acting | Brows track the phrase, gaze saccades between fixations, natural blinking, a small nod on stressed syllables |
| 😐 Face as Status | Looks away while thinking, meets your eyes while listening, lids fall while asleep, glances down at new content |
| 🎚️ Push-to-Talk | Hold **Ctrl+Space** and the mic opens — closed the rest of the time. Truly global on Windows, window-scoped elsewhere |
| 🔇 Self-Echo Guard | Never answers its own last sentence: the tail of its own voice is recognised and dropped without muting you |
| 🪪 Runtime Self-Knowledge | Name, OS, abilities **and limits** are generated from the live system each session — rename it or add a plugin and it knows |
| 🎙️ Wake Word | Local **"pretrained wake phrase"** detection — sleeps until called, auto-sleeps after 2 min of silence, and never streams audio while asleep |
| ⚡ Instant Acknowledgment | Speaks a short, context-aware reply in **your language** the instant a longer task starts — no more silent waiting |
| 🚀 Faster Live Engine | Runs on **Gemini 3.1 Flash Live** — roughly 2× faster time-to-first-word than the previous model |
| 🧩 Self-Describing Skills | Every bundled skill declares its own `TOOL` dict + handler and is auto-discovered at launch — adding one is a single file |
| 🧠 Recallable Memory | No size limit and nothing silently forgotten — the prompt carries what fits, the rest is looked up on demand from a local search |
| 👁️ Memory Panel | See every fact BRAVE has stored about you, when it learned it, and delete any of it in one click |
| ↩️ Undo | Take back what the assistant did — files it moved, renamed, created or wrote, and settings it changed |
| ⚠️ Real Confirmation | Shutdown, restart and WiFi wait for a button **you** press — the model cannot confirm its own irreversible actions |
| 🎧 Audio Device Picker | Choose the microphone and speakers by name, filtered to the short list your OS shows — and measured, so every entry actually works |
| 🔗 Session Continuity | A dropped connection, a voice change or a device change no longer wipes the conversation |
| 🧩 Plugin System | Drop a single `.py` file into `plugins/` — BRAVE learns a new skill on next launch |
| 📺 Video on the HUD | Plays YouTube, a local file or any video URL **where the avatar sits** — starts muted, sound on request |
| 🪜 Model Ladder | Nine Gemini models in one measured order — a quota, a timeout or an outage steps to the next rung instead of failing |
| 🎙️ Real-time Voice | Ultra-low latency conversation in any language via Gemini Live API |
| 🎨 Live Theming | Recolour the entire HUD from a hue wheel or hex — the avatar retints with it |
| 〰️ Reactive HUD | Waveform pulses to real audio — your mic while listening, BRAVE while speaking |
| 🎙️ Voice Picker | Choose from 5 native Gemini voices and switch live from the UI — no restart |
| ♾️ Unlimited Sessions | Sliding-window context compression — one conversation can last for hours |
| 🖥️ System Control | Launch apps, adjust volume/brightness, WiFi, shortcuts, power — all by voice |
| 🧩 Autonomous Tasks | High-level planning for complex multi-step goals via agent mode |
| 👁️ Visual Awareness | Screen capture and webcam vision piped into your main Gemini session, labelled by source |
| 🧠 Persistent Memory | Deeply remembers projects, preferences, and personal context across sessions |
| ⌨️ Hybrid Input | Seamlessly switch between keyboard typing and voice commands |
| 🌅 Morning Briefing | On first boot: greets you, reads the time, recaps yesterday, and fetches live news |
| 🔔 Proactive 2.0 | Time-aware, context-aware check-ins — knows the time of day, your projects, and what you've been discussing |
| 🗓️ Session Memory | Summarises each conversation and mentions it naturally next morning — consumed after use, never repeats |
| 👁️‍🗨️ Background Monitoring | User-configured topic watching — checks for new headlines once a day and alerts naturally |
| 📊 Hardware Monitoring | Continuous CPU, RAM, GPU and temperature telemetry with localized voice alerts |
| 🌤️ Weather Report | Live weather data for your city, personalized from memory |
| 🗺️ Dynamic Content Panel | Scrollable display layer beneath the HUD that renders web results, news, and search data |
| 🔍 Multi-Mode Web Search | `news` / `research` / `price` / `compare` / `search` — Gemini Grounded first, DDG fallback |
| ⏰ Smart Reminders | OS-native scheduled notifications (Windows Task Scheduler / macOS LaunchAgent / Linux systemd) |
| 📂 File Processor | Read, summarize, and answer questions about local files |
| 🌐 Browser Control | Open URLs, navigate tabs, and interact with the browser by voice |
| 📨 Send Message | Compose and send messages through WhatsApp, Telegram, and more |
| 🖱️ Desktop Control | Taskbar, window management, and desktop-level operations |
| 🧑‍💻 Silent Language Memory | Detects spoken language on first use — all future sessions adapt automatically |
| 📱 Remote Dashboard | Control the assistant from your phone via QR code pairing |
| ⚡ Auto-Start on Boot | Registers with the OS startup system (registry / LaunchAgent / .desktop) |
| 📋 Clipboard Intelligence | Copy any text → floating panel with Translate / Summarise / Explain / Fix |
| 🪪 Assistant Customization | Change the assistant name, your name, voice, and colour from the UI — takes effect immediately |

---

## 🆕 What's New in Mark LV

One new dependency for the whole release — `yt-dlp`, and only to turn a YouTube page into something Qt can play.

### The display

#### 📺 Video where the face is
The HUD already had a surface that takes the centre of the screen and gives it back: the camera. Video shares that same stack, so the avatar, the live camera and a video can never be on screen at once — and a video always lands exactly where you are already looking.

It accepts **a local file, a direct media URL, a YouTube link, or just a description** ("play the new Dune trailer") and searches for it. It **starts muted every time**, because a soundtrack talking over the assistant is the one way this feature could make BRAVE worse rather than better. You turn the sound on by asking, or from the button in the video header.

**It answers before it opens.** Resolving what to play takes seconds nothing can remove — measured at 2.0s for a link and 3.3s for a spoken phrase, plus buffering. Restricting yt-dlp to a lighter client was tried and made it worse: the fast clients came back with zero usable formats. So the seconds stay, and what changed is where you spend them — listening to BRAVE say it is coming, instead of watching nothing happen. Say "stop" during those seconds and the video is cancelled before it ever reaches the screen.

#### 🔀 Two streams, one picture
The first version asked YouTube for a format carrying both picture and sound and got *"Requested format is not available"*. That was not a bad selector; it was a wrong assumption. Checked against three videos — including the oldest upload on the site — **every one offered zero combined formats.** Picture and sound are separate streams now.

So there are two players running together, with a timer that corrects any drift over 300 ms. And the audio track is chosen on **language first, bitrate second** — because YouTube auto-dubs a great many videos and ships every dub at the *same* bitrate as the original: measured on one video, English at 129.483 and Arabic, Bangla, German, Spanish, French, Hindi and Indonesian all at 129.482. Sorting on bitrate alone came down to a thousandth of a kilobit, so the same video would play in Arabic one time and English the next for no reason you could see. It now reads YouTube's own original-track marker first.

#### 🔇 It stopped hearing the film
The microphone is open while a video plays, so the moment you turn the sound on, BRAVE starts answering the film. The mic now mutes itself when the video's sound goes on and unmutes when it goes off — and it says so in the activity log rather than going deaf silently.

#### 🎛 Two drawers instead of one
⚙ **SETUP** holds the things you set once — remote control, desktop shortcut, auto-start and customisation. 🎛 **CONTROLS** holds the switches you flick daily — fullscreen, morning brief, wake word, sleep, push-to-talk, HUD style. Only one is open at a time, and each sits under its own header button.

The panel used to stutter when it opened, and the obvious explanation — too many buttons — was wrong. Measured, the **first** wake-word state check took **2.104 seconds**, because it imported `openwakeword` on the UI thread the moment the drawer was built. That import now happens off-thread at boot, and the drawer opens instantly whether it has six buttons or sixteen.

> The drawer also used to vanish *behind* the video. `QVideoWidget` creates a native child window, and no Qt overlay can be drawn on top of one. The video is now a `QGraphicsVideoItem` inside a graphics view — same picture, and the interface stays where it belongs.

### Staying up

#### 🪜 Every Gemini model, in one ladder
Every one-shot Gemini call in the app now goes through `core/gemini.py`. Before this, **sixteen files named their own model — twenty-six times — and not one of them set a timeout.** When a single alias went unwell, the call did not fail; it hung.

The ladder is nine models deep, ordered by **measurement rather than guesswork**:

| Model | Measured | Model | Measured |
|---|---|---|---|
| `gemini-3.5-flash-lite` | 0.56s | `gemini-2.5-flash` | 0.67s |
| `gemini-3.1-flash-lite` | 0.60s | `gemini-2.5-flash-lite` | 0.74s |
| `gemini-flash-lite-latest` | 0.60s | `gemini-3.5-flash` | 1.13s |
| `gemini-3-flash-preview` | 504 after 14.7s | `gemini-3.6-flash` | 504 after 12.0s |
| `gemini-flash-latest` | 503 UNAVAILABLE | | |

The three that fail were **not deleted** — a model that is unwell today is a real rung tomorrow. They sit at the bottom, and a **cooldown** decides how long a failure is believed:

| What happened | Rested for | Why |
|---|---|---|
| Quota exhausted (429) | 5 minutes | Quotas refill |
| No answer (503 / 504 / DEADLINE_EXCEEDED) | 30 minutes | An outage outlasts a retry |
| Not found, or no access (404) | 6 hours | Your key does not have it, and won't in a minute |

That middle row is where the time was going. Only quota and 404 used to be cooled, so the 14-second wait on a dead model was paid **on every single call**. Measured after the fix: first call 13.15s, second 1.98s, third 1.16s — **11.2 seconds saved on every call from then on.**

**The Live model is deliberately not on this ladder.** Live models are not drop-in replacements for one another; they accept different config fields, and the same API key also exposes transcribe-live, live-translate and robotics-streaming models that will happily connect and then not behave like an assistant. So Live has exactly **two** rungs — the current model, and the one this project used before it — and it steps only on quota or loss of access. Never on a network blip or a bad key, which would otherwise walk the whole list into the same wall.

### The shape

#### 🧩 Everything bundled drives the computer
The bundled skill list had grown to seventeen, and some of it was nobody's business but its author's. **Not everyone updates games; everyone opens applications.**

Mark LV trims it to **twelve**, and every one of them does the same kind of thing: drive this machine. Applications, the browser, files, the desktop, the screen, the clock, the weather, the display. The rule is written into the project tree, so the next skill lands in the right folder without anyone having to ask.

This is not only tidiness. Every bundled skill is declared to the model on **every** connection, whether you ever use it or not. The declarations sent at startup dropped from **16,827 characters to 12,907** — roughly a thousand tokens off every session, and five fewer wrong tools for the model to reach for.

### 🩹 Fixes
* An unanswering model was retried on **every call**, at 12–15 seconds a time, because only quota and 404 failures were ever cooled down. 503/504 now rest for 30 minutes — **11.2 seconds saved per call**.
* One-shot Gemini calls had **no timeout anywhere**, in any of the sixteen files that made them. Every call now carries a deadline of at least 10 seconds.
* YouTube playback failed outright with *"Requested format is not available"* — it was asking for a combined stream that no longer exists.
* Videos played in a **random language**, because YouTube's auto-dubs carry the same bitrate as the original track.
* The settings drawer **stuttered on first open** — a 2.1-second `openwakeword` import on the UI thread, not the button count it looked like.
* The settings drawer opened **underneath the video**, because `QVideoWidget` creates a native window.
* BRAVE **answered the video's soundtrack.** The microphone now follows the video's sound.
* Qt's multimedia backend printed an ffmpeg banner to the console on every play, containing the **signed streaming URL with the viewer's IP address in it**. Silenced at startup.
* **Every launch paid 201 ms for a plugin nobody had asked to use.** Discovery executes every file in `plugins/`, and `youtube_video` imported `requests` and `youtube_transcript_api` at module scope. Deferring one of them would have saved nothing — the transcript library imports `requests` itself. Both are now checked with `find_spec`, which answers "is it installed?" without executing anything, and loaded on first use: **plugin discovery 211 ms → 39 ms**.
* A plugin that needed a file from a **newer Mark** was rejected with *"pip install core"*. The loader could not tell this project's own packages from a third-party one, so it told people to install a same-named stranger from an index — wrong, and a supply-chain hazard dressed up as a fix. First-party names now say the app is behind the plugin and that there is nothing to install.

> Built on the Mark LI–LIV foundation: the **🧑‍🎤 Holographic Avatar**, **👄 Lip-Sync**, **🎚️ Push-to-Talk**, **🔇 Self-Echo Guard**, **🧩 Plugin System**, **♾️ Unlimited Sessions**, **🎨 Live Theming** and **🎙️ Wake Word** are all still here.

---

## 🔄 The Foundation Update — in every Mark from LII

These four landed across **Mark LII, LIII, LIV and LV at the same time**, after each of those releases had already shipped. They are not what any one of those versions originally introduced; they are the floor all of them now stand on, so moving up a Mark never costs you something the one below it had.

No new dependencies. No bundled asset files. No hardcoded language, and nothing that assumes one operating system.

### 🧠 A memory that actually remembers

The store was capped at **2,200 characters — the whole memory, not per entry** — because all of it was pasted into the system prompt on every connect, so growing the memory grew every request. When it filled, the oldest entries were deleted and one line was printed to a console nobody reads. An assistant advertised as remembering "projects, preferences and personal context" was in practice a two-page notepad that quietly forgot your sister's name after a few weeks.

Storage and prompt budget are now separate problems:

* **Nothing is deleted.** The cap is a runaway guard normal use never approaches, and if it is ever hit it says so in the activity log instead of on stdout.
* **The prompt carries a core, not a dump.** Identity in full, then the most recently updated facts, budgeted — measured at **971 characters on a memory holding 62 stored facts.** That is *smaller* than the old whole-store cap, so sessions now connect with fewer tokens than before.
* **The rest is fetched on demand.** A `recall_memory` tool searches the full store locally — no network, no second model, well under a millisecond.

The part that is easy to get wrong: **a model cannot look something up if it doesn't know the thing exists.** So the prompt also carries an **index of the keys** it had no room for. Without it, "who is Ayşe?" gets "I don't know" while `ayse_sister` sits on disk unread. That index interleaves categories rather than sorting by recency — sorted like the core, a memory with forty preferences pushed the one entry the index existed for off the end.

⚙ → **🧠 MEMORY** shows every stored fact, when it was learned, and a ✕ to forget it. Everything stays in `memory/long_term.json` on your machine.

### ↩️ Undo — it can take back what it did

BRAVE moves files, renames them, writes to them and changes your settings. None of that had a way back; if it misheard you, the only remedy was to fix it by hand.

Say **"undo"** — in any language — and it reverses its own last action:

| | |
|---|---|
| **Files** | move · rename · create · copy · write · delete · organize desktop |
| **Settings** | volume · brightness · dark mode |

Three things it deliberately does *not* do:

* **It does not guess.** Settings undo reads the current value *before* changing it. Where a platform won't report that value, nothing is registered — an undo that restores a guess is worse than no undo.
* **It does not hoard.** Undoing a write means keeping the old contents in memory, so files over 1 MB are excluded and it says so rather than holding a 200 MB log for the session.
* **It does not delete your files to undo a copy.** The reverse of a copy is removing the copy; the reverse of "create a folder" is removing it *only while it's still empty*.

`organize_desktop` gets special treatment — one command that moves dozens of files, which made it the least reversible thing the assistant could do. It journals every move and puts all of them back in one go, cleaning up the folders it created if they're still empty.

**Undo costs nothing at runtime.** It appends a closure to a list; nothing in it runs unless you ask.

### ⚠️ A confirmation the model can't forge

The old gate read like this:

```python
if action in _DANGEROUS_ACTIONS:            # {"restart", "shutdown"}
    confirmed = str(params.get("confirmed", "")).lower()
```

`confirmed` is a **tool parameter, which means the model fills it in.** Nothing stopped it sending `confirmed=yes` on the first call and nothing checked that a human was ever involved. It was a convention, not a gate. And its coverage was two actions — so `toggle_wifi`, which cuts the assistant's own connection to the Live API and therefore *cannot be asked to undo itself*, went through with no gate at all.

The token is now issued by the interface. Shutdown, restart and WiFi put a banner on the HUD and **return immediately**; the action runs only if you press CONFIRM. Nothing blocks — BRAVE keeps talking while the banner is up — so this is **cheaper than the old gate**, which burned two tool round trips on every power command.

> The split between the two mechanisms is about reversibility, not about how alarming a word sounds. Anything undoable is done at once; only the genuinely irreversible asks. An assistant that checks with you before turning the volume down is one you stop talking to.

### 🎧 It finally asks which microphone

Both audio streams opened with no device argument at all, so they always took whatever the OS called "default" — and on Windows that *moves on its own* the moment you plug a headset in. "BRAVE can't hear me" almost always meant "BRAVE is listening to the webcam".

⚙ → **🎧 AUDIO DEVICES** lets you pick the microphone and the speakers by name. Two things matter more than the dropdown:

**The list is short.** `query_devices()` returns one entry per *device × host API*, not per device — measured on an ordinary Windows machine, **41 entries for what the sound settings show as 4 microphones and 4 speakers.** The same microphone appears four times, under MME, DirectSound, WASAPI and WDM-KS, with nothing to say which is which. That is not a choice, it's a quiz. The picker takes one host API per direction, drops the "Sound Mapper" and "Primary Sound Driver" pseudo-devices that just mean "default", and deduplicates. **41 → 8.**

**Every entry has been measured, not assumed.** The obvious approach is to pick the host API with the nicest names — WASAPI on Windows, which in shared mode **doesn't resample**, so with 16 kHz in and 24 kHz out against 48 kHz hardware every open failed. Adding a rate check and moving to DirectSound passes that test on both sides, and PortAudio's DirectSound **output is a silent sink**: the stream opens, every write returns success in ~0 ms, and not one sample reaches the speakers.

| | write(2.0 s) took | |
|---|---|---|
| MME | **2.02 s** | consumed in real time |
| DirectSound | **0.00 s** | swallowed instantly |

No capability flag reports that. So the app measures it — once per host API per direction, on a background thread at startup, using silence. Two consequences worth stating plainly:

* **Each direction picks its own host API.** On Windows this lands on DirectSound for the microphone and MME for the speakers — a split no amount of reasoning would have produced.
* **The probe runs in the mode the app actually ships.** DirectSound input passes a callback stream and fails a blocking read; probing the wrong mode rejected a microphone that works perfectly.

Your choice is stored **by name, not by index** — indices shift whenever something is plugged in. If the saved device is gone, it falls back to the system default and says so in the log rather than failing to start.

### 🔗 It stops forgetting the conversation when the connection drops

`session_resumption` was switched on in the config and the handle the server sent back was **never read** — so every reconnect started an empty session. A dropped packet, or simply changing the voice, wiped the conversation. "Unlimited sessions" leaked through exactly this hole.

The handle is captured and replayed now. A network blip, or switching your microphone, keeps the conversation intact.

It is held in memory only, deliberately: writing it to disk would make a fresh launch continue yesterday's chat, which sounds appealing but breaks the session-summary flow — a conversation that never ends never produces a summary, and the "yesterday we talked about…" line in the morning briefing silently disappears. Changing the **voice** also starts clean on purpose, since resuming restores the server's session state and would likely bring the old voice back with it.

### 🩹 Fixes that came with it

* **The assistant could die on a log line.** Status lines carry emoji and arrows (`📤 file_controller → Moved: a.txt → Documents/`). On a non-UTF-8 console — cp1254 on a Turkish Windows, cp1251 on a Russian one, cp932 on a Japanese one — printing one raises `UnicodeEncodeError`, and because that print sits *after* the tool's own `try/except`, it escaped into the receive loop and took the session down.
* **Every computer command paid for two model round trips.** `computer_settings` made an *entire second Gemini call, inside the tool*, purely to translate the request into one of its own action names — because the declaration only said "The action to perform", so the model rarely filled it in. When that second call failed, the fallback was `description.lower().replace(" ", "_")`, which turns the Turkish for "turn it down" into `sesi_kis` and straight into "Unknown action". The declaration now names all 56 actions and the rest is spelling tolerance handled locally by `difflib` in microseconds. When nothing matches it suggests real action names instead of dead-ending.
* An unresolvable saved audio device, or one the driver refuses to open, falls back to the system default and says so — on both the microphone and the speakers.
* A rejected session-resumption handle is dropped after one attempt, so an expired handle can never be replayed on every retry and prevent the reconnect it exists to protect.



---

## 🗺️ Mark Roadmap

| Mark | Focus |
|---|---|
| **XLIX** | Auto-start · clipboard intelligence · assistant customization |
| **L** | Session memory · background monitoring · proactive 2.0 · instant vision |
| **LI** | Plugin system · affective dialog · proactive audio · unlimited sessions |
| **LII** | Voice picker · live theming · reactive HUD · recallable memory · undo · real confirmation · audio device picker · session continuity |
| **LIII** | Wake word · Gemini 3.1 Flash Live · instant acknowledgment · self-describing action/plugin architecture |
| **LIV** | Holographic avatar · viseme lip-sync · facial acting · face-as-status · push-to-talk · self-echo guard · runtime self-knowledge & limits |
| **LV** | Video on the HUD · model ladder with measured fallback · split settings drawers · trimmed bundled skill list |
| *shared* | The last five above also shipped to LIII, LIV and LV at the same time — moving up a Mark never loses them |
| **LVI+** | Interrupt by voice · conversation history · Telegram remote · full file access · security camera · Obsidian |

---

## ⚡ Quick Start

```bash
git clone https://github.com/FatihMakes/Mark-LV.git
cd Mark-LV
python setup.py        # installs deps for YOUR OS + the browser automation engine
python main.py
```

`setup.py` only ever installs what your operating system needs — the Windows-only libraries are skipped automatically on macOS and Linux, and vice-versa. It also checks your Python version up front, so a wrong interpreter fails with a sentence instead of a wall of pip output. Prefer to do it by hand? `pip install -r requirements.txt` works too.

> ⚠️ **Installation Note:** If you hit a `ModuleNotFoundError` for an OS-specific package, install it with `pip install <module_name>`. The optional **wake word** engine is *not* installed here — grab it in one click from **⚙ → WAKE WORD** inside the app.

---

## 📋 Requirements

| Requirement | Details |
| --- | --- |
| **OS** | Windows 10/11, macOS, or Linux |
| **Python** | 3.11, 3.12 or 3.13 |
| **Microphone** | Required for voice interaction (and for the "pretrained wake phrase" wake word) |
| **Speakers** | Required for voice replies |
| **API Key** | Free Gemini API key (entered on first launch → `config/api_keys.json`) |
| **GPU** | **Not required.** The avatar is rendered in software, and so is HUD video |
| **YouTube on the HUD** | `yt-dlp`, installed by `setup.py`. Without it, local files and direct URLs still play and YouTube links open in the browser with an explanation |
| **Wake word** *(optional)* | One-click download from ⚙ → WAKE WORD (`openwakeword`, a few MB, fully local) |

---

## 🗂️ Project Structure

```
Mark LV/
├── main.py                   # Core loop — Gemini Live session, audio I/O, viseme extraction, tool dispatch
├── ui.py                     # PyQt6 HUD — avatar canvas, waveform, log panel, settings drawer, camera feed
├── setup.py                  # OS-aware installer (skips wrong-OS dependencies, checks your Python)
├── .gitignore                # Keeps your API key, TLS key and memories out of the repository
├── plugins/
│   └── _template.py          # Copy this to write a new skill — one file, drop in, done
├── actions/                  # Bundled skills — each self-describes via a TOOL dict + handler
│                             #   Everything here drives the COMPUTER, which is what decides
│                             #   whether a new skill belongs in this folder at all.
│   ├── web_search.py         # Gemini + DDG parallel search (news, research, price, compare)
│   ├── screen_processor.py   # Screen & webcam capture for vision
│   ├── background_monitor.py # User-configured topic watching — daily DDG check
│   ├── proactive.py          # Proactive 2.0 — time/context/rotation-aware check-ins
│   ├── reminder.py           # OS-native scheduled notifications
│   ├── system_monitor.py     # CPU / RAM / GPU / temperature telemetry
│   ├── computer_settings.py  # Volume, brightness, WiFi, power (per-OS)
│   ├── computer_control.py   # Keyboard shortcuts, mouse, window management
│   ├── open_app.py           # Application launcher (per-OS name map)
│   ├── browser_control.py    # Web browser control
│   ├── file_controller.py    # File system operations
│   ├── file_processor.py     # Document reading and summarization
│   ├── send_message.py       # Messaging integration
│   ├── weather_report.py     # Live weather data
│   ├── video_player.py       # Plays video on the HUD, where the avatar normally is
│   └── desktop.py            # Desktop and taskbar control
├── memory/
│   ├── memory_manager.py     # Load/save long_term.json — sessions, monitors, identity
│   ├── config_manager.py     # api_keys.json access — key, OS, name, voice, colour, toggles
│   └── long_term.json        # Persistent store — created on first run
├── core/
│   ├── gemini.py             # One place for every one-shot Gemini call — model ladder, timeouts, cooldowns
│   ├── prompt.txt            # All prompt wording — {tokens} are filled from the live system at startup
│   ├── avatar.py             # Avatar renderer — lighting, pose, expression, mouth (QPainter)
│   ├── avatar_mesh.py        # Head geometry — loads the face, generates skull/neck/rigs
│   ├── face_model.obj        # The face itself (MediaPipe canonical model, Apache-2.0, 25 KB)
│   ├── viseme.py             # Transcript → mouth shapes, fused with the audio's timing
│   ├── echo.py               # Tells your voice from the assistant's own echo; self-calibrating
│   ├── hotkey.py             # Push-to-talk chord — global on Windows, windowed fallback elsewhere
│   ├── undo.py               # One shared undo stack — actions register how to reverse themselves
│   ├── confirm.py            # Irreversible-action gate — the token is issued by the UI, not the model
│   ├── audio_devices.py      # Microphone / speaker list — filtered, measured, resolved by name
│   ├── plugin_loader.py      # Plugin engine — discovery, validation, crash isolation
│   ├── action_loader.py      # Bundled-action engine — the built-in twin of plugin_loader
│   └── wake_word.py          # Local "pretrained wake phrase" detector — own thread, offline, opt-in
└── config/
    ├── api_keys.json         # API key, name, voice, colour, toggles — created on first launch (git-ignored)
    └── certs/                # Self-signed TLS pair for the phone dashboard — generated locally (git-ignored)
```

---

## 🙏 Third-Party Assets

| Asset | Source | Licence |
| --- | --- | --- |
| `core/face_model.obj` | [MediaPipe](https://github.com/google-ai-edge/mediapipe) canonical face model — 468 vertices of measured human face geometry | Apache License 2.0 |

---

## 🔒 Your Data

Everything stays on your machine. There is no MARK server, no telemetry and no account.

| What | Where | Notes |
|---|---|---|
| Gemini API key, plugin credentials | `config/api_keys.json` | **Plaintext.** Anyone with your user account can read it. Treat it like a password file. |
| Dashboard TLS certificate + private key | `config/certs/` | Generated locally, self-signed, never leaves the machine. |
| What the assistant remembers about you | `memory/long_term.json` | Delete the file to make it forget everything. |

All three are listed in `.gitignore`, so a fork or a pull request cannot leak them by accident. **If you have already committed `config/api_keys.json` anywhere public, revoke that key** at [aistudio.google.com](https://aistudio.google.com/app/apikey) and generate a new one — removing the file in a later commit does not remove it from the history.

In Gemini mode, your voice is streamed to Google's Gemini Live API while a session is open; that is the one thing that leaves your computer, and it stops when you mute or close the app.

---

## ⚠️ License

Personal and non-commercial use only.
Licensed under **[Creative Commons BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)**.

---

## 👤 Connect with the Creator

Engineered by a developer building a real-world BRAVE-style assistant.
⭐ **Star the repository to support the journey to Mark 100.**

| Platform | Link |
| --- | --- |
| YouTube | [@FatihMakes](https://www.youtube.com/@FatihMakes) |
| Instagram | [@fatihmakes](https://www.instagram.com/fatihmakes) |
# Brave companion features

The Center also contains **Usage**, **Recovery**, and **Voice test**. Multiple attachments can be selected or dropped into chat; the 24,000-character text budget (60,000 in Turbo) is shared fairly across the files. Each file must be at most 25 MB and the batch at most 50 MB. Preview lets you choose which attached file to inspect. Attachments remain explicit-send only.

The Project page can save named profiles with a folder, project context, access policy, Turbo settings, and routines. **Apply profile** restores these choices and reconnects, but does not send the project automatically. Applying a profile can change permissions; review the Security page. Profiles are saved locally.

File-control writes and overwrites now save exact pre-write copies under `%LOCALAPPDATA%\Brave\file-backups`. The existing Undo tool can restore these during the session; Recovery can restore them after restarting. Restoration refuses to overwrite a file edited since Brave wrote it. Other actions or arbitrary generated code do not automatically participate in this backup system. Copies can be deleted from Recovery.

Grounded web search preserves provider source URLs and adds a retrieval timestamp; the assistant is instructed to cite returned URLs. Retrieval is not verification of the source's claims. Usage measures successful live chat/audio payloads and logical side-model requests for the current process, plus observed model cooldowns; it does not estimate billing or remaining account quota. It excludes some auxiliary traffic.

Voice test uses the existing microphone stream: three seconds of room noise, followed by five seconds of normal speech. During this calibration, microphone audio is not sent to Gemini and raw audio is not saved. The wizard offers a speech-ending pause to apply explicitly. It requires an active microphone in voice mode and never changes Windows permission or volume.

Chat tools are available in the **⋯** menu beside History and New. **Ctrl+Shift+E** exports the current conversation as a local Markdown file, preserving code blocks and excluding activity logs. **F1** opens the keyboard reference; **Ctrl+L** focuses the composer. Unsent composer text is automatically saved after 500 ms to `%LOCALAPPDATA%\Brave\chat-draft.json` and restored on the next launch as a draft in a new conversation. It is never sent automatically. Clearing or sending the composer clears the saved draft; selecting a new conversation also clears it.

The next refinement adds local attachment previews via **Ko‘rish / Preview**, searchable task history with status filters and result copying, and an idle-response watchdog. After 120 seconds without response progress (excluding active tools or playback), automatic recovery rebuilds the connection without replaying the pending request. Recovery honors the Conversation switch. Overlapping text sends are blocked, drafts stay in the composer, and cancelling an already completed task preserves its completed status.

Open **Markaz / Center → Conversation, Memory, Routines, or Tasks**.

- Choose short, balanced, or detailed answers. Voice interruption is enabled by default, uses four consecutive non-echo microphone blocks, preserves the speech onset, and honors mute, microphone permission, phone mode, and push-to-talk. Disable it if your room causes unwanted interruptions. Escape stops the response; recognized stop commands also cancel it.
- Inspect, search, edit, and delete individual saved memory facts. Changes apply when the Live session is rebuilt; deleting a fact does not erase words already present in chat history or provider context.
- Save named routines using ordinary instructions, then say the name or click Run. Gemini carries out the routine through existing tools and the current approval policy. No routine runs automatically just because it is saved.
- Tasks retain requests, action stages, replies, interruption/error status, and cancellation. Prepare a request again to review it in the composer before resending. No failed action is replayed automatically. Task records are local, capped at 100, and can be deleted.
- Attach PDF, DOCX, XLSX, UTF-8 text/code, or common image files and send a question. Selecting a file alone sends nothing. Documents are read locally, images are resized and stripped of EXIF, and extracted content is sent with the explicit question. File permissions are checked before reading and before sending. The input limit is 25 MB; extracted text is capped at 24,000 characters, or 60,000 in Turbo. Scanned PDFs need a readable image attachment; this reader has no local PDF OCR.
- Automatic connection and audio recovery can be disabled in Conversation. Diagnostics offers manual reconnect and audio refresh. Recovery never resends a failed chat request automatically.

Companion settings, routines, and task records are stored under `%LOCALAPPDATA%\Brave`. Memory continues to use the existing `memory/long_term.json` store. Text credential redaction is heuristic; review sensitive documents and images before sending.

