"""Generate defense/DST statistics from nflverse team stats and schedules."""

import json
from datetime import datetime
import nflreadpy as nfl
from core_data import calculate_fantasy_points, SCORING_PRESETS, ensure_directories, ROSTERABLE_POSITIONS, OUTPUT_DIR, ASTRO_DATA_DIR, save_json


def generate_defense_stats_json():
    """Generate defense statistics and save to JSON."""
    print("\nGenerating Defense Statistics...")
    ensure_directories()
    
    # Load NFL data
    print("  Loading NFL weekly player stats...")
    nfl_season = nfl.get_current_season()
    season = [nfl_season]
    
    try:
        weekly_stats = nfl.load_player_stats(season)
        print(f"  Detected current NFL season: {nfl_season}")
        print(f"  Loaded weekly data for {nfl_season} season ({len(weekly_stats)} records)")
    except Exception as e:
        print(f"  Error loading NFL data: {e}")
        return
    
    # Calculate defensive statistics
    print("  Calculating defensive statistics...")
    defense_stats = {}
    
    # Process weekly stats
    for row in weekly_stats.iter_rows(named=True):
        opponent = row.get('opponent_team')
        if not opponent:
            continue
        
        position = row.get('position', '')
        if position not in ROSTERABLE_POSITIONS:
            continue
        
        player_team = row.get('team')
        
        # Initialize defense stats if needed
        if opponent not in defense_stats:
            defense_stats[opponent] = {
                'team': opponent,
                'games': 0,
                'total_points_allowed': 0,
                'qb_points_allowed': 0,
                'rb_points_allowed': 0,
                'wr_points_allowed': 0,
                'te_points_allowed': 0,
                'rushing_yards_allowed': 0,
                'rushing_tds_allowed': 0,
                'receiving_yards_allowed': 0,
                'receiving_tds_allowed': 0,
                'passing_tds_allowed': 0,
                'weeks_played': set(),
                'weekly_breakdown': {},
                # Track individual player scores per week for "Top 1" calculations
                'weekly_player_scores': {} 
            }
        
        week = row.get('week')
        if week:
            defense_stats[opponent]['weeks_played'].add(week)
            
            # Initialize weekly stats if needed
            if week not in defense_stats[opponent]['weekly_breakdown']:
                defense_stats[opponent]['weekly_breakdown'][week] = {
                    'week': week,
                    'opponent': player_team if player_team else 'N/A',
                    'total_points': 0,
                    'qb_points': 0,
                    'rb_points': 0,
                    'wr_points': 0,
                    'te_points': 0,
                    # Raw stats for client-side calculation
                    'raw_stats': {
                        'qb': {'passing_yards': 0, 'passing_tds': 0, 'interceptions': 0, 'rushing_yards': 0, 'rushing_tds': 0, 'fumbles_lost': 0},
                        'rb': {'rushing_yards': 0, 'rushing_tds': 0, 'receptions': 0, 'receiving_yards': 0, 'receiving_tds': 0, 'fumbles_lost': 0},
                        'wr': {'receptions': 0, 'receiving_yards': 0, 'receiving_tds': 0, 'rushing_yards': 0, 'rushing_tds': 0, 'fumbles_lost': 0},
                        'te': {'receptions': 0, 'receiving_yards': 0, 'receiving_tds': 0, 'fumbles_lost': 0}
                    },
                    'rushing_yards': 0,
                    'receiving_yards': 0,
                    'rushing_tds': 0,
                    'receiving_tds': 0,
                    'passing_tds': 0
                }
                # Initialize weekly player scores
                defense_stats[opponent]['weekly_player_scores'][week] = {
                    'QB': [], 'RB': [], 'WR': [], 'TE': []
                }

            # Update opponent if we have a valid player_team and current is N/A
            elif player_team and defense_stats[opponent]['weekly_breakdown'][week]['opponent'] == 'N/A':
                defense_stats[opponent]['weekly_breakdown'][week]['opponent'] = player_team
        
        # Calculate fantasy points
        pts = calculate_fantasy_points(row)
        
        # Track individual player score for Top 1 calculation
        if week and position in ['QB', 'RB', 'WR', 'TE']:
             defense_stats[opponent]['weekly_player_scores'][week][position].append(pts)

        # Track stats (season totals)
        defense_stats[opponent]['total_points_allowed'] += pts
        
        if position == 'QB':
            defense_stats[opponent]['qb_points_allowed'] += pts
            defense_stats[opponent]['passing_tds_allowed'] += (row.get('passing_tds', 0) or 0)
        elif position == 'RB':
            defense_stats[opponent]['rb_points_allowed'] += pts
        elif position == 'WR':
            defense_stats[opponent]['wr_points_allowed'] += pts
        elif position == 'TE':
            defense_stats[opponent]['te_points_allowed'] += pts
        
        # Yards and TDs
        defense_stats[opponent]['rushing_yards_allowed'] += (row.get('rushing_yards', 0) or 0)
        defense_stats[opponent]['rushing_tds_allowed'] += (row.get('rushing_tds', 0) or 0)
        defense_stats[opponent]['receiving_yards_allowed'] += (row.get('receiving_yards', 0) or 0)
        defense_stats[opponent]['receiving_tds_allowed'] += (row.get('receiving_tds', 0) or 0)
        
        # Track weekly stats
        if week and week in defense_stats[opponent]['weekly_breakdown']:
            weekly = defense_stats[opponent]['weekly_breakdown'][week]
            weekly['total_points'] += pts
            
            # Store raw stats per position for client-side calculation
            pos_key = position.lower()
            if pos_key in weekly['raw_stats']:
                raw = weekly['raw_stats'][pos_key]
                
                if position == 'QB':
                    raw['passing_yards'] += (row.get('passing_yards', 0) or 0)
                    raw['passing_tds'] += (row.get('passing_tds', 0) or 0)
                    raw['interceptions'] += (row.get('interceptions', 0) or 0)
                    raw['rushing_yards'] += (row.get('rushing_yards', 0) or 0)
                    raw['rushing_tds'] += (row.get('rushing_tds', 0) or 0)
                    raw['fumbles_lost'] += (row.get('fumbles_lost', 0) or 0)
                elif position in ['RB', 'WR']:
                    raw['rushing_yards'] += (row.get('rushing_yards', 0) or 0)
                    raw['rushing_tds'] += (row.get('rushing_tds', 0) or 0)
                    raw['receiving_yards'] += (row.get('receiving_yards', 0) or 0)
                    raw['receiving_tds'] += (row.get('receiving_tds', 0) or 0)
                    raw['receptions'] += (row.get('receptions', 0) or 0)
                    raw['fumbles_lost'] += (row.get('fumbles_lost', 0) or 0)
                elif position == 'TE':
                    raw['receptions'] += (row.get('receptions', 0) or 0)
                    raw['receiving_yards'] += (row.get('receiving_yards', 0) or 0)
                    raw['receiving_tds'] += (row.get('receiving_tds', 0) or 0)
                    raw['fumbles_lost'] += (row.get('fumbles_lost', 0) or 0)
            
            if position == 'QB':
                weekly['qb_points'] += pts
                weekly['passing_tds'] += (row.get('passing_tds', 0) or 0)
            elif position == 'RB':
                weekly['rb_points'] += pts
            elif position == 'WR':
                weekly['wr_points'] += pts
            elif position == 'TE':
                weekly['te_points'] += pts
            
            weekly['rushing_yards'] += (row.get('rushing_yards', 0) or 0)
            weekly['rushing_tds'] += (row.get('rushing_tds', 0) or 0)
            weekly['receiving_yards'] += (row.get('receiving_yards', 0) or 0)
            weekly['receiving_tds'] += (row.get('receiving_tds', 0) or 0)
    
        # Calculate games played and per-game averages
    defenses_list = []
    for team, stats in defense_stats.items():
        stats['games'] = len(stats['weeks_played'])
        del stats['weeks_played']
        
        # Calculate Top 1 Averages (WR1, RB1, TE1, QB1)
        top1_totals = {'QB': 0, 'RB': 0, 'WR': 0, 'TE': 0}
        
        # Also calculate weekly Top 1 for the breakdown
        for week_num, week_data in stats['weekly_breakdown'].items():
            player_scores = stats['weekly_player_scores'].get(week_num, {})
            
            for pos in ['QB', 'RB', 'WR', 'TE']:
                scores = player_scores.get(pos, [])
                top_score = max(scores) if scores else 0
                
                # Add to weekly breakdown
                week_data[f'{pos.lower()}_top1_points'] = top_score
                
                # Add to season total
                top1_totals[pos] += top_score
        
        # Remove the temporary player scores structure
        del stats['weekly_player_scores']

        # Convert weekly_breakdown dict to sorted list
        stats['weekly_breakdown'] = sorted(
            stats['weekly_breakdown'].values(),
            key=lambda x: x['week']
        )
        
        # Calculate per-game averages
        if stats['games'] > 0:
            stats['avg_points_per_game'] = stats['total_points_allowed'] / stats['games']
            stats['qb_ppg'] = stats['qb_points_allowed'] / stats['games']
            stats['rb_ppg'] = stats['rb_points_allowed'] / stats['games']
            stats['wr_ppg'] = stats['wr_points_allowed'] / stats['games']
            stats['te_ppg'] = stats['te_points_allowed'] / stats['games']
            
            # Top 1 PPG
            stats['qb1_ppg'] = top1_totals['QB'] / stats['games']
            stats['rb1_ppg'] = top1_totals['RB'] / stats['games']
            stats['wr1_ppg'] = top1_totals['WR'] / stats['games']
            stats['te1_ppg'] = top1_totals['TE'] / stats['games']
        else:
            stats['avg_points_per_game'] = 0
            stats['qb_ppg'] = 0
            stats['rb_ppg'] = 0
            stats['wr_ppg'] = 0
            stats['te_ppg'] = 0
            stats['qb1_ppg'] = 0
            stats['rb1_ppg'] = 0
            stats['wr1_ppg'] = 0
            stats['te1_ppg'] = 0
        
        defenses_list.append(stats)
    
    print(f"  Calculated stats for {len(defenses_list)} defenses")
    
    # Prepare output data
    output_data = {
        'season': str(nfl_season),
        'generated_at': __import__('datetime').datetime.now().isoformat(),
        'defenses': defenses_list
    }
    
    # Save JSON files
    save_json(output_data, f"{OUTPUT_DIR}/defense_stats.json")
    save_json(output_data, f"{ASTRO_DATA_DIR}/defense_stats.json")
    
    print("✅ Defense statistics generated successfully!")


if __name__ == "__main__":
    generate_defense_stats_json()
