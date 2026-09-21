import json
import os
import sys
import tempfile
import unittest
from unittest import mock


SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import generate_data  # noqa: E402


class GamedayModeTests(unittest.TestCase):
    def _write_outputs(self, output_dir, filenames):
        for filename in filenames:
            with open(os.path.join(output_dir, filename), 'w', encoding='utf-8') as f:
                json.dump({'generated': True}, f)

    def test_gameday_regenerates_all_critical_outputs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = os.path.join(temp_dir, 'output')
            astro_dir = os.path.join(temp_dir, 'public')
            os.makedirs(output_dir)
            os.makedirs(astro_dir)

            def season():
                self._write_outputs(
                    output_dir,
                    ('season_stats_dynasty.json', 'season_stats_chopped.json'),
                )

            def lineups():
                self._write_outputs(
                    output_dir,
                    ('user_lineups_dynasty.json', 'user_lineups_chopped.json'),
                )

            def reviews():
                self._write_outputs(
                    output_dir,
                    ('weekly_reviews_dynasty.json', 'weekly_reviews_chopped.json'),
                )

            patches = (
                mock.patch.object(generate_data, 'OUTPUT_DIR', output_dir),
                mock.patch.object(generate_data, 'ASTRO_DATA_DIR', astro_dir),
                mock.patch.object(generate_data, 'ensure_directories'),
                mock.patch.object(generate_data, 'save_scoring_config'),
                mock.patch.object(generate_data, 'load_sleeper_player_lookup', return_value={'1': {}}),
                mock.patch.object(generate_data, 'generate_season_stats_json', side_effect=season),
                mock.patch.object(generate_data, 'generate_user_lineups', side_effect=lineups),
                mock.patch.object(generate_data, 'generate_weekly_reviews', side_effect=reviews),
                mock.patch.object(generate_data, 'generate_playoff_predictions'),
            )
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8]:
                generate_data.generate_gameday()

            for filename in generate_data.GAMEDAY_CRITICAL_FILES:
                self.assertTrue(os.path.exists(os.path.join(output_dir, filename)))

    def test_gameday_fails_when_a_generator_omits_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = os.path.join(temp_dir, 'output')
            astro_dir = os.path.join(temp_dir, 'public')
            os.makedirs(output_dir)
            os.makedirs(astro_dir)

            def incomplete_season():
                self._write_outputs(output_dir, ('season_stats_dynasty.json',))

            patches = (
                mock.patch.object(generate_data, 'OUTPUT_DIR', output_dir),
                mock.patch.object(generate_data, 'ASTRO_DATA_DIR', astro_dir),
                mock.patch.object(generate_data, 'ensure_directories'),
                mock.patch.object(generate_data, 'save_scoring_config'),
                mock.patch.object(generate_data, 'load_sleeper_player_lookup', return_value={'1': {}}),
                mock.patch.object(generate_data, 'generate_season_stats_json', side_effect=incomplete_season),
                mock.patch.object(generate_data, 'generate_user_lineups'),
                mock.patch.object(generate_data, 'generate_weekly_reviews'),
                mock.patch.object(generate_data, 'generate_playoff_predictions'),
            )
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8]:
                with self.assertRaises(RuntimeError):
                    generate_data.generate_gameday()


if __name__ == '__main__':
    unittest.main()
