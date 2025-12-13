"""Generate statistics with multiple scoring formats."""

import json
import os
from core_data import SCORING_PRESETS, ensure_directories, OUTPUT_DIR, ASTRO_DATA_DIR


def save_scoring_config():
    """Save scoring configuration for Astro site."""
    ensure_directories()
    
    config = {
        'presets': {},
        'default': 'ppr',
        'scoring_categories': [
            {'id': 'passing_yards', 'label': 'Passing Yards', 'step': 0.01},
            {'id': 'passing_tds', 'label': 'Passing TDs', 'step': 0.5},
            {'id': 'passing_2pt', 'label': 'Passing 2PT', 'step': 0.5},
            {'id': 'interceptions', 'label': 'Interceptions', 'step': 0.5},
            {'id': 'rushing_yards', 'label': 'Rushing Yards', 'step': 0.01},
            {'id': 'rushing_tds', 'label': 'Rushing TDs', 'step': 0.5},
            {'id': 'rushing_2pt', 'label': 'Rushing 2PT', 'step': 0.5},
            {'id': 'receptions', 'label': 'Receptions', 'step': 0.1},
            {'id': 'receiving_yards', 'label': 'Receiving Yards', 'step': 0.01},
            {'id': 'receiving_tds', 'label': 'Receiving TDs', 'step': 0.5},
            {'id': 'receiving_2pt', 'label': 'Receiving 2PT', 'step': 0.5},
            {'id': 'fumbles_lost', 'label': 'Fumbles Lost', 'step': 0.5}
        ]
    }
    
    # Add presets
    for preset_id, preset_data in SCORING_PRESETS.items():
        config['presets'][preset_id] = preset_data
    
    # Save to both directories
    filepath_output = os.path.join(OUTPUT_DIR, 'scoring_config.json')
    filepath_astro = os.path.join(ASTRO_DATA_DIR, 'scoring_config.json')
    
    for filepath in [filepath_output, filepath_astro]:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        print(f"  ✓ Saved: {filepath}")


if __name__ == "__main__":
    print("\nGenerating Scoring Configuration...")
    save_scoring_config()
    print("✅ Scoring configuration generated!")
