"""Tests for Uzbek dialects, gender/emotion/speed prosody DSP, VoiceDialectDialog, and Chat/Tutor enhancements."""
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QPushButton

from brave_chat import ComposerEdit, MessageCard
import brave_i18n
import brave_navigation
import brave_text_actions
from brave_language_tutor import (
    LANGUAGE_GRAMMAR_CHEATSHEETS,
    LANGUAGE_LINGUISTIC_GUIDES,
    PROFESSOR_QUIZ_BANK,
    PROFESSOR_STARTER_VOCAB,
    ROLE_MAP,
    AcademyHubDialog,
    FlashcardDialog,
)
from brave_voice_dialect import VoiceDialectDialog, score_pronunciation
from core import app_recovery, uzbek_tts, workspace_store
from core.voice_style import (
    DIALECTS,
    EMOTIONS,
    GENDERS,
    SPEEDS,
    apply_uzbek_dialect_text,
    build_voice_style_prompt,
    is_neutral_dsp,
    load_voice_style,
    recommended_gemini_voice,
    save_voice_style,
    transform_waveform,
)
from ui import MainWindow


class VoiceStyleAndProsodyTests(unittest.TestCase):
    def test_uzbek_dialect_text_transformations_and_case(self):
        src = "U kelyapti, men boryapman, siz nima qilyapsiz?"
        self.assertEqual(apply_uzbek_dialect_text(src, "adabiy"), src)

        tosh = apply_uzbek_dialect_text(src, "toshkent")
        self.assertIn("kevotti", tosh)
        self.assertIn("borvomman", tosh)
        self.assertIn("qivosiz", tosh)

        sam = apply_uzbek_dialect_text(src, "samarqand_buxoro")
        self.assertIn("kelopti", sam)
        self.assertIn("boromman", sam)
        self.assertIn("qilopsiz", sam)

        xorazm = apply_uzbek_dialect_text("Kelinglar, u kelyapti!", "xorazm")
        self.assertEqual(xorazm, "Galingla, u galyabdi!")

        qash = apply_uzbek_dialect_text("U kelyapti va ish qilyapti.", "qashqadaryo_surxon")
        self.assertIn("kelayapti", qash)
        self.assertIn("qilayapti", qash)

    def test_wsola_speed_and_gender_emotion_dsp_waveforms(self):
        sr = 16000
        t = np.linspace(0, 1.0, sr, endpoint=False, dtype=np.float32)
        # Synthetic harmonic voiced signal (180 Hz + 360 Hz)
        wave = (0.45 * np.sin(2 * np.pi * 180 * t) + 0.20 * np.sin(2 * np.pi * 360 * t)).astype(np.float32)

        # Neutral female 1.0x is identity
        neutral_style = {"gender": "female", "emotion": "neutral", "speed": "normal", "dialect": "adabiy"}
        self.assertTrue(is_neutral_dsp(neutral_style))
        same = transform_waveform(wave, sr, neutral_style)
        self.assertEqual(same.size, wave.size)

        # Very slow (0.70x) produces longer waveform
        slow_out = transform_waveform(wave, sr, {"gender": "female", "emotion": "neutral", "speed": "very_slow"})
        self.assertGreater(slow_out.size, int(sr * 1.25))
        self.assertTrue(np.isfinite(slow_out).all())
        self.assertLessEqual(float(np.max(np.abs(slow_out))), 1.0)

        # Very fast (1.40x) produces shorter waveform
        fast_out = transform_waveform(wave, sr, {"gender": "female", "emotion": "neutral", "speed": "very_fast"})
        self.assertLess(fast_out.size, int(sr * 0.82))
        self.assertTrue(np.isfinite(fast_out).all())

        # Male baritone + all emotions produce valid bounded float32 audio
        for g in GENDERS:
            for e in EMOTIONS:
                out = transform_waveform(wave, sr, {"gender": g.key, "emotion": e.key, "speed": "normal"})
                self.assertGreater(out.size, sr // 2)
                self.assertTrue(np.isfinite(out).all())
                self.assertLessEqual(float(np.max(np.abs(out))), 1.0001)

    def test_gemini_voice_mapping_and_prompt_directives(self):
        self.assertEqual(recommended_gemini_voice({"gender": "female", "emotion": "gentle"}), "Aoede")
        self.assertEqual(recommended_gemini_voice({"gender": "female", "emotion": "loving"}), "Aoede")
        self.assertEqual(recommended_gemini_voice({"gender": "male", "emotion": "polite_professor"}), "Charon")
        self.assertEqual(recommended_gemini_voice({"gender": "male", "emotion": "rough"}), "Fenrir")
        self.assertEqual(recommended_gemini_voice({"gender": "male", "emotion": "cheerful"}), "Puck")

        prompt = build_voice_style_prompt({
            "gender": "male",
            "dialect": "xorazm",
            "emotion": "loving",
            "speed": "slow",
        })
        self.assertIn("Khorezm Oghuz dialect", prompt)
        self.assertIn("MUHABBAT BILAN", prompt)
        self.assertIn("Erkak ovozi", prompt)
        self.assertIn("relaxed, slow", prompt)

    def test_pronunciation_shadowing_scorer(self):
        exact = score_pronunciation("Assalomu alaykum yaxshimisiz", "assalomu alaykum, yaxshimisiz!")
        self.assertEqual(exact["accuracy"], 100.0)
        self.assertEqual(exact["missed"], [])

        partial = score_pronunciation("Bugun yangi so‘zlarni birga o‘rganamiz", "Bugun yangi birga")
        self.assertLess(partial["accuracy"], 80.0)
        self.assertTrue(len(partial["missed"]) >= 1)

    def test_uzbek_tts_prefetch_and_dialect_playback(self):
        import sounddevice
        stream = MagicMock()
        chunks = [
            (np.sin(np.linspace(0, 20, 4000, dtype=np.float32)) * 0.2, 16000),
            (np.sin(np.linspace(0, 20, 4000, dtype=np.float32)) * 0.2, 16000),
        ]
        style = {"gender": "male", "dialect": "toshkent", "emotion": "gentle", "speed": "fast", "phonetic_dialect_tts": True}
        with patch.object(uzbek_tts, "synthesize", return_value=iter(chunks)) as synth, \
                patch.object(sounddevice, "OutputStream", return_value=stream), \
                patch("core.audio_devices.resolve", return_value=None):
            uzbek_tts.speak("U kelyapti.", threading.Event(), style=style)
        # Dialect text was transformed before synthesis
        called_text = synth.call_args.args[0]
        self.assertIn("kevotti", called_text)
        self.assertTrue(stream.write.called)
        stream.close.assert_called_once()


class StudioChatAndTutorIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._patch = patch.object(workspace_store, "directory", return_value=Path(self._tmp.name))
        self._patch.start()
        self.win = MainWindow(Path(__file__).resolve().parents[1] / "face.png")

    def tearDown(self):
        self.win.close()
        self._patch.stop()
        self._tmp.cleanup()

    def test_voice_dialect_studio_saves_and_updates_tutor_bar(self):
        dlg = VoiceDialectDialog(self.win)
        self.assertEqual(len(dlg.dialect_buttons), len(DIALECTS))
        self.assertEqual(len(dlg.emotion_buttons), len(EMOTIONS))

        dlg._select_gender("male")
        dlg._select_dialect("xorazm")
        dlg._select_emotion("loving")
        dlg.speed_combo.setCurrentIndex(dlg.speed_combo.findData("slow"))
        self.assertIn("Xorazm", dlg.summary_lbl.text())
        self.assertIn("galing", dlg.preview_input.toPlainText().lower())

        # Test pronunciation scoring inside dialog
        dlg.spoken_input.setText(dlg.preview_input.toPlainText())
        dlg._evaluate_pronunciation()
        self.assertIn("100.0%", dlg.feedback_lbl.text())

        with patch("memory.config_manager.save_voice") as save_gem_voice:
            dlg.apply_and_save()
            self.assertTrue(save_gem_voice.called)

        saved = load_voice_style()
        self.assertEqual(saved["gender"], "male")
        self.assertEqual(saved["dialect"], "xorazm")
        self.assertEqual(saved["emotion"], "loving")
        self.assertEqual(saved["speed"], "slow")
        self.assertIn("👨", self.win._tutor_voice_btn.text())
        self.assertIn("Xorazmcha", self.win._tutor_voice_btn.text())

    def test_uzbek_academy_language_and_new_teacher_roles(self):
        self.assertIn("loving_gentle_mentor", ROLE_MAP)
        self.assertIn("blunt_coach", ROLE_MAP)
        self.assertIn("uz", PROFESSOR_STARTER_VOCAB)
        self.assertGreaterEqual(len(PROFESSOR_STARTER_VOCAB["uz"]), 6)
        self.assertIn("uz", LANGUAGE_LINGUISTIC_GUIDES)
        self.assertIn("uz", LANGUAGE_GRAMMAR_CHEATSHEETS)
        self.assertGreaterEqual(len(PROFESSOR_QUIZ_BANK["uz"]), 5)

        tutor = self.win._language_tutor
        tutor.apply_state({
            "target_language": "uz",
            "level": "C1",
            "teacher_role": "loving_gentle_mentor",
            "active_skill": "speaking",
        }, announce=True)
        prompt = tutor.system_prompt()
        self.assertIn("UZBEK ELOQUENCE & DIALECTOLOGY PEDAGOGY", prompt)
        self.assertIn("Mehrli va Mayin Ustoz", prompt)

    def test_slow_pronunciation_in_flashcards_and_hub(self):
        tutor = self.win._language_tutor
        tutor.apply_state({"target_language": "en"})
        tutor.add_vocab_entry("articulate", "ravon ifodalaydigan")

        fc = FlashcardDialog(tutor, self.win)
        self.assertTrue(hasattr(fc, "slow_speak_btn"))
        with patch("brave_language_tutor._sapi_speak") as speak_mock:
            fc._speak_current(slow=True)
            for _ in range(40):
                if speak_mock.called:
                    break
                QApplication.processEvents()
                import time; time.sleep(0.01)
            speak_mock.assert_called_once_with("articulate", "en", True)
        fc.close()

        hub = AcademyHubDialog(tutor)
        btns = [b.text() for b in hub.list_host.findChildren(QPushButton)]
        self.assertIn("🔊", btns)
        self.assertIn("🐢", btns)
        hub.close()

    def test_message_card_speak_composer_autogrow_and_ui_fixes(self):
        card = MessageCard("ai", "Assalomu alaykum! Bugun ajoyib mavzu o‘rganamiz.", "12:00", "TAI", self.win)
        names = {b.objectName() for b in card.findChildren(QPushButton)}
        self.assertIn("BraveSpeakAnswer", names)
        self.assertIn("BraveSlowSpeakAnswer", names)
        with patch.object(self.win, "_local_voice", create=True) as mock_voice:
            mock_voice.speaking = False
            card.speak_answer(None, "Salom dunyo", slow=True)
            mock_voice.say.assert_called_once()
            self.assertEqual(mock_voice.say.call_args.kwargs["style"]["speed"], "very_slow")
        card.close()

        # Composer auto-grow and word count
        self.win._input.setText("Bir ikki uch")
        self.assertEqual(self.win._word_count_lbl.text(), "3 so‘z")
        h_short = self.win._input.height()
        self.win._input.setText("\n".join([f"Qator {i}" for i in range(6)]))
        self.assertGreater(self.win._input.height(), h_short)
        self.assertLessEqual(self.win._input.height(), ComposerEdit.MAX_HEIGHT)

        # Non-recursive glance & TAI title preservation
        self.win.hud.glance(0.2, -0.3, hold=0.5)
        with patch("ui.API_FILE", Path(self._tmp.name) / "api_keys.json"):
            self.win._apply_name_update("TAI", "Foydalanuvchi")
        self.assertIn("30 Yillik Professor", self.win.windowTitle())

        # Navigation, text actions, app recovery & i18n
        hits = [e.key for e in brave_navigation.search_entries(brave_navigation.ACTIONS, "sheva nejniy")]
        self.assertIn("voice-dialect", hits)
        self.assertIn("uzbek_dialect", [k for k, _, _ in brave_text_actions.ACTIONS])
        self.assertIn("voice-style.json", app_recovery.FILES)
        self.assertEqual(
            brave_i18n.translate("Ovoz, Sheva va Talaffuz Studiyasi", "en"),
            "Voice, Dialect & Pronunciation Studio",
        )


if __name__ == "__main__":
    unittest.main()
