#!/usr/bin/env python3
"""
Generate kicker statistics from nflverse team stats and rosters.
"""

import json
import os
from datetime import datetime
import nflreadpy as nfl
from core_data import calculate_fantasy_points, SCORING_PRESETS
# from player_detail_generator import generate_player_detail_page

def generate_kicker_stats():
    """Generate comprehensive kicker statistics."""
    print("Loading data from nflverse...")
    
    # Get current season
    current_season = nfl.get_current_season()
    print(f"Using season: {current_season}")
    
    # Load team stats and rosters
    team_stats = nfl.load_team_stats([current_season]).to_pandas()
    rosters = nfl.load_rosters([current_season]).to_pandas()
    
    # Get kickers from rosters
    kickers = rosters[rosters['position'] == 'K'][['team', 'full_name', 'gsis_id', 'birth_date']].copy()
    kickers = kickers.rename(columns={'full_name': 'player_name', 'gsis_id': 'player_id'})
    
    print(f"Found {len(kickers)} kickers")
    
    # Merge kicker info with team stats
    kicker_stats = team_stats.merge(kickers, on='team', how='inner')
    
    # Filter to regular season only
    kicker_stats = kicker_stats[kicker_stats['season_type'] == 'REG'].copy()
    
    # Build player data structure
    players_dict = {}
    
    for _, row in kicker_stats.iterrows():
        player_id = row['player_id']
        
        if player_id not in players_dict:
            players_dict[player_id] = {
                'player_name': row['player_name'],
                'player_id': player_id,
                'position': 'K',
                'team': row['team'],
                'birth_date': str(row.get('birth_date')) if row.get('birth_date') else None,
                'games_played': 0,
                'total_points': 0,
                'weekly_stats': []
            }
        
        player = players_dict[player_id]
        
        # Calculate fantasy points using distance-based FG scoring
        raw_stats = {
            'fg_0_19': row['fg_made_0_19'],
            'fg_20_29': row['fg_made_20_29'],
            'fg_30_39': row['fg_made_30_39'],
            'fg_40_49': row['fg_made_40_49'],
            'fg_50_59': row['fg_made_50_59'],
            'fg_60_plus': row['fg_made_60_'],
            'fg_missed': row['fg_missed'],
            'pat_made': row['pat_made'],
            'pat_missed': row['pat_missed']
        }
        
        weekly_points = calculate_fantasy_points(raw_stats, SCORING_PRESETS['ppr'])
        
        player['weekly_stats'].append({
            'week': int(row['week']),
            'opponent': row['opponent_team'],
            'points': round(weekly_points, 2),
            'raw_stats': {
                'fg_0_19': int(row['fg_made_0_19']),
                'fg_20_29': int(row['fg_made_20_29']),
                'fg_30_39': int(row['fg_made_30_39']),
                'fg_40_49': int(row['fg_made_40_49']),
                'fg_50_59': int(row['fg_made_50_59']),
                'fg_60_plus': int(row['fg_made_60_']),
                'fg_missed': int(row['fg_missed']),
                'fg_att': int(row['fg_att']),
                'pat_made': int(row['pat_made']),
                'pat_missed': int(row['pat_missed']),
                'pat_att': int(row['pat_att'])
            }
        })
        
        player['games_played'] += 1
        player['total_points'] += weekly_points
    
    # Convert to list and calculate aggregate stats
    players = []
    for player_id, player_data in players_dict.items():
        # Sort weekly stats by week
        player_data['weekly_stats'].sort(key=lambda x: x['week'])
        
        # Calculate aggregate stats
        total_fg_made = sum(
            w['raw_stats']['fg_0_19'] + w['raw_stats']['fg_20_29'] + 
            w['raw_stats']['fg_30_39'] + w['raw_stats']['fg_40_49'] + 
            w['raw_stats']['fg_50_59'] + w['raw_stats']['fg_60_plus']
            for w in player_data['weekly_stats']
        )
        total_fg_att = sum(w['raw_stats']['fg_att'] for w in player_data['weekly_stats'])
        total_pat_made = sum(w['raw_stats']['pat_made'] for w in player_data['weekly_stats'])
        total_pat_att = sum(w['raw_stats']['pat_att'] for w in player_data['weekly_stats'])
        
        player_data['aggregate_stats'] = {
            'fg_0_19': sum(w['raw_stats']['fg_0_19'] for w in player_data['weekly_stats']),
            'fg_20_29': sum(w['raw_stats']['fg_20_29'] for w in player_data['weekly_stats']),
            'fg_30_39': sum(w['raw_stats']['fg_30_39'] for w in player_data['weekly_stats']),
            'fg_40_49': sum(w['raw_stats']['fg_40_49'] for w in player_data['weekly_stats']),
            'fg_50_59': sum(w['raw_stats']['fg_50_59'] for w in player_data['weekly_stats']),
            'fg_60_plus': sum(w['raw_stats']['fg_60_plus'] for w in player_data['weekly_stats']),
            'total_fg_made': total_fg_made,
            'total_fg_att': total_fg_att,
            'total_fg_missed': sum(w['raw_stats']['fg_missed'] for w in player_data['weekly_stats']),
            'fg_pct': round(total_fg_made / total_fg_att * 100, 1) if total_fg_att > 0 else 0,
            'total_pat_made': total_pat_made,
            'total_pat_att': total_pat_att,
            'total_pat_missed': sum(w['raw_stats']['pat_missed'] for w in player_data['weekly_stats']),
            'pat_pct': round(total_pat_made / total_pat_att * 100, 1) if total_pat_att > 0 else 0
        }
        
        # Calculate Age
        age = '-'
        if player_data.get('birth_date'):
            try:
                bd_str = str(player_data['birth_date']).split(' ')[0]
                birth_date = datetime.strptime(bd_str, '%Y-%m-%d')
                today = datetime.today()
                age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
            except (ValueError, TypeError):
                pass
        
        player_data['nfl_stats'] = {
            'age': age
        }

        player_data['avg_points'] = round(player_data['total_points'] / player_data['games_played'], 2) if player_data['games_played'] > 0 else 0
        player_data['total_points'] = round(player_data['total_points'], 2)
        
        players.append(player_data)
    
    # Sort by total points
    players.sort(key=lambda x: x['total_points'], reverse=True)
    
    print(f"Calculated stats for {len(players)} kickers")
    
    # Create output structure
    output = {
        'season': current_season,
        'generated_at': datetime.now().isoformat(),
        'players': players
    }
    
    # Write to JSON file
    output_path = 'website/public/data/kicker_stats.json'
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"Kicker stats written to {output_path}")
    
    # Generate individual player pages (DEPRECATED - Now handled by Astro)
    # print("Generating individual kicker pages...")
    # website_public_dir = "website/public"
    # if not os.path.exists(website_public_dir):
    #     os.makedirs(website_public_dir)

    # for player in players:
    #     # Calculate age
    #     age = '-'
    #     if player.get('birth_date'):
    #         try:
    #             # Handle both "YYYY-MM-DD" and "YYYY-MM-DD HH:MM:SS" formats
    #             bd_str = str(player['birth_date']).split(' ')[0]
    #             birth_date = datetime.strptime(bd_str, '%Y-%m-%d')
    #             today = datetime.today()
    #             age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    #         except (ValueError, TypeError):
    #             pass

    #     # Prepare data for detail page
    #     player_data = {
    #         'position': 'K',
    #         'team': player['team'],
    #         'total_points': player['total_points'],
    #         'avg_ppg': player['avg_points'],
    #         'games': player['games_played'],
    #         'consistency': 0,
    #         'nfl_stats': {'age': age}
    #     }
    #     weekly_performances = {wp['week']: wp['points'] for wp in player['weekly_stats']}
    #     
    #     generate_player_detail_page(
    #         player['player_name'], 
    #         player_data, 
    #         weekly_performances, 
    #         output_dir=website_public_dir
    #     )
    
    # Print top 10 kickers
    print("\nTop 10 Kickers:")
    for i, player in enumerate(players[:10], 1):
        print(f"{i}. {player['player_name']} ({player['team']}) - {player['total_points']} pts, {player['avg_points']} PPG")

if __name__ == '__main__':
    generate_kicker_stats()
