#!/usr/bin/env python3
"""Patch script: add new vocab languages and quiz questions, methods, and UI changes."""
import re, sys

path = r'brave_language_tutor.py'
content = open(path, encoding='utf-8').read()

# ── 1. PROFESSOR_STARTER_VOCAB: insert new languages before 'ko': ───────────
NEW_VOCAB = """    'fr': [
        {'word': 'néanmoins', 'meaning': 'shunga qaramasdan, baribir (B2/C1)', 'collocation': 'néanmoins important / néanmoins pertinent', 'mnemonic': "Ne + an + moins → hech bo'lmasa, baribir"},
        {'word': 'épanouissement', 'meaning': 'kamolot, rivojlanish, gullanish (C1)', 'collocation': 'épanouissement personnel', 'mnemonic': "Épanoui → gulga aylangan → to'liq rivojlanish"},
        {'word': 'pertinent', 'meaning': "o'rinli, dolzarb, tegishli (B2)", 'collocation': 'une question pertinente', 'mnemonic': "Pertinent → to'g'ridan-to'g'ri tegishli"},
    ],
    'es': [
        {'word': 'imprescindible', 'meaning': "o'ta zarur, muqarrar (B2/C1)", 'collocation': 'es imprescindible + infinitivo', 'mnemonic': "Im-prescindible → ayrilmaydigan, shart bo'lgan"},
        {'word': 'perspicaz', 'meaning': "ziyrak, o'tkir zehni bor (C1)", 'collocation': 'una mente perspicaz', 'mnemonic': "Perspicaz → perspektiva ko'ra oladigan"},
        {'word': 'contundente', 'meaning': 'ishonchli, kuchli, hal qiluvchi (B2/C1)', 'collocation': 'un argumento contundente', 'mnemonic': 'Contunde → zarba beruvchi kuch'},
    ],
    'zh': [
        {'word': '坚持不懈 (jiānchí bùxiè)', 'meaning': "qat'iyat bilan davom etmoq, charchamay urinmoq (HSK 5)", 'collocation': '坚持不懈地努力', 'mnemonic': "坚 (puxta) + 持 (ushlamoq) → to'xtovsiz ushlab turish"},
        {'word': '突破 (tūpò)', 'meaning': "to'siqni yengmoq, yutuq qozonmoq (HSK 4)", 'collocation': '取得突破 / 突破瓶颈', 'mnemonic': "突 (to'satdan) + 破 (sindirmoq) → to'siqni sindirmoq"},
        {'word': '融合 (rónghé)', 'meaning': "qo'shilmoq, birlashmoq, uyg'unlashmoq (HSK 5)", 'collocation': '文化融合 / 融合发展', 'mnemonic': "融 (eritmoq) + 合 (qo'shmoq) → biriga eritib qo'shish"},
    ],
    'ja': [
        {'word': '努力 (どりょく, doryoku)', 'meaning': "g'ayrat, mehnat qilmoq (JLPT N4)", 'collocation': '努力する / 努力が実る', 'mnemonic': '努 (harakat) + 力 (kuch) → kuch sarflash'},
        {'word': '克服 (こくふく, kokufuku)', 'meaning': 'yengmoq, bartaraf etmoq (JLPT N2)', 'collocation': '困難を克服する', 'mnemonic': "克 (yengmoq) + 服 (bo'ysunmoq) → qiyinlikni bo'ysundirmoq"},
        {'word': '洞察力 (どうさつりょく, dōsatsuryoku)', 'meaning': 'ziyraklik, chuqur tushunish (JLPT N1)', 'collocation': '洞察力がある / 優れた洞察力', 'mnemonic': "洞 (g'or → ichiga kirish) + 察 (kuzatmoq) → chuqurga qarab ko'rish"},
    ],
    'it': [
        {'word': 'impeccabile', 'meaning': "beg'ubor, mukammal, nuqsonsiz (C1)", 'collocation': "un'esecuzione impeccabile", 'mnemonic': 'Im-peccabile → gunohsiz → hech nuqsonsiz'},
        {'word': 'perspicace', 'meaning': "ziyrak, o'tkir zehnli (C1)", 'collocation': 'una mente perspicace', 'mnemonic': "Perspicace → uzoqni ko'ra oladigan"},
        {'word': 'preponderante', 'meaning': 'ustunlik qiluvchi, asosiy (B2/C1)', 'collocation': 'il fattore preponderante', 'mnemonic': "Pre-ponderante → oldin og'ir bosadigan → ustunlik"},
    ],
    'ko': ["""

