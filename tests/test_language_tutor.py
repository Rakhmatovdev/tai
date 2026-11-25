import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

import brave_brand
from brave_language_tutor import (
    LANGUAGES,
    LEVELS,
    SKILLS,
    TEACHER_ROLES,
    AcademyHubDialog,
    FlashcardDialog,
    LanguageTutorDialog,
    build_professor_system_prompt,
)
from core import workspace_store
from ui import MainWindow


class LanguageTutorTests(unittest.TestCase):
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

    def test_tai_brand_logo_and_identity(self):
        self.assertEqual(self.win._assistant_name, "TAI")
        self.assertIn("TAI", self.win.windowTitle())
        for theme in ("dark", "light", "hacker"):
            pix = brave_brand.logo_pixmap(64, theme, 2)
            self.assertFalse(pix.isNull())
        self.assertTrue(hasattr(self.win, "_header_academy_btn"))
        self.assertIn("🎓", self.win._header_academy_btn.text())

    def test_seven_skill_sidebar_buttons_exist_and_switch_channels(self):
        expected_keys = ["speaking", "writing", "listening", "grammar", "vocabulary", "reading", "general"]
        self.assertEqual([s.key for s in SKILLS], expected_keys)
        for skill_key in expected_keys:
            self.assertIn(skill_key, self.win._skill_buttons)

        seen_chat_ids = set()
        for skill_key in expected_keys:
            ok = self.win.switch_tutor_skill(skill_key)
            self.assertTrue(ok)
            self.assertEqual(self.win._language_tutor.state["active_skill"], skill_key)
            chat_id = self.win._features.chat_id
            self.assertTrue(chat_id)
            seen_chat_ids.add(chat_id)
            self.assertTrue(self.win._skill_buttons[skill_key].isChecked())
            for other_key in expected_keys:
                if other_key != skill_key:
                    self.assertFalse(self.win._skill_buttons[other_key].isChecked())

        self.assertEqual(len(seen_chat_ids), 7, "Each of the 7 skills must have its own dedicated chat channel")

    def test_role_and_language_switching_updates_professor_prompt(self):
        self.win._language_tutor.apply_state(
            {
                "target_language": "ar",
                "level": "B2",
                "teacher_role": "strict_professor",
                "active_skill": "grammar",
            },
            announce=True,
        )
        prompt = self.win._language_tutor.system_prompt()
        self.assertIn("Arab tili", prompt)
        self.assertIn("B2", prompt)
        self.assertIn("Qattiqqo‘l Ustoz", prompt)
        self.assertIn("GRAMMAR", prompt)
        self.assertIn("30-YEAR PROFESSOR", prompt)

        history_texts = self.win._log.toPlainText()
        self.assertIn("Arab tili", history_texts)

    def test_onboarding_dialog_saves_selection(self):
        dlg = LanguageTutorDialog(self.win._language_tutor)
        idx = dlg.lang_combo.findData("custom")
        dlg.lang_combo.setCurrentIndex(idx)
        dlg.custom_lang_input.setText("Spanish (Academic)")
        lvl_idx = dlg.level_combo.findData("C1")
        dlg.level_combo.setCurrentIndex(lvl_idx)
        dlg._select_role("kind_mentor")
        dlg._select_skill("speaking")
        dlg.apply_and_start()

        state = self.win._language_tutor.state
        self.assertEqual(state["target_language"], "custom")
        self.assertEqual(state["custom_language"], "Spanish (Academic)")
        self.assertEqual(state["level"], "C1")
        self.assertEqual(state["teacher_role"], "kind_mentor")
        self.assertEqual(state["active_skill"], "speaking")
        self.assertTrue(state["onboarded"])

    def test_vocab_bank_professor_actions_and_interactive_quiz(self):
        tutor = self.win._language_tutor
        count = tutor.load_starter_vocab_pack()
        self.assertGreaterEqual(count, 3)
        self.assertIn("📚", self.win._tutor_vocab_btn.text())

        # Test AcademyHubDialog renders saved words
        hub = AcademyHubDialog(tutor)
        hub.word_in.setText("resilient")
        hub.meaning_in.setText("bardoshli, chidamli (C1)")
        hub.colloc_in.setText("resilient economy")
        hub.mnem_in.setText("Re-spring -> qayta tiklanuvchi")
        hub._add_word()
        self.assertEqual(tutor.state["vocab_bank"][0]["word"], "resilient")
        hub.close()

        # Test 1-click Professor Action buttons (X-Ray, Formula, Drill)
        self.win._input.setText("He go to school yesterday")
        self.win._tutor_xray_btn.click()
        self.assertIn("XATOLAR RENTGENI", self.win._input.text())
        self.assertIn("He go to school yesterday", self.win._input.text())

        self.win._input.setText("Present Perfect")
        self.win._tutor_formula_btn.click()
        self.assertIn("OLTIN FORMULA", self.win._input.text())

        # Test Center-Board Quiz launch & grading
        self.win._tutor_quiz_btn.click()
        self.assertIsNotNone(self.win._quiz)
        first_q = self.win._quiz["questions"][0]
        self.win._quiz_submit(first_q["answer"])
        self.assertTrue(self.win._quiz["results"][0]["correct"])
        self.assertIn("correct", self.win._quiz_note_lbl.text())

    def test_educational_access_restrictions_and_domain_filter(self):
        from core import access_policy

        # 1. Domain allowlist check: YouTube & Dictionaries allowed, distracting/dangerous blocked
        allowed_urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://m.youtube.com/watch?v=123",
            "https://dictionary.cambridge.org/dictionary/english/ubiquitous",
            "https://www.oxfordlearnersdictionaries.com/definition/english/meticulous",
            "https://www.merriam-webster.com/dictionary/articulate",
            "https://www.ted.com/talks/example",
            "https://www.bbc.co.uk/learningenglish",
            "https://youglish.com/pronounce/compelling/english",
            "https://en.wikipedia.org/wiki/English_language",
            "about:blank",
        ]
        blocked_urls = [
            "https://www.facebook.com",
            "https://www.tiktok.com",
            "https://www.instagram.com",
            "https://casino777.com",
            "https://evil-youtube.com/watch?v=123",
            "https://fakecambridge.org",
        ]

        for url in allowed_urls:
            self.assertTrue(
                access_policy.is_educational_url_allowed(url),
                f"Educational URL should be allowed: {url}",
            )

        for url in blocked_urls:
            self.assertFalse(
                access_policy.is_educational_url_allowed(url),
                f"Non-educational URL should be blocked: {url}",
            )

        # 2. Reduced permissions by default: code and system are restricted
        policy = access_policy.DEFAULT_POLICY
        self.assertFalse(policy["permissions"]["code"], "Arbitrary code execution should be restricted by default")
        self.assertFalse(policy["permissions"]["system"], "System/OS settings modification should be restricted by default")
        self.assertTrue(policy["permissions"]["network"], "Network is required for language tutoring & YouTube")
        self.assertTrue(policy["permissions"]["files"], "Files is required for vocabulary storage")
        self.assertTrue(policy["educational_filter"], "Educational filter must be active by default")

        # 3. Decision enforcement
        # Dangerous code_helper or computer_control blocked by default
        dec_code = access_policy.decide("code_helper", {"action": "run"}, policy)
        self.assertFalse(dec_code.allowed, "code_helper should be blocked in default educational profile")

        dec_sys = access_policy.decide("computer_settings", {"action": "change"}, policy)
        self.assertFalse(dec_sys.allowed, "computer_settings should be blocked in default educational profile")

        # YouTube video with YouTube URL allowed
        dec_yt_ok = access_policy.decide(
            "youtube_video",
            {"action": "play", "url": "https://www.youtube.com/watch?v=123"},
            policy,
        )
        self.assertTrue(dec_yt_ok.allowed, "Valid YouTube URL must be allowed")

        # YouTube video with non-YouTube URL blocked
        dec_yt_bad = access_policy.decide(
            "youtube_video",
            {"action": "play", "url": "https://untrusted-site.com/video"},
            policy,
        )
        self.assertFalse(dec_yt_bad.allowed, "Non-YouTube URL in youtube_video must be blocked")

        # browser_control to Cambridge dictionary allowed
        dec_browser_ok = access_policy.decide(
            "browser_control",
            {"action": "go_to", "url": "https://dictionary.cambridge.org"},
            policy,
        )
        self.assertTrue(dec_browser_ok.allowed, "Educational site must be allowed in browser_control")

        # browser_control to blocked site blocked
        dec_browser_bad = access_policy.decide(
            "browser_control",
            {"action": "go_to", "url": "https://tiktok.com"},
            policy,
        )
        self.assertFalse(dec_browser_bad.allowed, "Distracting non-educational site must be blocked")

        # 4. Tutor UI has educational lock button visible
        self.assertTrue(hasattr(self.win, "_tutor_lock_btn"))
        self.assertIn("YouTube", self.win._tutor_lock_btn.text())


