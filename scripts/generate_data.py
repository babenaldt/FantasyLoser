"""Main script to generate all fantasy football data for Astro site."""

import sys
import os

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
        
        print("\n" + "=" * 80)
        print("✅ ALL DATA GENERATED SUCCESSFULLY!")
        print("=" * 80)
        print("\nFiles saved to:")
        print("  • output/")
        print("  • website/public/data/")
        
    except Exception as e:
        print(f"\n❌ Error generating data: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


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
        raise  # Fail the build
    except Exception as e:
        print(f"❌ Error generating playoff predictions: {e}")
        import traceback
        traceback.print_exc()
        raise  # Fail the build


def show_help():
    """Show help message."""
    print("""
Fantasy Football Data Generator

Usage:
  python generate_data.py [option]

Options:
  --all            Generate all statistics (default, full nflverse refresh)
  --quick          Quick update: current season only from nflverse (faster)
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
