"""Main script to generate all fantasy football data for Astro site."""

import sys
import os
import json

# Add scripts directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_defense_stats import generate_defense_stats_json
from generate_player_stats import generate_player_stats_json
from generate_season_stats import generate_season_stats_json
from generate_scoring_config import save_scoring_config
from generate_dst_stats import generate_dst_stats
from generate_kicker_stats import generate_kicker_stats
from generate_enriched_stats import generate_enriched_player_stats
from generate_user_lineups import generate_user_lineups
from generate_weekly_reviews import generate_weekly_reviews
from core_data import ASTRO_DATA_DIR
from core_data import (
    ASTRO_DATA_DIR,
    OUTPUT_DIR,
    SleeperAPI,
    ensure_directories,
    load_sleeper_player_lookup,
    save_json_compact,
    slim_sleeper_players,
)


GAMEDAY_CRITICAL_FILES = (
    'season_stats_dynasty.json',
    'season_stats_chopped.json',
    'user_lineups_dynasty.json',
    'user_lineups_chopped.json',
    'weekly_reviews_dynasty.json',
    'weekly_reviews_chopped.json',
)


def save_players_database():
    """Save a compact build-only Sleeper player lookup."""
    print("Saving compact Sleeper player lookup...")
    players = SleeperAPI.get_all_players()
    if players:
        lookup = slim_sleeper_players(players)
        save_json_compact(lookup, "output/players_lookup.json")
        print(f"  Saved {len(lookup)} players to build lookup")
        return lookup
    else:
        print("  ⚠️ Warning: Could not fetch player database")
        return {}


def ensure_chopped_survival_odds_stub():
    """Guarantee website/public/data/chopped_survival_odds.json exists.

    The real file is written by scripts/chopped_week.py (daily brief). The
    chopped weekly-review page statically imports it, so a stub keeps fresh
    builds working when the brief hasn't run yet in this environment.
    """
    import json
    path = os.path.join(ASTRO_DATA_DIR, "chopped_survival_odds.json")
    if os.path.exists(path):
        return
    os.makedirs(ASTRO_DATA_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"week": 0, "generated_at": None, "teams": []}, handle, indent=2)
    print("  • wrote chopped_survival_odds.json stub (no brief data yet)")


def generate_all(current_season_only: bool = False):
    """Generate all statistics.
    
    Args:
        current_season_only: If True, only refresh current season from nflverse (faster update).
    """
    print("=" * 80)
    print("FANTASY FOOTBALL DATA GENERATOR")
    print("=" * 80)
    
    if current_season_only:
        print("⚡ QUICK MODE: Only refreshing current NFL season from nflverse")
    
    try:
        save_scoring_config()
        save_players_database()  # Save Sleeper player database - needed by season stats
        
        # Generate enriched stats - either full refresh or current season only
        if current_season_only:
            import nflreadpy as nfl
            current = nfl.get_current_season()
            print(f"\nRefreshing current season ({current}) only...")
            generate_enriched_player_stats([current])
        else:
            generate_enriched_player_stats()  # Must run first - needed by player_stats
        
        generate_defense_stats_json()
        generate_player_stats_json()
        generate_dst_stats()
        generate_kicker_stats()
        generate_season_stats_json()
        generate_user_lineups()
        generate_weekly_reviews()
        ensure_chopped_survival_odds_stub()
        
        print("\n" + "=" * 80)
        print("✅ ALL DATA GENERATED SUCCESSFULLY!")
        print("=" * 80)
        print("\nFiles saved to:")
        print("  • output/")
        print("  • website/public/data/")
        
    except Exception as e:
        print(f"\n⚠️ Error generating data: {e}")
        import traceback
        traceback.print_exc()
        print("ℹ️ Some data may not have been generated (expected in preseason).")


def _remove_stale_gameday_outputs():
    """Ensure validation cannot pass using files left by an earlier run."""
    for filename in GAMEDAY_CRITICAL_FILES:
        path = os.path.join(OUTPUT_DIR, filename)
        if os.path.exists(path):
            os.remove(path)


