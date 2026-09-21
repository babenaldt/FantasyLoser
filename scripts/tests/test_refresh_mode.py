import os
import sys
import unittest


SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from select_refresh_mode import select_refresh_mode  # noqa: E402


class RefreshModeTests(unittest.TestCase):
    def test_live_schedules_use_gameday_mode(self):
        schedules = (
            '17,47 20-23 * * 4',
            '17,47 13-23 * * 0',
            '17,47 20-23 * * 1',
        )
        for schedule in schedules:
            with self.subTest(schedule=schedule):
                self.assertEqual(
                    select_refresh_mode('schedule', schedule),
                    'gameday',
                )

    def test_nightly_and_postgame_schedules_use_quick_mode(self):
        self.assertEqual(
            select_refresh_mode('schedule', '17 3 * * *'),
            'quick',
        )
        self.assertEqual(
            select_refresh_mode('schedule', '17 0 * * 1,2,5'),
            'quick',
        )

    def test_manual_full_refresh_uses_all_mode(self):
        self.assertEqual(
            select_refresh_mode('workflow_dispatch', full_refresh=True),
            'all',
        )

    def test_push_and_default_manual_runs_use_quick_mode(self):
        self.assertEqual(select_refresh_mode('push'), 'quick')
        self.assertEqual(
            select_refresh_mode('workflow_dispatch', full_refresh=False),
            'quick',
        )


if __name__ == '__main__':
    unittest.main()
