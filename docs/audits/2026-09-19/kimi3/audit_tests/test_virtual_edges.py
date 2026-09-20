"""Virtual display recovery edges: disabled source, removed output, session errors."""
import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parents[1] / "tests"))
sys.path.insert(0, str(Path(__file__).parents[1] / "lib"))

from audit_helpers import load_beam
from test_display import DisplaySystem
from beam_display import DisplayError, load, save
from beam_virtual import OUTPUT, readable_scale
from beam_ipads import PROFILES

beam = load_beam()


class VirtualEdgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.system = DisplaySystem()
        self.beam = beam.Beam(home=Path(self.temp.name), system=self.system)
        self.fit = self.beam.display
        self.v = self.fit.virtual
        self.physical = dict(self.system.monitors[0], id=0, mirrorOf='none',
                             activeWorkspace=dict(id=1, name='1'))
        self.virtual = dict(self.physical, name=OUTPUT, id=1, width=2048, height=1536,
                            scale=2, x=8000, activeWorkspace=dict(id=-1337, name='beam-idle'))
        self.rows = [self.physical, self.virtual]
        self.spaces = [dict(id=1, name='1', monitor='DP-1'),
                       dict(id=-1337, name='beam-idle', monitor=OUTPUT)]
        self.v.monitors = lambda: copy.deepcopy(self.rows)
        self.v.workspaces = lambda: copy.deepcopy(self.spaces)
        self.v.command = lambda code: None
        self.v.focus = lambda *args, **kwargs: None
        def apply(name, mode):
            row = next(m for m in self.rows if m['name'] == name)
            row.update({k: mode[k] for k in ['width', 'height', 'refreshRate', 'x', 'y', 'scale', 'transform']})
            if 'mirror' in mode:
                row['mirrorOf'] = str(next(m['id'] for m in self.rows if m['name'] == mode['mirror'])) if mode['mirror'] else 'none'
        self.fit.apply = apply
        self.v.move = lambda w, mon: next(s for s in self.spaces if s['id'] == w['id']).update(monitor=mon)
        self.beam.processes = lambda: [dict(pid=1, identity='1')]
        save(self.v.preferences, dict(entry=str(self.beam.entry), output=OUTPUT))

    def start(self, w='2732', h='2048'):
        return self.fit.start(dict(SUNSHINE_CLIENT_WIDTH=w, SUNSHINE_CLIENT_HEIGHT=h,
                                   SUNSHINE_CLIENT_FPS='60'))

    def test_disabled_source_leaks_value_error_instead_of_display_error(self):
        self.start()
        self.physical['disabled'] = True
        self.physical['mirrorOf'] = 'none'
        # BUG: idle() computes max() over an empty iterable when every
        # non-virtual monitor is disabled. ValueError escapes restore(),
        # skipping the session error annotation ("Use Restore display.")
        # that DisplayError paths record.
        with self.assertRaises(ValueError):
            self.fit.stop()
        self.assertTrue(load(self.fit.state))  # recovery state is at least retained

    def test_removed_virtual_output_restores_without_mirror_undo(self):
        session = self.start()
        self.rows.remove(self.virtual)
        self.physical['mirrorOf'] = 'none'
        result = self.fit.stop(session['token'])
        self.assertTrue(result)
        self.assertFalse(load(self.fit.state))

    def test_every_profile_scale_is_compositor_clean(self):
        for p in PROFILES:
            with self.subTest(profile=p['id']):
                scale = readable_scale(p['width'], p['height'])
                self.assertEqual(self.fit.validate_scale((p['width'], p['height'], 60), scale), scale)

    def test_start_with_two_sunshine_processes_fails_before_any_change(self):
        self.beam.processes = lambda: [dict(pid=1, identity='1'), dict(pid=2, identity='2')]
        with self.assertRaises(DisplayError):
            self.start()
        self.assertEqual(self.physical['width'], 5120)
        self.assertFalse(load(self.fit.state))

    def test_second_session_supersedes_crashed_first_and_restores_once(self):
        first = self.start('2732', '2048')
        stale_token = first['token']
        second = self.start('2048', '1536')  # previous session restored, then re-applied
        self.fit.stop(stale_token)  # old token must not touch the new session
        self.assertTrue(load(self.fit.state))
        self.fit.stop(second['token'])
        self.assertFalse(load(self.fit.state))
        self.assertEqual(self.physical['mirrorOf'], 'none')

    def test_corrupt_virtual_preferences_block_repair_truthfully(self):
        self.v.preferences.write_text('{broken')
        with self.assertRaises(DisplayError):
            self.v.install()

    def test_conflicting_output_name_is_refused(self):
        self.v.preferences.unlink()
        with self.assertRaises(DisplayError):
            self.v.install()


if __name__ == '__main__':
    unittest.main()