class StreakAndExportTests(unittest.TestCase):
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

    def test_export_vocab_csv_produces_valid_utf8_output(self):
        tutor = self.win._language_tutor
        tutor.add_vocab_entry("resilient", "bardoshli (C1)", "resilient economy", "Re-spring")
        tutor.add_vocab_entry("ubiquitous", "hamma joyda uchraydigan (C1)", "ubiquitous technology", "Ubi=hamma yer")
        csv_text = tutor.export_vocab_csv()
        self.assertIn("resilient", csv_text)
        self.assertIn("ubiquitous", csv_text)
        self.assertIn("bardoshli", csv_text)
        self.assertIn("So'z", csv_text)
        import io, csv
        reader = csv.reader(io.StringIO(csv_text))
        rows = list(reader)
        self.assertGreaterEqual(len(rows), 3)  # header + 2 entries
        self.assertEqual(rows[0][0], "So'z")

    def test_streak_tracking_records_and_increments(self):
        tutor = self.win._language_tutor
        tutor.apply_state({'target_language': 'en'})
        # Fresh state: no streak
        stats = tutor.get_streak_stats()
        self.assertEqual(stats.get('streak', 0), 0)
        # Record a session
        tutor.record_study_session()
        stats = tutor.get_streak_stats()
        self.assertEqual(stats['streak'], 1)
        self.assertEqual(stats['total_days'], 1)
        # Calling again on same day should not double-count
        tutor.record_study_session()
        stats = tutor.get_streak_stats()
        self.assertEqual(stats['total_days'], 1)

    def test_streak_separate_per_language(self):
        tutor = self.win._language_tutor
        tutor.apply_state({'target_language': 'en'})
        tutor.record_study_session()
        tutor.apply_state({'target_language': 'ru'})
        tutor.record_study_session()
        en_stats = workspace_store.read('tutor-streak.json', {}).get('en', {})
        ru_stats = workspace_store.read('tutor-streak.json', {}).get('ru', {})
        self.assertEqual(en_stats.get('streak', 0), 1)
        self.assertEqual(ru_stats.get('streak', 0), 1)

    def test_new_languages_have_vocab_starter_packs(self):
        # All 6 new languages should have starter vocab packs
        from brave_language_tutor import PROFESSOR_STARTER_VOCAB
        for lang_code in ('fr', 'es', 'zh', 'ja', 'it'):
            self.assertIn(lang_code, PROFESSOR_STARTER_VOCAB, f"{lang_code} starter pack mavjud emas")
            self.assertGreaterEqual(len(PROFESSOR_STARTER_VOCAB[lang_code]), 2,
                                    f"{lang_code} uchun kamida 2 ta so'z kerak")

    def test_new_languages_have_quiz_questions(self):
        from brave_language_tutor import PROFESSOR_QUIZ_BANK
        for lang_code in ('ru', 'fr', 'es', 'zh', 'ja'):
            self.assertIn(lang_code, PROFESSOR_QUIZ_BANK, f"{lang_code} quiz savollari mavjud emas")
            self.assertGreaterEqual(len(PROFESSOR_QUIZ_BANK[lang_code]), 1,
                                    f"{lang_code} uchun kamida 1 ta savol kerak")

    def test_academy_hub_streak_banner_visible(self):
        tutor = self.win._language_tutor
        tutor.record_study_session()
        hub = AcademyHubDialog(tutor)
        # streak banner should be part of the dialog
        from PyQt6.QtWidgets import QLabel
        labels = hub.findChildren(QLabel)
        texts = [lbl.text() for lbl in labels]
        # should have streak or session info
        found_streak = any('Streak' in t or "o'quv" in t or 'kun' in t for t in texts)
        self.assertTrue(found_streak, f"Streak banner topilmadi. Labels: {texts}")
        hub.close()

    def test_delete_vocab_entry(self):
        tutor = self.win._language_tutor
        tutor.add_vocab_entry("serendipity", "kutilmagan baxtli topilma", "a happy serendipity")
        self.assertTrue(any(v['word'] == 'serendipity' for v in tutor.state.get('vocab_bank', [])))
        ok = tutor.delete_vocab_entry("serendipity")
        self.assertTrue(ok)
        self.assertFalse(any(v['word'] == 'serendipity' for v in tutor.state.get('vocab_bank', [])))

    def test_export_vocab_anki_tsv(self):
        tutor = self.win._language_tutor
        tutor.add_vocab_entry("eloquent", "notiq, ta'sirli gapiruvchi", "an eloquent speech", "El-oq -> ravon oquvchi")
        anki_text = tutor.export_vocab_anki()
        self.assertIn("#separator:tab", anki_text)
        self.assertIn("eloquent", anki_text)
        self.assertIn("notiq", anki_text)
        self.assertIn("tai-en", anki_text)
        self.assertIn("\t", anki_text)

    def test_vocab_search_and_speak_in_hub(self):
        tutor = self.win._language_tutor
        tutor.add_vocab_entry("ubiquitous", "hamma joyda mavjud")
        tutor.add_vocab_entry("ephemeral", "o'tkinchi, qisqa muddatli")
        hub = AcademyHubDialog(tutor)
        self.assertTrue(hasattr(hub, 'search_in'))
        hub.search_in.setText("ephem")
        # Search must filter the cards down to the matching word.
        from PyQt6.QtWidgets import QLabel
        shown = " ".join(lbl.text() for lbl in hub.list_host.findChildren(QLabel))
        self.assertIn("ephemeral", shown)
        self.assertNotIn("ubiquitous", shown)
        # Pronunciation uses a voice for the target language, not the Uzbek chat voice.
        with patch("brave_language_tutor._sapi_speak") as speak:
            tutor.speak_word("ephemeral")
            for _ in range(50):
                if speak.called:
                    break
                QApplication.processEvents()
                import time; time.sleep(0.01)
        speak.assert_called_once_with("ephemeral", "en")
        hub.close()

    def test_anki_export_escapes_html(self):
        tutor = self.win._language_tutor
        tutor.add_vocab_entry("a<b>", "x & y\tz")
        anki_text = tutor.export_vocab_anki()
        row = [line for line in anki_text.splitlines() if line.startswith("a&lt;b&gt;")]
        self.assertEqual(len(row), 1)
        self.assertEqual(len(row[0].split("\t")), 3)
        self.assertIn("x &amp; y z", row[0])

    def test_vocab_mastery_stats_and_update(self):
        tutor = self.win._language_tutor
        tutor.state["vocab_bank"] = []
        tutor.add_vocab_entry("ephemeral", "o'tkinchi")
        tutor.add_vocab_entry("resilient", "bardoshli")

        stats = tutor.vocab_mastery_stats()
        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["mastered"], 0)
        self.assertEqual(stats["percent"], 0)

        tutor.update_vocab_progress("ephemeral", mastered=True)
        stats = tutor.vocab_mastery_stats()
        self.assertEqual(stats["mastered"], 1)
        self.assertEqual(stats["percent"], 50)

        # verify review count incremented
        bank = tutor.state.get("vocab_bank", [])
        eph = [v for v in bank if v.get("word") == "ephemeral"][0]
        self.assertEqual(eph.get("review_count"), 1)
        self.assertTrue(eph.get("mastered"))

        # second review as not mastered
        tutor.update_vocab_progress("ephemeral", mastered=False)
        eph = [v for v in tutor.state.get("vocab_bank", []) if v.get("word") == "ephemeral"][0]
        self.assertEqual(eph.get("review_count"), 2)
        self.assertFalse(eph.get("mastered"))

    def test_flashcard_dialog_queue_and_review(self):
        tutor = self.win._language_tutor
        tutor.state["vocab_bank"] = []
        tutor.add_vocab_entry("catalyst", "katalizator, tezlatuvchi")
        tutor.add_vocab_entry("paradigm", "namuna, andoza")

        dlg = FlashcardDialog(tutor, parent=self.win)
        dlg.show()
        self.assertEqual(len(dlg.queue), 2)
        self.assertFalse(dlg.flipped)
        self.assertTrue(dlg.back_container.isHidden())

        # flip card
        dlg._toggle_flip()
        self.assertTrue(dlg.flipped)
        self.assertFalse(dlg.back_container.isHidden())
        self.assertFalse(dlg.rate_good_btn.isHidden())

        # rate first card good
        dlg._rate('good')
        self.assertEqual(dlg.reviewed_count, 1)
        self.assertEqual(len(dlg.queue), 1)

        # rate second card hard -> placed back to queue
        dlg._toggle_flip()
        dlg._rate('hard')
        self.assertEqual(dlg.reviewed_count, 2)
        self.assertEqual(len(dlg.queue), 1)

        # finish last card with easy
        dlg._toggle_flip()
        dlg._rate('easy')
        self.assertEqual(len(dlg.queue), 0)
        self.assertIn("yakunlandi", dlg.word_lbl.text().lower())

        dlg.accept()
        dlg.close()

    def test_flashcard_dialog_empty_state_and_pack_load(self):
        tutor = self.win._language_tutor
        tutor.state["vocab_bank"] = []
        dlg = FlashcardDialog(tutor, parent=self.win)
        self.assertEqual(len(dlg.queue), 0)
        self.assertEqual(dlg.side_badge.text(), "LUG‘AT BO‘SH")

        # trigger starter pack load
        dlg._load_pack_and_start()
        self.assertGreater(len(dlg.queue), 0)
        self.assertEqual(dlg.side_badge.text(), "OLD TOMON · SO‘Z")

        dlg.accept()
        dlg.close()