old_ko = "    'ko': ["
if old_ko not in content:
    print("ERROR: 'ko': [ not found in PROFESSOR_STARTER_VOCAB area"); sys.exit(1)
content = content.replace(old_ko, NEW_VOCAB, 1)
print("1. PROFESSOR_STARTER_VOCAB: new langs added OK")

# ── 2. PROFESSOR_QUIZ_BANK: insert new languages before 'default': ──────────
NEW_QUIZ = """    'ru': [
        {
            'question': "[Grammatika Formulasi] «Несмотря на то, что» iborasining qisqa C1 muqobili qaysi?",
            'options': ['Несмотря на + существительное', 'Хотя + глагол', 'Потому что', 'Всё же + глагол'],
            'answer': 'Несмотря на + существительное',
            'note': "Formula: «Несмотря на усталость, он продолжал» = «Despite fatigue, he continued» (C1 qisqartma).",
        },
        {
            'question': "[Kollokatsiya] «способствовать» fe'li bilan eng tabiiy birikma qaysi?",
            'options': ['способствовать развитию', 'способствовать стол', 'способствовать быстро', 'способствовать книгу'],
            'answer': 'способствовать развитию',
            'note': "«Способствовать + dative» → rivojlanishga ko'maklashmoq. Dativ boshqaruvi.",
        },
    ],
    'fr': [
        {
            'question': "[Grammaire C1] Qaysi gapda «Subjonctif» to'g'ri ishlatilgan?",
            'options': [
                'Il faut que tu viennes maintenant.',
                'Il faut que tu viens maintenant.',
                'Je sais que tu viennes.',
                'Il pense que tu puisses.',
            ],
            'answer': 'Il faut que tu viennes maintenant.',
            'note': '«Il faut que» → Subjonctif talab qiladi: venir → vienne/viennes.',
        },
        {
            'question': "[Vocabulaire B2] «Néanmoins» so'zi qaysi ma'noni bildiradi?",
            'options': ['Shunga qaramasdan, baribir', 'Shuning uchun', 'Demak, xulosa qilib', 'Avvalo, birinchi navbatda'],
            'answer': 'Shunga qaramasdan, baribir',
            'note': "«Néanmoins» = nevertheless → ziddiyatni ifodalovchi C1 bog'lovchi.",
        },
    ],
    'es': [
        {
            'question': "[Gramática C1] «Si hubiera estudiado más, habría aprobado» — bu qaysi conditional?",
            'options': ['Condicional Perfecto (Type 3)', 'Condicional Simple (Type 2)', 'Presente de Subjuntivo', 'Futuro Perfecto'],
            'answer': 'Condicional Perfecto (Type 3)',
            'note': "Formula: Si + hubiera/hubiese + V3 → habría + V3 (o'tmishdagi imkonsiz shart).",
        },
    ],
    'zh': [
        {
            'question': "[语法 HSK5] «虽然…但是…» konstruksiyasining ingliz tilidagi muqobili qaysi?",
            'options': ['Although… nevertheless…', 'Because… therefore…', 'If… then…', 'Not only… but also…'],
            'answer': 'Although… nevertheless…',
            'note': '虽然 (garchi) + 但是 (lekin/ammo) → ziddiyat bog\'lovchisi. «虽然很难，但是值得。»',
        },
    ],
    'ja': [
        {
            'question': "[文法 JLPT N2] «〜にもかかわらず» iborasining ma'nosi nima?",
            'options': ['...ga qaramasdan (despite)', '...sababli (because)', '...uchun (in order to)', '...kabi (as if)'],
            'answer': '...ga qaramasdan (despite)',
            'note': '「雨にもかかわらず出かけた」= Yomg\'irga qaramasdan chiqib ketdi. C1/N2 darajasi.',
        },
    ],
    'default': ["""

old_default = "    'default': ["
if old_default not in content:
    print("ERROR: 'default': [ not found"); sys.exit(1)
content = content.replace(old_default, NEW_QUIZ, 1)
print("2. PROFESSOR_QUIZ_BANK: new lang quizzes added OK")

