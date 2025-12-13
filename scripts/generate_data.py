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


def generate_all():
    """Generate all statistics."""
    print("=" * 80)
    print("FANTASY FOOTBALL DATA GENERATOR")
    print("=" * 80)
    
    try:
        save_scoring_config()
        generate_defense_stats_json()
        generate_player_stats_json()
        generate_dst_stats()
        generate_kicker_stats()
        generate_season_stats_json()
        
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


def show_help():
    """Show help message."""
    print("""
Fantasy Football Data Generator

Usage:
  python generate_data.py [option]

Options:
  --all            Generate all statistics (default)
  --defense        Generate defense statistics only
  --players        Generate player statistics only
  --dst            Generate DST statistics only
  --kickers        Generate kicker statistics only
  --season         Generate season statistics only
  --help           Show this help message

Examples:
  python generate_data.py
  python generate_data.py --defense
  python generate_data.py --players
""")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        
        if arg in ['--help', '-h']:
            show_help()
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
        elif arg == '--all':
            generate_all()
        else:
            print(f"Unknown option: {arg}")
            print("Run 'python generate_data.py --help' for usage information.")
            sys.exit(1)
    else:
        generate_all()
