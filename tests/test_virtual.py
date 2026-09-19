"""Native tablet sizing and recovery independent of physical EDID modes."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_display import beam, DisplaySystem
from beam_display import DisplayError, load, save
from beam_virtual import OUTPUT, readable_scale


class NativeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.system = DisplaySystem()
        self.beam = beam.Beam(home=Path(self.temp.name), system=self.system)
        self.fit = self.beam.display
        self.v = self.fit.virtual
        self.physical = dict(self.system.monitors[0], id=0, mirrorOf='none', activeWorkspace=dict(id=1, name='1'))
        self.virtual = dict(self.physical, name=OUTPUT, id=1, width=2048, height=1536, scale=2, x=8000,
                            activeWorkspace=dict(id=-1337, name='beam-idle'))
        self.rows = [self.physical, self.virtual]
        self.spaces = [dict(id=1, name='1', monitor='DP-1'), dict(id=-1337, name='beam-idle', monitor=OUTPUT)]
        self.v.monitors = lambda: copy.deepcopy(self.rows)
        self.v.workspaces = lambda: copy.deepcopy(self.spaces)
        self.v.command = lambda code: None
        self.v.focus = lambda *args, **kwargs: None
        def apply(name, mode):
            row = next(m for m in self.rows if m['name'] == name)
            row.update({k:mode[k] for k in ['width','height','refreshRate','x','y','scale','transform']})
            if 'mirror' in mode:
                row['mirrorOf'] = str(next(m['id'] for m in self.rows if m['name']==mode['mirror'])) if mode['mirror'] else 'none'
        self.fit.apply = apply
        def move(w, monitor):
            next(s for s in self.spaces if s['id']==w['id'])['monitor'] = monitor
        self.v.move = move
        self.beam.processes = lambda: [dict(pid=123, identity='456')]
        save(self.v.preferences, dict(entry=str(self.beam.entry),output=OUTPUT))

    def start(self, w=2752,h=2064):
        return self.fit.start(dict(SUNSHINE_CLIENT_WIDTH=str(w),SUNSHINE_CLIENT_HEIGHT=str(h),SUNSHINE_CLIENT_FPS='60'))

    def test_native_pixels_and_readable_workspace_for_different_ipads(self):
        for w,h in [(2752,2064),(2732,2048),(2420,1668),(2360,1640),(2266,1488),(2048,1536)]:
            self.assertEqual(readable_scale(w,h),2)
        self.assertEqual(readable_scale(1280,720),1)
        self.assertEqual(readable_scale(1920,1080),1.5)

    def test_every_ipad_profile_captures_native_size_and_restores_ultrawide(self):
        from beam_ipads import PROFILES
        original = copy.deepcopy(self.physical)
        for profile in PROFILES:
            with self.subTest(profile=profile['id']):
                target = self.fit.select_ipad(profile['id'])
                session = self.start(profile['width'], profile['height'])
                self.assertEqual(tuple(session['target']), target)
                self.assertEqual((session['applied']['width'], session['applied']['height']), target[:2])
                self.assertIn('Moonlight matches', self.fit.status()['resolutionDetail'])
                self.assertEqual(self.fit.status()['ipadProfile'], profile['id'])
                self.fit.stop(session['token'])
                self.assertEqual(self.physical, original)

    def test_reselecting_same_ipad_pixels_preserves_custom_text_scale(self):
        self.fit.set_resolution('2732x2048', 4/3)
        self.fit.select_ipad('pro-2732')
        self.assertEqual(self.fit.fixed_scale(), 4/3)
        self.fit.select_ipad('air-2732')
        self.assertEqual(self.fit.fixed_scale(), 4/3)

    def test_ipad_selection_is_persistent_and_only_changes_next_session(self):
        session = self.start(2732,2048)
        self.fit.select_ipad('mini-2266')
        self.assertEqual(next(m for m in self.rows if m['name']==OUTPUT)['width'],2732)
        new_beam = beam.Beam(home=Path(self.temp.name), system=self.system)
        self.assertEqual(new_beam.display.fixed_size(), (2266,1488,60))
        self.fit.stop(session['token'])
        session = self.start(2266,1488)
        self.assertEqual(session['applied']['width'],2266)
        self.fit.stop(session['token'])

    def test_bad_profile_and_preinstall_selection_preserve_preferences(self):
        self.fit.select_ipad('pro-2732')
        before = self.fit.preferences.read_bytes()
        with self.assertRaises(DisplayError):
            self.fit.select_ipad('../../bad-profile')
        self.assertEqual(self.fit.preferences.read_bytes(), before)
        self.v.preferences.unlink()
        with self.assertRaises(DisplayError):
            self.fit.select_ipad('air-2360')
        self.assertEqual(self.fit.preferences.read_bytes(), before)

    def test_full_clears_model_selection(self):
        self.fit.select_ipad('pro-2732')
        self.fit.set_resolution('auto')
        self.assertEqual(self.fit.status()['ipadProfile'], '')
        self.assertEqual(self.fit.status()['moonlightSetting'], 'Full')

    def test_exact_client_size_ignores_physical_mode_limits_and_restores(self):
        original=copy.deepcopy(self.physical)
        s=self.start()
        self.assertEqual(s['applied']['mode'],'2752x2064@60')
        self.assertEqual(self.physical['width'],5120)
        self.assertEqual(self.physical['mirrorOf'],'1')
        self.assertEqual(self.spaces[0]['monitor'],OUTPUT)
        self.assertIn('200% text',self.fit.status()['resolutionDetail'])
        self.fit.stop(s['token'])
        self.assertEqual(self.physical,original)
        self.assertEqual(self.spaces[0]['monitor'],'DP-1')
        self.assertFalse(load(self.fit.state))

    def test_failed_transition_rolls_back_with_durable_recovery(self):
        apply=self.fit.apply
        seen=[]
        def fail(name,mode):
            self.assertTrue(load(self.fit.state))
            seen.append(name)
            if name=='DP-1' and mode.get('mirror'):
                raise DisplayError('test mirror failure')
            return apply(name,mode)
        with patch.object(self.fit,'apply',side_effect=fail):
            with self.assertRaises(DisplayError):self.start()
        self.assertEqual(self.spaces[0]['monitor'],'DP-1')
        self.assertEqual(self.physical['width'],5120)
        self.assertFalse(load(self.fit.state))

    def test_restoration_failure_retains_state_for_retry(self):
        self.start()
        with patch.object(self.v,'move',side_effect=DisplayError('test move failure')):
            with self.assertRaises(DisplayError):self.fit.stop()
        self.assertIn('Restore display',load(self.fit.state)['error'])
        self.fit.stop()
        self.assertFalse(load(self.fit.state))

    def test_manual_physical_change_is_preserved_and_windows_return(self):
        self.start()
        self.physical.update(mirrorOf='none',width=1920,height=1080)
        self.fit.stop()
        self.assertEqual(self.physical['width'],1920)
        self.assertEqual(self.spaces[0]['monitor'],'DP-1')

    def test_source_disconnection_retains_recovery(self):
        self.start()
        self.rows.remove(self.physical)
        with self.assertRaises(DisplayError):self.fit.stop()
        self.assertTrue(load(self.fit.state))

    def test_new_workspace_returns_with_original_workspaces(self):
        self.start()
        self.spaces.append(dict(id=9,name='9',monitor=OUTPUT))
        self.virtual['activeWorkspace']=dict(id=9,name='9')
        self.fit.stop()
        self.assertEqual(self.spaces[-1]['monitor'],'DP-1')

    def test_multiple_sources_require_explicit_selection(self):
        self.rows.append(dict(self.physical,name='DP-2',id=2))
        with self.assertRaises(DisplayError):self.start()
        self.beam.sun.mkdir(parents=True)
        (self.beam.sun/'sunshine.conf').write_text('output_name = DP-2\n')
        self.assertEqual(self.v.source()['name'],'DP-2')

    def test_disabled_laptop_panel_does_not_make_source_ambiguous(self):
        self.rows.insert(0,dict(self.physical,name='eDP-1',id=2,disabled=True))
        self.assertEqual(self.v.source()['name'],'DP-1')

    def test_native_fixed_size_is_validated_without_an_edid_limit(self):
        self.fit.set_resolution('2752x2064')
        s=self.start(1920,1080)
        self.assertEqual(s['requested'],[1920,1080,60])
        self.assertEqual(s['target'],[2752,2064,60])
        self.assertIn('Moonlight requests 1920×1080',self.fit.status()['resolutionDetail'])
        with self.assertRaises(DisplayError):self.fit.set_resolution('99999x2064')

    def test_custom_middle_ground_keeps_full_workspace_instead_of_enlarging_text(self):
        self.fit.set_resolution('1920x1440')
        session = self.start(1920, 1440)
        self.assertEqual(session['applied']['scale'], 1)
        self.assertEqual(self.virtual['width'] / self.virtual['scale'], 1920)
        self.assertEqual(self.virtual['height'] / self.virtual['scale'], 1440)
        self.assertIn('100% scale', self.fit.status()['recommendedRes'])
        self.fit.stop()
        self.fit.set_resolution('auto')
        self.assertEqual(self.start()['applied']['scale'], 2)

    def test_native_2732_middle_ground_has_exact_aspect_and_2049_workspace(self):
        self.fit.set_resolution('2732x2048', 4 / 3)
        session = self.start(2732, 2048)
        mode = session['applied']
        self.assertEqual((mode['width'], mode['height']), (2732, 2048))
        self.assertEqual((mode['width'] / mode['scale'], mode['height'] / mode['scale']), (2049, 1536))
        self.assertIn('133% scale', self.fit.status()['recommendedRes'])
        self.assertTrue(self.fit.matches(dict(mode, scale=1.3333334), mode))
        self.assertFalse(self.fit.matches(dict(mode, scale=1.5), mode))
        self.fit.stop()
        self.assertEqual(self.physical['scale'], 1)
        self.assertEqual(self.fit.fixed_scale(), 4 / 3)

    def test_invalid_custom_scale_preserves_previous_preference(self):
        self.fit.set_resolution('2732x2048', 4 / 3)
        for value in ('nan', 'inf', 'bad', 0, 3, 1.5):
            with self.subTest(value=value), self.assertRaises(DisplayError):
                self.fit.set_resolution('2732x2048', value)
            self.assertEqual(self.fit.fixed_scale(), 4 / 3)

    def test_missing_virtual_display_does_not_resize_physical(self):
        self.rows.remove(self.virtual)
        with self.assertRaises(DisplayError):self.start()
        self.assertEqual(self.physical['width'],5120)
        self.assertFalse(load(self.fit.state))

if __name__=='__main__':unittest.main()