# ── 3. TutorController: add 3 new methods after refresh_ui ──────────────────
NEW_METHODS = '''    def export_vocab_csv(self) -> str:
        """Export the current language vocab bank as a UTF-8 CSV string."""
        import io
        import csv as csv_module
        lang_code = self.state.get('target_language', 'en')
        items = [
            v for v in (self.state.get('vocab_bank') or [])
            if v.get('lang', lang_code) == lang_code
        ]
        buffer = io.StringIO()
        writer = csv_module.writer(buffer)
        writer.writerow(["So\'z", "Ma\'nosi", 'Kollokatsiya', 'Mnemonika', 'Til'])
        for item in items:
            writer.writerow([
                item.get('word', ''),
                item.get('meaning', ''),
                item.get('collocation', ''),
                item.get('mnemonic', ''),
                item.get('lang', lang_code),
            ])
        return buffer.getvalue()

    def record_study_session(self) -> None:
        """Record today\'s study session for streak tracking."""
        from datetime import date
        today = date.today().isoformat()
        stats = workspace_store.read(\'tutor-streak.json\', {})
        if not isinstance(stats, dict):
            stats = {}
        lang = self.state.get(\'target_language\', \'en\')
        lang_stats = stats.get(lang, {\'streak\': 0, \'last_date\': \'\', \'total_days\': 0, \'sessions\': []})
        sessions = lang_stats.get(\'sessions\', [])
        if today not in sessions:
            sessions.append(today)
            sessions = sessions[-365:]
            last_date = lang_stats.get(\'last_date\', \'\')
            streak = lang_stats.get(\'streak\', 0)
            total_days = lang_stats.get(\'total_days\', 0)
            from datetime import date as date_cls, timedelta
            try:
                last = date_cls.fromisoformat(last_date) if last_date else None
            except ValueError:
                last = None
            today_date = date_cls.today()
            if last is None or (today_date - last).days > 1:
                streak = 1
            elif (today_date - last).days == 1:
                streak += 1
            total_days += 1
            lang_stats = {
                \'streak\': streak,
                \'last_date\': today,
                \'total_days\': total_days,
                \'sessions\': sessions,
            }
            stats[lang] = lang_stats
            workspace_store.write(\'tutor-streak.json\', stats)

    def get_streak_stats(self) -> dict:
        """Return streak statistics for the current language."""
        lang = self.state.get(\'target_language\', \'en\')
        stats = workspace_store.read(\'tutor-streak.json\', {})
        if not isinstance(stats, dict):
            return {\'streak\': 0, \'total_days\': 0, \'last_date\': \'\'}
        return stats.get(lang, {\'streak\': 0, \'total_days\': 0, \'last_date\': \'\'})

'''

# Insert after refresh_ui method (find "def refresh_ui" and its block end, then the blank lines before "class AcademyHubDialog")
REFRESH_UI_END = "        if hasattr(self.win, 'hud'):\n            self.win.hud.update()\n\n\nclass AcademyHubDialog"
REFRESH_UI_END_NEW = "        if hasattr(self.win, 'hud'):\n            self.win.hud.update()\n\n" + NEW_METHODS + "\nclass AcademyHubDialog"

if REFRESH_UI_END not in content:
    print("ERROR: refresh_ui end block not found"); sys.exit(1)
content = content.replace(REFRESH_UI_END, REFRESH_UI_END_NEW, 1)
print("3. TutorController: 3 new methods added OK")

# ── 4. AcademyHubDialog: add streak banner before footer = QHBoxLayout() ────
STREAK_BANNER = """        # Streak and study stats banner
        streak_stats = controller.get_streak_stats()
        streak_val = streak_stats.get('streak', 0)
        total_val = streak_stats.get('total_days', 0)
        streak_card = QFrame()
        streak_card.setStyleSheet(f'QFrame {{background:{c.PRI_GHO};border:1px solid {c.PRI_DIM};border-radius:10px;}}')
        sk_lay = QHBoxLayout(streak_card)
        sk_lay.setContentsMargins(14, 8, 14, 8)
        flame_lbl = QLabel(f"🔥 Streak: {streak_val} kun" if streak_val else "📅 Hali streak yo'q — bugun o'rganishni boshlang!")
        flame_lbl.setFont(font(10, True))
        flame_lbl.setStyleSheet(f'color:{c.PRI};border:none;background:transparent;')
        total_lbl = QLabel(f"📊 Jami: {total_val} o'quv kuni")
        total_lbl.setFont(font(9))
        total_lbl.setStyleSheet(f'color:{c.TEXT};border:none;background:transparent;')
        sk_lay.addWidget(flame_lbl)
        sk_lay.addStretch()
        sk_lay.addWidget(total_lbl)
        root.addWidget(streak_card)

        footer = QHBoxLayout()"""

