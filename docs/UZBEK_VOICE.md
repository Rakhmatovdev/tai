# Offline Uzbek neural voice

The selected Uzbek female voice uses a local VITS model through ONNX Runtime on the CPU. It does not use Windows SAPI, an API key, a web speech service, or a runtime model download. The voice weights occupy about 114 MB. Files live in `%LOCALAPPDATA%/Brave/tts-models/uzbek-female-vits`, outside the application checkout and packaged build.

In **… → Offline voice**, select **O‘zbekcha ayol ovozi · lokal AI**, use **Download Uzbek voice** once, then **Preview voice** and **Save**. The model can also be prepared explicitly with `.venv/Scripts/python.exe -m core.uzbek_tts --prepare`. Once prepared, it works with Internet permission disabled. **Voice + text** reads Ollama replies using the saved voice. Recording still starts only through Speak / F4. Esc cancels recording or playback.

Uzbek Latin letters, common apostrophe variants and numbers are normalized locally into the model's Cyrillic vocabulary. Existing Cyrillic input is accepted. Long replies are split into bounded phrases; Markdown code blocks and raw URLs are omitted from speech. This single Uzbek voice can mispronounce foreign words. Initial model loading and phrase synthesis add latency; this is not a streaming voice model.

Preparation downloads only pinned data files over HTTPS and checks their SHA-256 digests before installation. Inference verifies the files when loading, uses CPU inference with four threads and never imports downloaded Python code. Missing or corrupt voice files produce an error; the app does not silently switch to Windows speech.

## Model attribution

- Fine-tuned voice: [Muzaffar Sharofitdinov — mms-tts-uzbek-girl-voice_cyrillic](https://huggingface.co/MuzaffarSharofitdinov/mms-tts-uzbek-girl-voice_cyrillic), trained on Beehzod/UzTTS_data. Its model card declares CC BY 4.0.
- ONNX conversion: [davron112/mms-tts-uzbek-girl-cyrl-onnx](https://huggingface.co/davron112/mms-tts-uzbek-girl-cyrl-onnx), revision `f81775a7279f9f5b8ec9904156abe75730af2182`. The exporter supplies no separate model card/license.
- Underlying model: [Meta MMS-TTS Uzbek Cyrillic](https://huggingface.co/facebook/mms-tts-uzb-script_cyrillic), whose model card declares CC BY-NC 4.0. The fine-tuned card's more permissive label does not remove the underlying model's stated restriction. This installation downloads the weights for personal local use; they are not bundled or redistributed with the app.
- Tokenization follows the blank-interspersed VITS character vocabulary documented by [Hugging Face Transformers](https://github.com/huggingface/transformers/blob/main/src/transformers/models/vits/tokenization_vits.py).
