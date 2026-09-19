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

    def test_missing_virtual_display_does_not_resize_physical(self):
        self.rows.remove(self.virtual)
        with self.assertRaises(DisplayError):self.start()
        self.assertEqual(self.physical['width'],5120)
        self.assertFalse(load(self.fit.state))

if __name__=='__main__':unittest.main()
