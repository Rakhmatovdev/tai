"""Command discoverability, draft safety, local storage and actual AI payloads."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication,QMessageBox
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_ollama as fixtures
from core import workspace_store,command_store,model_router
from core.slash_commands import COMMANDS,INDEX,ALIASES,CODE_COMMANDS,category,matches,parse
from core.ollama_chat import Settings
from memory import config_manager


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.location=patch.object(workspace_store,'directory',return_value=self.root);self.location.start()
    def tearDown(self):self.location.stop();self.temp.cleanup()

    def test_registry_has_66_real_prompts_or_actions_and_translations(self):
        from brave_i18n import translate
        self.assertEqual(len(COMMANDS),66);self.assertEqual(len(INDEX),66)
        for row in COMMANDS:
            self.assertNotEqual(bool(row.action),bool(row.instruction),row.name)
            self.assertIn(category(row),('ai','code','chat','tools'))
            for lang in ('en','ru'):self.assertNotEqual(translate(row.description,lang),row.description,row.name)
        self.assertTrue({'debug','fix','refactor','optimize','tests','document','sql','regex','code'}<=CODE_COMMANDS)

    def test_aliases_and_multilingual_description_search(self):
        for alias,name in ALIASES.items():self.assertEqual(parse('/'+alias)[0].name,name)
        self.assertIn('debug',[row.name for row in matches('/cause error')])
        self.assertIn('debug',[row.name for row in matches('/причину ошибки')])
        self.assertIn('debug',[row.name for row in matches('/xatoning sababini')])
        self.assertEqual(matches('/debug question'),[])
        self.assertEqual(matches('/missing command'),[])

    def test_categories_favorites_and_recent_ranking(self):
        for group in ('ai','code','chat','tools'):
            rows=matches('/',group);self.assertTrue(rows);self.assertTrue(all(category(row)==group for row in rows))
        command_store.used('extract');command_store.used('debug');command_store.favorite('copy')
        prefs=command_store.preferences();rows=matches('/',favorites=prefs['favorites'],recents=prefs['recent'])
        self.assertEqual([row.name for row in rows[:3]],['copy','debug','extract'])
        self.assertEqual([row.name for row in matches('/','favorites',prefs['favorites'])],['copy'])
        command_store.favorite('copy');self.assertEqual(command_store.preferences()['favorites'],[])

    def test_preferences_bound_names_and_never_save_prompt_content(self):
        for row in COMMANDS:command_store.used(row.name)
        command_store.used('PRIVATE PROMPT')
        self.assertEqual(len(command_store.preferences()['recent']),12)
        self.assertNotIn('PRIVATE', (self.root/'slash-preferences.json').read_text())
        workspace_store.write('slash-preferences.json',{'favorites':['debug','bad','debug',42],'recent':'bad'})
        self.assertEqual(command_store.preferences(),{'favorites':['debug'],'recent':[]})

    def test_template_crud_limits_and_malformed_storage(self):
        identity=command_store.save_snippet(None,' Plan ',' /plan site ')
        command_store.save_snippet(identity,'Updated','/debug code')
        self.assertEqual(len(command_store.snippets()),1);self.assertEqual(command_store.snippets()[0]['text'],'/debug code')
        for title,text in (('','x'),('x',''),('x'*81,'x'),('x','a'*10001)):
            with self.assertRaises(ValueError):command_store.save_snippet(None,title,text)
        command_store.delete_snippet(identity);self.assertEqual(command_store.snippets(),[])
        workspace_store.write('prompt-snippets.json',[{},None,{'id':1,'title':'bad','text':'x'}]);self.assertEqual(command_store.snippets(),[])

    def test_bounded_template_and_favorite_capacity_allows_updates(self):
        identity=None
        for i in range(30):identity=command_store.save_snippet(None,str(i),'prompt')
        with self.assertRaises(ValueError):command_store.save_snippet(None,'31','prompt')
        command_store.save_snippet(identity,'updated','text')
        for row in COMMANDS[:20]:command_store.favorite(row.name)
        with self.assertRaises(ValueError):command_store.favorite(COMMANDS[20].name)
        command_store.favorite(COMMANDS[0].name);self.assertEqual(len(command_store.preferences()['favorites']),19)

    def test_last_answer_is_scoped_to_chat_and_ignores_user_text(self):
        from brave_history import HistoryStore
        store=HistoryStore()
        for chat,role,text in [('a','assistant','old'),('b','assistant','other'),('a','assistant','new'),('a','user','latest question')]:store.append(chat,role,text,'now')
        self.assertEqual(store.last_answer('a'),'new');self.assertEqual(store.last_answer('empty'),'');store.close()

    def test_templates_and_preferences_are_in_backup_allowlist(self):
        from core.app_recovery import FILES
        self.assertTrue({'slash-preferences.json','prompt-snippets.json'}<=FILES)


class UITests(unittest.TestCase):
    setUpClass=classmethod(fixtures.LocalUITests.setUpClass.__func__)
    setUp=fixtures.LocalUITests.setUp
    wait_for=fixtures.LocalUITests.wait_for
    start_local=fixtures.LocalUITests.start_local

    def tearDown(self):
        for attr in ('_prompt_snippets','_slash_help','_slash_center','_slash_history','_ai_studio'):
            dialog=getattr(self.win,attr,None)
            if dialog:
                if attr=='_prompt_snippets':dialog.original=(dialog.title.text(),dialog.text.toPlainText())
                dialog.reject()
        QTest.qWait(10);fixtures.LocalUITests.tearDown(self)

    def action(self,text):
        from brave_slash import prepare_send
        self.win._input.setText(text);return prepare_send(self.win,text)

    def answer(self,text):self.win._features.store.append(self.win._features.chat_id,'assistant',text,'now')

    def test_popup_filter_favorite_mouse_and_empty_keyboard_keep_composer(self):
        self.win._input.setFocus();self.win._input.setText('/');QTest.qWait(20)
        menu=self.win._slash_menu
        QTest.mouseClick(menu.filters['code'],Qt.MouseButton.LeftButton);self.assertTrue(menu.popup.isVisible())
        self.assertTrue(all(menu.list.item(i).data(Qt.ItemDataRole.UserRole) in CODE_COMMANDS for i in range(menu.list.count())))
        QTest.mouseClick(menu.star,Qt.MouseButton.LeftButton);self.assertTrue(command_store.preferences()['favorites'])
        QTest.mouseClick(menu.filters['favorites'],Qt.MouseButton.LeftButton);self.assertEqual(menu.list.count(),1)
        self.win._input.setText('/no-match');QTest.qWait(10);self.assertTrue(menu.popup.isVisible());self.assertEqual(menu.list.count(),0)
        QTest.keyClick(self.win._input,Qt.Key.Key_Down);QTest.keyClick(self.win._input,Qt.Key.Key_Escape)
        self.assertEqual(self.win._input.text(),'/no-match')

    def test_searchable_help_inserts_without_execution_and_favorites_persist(self):
        self.action('/help');dialog=self.win._slash_help;dialog.search.setText('cause error')
        self.assertEqual(dialog.list.count(),1);dialog.favorite();self.assertIn('debug',command_store.preferences()['favorites'])
        with patch.object(self.win,'on_text_command') as send:dialog.choose();send.assert_not_called()
        self.assertEqual(self.win._input.text(),'/debug ')

    def test_templates_save_insert_draft_and_reopen(self):
        self.action('/snippets');dialog=self.win._prompt_snippets;dialog.title.setText('My plan');dialog.text.setPlainText('/plan Build a demo');dialog.save()
        self.win._input.setText('Existing draft')
        with patch.object(self.win,'on_text_command') as send:dialog.insert();send.assert_not_called()
        self.assertEqual(self.win._input.text(),'Existing draft\n\n/plan Build a demo')
        self.action('/snippets');self.assertIs(self.win._prompt_snippets,dialog)
        self.assertEqual(command_store.snippets()[0]['title'],'My plan')
        dialog.new();dialog.list.setCurrentRow(0)
        self.assertEqual(dialog.text.toPlainText(),'/plan Build a demo')

    def test_template_permissions_are_checked_at_read_save_and_insert(self):
        self.win._capabilities.policy['permissions']['files']=False;self.action('/snippets');dialog=self.win._prompt_snippets
        self.assertEqual(dialog.list.count(),0);dialog.title.setText('Hidden');dialog.text.setPlainText('secret')
        dialog.save();dialog.insert();self.assertEqual(command_store.snippets(),[]);self.assertEqual(self.win._input.text(),'')

    def test_unsaved_template_selection_and_close_can_be_cancelled(self):
        command_store.save_snippet(None,'saved','old')
        self.action('/snippets');dialog=self.win._prompt_snippets;dialog.title.setText('unsaved');dialog.text.setPlainText('draft')
        with patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.No):
            dialog.list.setCurrentRow(0);dialog.reject()
        self.assertTrue(dialog.isVisible());self.assertEqual(dialog.text.toPlainText(),'draft')

    def test_last_source_expands_only_explicit_marker_and_retains_translation_target(self):
        self.answer('Budget 42. Ali Monday.')
        self.assertEqual(self.action('/shorten @last'),'/shorten Budget 42. Ali Monday.')
        self.assertEqual(self.action('/translate en @last'),'/translate en Budget 42. Ali Monday.')
        self.assertEqual(self.action('/explain use @last as a token'),'/explain use @last as a token')

    def test_missing_last_answer_and_oversized_source_preserve_original_draft(self):
        self.assertIsNone(self.action('/shorten @last'));self.assertEqual(self.win._input.text(),'/shorten @last')
        self.start_local();self.answer('x'*100001);self.win._input.setText('/shorten @last')
        with patch.object(self.win,'on_text_command') as send:self.win._send();send.assert_not_called()
        self.assertEqual(self.win._input.text(),'/shorten @last')

    def test_busy_chat_rejects_new_retry_edit_memory_without_losing_draft(self):
        original=self.win._features.chat_id;self.win._features.started=1.0
        for name in ('new','retry','edit','memory'):
            self.action('/'+name);self.assertEqual(self.win._input.text(),'/'+name);self.assertEqual(self.win._features.chat_id,original)
        self.win._features.started=None

    def test_new_chat_consumes_action_without_saving_it_as_previous_draft(self):
        old=self.win._features.chat_id;self.action('/new')
        self.assertNotEqual(self.win._features.chat_id,old);self.assertEqual(self.win._features.drafts[old],'');self.assertEqual(self.win._input.text(),'')

    def test_native_actions_open_actual_tabs_and_history_search(self):
        for name,index in [('project',1),('knowledge',3),('permissions',0)]:
            self.action('/'+name);self.assertEqual(self.win._slash_center.tabs.currentIndex(),index)
        self.action('/history keyword');self.assertEqual(self.win._slash_history.search.text(),'keyword')
        for name in ('dictionary','desktop'):
            self.action('/'+name);self.assertIs(self.win._ai_studio.tabs.currentWidget(),self.win._ai_studio.tab_widgets[name])

    def test_copy_uses_completed_answer_and_action_arguments_fail_explicitly(self):
        self.answer('Budget 42.');self.action('/copy');self.assertEqual(QApplication.clipboard().text(),'Budget 42.')
        self.action('/copy unexpected');self.assertEqual(self.win._input.text(),'/copy unexpected')
        self.assertNotIn('unexpected',command_store.preferences()['recent'])

    def test_settings_and_remaining_native_handlers(self):
        targets={'settings ai':'brave_settings.open_settings','diagnostics':'brave_diagnostics.open_diagnostics',
                 'memory':'brave_conversation.memory_dialog','focus':'brave_chat.toggle_chat_focus'}
        for text,target in targets.items():
            with patch(target) as handler:self.action('/'+text);handler.assert_called_once()
        self.action('/settings bad');self.assertEqual(self.win._input.text(),'/settings bad')
        with patch.object(self.win,'_toggle_fullscreen') as handler:self.action('/fullscreen');handler.assert_called_once()
        with patch.object(self.win._drop_zone,'_browse') as handler:self.action('/attach');handler.assert_called_once()
        with patch('brave_ai_studio.open_studio') as handler:
            self.action('/warmup');handler.assert_called_once_with(self.win,'screen');handler.return_value.pages['screen'].warmup.assert_called_once()

    def test_retry_and_edit_preserve_handler_new_draft(self):
        self.win._features.store.append(self.win._features.chat_id,'user','question','now')
        for name in ('retry','edit'):
            def branch(win,edit):win._input.setText('new draft');return True
            with patch('brave_conversation.branch_last',side_effect=branch) as handler:
                self.action('/'+name);handler.assert_called_once_with(self.win,edit=name=='edit')
            self.assertEqual(self.win._input.text(),'new draft')

    def test_code_modes_really_route_and_send_instruction_without_tools(self):
        with fixtures.FakeOllama() as server:
            Settings(server.url,'local',autostart=False).save('ollama');config_manager._patch_config(local_tools_enabled=True);runtime=self.start_local()
            for name in sorted(CODE_COMMANDS-{'code'}):
                before=len(runtime.history)
                model_router._cache.clear()
                with patch('core.model_router.recommend',return_value=[]) as route:
                    runtime.submit('/'+name+' example',[]);self.wait_for(lambda:not runtime.busy and len(runtime.history)==before+2)
                    route.assert_called()
                    self.assertEqual(route.call_args.args[1],'code')
                payload=[body for path,body in server.requests if path=='/api/chat'][-1]
                self.assertIn(INDEX[name].instruction,payload['messages'][0]['content']);self.assertNotIn('tools',payload)
            self.assertEqual(Settings.read().profile,'balanced')

    def test_extract_requests_json_and_saves_no_markdown_citation(self):
        with fixtures.FakeOllama() as server:
            server.chunks=[{'message':{'content':'{"name":"Ali","amount":42}'},'done':True}]
            Settings(server.url,'local',autostart=False).save('ollama');runtime=self.start_local()
            runtime.submit('/extract Name Ali, amount 42',[]);self.wait_for(lambda:not runtime.busy and len(runtime.history)==2)
            payload=[body for path,body in server.requests if path=='/api/chat'][-1];self.assertEqual(payload['format'],'json')
            self.assertEqual(json.loads(runtime.history[-1]['content']),{'name':'Ali','amount':42})

    def test_extract_invalid_or_truncated_json_never_becomes_completed_answer(self):
        with fixtures.FakeOllama() as server:
            Settings(server.url,'local',autostart=False).save('ollama');runtime=self.start_local()
            for text in ('{"amount":','{"amount":NaN}'):
                server.chunks=[{'message':{'content':text},'done':True}]
                runtime.submit('/extract amount 42',[]);self.wait_for(lambda:not runtime.busy)
                self.assertEqual(runtime.history,[]);self.assertEqual(self.win._features.store.last_answer(self.win._features.chat_id),'')
                self.assertEqual(runtime.last_request['status'],'error')
                self.assertEqual(workspace_store.read('model-performance.json',[]),[])

    def test_library_templates_and_popup_render_in_all_themes_and_languages(self):
        import brave_ui
        from brave_command_library import open_library
        for theme in ('dark','light','hacker'):
            for language in ('uz','en','ru'):
                brave_ui.set_theme(self.win,theme,persist=False);brave_ui.set_language(self.win,language,persist=False)
                library=open_library(self.win);snippets=open_library(self.win,snippets=True)
                self.win.activateWindow();self.win._input.setFocus();self.win._input.setText('/');QTest.qWait(30)
                objects={'library':library,'snippets':snippets,'menu':self.win._slash_menu.popup}
                for key,widget in objects.items():
                    self.assertLessEqual(widget.height(),self.win.screen().availableGeometry().height())
                    target=os.environ.get('BRAVE_COMMAND_PREVIEWS')
                    if target:
                        folder=Path(target);folder.mkdir(parents=True,exist_ok=True);widget.grab().save(str(folder/f'{key}-{theme}-{language}.png'))
                library.reject();snippets.reject();QTest.qWait(10)


if __name__=='__main__':unittest.main()
