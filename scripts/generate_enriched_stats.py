"""
Generate enriched player stats for v7 prediction model.

This script creates the enriched_player_stats.json file required by player_score_model_v7.py.
It fetches comprehensive NFL data from nflverse/nflreadr and computes cumulative stats
through each week with advanced metrics like EPA, CPOE, red zone opportunities, etc.

Key features:
- Cumulative stats through each week (for model training)
- Advanced passing metrics (CPOE, EPA, air yards)
- Red zone and goal line opportunities (for TD prediction)
- Receiving advanced stats (target share, air yards share, WOPR)
- Fumbles data from play-by-play
- Opponent information for matchup features
"""

import json
import os
import nflreadpy as nfl
from collections import defaultdict
from typing import Dict, List, Any, Optional
from core_data import OUTPUT_DIR, ensure_directories


def generate_enriched_player_stats(seasons: Optional[List[int]] = None):
    """
    Generate enriched player statistics database.
    
    Args:
        seasons: List of seasons to process. If None, uses last 6 seasons.
    """
    print("\n" + "=" * 80)
    print("GENERATING ENRICHED PLAYER STATS FOR V7 MODEL")
    print("=" * 80)
    
    ensure_directories()
    
    # Default to last 6 seasons if not specified
    if seasons is None:
        current_season = nfl.get_current_season()
        seasons = list(range(current_season - 5, current_season + 1))
    
    print(f"\nProcessing seasons: {seasons}")
    
    all_seasons_data = []
    
    for season in seasons:
        print(f"\n{'='*80}")
        print(f"Processing {season} season...")
        print(f"{'='*80}")
        
        season_data = process_season(season)
        if season_data:
            all_seasons_data.append(season_data)
    
    # Save to output
    output_data = {
        'generated_at': __import__('datetime').datetime.now().isoformat(),
        'seasons': all_seasons_data
    }
    
    output_path = os.path.join(OUTPUT_DIR, 'enriched_player_stats.json')
    print(f"\n{'='*80}")
    print(f"Saving enriched stats to {output_path}...")
    
    with open(output_path, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"✅ Enriched player stats generated successfully!")
    print(f"   Total seasons: {len(all_seasons_data)}")
    total_players = sum(len(s['players']) for s in all_seasons_data)
    print(f"   Total player-seasons: {total_players}")
    print(f"{'='*80}\n")