OLD_FOOTER = "        footer = QHBoxLayout()\n        quiz_btn = QPushButton(\"🎯 Markaziy Ekranda 5-Savollik Sinovni Boshlash\")"
NEW_FOOTER = STREAK_BANNER + "\n        quiz_btn = QPushButton(\"🎯 Markaziy Ekranda 5-Savollik Sinovni Boshlash\")"

if OLD_FOOTER not in content:
    print("ERROR: Old footer block not found"); sys.exit(1)
content = content.replace(OLD_FOOTER, NEW_FOOTER, 1)
print("4. AcademyHubDialog: streak banner added OK")

# ── 5. Replace old footer block with new footer (add csv_btn) ────────────────
OLD_FOOTER_BLOCK = """        quiz_btn = QPushButton("🎯 Markaziy Ekranda 5-Savollik Sinovni Boshlash")
        quiz_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        quiz_btn.setStyleSheet(button_style(True) + 'QPushButton {padding:6px 14px;font-weight:600;}')
        quiz_btn.clicked.connect(lambda: (self.accept(), controller.launch_skill_quiz()))
        close_btn = QPushButton("Yopish")
        close_btn.setStyleSheet(button_style())
        close_btn.clicked.connect(self.accept)
        footer.addWidget(quiz_btn)
        footer.addStretch()
        footer.addWidget(close_btn)
        root.addLayout(footer)"""

NEW_FOOTER_BLOCK = """        quiz_btn = QPushButton("🎯 Markaziy Ekranda 5-Savollik Sinovni Boshlash")
        quiz_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        quiz_btn.setStyleSheet(button_style(True) + 'QPushButton {padding:6px 14px;font-weight:600;}')
        quiz_btn.clicked.connect(lambda: (self.accept(), controller.launch_skill_quiz()))
        csv_btn = QPushButton("📥 CSV Eksport")
        csv_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        csv_btn.setStyleSheet(button_style() + 'QPushButton {padding:6px 10px;}')
        csv_btn.setToolTip("Shaxsiy lug'atni CSV fayl sifatida saqlash (Excel, Anki uchun)")
        csv_btn.clicked.connect(lambda: self._export_csv(controller))
        close_btn = QPushButton("Yopish")
        close_btn.setStyleSheet(button_style())
        close_btn.clicked.connect(self.accept)
        footer.addWidget(quiz_btn)
        footer.addWidget(csv_btn)
        footer.addStretch()
        footer.addWidget(close_btn)
        root.addLayout(footer)"""

if OLD_FOOTER_BLOCK not in content:
    print("ERROR: old footer buttons block not found"); sys.exit(1)
content = content.replace(OLD_FOOTER_BLOCK, NEW_FOOTER_BLOCK, 1)
print("5. AcademyHubDialog: csv_btn added to footer OK")

# ── 6. Add _export_csv after _render_vocab_list ──────────────────────────────
EXPORT_CSV_METHOD = """
    def _export_csv(self, controller: 'TutorController'):
        from PyQt6.QtWidgets import QFileDialog
        from brave_language_tutor import language_display_name
        lang_name = language_display_name(controller.state)
        path, _ = QFileDialog.getSaveFileName(
            self, f"Lug'atni CSV sifatida saqlash — {lang_name}",
            f"tai_vocab_{controller.state.get('target_language', 'en')}.csv",
            "CSV fayl (*.csv)",
        )
        if not path:
            return
        try:
            csv_text = controller.export_vocab_csv()
            from pathlib import Path
            Path(path).write_text(csv_text, encoding='utf-8-sig')
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Eksport muvaffaqiyatli", f"Lug'at saqlandi:\\n{path}")
        except OSError as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Xato", f"Saqlashda xato: {e}")

"""

# Find _render_vocab_list end and the next def
RENDER_END_ANCHOR = "        self.list_layout.addStretch()\n\n\ndef build_tutor_chat_bar"
RENDER_END_NEW = "        self.list_layout.addStretch()\n" + EXPORT_CSV_METHOD + "\ndef build_tutor_chat_bar"

if RENDER_END_ANCHOR not in content:
    print("ERROR: _render_vocab_list end anchor not found"); sys.exit(1)
content = content.replace(RENDER_END_ANCHOR, RENDER_END_NEW, 1)
print("6. AcademyHubDialog: _export_csv method added OK")

open(path, 'w', encoding='utf-8').write(content)
print("All patches applied successfully!")
