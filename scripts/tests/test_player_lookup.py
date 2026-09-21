import json
import os
import sys
import tempfile
import unittest


SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from core_data import (  # noqa: E402
    PLAYER_LOOKUP_FIELDS,
    load_sleeper_player_lookup,
    save_json_compact,
    slim_sleeper_players,
)
from generate_weekly_reviews import player_name, player_position  # noqa: E402


class PlayerLookupTests(unittest.TestCase):
    def setUp(self):
        self.full_players = {
            '123': {
                'player_id': '123',
                'first_name': 'Test',
                'last_name': 'Player',
                'full_name': 'Test Player',
                'position': 'WR',
                'team': 'BUF',
                'status': 'Active',
                'metadata': {'large': 'unused'},
                'search_full_name': 'testplayer',
            },
            456: {
                'first_name': 'Other',
                'last_name': 'Player',
                'position': 'RB',
                'team': None,
                'status': 'Inactive',
            },
        }

    def test_slim_lookup_preserves_all_ids_and_required_fields(self):
        lookup = slim_sleeper_players(self.full_players)

        self.assertEqual(set(lookup), {'123', '456'})
        self.assertEqual(set(lookup['123']), set(PLAYER_LOOKUP_FIELDS))
        self.assertEqual(lookup['456']['player_id'], '456')
        self.assertNotIn('metadata', lookup['123'])
        self.assertNotIn('search_full_name', lookup['123'])

    def test_compact_lookup_round_trip(self):
        lookup = slim_sleeper_players(self.full_players)
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, 'players_lookup.json')
            save_json_compact(lookup, path)
            loaded = load_sleeper_player_lookup(paths=(path,))

            self.assertEqual(loaded, lookup)
            with open(path, 'r', encoding='utf-8') as f:
                raw = f.read()
            self.assertNotIn('\n', raw)

    def test_legacy_list_fallback_and_name_resolution(self):
        legacy = [
            {
                'player_id': '789',
                'first_name': 'Legacy',
                'last_name': 'Name',
                'full_name': 'Legacy Name',
                'position': 'TE',
            }
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, 'players_data.json')
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(legacy, f)
            loaded = load_sleeper_player_lookup(paths=(path,))

        self.assertEqual(player_name(loaded, 789), 'Legacy Name')
        self.assertEqual(player_position(loaded, 789), 'TE')


if __name__ == '__main__':
    unittest.main()