def process_season(season: int) -> Optional[Dict[str, Any]]:
    """Process a single season and return enriched data."""
    
    try:
        # Load weekly player stats
        print(f"  Loading weekly player stats...")
        weekly_stats = nfl.load_player_stats([season])
        
        # Load play-by-play for advanced stats
        print(f"  Loading play-by-play data...")
        pbp = nfl.load_pbp([season])
        
        # Load schedules for opponent data
        print(f"  Loading schedules...")
        schedules = nfl.load_schedules([season])
        
        print(f"  Loaded {len(weekly_stats)} weekly stat records")
        print(f"  Loaded {len(pbp)} play-by-play records")
        
    except Exception as e:
        print(f"  ❌ Error loading data for {season}: {e}")
        return None
    
    # Build schedule lookup: (team, week) -> opponent
    schedule_lookup = {}
    for row in schedules.iter_rows(named=True):
        week = row.get('week')
        home = row.get('home_team')
        away = row.get('away_team')
        if week and home and away:
            schedule_lookup[(home, week)] = away
            schedule_lookup[(away, week)] = home
    
    # Calculate advanced stats from play-by-play
    print(f"  Calculating advanced stats from play-by-play...")
    advanced_stats = calculate_advanced_stats_from_pbp(pbp)
    
    # Calculate red zone stats
    print(f"  Calculating red zone stats...")
    red_zone_stats = calculate_red_zone_stats(pbp)
    
    # Calculate fumbles from play-by-play (more reliable than weekly stats)
    print(f"  Calculating fumbles from play-by-play...")
    fumbles_data = calculate_fumbles_from_pbp(pbp)
    
    # Organize by player and calculate cumulative stats
    print(f"  Organizing cumulative stats by player...")
    player_data = defaultdict(lambda: defaultdict(dict))
    
    # Process weekly stats
    for row in weekly_stats.iter_rows(named=True):
        player_id = row.get('player_id')
        if not player_id:
            continue
        
        position = row.get('position', '')
        if position not in ['QB', 'RB', 'WR', 'TE']:
            continue
        
        week = row.get('week')
        if not week or week > 18:
            continue
        
        team = row.get('team')
        
        # Store weekly stats
        week_stats = {
            # Basic counting stats
            'attempts': row.get('attempts', 0) or 0,
            'completions': row.get('completions', 0) or 0,
            'passing_yards': row.get('passing_yards', 0) or 0,
            'passing_tds': row.get('passing_tds', 0) or 0,
            'passing_interceptions': row.get('interceptions', 0) or 0,
            'sacks_suffered': row.get('sacks', 0) or 0,
            'carries': row.get('carries', 0) or 0,
            'rushing_yards': row.get('rushing_yards', 0) or 0,
            'rushing_tds': row.get('rushing_tds', 0) or 0,
            'targets': row.get('targets', 0) or 0,
            'receptions': row.get('receptions', 0) or 0,
            'receiving_yards': row.get('receiving_yards', 0) or 0,
            'receiving_tds': row.get('receiving_tds', 0) or 0,
            
            # Advanced stats from weekly data
            'passing_air_yards': row.get('passing_air_yards', 0) or 0,
            'receiving_air_yards': row.get('receiving_air_yards', 0) or 0,
            'target_share': row.get('target_share', 0) or 0,
            'air_yards_share': row.get('air_yards_share', 0) or 0,
            'wopr': row.get('wopr', 0) or 0,
            
            # Will be populated from advanced_stats
            'passing_epa': 0,
            'passing_cpoe': 0,
            'receiving_epa': 0,
            
            # Red zone stats (will be populated from red_zone_stats)
            'rz_touches': 0,
            'rz_tds': 0,
            'gl_touches': 0,
            'gl_tds': 0,
            
            # Fumbles (will be populated from fumbles_data)
            'fumbles_lost': 0,
        }
        
        # Add advanced stats from PBP if available
        player_week_key = (player_id, week)
        if player_week_key in advanced_stats:
            adv = advanced_stats[player_week_key]
            week_stats['passing_epa'] = adv.get('passing_epa', 0)
            week_stats['passing_cpoe'] = adv.get('cpoe', 0)
            week_stats['receiving_epa'] = adv.get('receiving_epa', 0)
        
        # Add red zone stats
        if player_week_key in red_zone_stats:
            rz = red_zone_stats[player_week_key]
            week_stats['rz_touches'] = rz.get('rz_touches', 0)
            week_stats['rz_tds'] = rz.get('rz_tds', 0)
            week_stats['gl_touches'] = rz.get('gl_touches', 0)
            week_stats['gl_tds'] = rz.get('gl_tds', 0)
        
        # Add fumbles
        if player_week_key in fumbles_data:
            week_stats['fumbles_lost'] = fumbles_data[player_week_key]
        
        player_data[player_id][week] = {
            'week': week,
            'team': team,
            'opponent': schedule_lookup.get((team, week)),
            'stats': week_stats
        }
    
    # Calculate cumulative stats through each week
    print(f"  Calculating cumulative stats through each week...")
    players_list = []
    
    for player_id, weeks_data in player_data.items():
        if not weeks_data:
            continue
        
        # Sort weeks
        sorted_weeks = sorted(weeks_data.keys())
        
        # Get player info from first week
        first_week_data = weeks_data[sorted_weeks[0]]
        player_name = None
        position = None
        
        # Get player name and position from weekly_stats
        for row in weekly_stats.iter_rows(named=True):
            if row.get('player_id') == player_id:
                player_name = row.get('player_display_name', 'Unknown')
                position = row.get('position', '')
                break
        
        if not player_name or position not in ['QB', 'RB', 'WR', 'TE']:
            continue
        
        # Calculate cumulative stats
        cumulative_by_week = []
        cumulative_stats = defaultdict(float)
        games_played = 0
        
        for week in sorted_weeks:
            week_data = weeks_data[week]
            week_stats = week_data['stats']
            
            # Add this week's stats to cumulative
            for stat_name, value in week_stats.items():
                cumulative_stats[stat_name] += value
            
            games_played += 1
            
            # Store cumulative stats through this week
            cumulative_record = {
                'through_week': week,
                'games_played': games_played,
                'team': week_data['team'],
                'opponent': week_data['opponent'],
                'stats': dict(cumulative_stats)
            }
            
            cumulative_by_week.append(cumulative_record)
        
        player_record = {
            'player_id': player_id,
            'player_name': player_name,
            'position': position,
            'cumulative_by_week': cumulative_by_week
        }
        
        players_list.append(player_record)
    
    print(f"  ✅ Processed {len(players_list)} players for {season}")
    
    return {
        'season': season,
        'players': players_list
    }


def calculate_advanced_stats_from_pbp(pbp) -> Dict[tuple, Dict[str, float]]:
    """
    Calculate advanced stats (EPA, CPOE) from play-by-play data.
    
    Returns:
        Dict[(player_id, week)] -> {'passing_epa': float, 'cpoe': float, 'receiving_epa': float}
    """
    stats = defaultdict(lambda: {'passing_epa': 0.0, 'cpoe': 0.0, 'receiving_epa': 0.0, 'passing_plays': 0, 'receiving_plays': 0})
    
    for row in pbp.iter_rows(named=True):
        week = row.get('week')
        if not week or week > 18:
            continue
        
        play_type = row.get('play_type', '')
        
        # Passing stats
        if play_type in ['pass', 'qb_kneel', 'qb_spike']:
            passer_id = row.get('passer_player_id')
            if passer_id:
                epa = row.get('epa', 0) or 0
                cpoe = row.get('cpoe', 0) or 0
                
                key = (passer_id, week)
                stats[key]['passing_epa'] += epa
                stats[key]['cpoe'] += cpoe
                stats[key]['passing_plays'] += 1
        
        # Receiving stats
        if play_type == 'pass':
            receiver_id = row.get('receiver_player_id')
            if receiver_id:
                epa = row.get('epa', 0) or 0
                
                key = (receiver_id, week)
                stats[key]['receiving_epa'] += epa
                stats[key]['receiving_plays'] += 1
    
    return dict(stats)