class ProfessionalLanguageAcademyTests(unittest.TestCase):
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

    def test_all_eleven_languages_have_rich_vocab_and_complete_quiz_banks(self):
        from brave_language_tutor import PROFESSOR_QUIZ_BANK, PROFESSOR_STARTER_VOCAB

        standard_langs = ("en", "ru", "ar", "tr", "de", "ko", "fr", "es", "zh", "ja", "it")
        for code in standard_langs:
            vocab = PROFESSOR_STARTER_VOCAB.get(code, [])
            self.assertGreaterEqual(len(vocab), 6, f"{code} uchun kamida 6 ta lug'at so'zi kerak")
            for row in vocab:
                self.assertTrue(row.get("word"))
                self.assertTrue(row.get("meaning"))
                self.assertTrue(row.get("collocation"))
                self.assertTrue(row.get("mnemonic"))

            quiz = PROFESSOR_QUIZ_BANK.get(code, [])
            self.assertGreaterEqual(len(quiz), 5, f"{code} uchun kamida 5 ta test savoli kerak")
            for q in quiz:
                self.assertEqual(len(q["options"]), 4)
                self.assertIn(q["answer"], q["options"])
                self.assertTrue(q.get("note"))

    def test_linguistic_guides_and_grammar_cheatsheets(self):
        from brave_language_tutor import (
            LANGUAGE_GRAMMAR_CHEATSHEETS,
            LANGUAGE_LINGUISTIC_GUIDES,
            GrammarFormulaDialog,
        )

        standard_langs = ("en", "ru", "ar", "tr", "de", "ko", "fr", "es", "zh", "ja", "it")
        for code in standard_langs:
            self.assertIn(code, LANGUAGE_LINGUISTIC_GUIDES)
            self.assertIn(code, LANGUAGE_GRAMMAR_CHEATSHEETS)
            self.assertGreaterEqual(len(LANGUAGE_GRAMMAR_CHEATSHEETS[code]), 2)

        de_prompt = build_professor_system_prompt({"target_language": "de", "level": "B2"})
        self.assertIn("GERMAN PEDAGOGY", de_prompt)
        ja_prompt = build_professor_system_prompt({"target_language": "ja", "level": "N2"})
        self.assertIn("JAPANESE PEDAGOGY", ja_prompt)

        tutor = self.win._language_tutor
        tutor.apply_state({"target_language": "ar", "level": "B2"})
        fdlg = GrammarFormulaDialog(tutor, self.win)
        sample_prompt = LANGUAGE_GRAMMAR_CHEATSHEETS["ar"][0]["practice_prompt"]
        fdlg._practice(sample_prompt)
        self.assertEqual(tutor.state["active_skill"], "grammar")
        self.assertEqual(self.win._input.text(), sample_prompt)
        fdlg.close()

    def test_extract_vocab_quick_save_message_card_and_study_report(self):
        from brave_chat import MessageCard
        from brave_language_tutor import extract_vocab_from_reply

        sample_reply = (
            "### 🔍 Kalit so‘zlar\n"
            "- **pragmatic** — amaliy va real natijaga yo‘naltirilgan | a pragmatic policy | 💡 Pragmatizm -> amaliy ish\n"
            "- **mitigate** — xavfni yumshatmoq | mitigate impact | 💡 Minusga tushirib yumshatish\n"
        )
        extracted = extract_vocab_from_reply(sample_reply)
        self.assertEqual(len(extracted), 2)
        self.assertEqual(extracted[0]["word"], "pragmatic")
        self.assertEqual(extracted[0]["collocation"], "a pragmatic policy")
        self.assertEqual(extracted[0]["mnemonic"], "Pragmatizm -> amaliy ish")

        tutor = self.win._language_tutor
        tutor.state["vocab_bank"] = []
        saved_count = tutor.quick_save_from_message(sample_reply, interactive=False)
        self.assertEqual(saved_count, 2)
        words = {v["word"] for v in tutor.state["vocab_bank"]}
        self.assertIn("pragmatic", words)
        self.assertIn("mitigate", words)

        card = MessageCard("ai", sample_reply, "10:00", "TAI", self.win)
        save_btns = [b for b in card.findChildren(type(card.continue_button)) if b.objectName() == "BraveSaveVocab"]
        self.assertEqual(len(save_btns), 1)
        card.close()

        tutor.update_vocab_progress("pragmatic", mastered=True)
        report = tutor.export_study_report_markdown()
        self.assertIn("TAI Akademiya — Shaxsiy O‘quv Hisoboti", report)
        self.assertIn("pragmatic", report)
        self.assertIn("🌟 Yodlangan", report)

    def test_academy_hub_filtering_and_mastery_toggle(self):
        from PyQt6.QtWidgets import QLabel

        tutor = self.win._language_tutor
        tutor.state["vocab_bank"] = []
        tutor.add_vocab_entry("resilient", "bardoshli (C1)")
        tutor.add_vocab_entry("ubiquitous", "hamma yerda bor (C1)")
        tutor.update_vocab_progress("resilient", mastered=True)

        hub = AcademyHubDialog(tutor)
        self.assertTrue(hasattr(hub, "filter_combo"))
        # Default filter shows both
        shown_all = " ".join(lbl.text() for lbl in hub.list_host.findChildren(QLabel))
        self.assertIn("resilient", shown_all)
        self.assertIn("ubiquitous", shown_all)

        # Mastered filter shows only resilient
        hub.filter_combo.setCurrentIndex(hub.filter_combo.findData("mastered"))
        shown_mastered = " ".join(lbl.text() for lbl in hub.list_host.findChildren(QLabel))
        self.assertIn("resilient", shown_mastered)
        self.assertNotIn("ubiquitous", shown_mastered)

        # Needs review filter shows only ubiquitous
        hub.filter_combo.setCurrentIndex(hub.filter_combo.findData("review"))
        shown_review = " ".join(lbl.text() for lbl in hub.list_host.findChildren(QLabel))
        self.assertIn("ubiquitous", shown_review)
        self.assertNotIn("resilient", shown_review)

        # Toggle mastery directly from hub method
        hub._toggle_mastered("ubiquitous", False)
        hub.filter_combo.setCurrentIndex(hub.filter_combo.findData("mastered"))
        shown_both = " ".join(lbl.text() for lbl in hub.list_host.findChildren(QLabel))
        self.assertIn("ubiquitous", shown_both)
        hub.close()

    def test_text_actions_navigation_recovery_and_title_i18n(self):
        import brave_i18n
        import brave_navigation
        import brave_text_actions
        from core import app_recovery

        action_keys = [k for k, _, _ in brave_text_actions.ACTIONS]
        for k in ("summary", "translate", "explain", "rewrite", "grammar_xray", "cefr_upgrade", "vocab_extract", "band_eval"):
            self.assertIn(k, action_keys)
        lang_keys = {k for k, _, _ in brave_text_actions.LANGUAGES}
        self.assertTrue({"uz", "en", "ru", "ar", "tr", "de", "ko", "fr", "es", "zh", "ja", "it"} <= lang_keys)

        msgs = brave_text_actions.action_messages("grammar_xray", "He go home yesterday.", "en", "balanced")
        self.assertIn("Error X-Ray", msgs[0]["content"])
        self.assertIn("untrusted data", msgs[0]["content"])

        nav_keys = {e.key for e in brave_navigation.ACTIONS}
        for k in ("tutor-setup", "academy-hub", "tutor-flashcards", "tutor-quiz"):
            self.assertIn(k, nav_keys)
        self.assertIn("tutor-flashcards", [e.key for e in brave_navigation.search_entries(brave_navigation.ACTIONS, "flashcard")])

        self.assertIn("language-tutor.json", app_recovery.FILES)
        self.assertIn("tutor-streak.json", app_recovery.FILES)

        brave_i18n.localize_widgets(self.win)
        self.assertIn("TAI", self.win.windowTitle())


if __name__ == "__main__":
    unittest.main()