def _validate_gameday_outputs():
    """Fail the refresh unless every live-data artifact was regenerated."""
    failures = []
    for filename in GAMEDAY_CRITICAL_FILES:
        path = os.path.join(OUTPUT_DIR, filename)
        if not os.path.exists(path):
            failures.append(f"{filename}: missing")
            continue
        try:
            with open(path, 'r', encoding='utf-8') as f:
                payload = json.load(f)
            if not isinstance(payload, dict) or not payload:
                failures.append(f"{filename}: empty or invalid root")
        except (OSError, ValueError) as exc:
            failures.append(f"{filename}: {exc}")
    if failures:
        raise RuntimeError("Gameday refresh validation failed: " + "; ".join(failures))


def generate_gameday():
    """Refresh Sleeper-driven data while carrying forward nflverse artifacts."""
    print("=" * 80)
    print("GAMEDAY DATA REFRESH")
    print("=" * 80)
    ensure_directories()
    _remove_stale_gameday_outputs()

    save_scoring_config()
    player_lookup = load_sleeper_player_lookup()
    if player_lookup:
        print(f"Reusing cached player lookup ({len(player_lookup)} players)")
    elif not save_players_database():
        raise RuntimeError("Could not load or refresh the Sleeper player lookup")

    generate_season_stats_json()
    generate_user_lineups()
    generate_weekly_reviews()
    generate_playoff_predictions()
    _validate_gameday_outputs()
    print("GAMEDAY DATA GENERATED SUCCESSFULLY!")


def generate_playoff_predictions():
    """Generate playoff predictions for dynasty league using simple season average model."""
    print("\n" + "="*80)
    print("GENERATING PLAYOFF PREDICTIONS")
    print("="*80)
    try:
        from generate_playoff_predictions_simple import main as generate_predictions
        generate_predictions()
        print("✅ Playoff predictions generated successfully!")
    except ImportError as e:
        print(f"❌ Could not import generate_playoff_predictions_simple: {e}")
        import traceback
        traceback.print_exc()
        raise
    except Exception as e:
        print(f"⚠️ Skipping playoff predictions (likely preseason): {e}")
        import traceback
        traceback.print_exc()
        print("ℹ️ This is expected before the season starts.")


def show_help():
    """Show help message."""
    print("""
Fantasy Football Data Generator

Usage:
  python generate_data.py [option]

Options:
  --all            Generate all statistics (default, full nflverse refresh)
  --quick          Quick update: current season only from nflverse (faster)
  --gameday        Sleeper-focused live refresh using carried-forward nflverse data
  --playoffs       Generate playoff predictions only (uses existing data)
  --enriched       Generate enriched player stats for v7 model only
  --defense        Generate defense statistics only
  --players        Generate player statistics only
  --dst            Generate DST statistics only
  --kickers        Generate kicker statistics only
  --season         Generate season statistics only
  --help           Show this help message

Examples:
  python generate_data.py              # Full refresh (all 6 seasons)
  python generate_data.py --quick      # Quick update (current season only)
  python generate_data.py --gameday    # Live game-day refresh
  python generate_data.py --playoffs   # Playoff predictions only
""")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        
        if arg in ['--help', '-h']:
            show_help()
        elif arg == '--enriched':
            generate_enriched_player_stats()
        elif arg == '--defense':
            generate_defense_stats_json()
        elif arg == '--players':
            generate_player_stats_json()
        elif arg == '--dst':
            generate_dst_stats()
        elif arg == '--kickers':
            generate_kicker_stats()
        elif arg == '--season':
            generate_season_stats_json()
        elif arg == '--playoffs':
            generate_playoff_predictions()
        elif arg == '--quick':
            generate_all(current_season_only=True)
            generate_playoff_predictions()
        elif arg == '--gameday':
            try:
                generate_gameday()
            except Exception as exc:
                print(f"Gameday refresh failed: {exc}")
                import traceback
                traceback.print_exc()
                sys.exit(1)
        elif arg == '--all':
            generate_all()
            generate_playoff_predictions()
        else:
            print(f"Unknown option: {arg}")
            print("Run 'python generate_data.py --help' for usage information.")
            sys.exit(1)
    else:
        generate_all()
        generate_playoff_predictions()