def calculate_red_zone_stats(pbp) -> Dict[tuple, Dict[str, int]]:
    """
    Calculate red zone and goal line opportunities from play-by-play.
    
    Red zone: Inside opponent's 20-yard line
    Goal line: Inside opponent's 5-yard line
    
    Returns:
        Dict[(player_id, week)] -> {'rz_touches': int, 'rz_tds': int, 'gl_touches': int, 'gl_tds': int}
    """
    stats = defaultdict(lambda: {'rz_touches': 0, 'rz_tds': 0, 'gl_touches': 0, 'gl_tds': 0})
    
    for row in pbp.iter_rows(named=True):
        week = row.get('week')
        if not week or week > 18:
            continue
        
        yardline = row.get('yardline_100')
        if yardline is None:
            continue
        
        # Red zone: 20 yards or less from end zone
        in_red_zone = yardline <= 20
        # Goal line: 5 yards or less from end zone
        in_goal_line = yardline <= 5
        
        play_type = row.get('play_type', '')
        
        # Rushing attempts
        if play_type == 'run':
            rusher_id = row.get('rusher_player_id')
            if rusher_id:
                key = (rusher_id, week)
                
                if in_red_zone:
                    stats[key]['rz_touches'] += 1
                    if row.get('touchdown') == 1:
                        stats[key]['rz_tds'] += 1
                
                if in_goal_line:
                    stats[key]['gl_touches'] += 1
                    if row.get('touchdown') == 1:
                        stats[key]['gl_tds'] += 1
        
        # Passing attempts (targets)
        elif play_type == 'pass':
            receiver_id = row.get('receiver_player_id')
            if receiver_id:
                key = (receiver_id, week)
                
                if in_red_zone:
                    stats[key]['rz_touches'] += 1
                    if row.get('touchdown') == 1:
                        stats[key]['rz_tds'] += 1
                
                if in_goal_line:
                    stats[key]['gl_touches'] += 1
                    if row.get('touchdown') == 1:
                        stats[key]['gl_tds'] += 1
    
    return dict(stats)


def calculate_fumbles_from_pbp(pbp) -> Dict[tuple, int]:
    """
    Calculate fumbles lost from play-by-play data.
    More reliable than weekly stats which have data quality issues.
    
    Returns:
        Dict[(player_id, week)] -> fumbles_lost count
    """
    fumbles = defaultdict(int)
    
    for row in pbp.iter_rows(named=True):
        week = row.get('week')
        if not week or week > 18:
            continue
        
        # Check if fumble was lost
        fumble_lost = row.get('fumble_lost')
        if fumble_lost != 1:
            continue
        
        # Determine who fumbled
        fumbler_id = None
        
        play_type = row.get('play_type', '')
        if play_type == 'run':
            fumbler_id = row.get('rusher_player_id')
        elif play_type == 'pass':
            # Could be passer or receiver
            # If it's a sack fumble, it's the passer
            if row.get('sack') == 1:
                fumbler_id = row.get('passer_player_id')
            else:
                # Otherwise it's the receiver
                fumbler_id = row.get('receiver_player_id')
        
        if fumbler_id:
            key = (fumbler_id, week)
            fumbles[key] += 1
    
    return dict(fumbles)


if __name__ == '__main__':
    import sys
    
    # Allow specifying seasons as command line arguments
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        
        if arg == '--current-season':
            # Only refresh current season (avoids re-pulling historical data)
            current_season = nfl.get_current_season()
            print(f"Refreshing current season only: {current_season}")
            generate_enriched_player_stats([current_season])
        elif arg in ['--help', '-h']:
            print("""
Generate Enriched Player Stats

Usage:
  python generate_enriched_stats.py                  # All 6 seasons (full refresh)
  python generate_enriched_stats.py --current-season # Current season only (fast update)
  python generate_enriched_stats.py 2024 2025        # Specific seasons

Options:
  --current-season  Only refresh the current NFL season (faster, no historical re-pull)
  --help, -h        Show this help message
  <years>           Space-separated list of season years
""")
        else:
            try:
                seasons = [int(s) for s in sys.argv[1:]]
                generate_enriched_player_stats(seasons)
            except ValueError:
                print("Error: Please provide valid season years (e.g., 2024 2025)")
                sys.exit(1)
    else:
        # Default: last 6 seasons
        generate_enriched_player_stats()
