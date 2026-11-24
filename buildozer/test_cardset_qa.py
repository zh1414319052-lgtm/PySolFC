"""Focused recovery tests. Set PYSOLFC_CARDSET_APK to the actual APK to audit.

Run from the checkout: python -m unittest buildozer.test_cardset_qa -v
"""

import copy
import io
import os
from pathlib import Path
import symtable
import tarfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from zipfile import ZipFile

import pysollib.app as app_module
import pysollib.options as options_module
from pysollib.androidlocale import language_for_primary
from pysollib.app import Application
from pysollib.cardsetparser import parse_cardset_config
from pysollib.options import Options
from pysollib.resource import CSI, Cardset, CardsetManager


@unittest.skipUnless(os.environ.get('PYSOLFC_CARDSET_APK'),
                     'Set PYSOLFC_CARDSET_APK to the final/pinned APK')
class CardsetRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with ZipFile(os.environ['PYSOLFC_CARDSET_APK']) as z:
            with tarfile.open(fileobj=io.BytesIO(z.read('assets/private.tar'))) as t:
                cls.configs = [t.extractfile(m).read().decode('utf-8-sig')
                               for m in t if '/cardset-' in m.name
                               and m.name.endswith('/config.txt')]

    def setUp(self):
        self.app = object.__new__(Application)
        self.app.game = None
        self.app.top = None
        self.app.cardset = None
        self.app.cardset_manager = CardsetManager()
        for text in self.configs:
            cs = Cardset()
            cs.update(parse_cardset_config(text.splitlines()).__dict__)
            self.app.cardset_manager.register(cs)
        self.app.opt = Options()
        with patch.object(options_module, 'TOOLKIT', 'kivy'), \
                patch.object(options_module, 'USE_PIL', False):
            self.app.opt.setDefaults()

    def gi(self, category=CSI.TYPE_FRENCH, subtype=0, ncards=52):
        return SimpleNamespace(id=2, name='QA game', category=category,
                               subcategory=subtype, ncards=ncards)

    def deck(self, name):
        return self.app.cardset_manager.getByName(name)

    def test_every_default_and_subtype_exists_and_is_compatible(self):
        for pil, toolkit in ((True, 'tk'), (False, 'kivy'), (False, 'tk')):
            top = Mock()
            top.winfo_screenwidth.return_value = 640
            top.winfo_screenheight.return_value = 480
            top.winfo_screendepth.return_value = 32
            opt = Options()
            with patch.object(options_module, 'USE_PIL', pil), \
                    patch.object(options_module, 'TOOLKIT', toolkit):
                opt.setDefaults(top)
            for category, subtypes in opt.cardset.items():
                for subtype, (name, _) in subtypes.items():
                    with self.subTest(pil=pil, toolkit=toolkit,
                                      category=category, subtype=subtype):
                        cs = self.deck(name)
                        self.assertIsNotNone(cs, name)
                        if category:
                            self.assertIsNone(self.app.checkCompatibleCardsetType(
                                self.gi(category, subtype, 30), cs)[1])

    def test_valid_current_choice_is_retained(self):
        cs = self.deck('Neo')
        self.assertIs(self.app.getCompatibleCardset(self.gi(), cs)[0], cs)

    def test_saved_game_choice_and_back_are_retained(self):
        gi = self.gi(CSI.TYPE_HANAFUDA)
        cs = self.deck('Hanafuda 200 Years')
        self.app.opt.cardset[(1, gi.id)] = {0: (cs.name, cs.backname)}
        before = copy.deepcopy(self.app.opt.cardset)
        self.assertIs(self.app.getCompatibleCardset(gi, None)[0], cs)
        self.assertEqual(before, self.app.opt.cardset)

    def test_incompatible_saved_category_recovers_standard(self):
        self.app.opt.cardset[CSI.TYPE_FRENCH][0] = ('Gnome Mahjongg 1', '')
        with patch.object(options_module, 'TOOLKIT', 'kivy'), \
                patch.object(options_module, 'USE_PIL', False):
            cs = self.app.getCompatibleCardset(
                self.gi(), self.deck('Gnome Mahjongg 1'))[0]
        self.assertEqual(cs.name, 'Standard')
        self.assertEqual(self.app.opt.cardset[CSI.TYPE_FRENCH][0][0],
                         'Gnome Mahjongg 1')

    def test_missing_saved_and_default_use_first_compatible(self):
        gi = self.gi(CSI.TYPE_HANAFUDA)
        self.app.opt.cardset[gi.category][0] = ('Kintengu', '')
        defaults = SimpleNamespace(cardset={gi.category: {0: ('missing', '')}},
                                   setDefaults=lambda top: None)
        with patch.object(app_module, 'Options', return_value=defaults):
            cs = self.app.getCompatibleCardset(gi, None)[0]
        self.assertEqual(cs.name, 'Hanafuda 200 Years')

    def test_switch_without_game_never_opens_dialog(self):
        gi = self.gi(CSI.TYPE_HANAFUDA)
        self.app.getGameInfo = Mock(return_value=gi)
        self.app.cardset = self.deck('Gnome Mahjongg 1')
        self.app.loadCardset = Mock(return_value=1)
        with patch.object(app_module, 'MfxMessageDialog') as dialog:
            self.assertEqual(self.app.requestCompatibleCardsetType(2), 1)
        dialog.assert_not_called()
        self.assertEqual(self.app.loadCardset.call_args.kwargs['update'], 1)

    def test_no_compatible_decks_without_game_is_safe(self):
        self.app.getGameInfo = Mock(return_value=self.gi())
        for cs in self.app.cardset_manager.getAll():
            cs.error = 1
        with patch.object(app_module, 'MfxMessageDialog') as dialog:
            self.assertEqual(self.app.requestCompatibleCardsetType(2), -1)
        dialog.assert_not_called()

    def test_failed_load_retries_another_compatible_deck(self):
        self.app.getGameInfo = Mock(return_value=self.gi(CSI.TYPE_HANAFUDA))
        attempted = []

        def load(cs, **kwargs):
            attempted.append(cs.name)
            if len(attempted) == 1:
                cs.error = 1
                return 0
            return 1

        self.app.loadCardset = load
        self.assertEqual(self.app.requestCompatibleCardsetType(2), 1)
        self.assertEqual(len(attempted), 2)
        self.assertNotEqual(attempted[0], attempted[1])

    def test_matching_missing_current_deck_does_not_crash(self):
        cs = self.app.getCompatibleCardset(
            self.gi(CSI.TYPE_MATCHING, ncards=24), None)[0]
        self.assertIsNotNone(cs)

    def test_select_dialog_without_game_can_cancel(self):
        dialog = SimpleNamespace(key=-1, status=1, button=1)
        with patch.object(app_module, 'SelectCardsetDialogWithPreview',
                          return_value=dialog):
            self.assertIsNone(self.app.selectCardset('QA', -1))

    def test_select_dialog_exception_restores_pause(self):
        game = SimpleNamespace(pause=False)
        game.doPause = lambda: setattr(game, 'pause', not game.pause)
        self.app.game = game
        with patch.object(app_module, 'SelectCardsetDialogWithPreview',
                          side_effect=RuntimeError('QA cancellation')):
            with self.assertRaises(RuntimeError):
                self.app.selectCardset('QA', -1)
        self.assertFalse(game.pause)

    def test_restored_id_is_checked_before_game_construction(self):
        self.app.top = Mock()
        self.app.nextgame = SimpleNamespace(loadedgame=SimpleNamespace(id=12345))
        self.app.getGameClass = Mock(return_value=Mock())
        self.app.getGameInfo = Mock(return_value=SimpleNamespace(id=12345))
        self.app.intro = SimpleNamespace(progress=None)
        self.app.requestCompatibleCardsetType = Mock(return_value=0)
        self.app.constructGame = Mock(side_effect=RuntimeError('construction'))
        with self.assertRaisesRegex(RuntimeError, 'construction'):
            self.app.runGame(2)
        self.app.requestCompatibleCardsetType.assert_called_once_with(12345, None)


class PrimaryLanguageTests(unittest.TestCase):
    def test_startup_translation_function_is_not_shadowed(self):
        path = Path(__file__).resolve().parents[1] / 'pysollib' / 'main.py'
        symbols = symtable.symtable(path.read_text(encoding='utf-8'),
                                   str(path), 'exec')
        startup = next(s for s in symbols.get_children()
                       if s.get_name() == 'pysol_init')
        self.assertFalse(startup.lookup('_').is_local())

    def test_primary_language_mapping(self):
        for tag in ('zh', 'zh-CN', 'zh_TW', 'zh-Hant-HK', 'ZH-SG'):
            self.assertEqual(language_for_primary(tag), 'zh_CN')
        for tag in ('en', 'en-US', 'ja-JP', 'de-DE', '', None):
            self.assertEqual(language_for_primary(tag), 'en')


if __name__ == '__main__':
    unittest.main()
