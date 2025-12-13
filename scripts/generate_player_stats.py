"""Generate player statistics JSON for Astro site."""

import json
import nflreadpy as nfl
import statistics
from datetime import datetime
from core_data import (
    ensure_directories, save_json, calculate_fantasy_points,
    OUTPUT_DIR, ASTRO_DATA_DIR, ROSTERABLE_POSITIONS
)
# from player_detail_generator import generate_player_detail_page
import os


def generate_player_stats_json():
    """Generate player statistics and save to JSON."""
    print("\nGenerating Player Statistics...")
    ensure_directories()
    
    # Load NFL data
    print("  Loading NFL weekly player stats...")
    nfl_season = nfl.get_current_season()
    season = [nfl_season]
    
    try:
        weekly_stats = nfl.load_player_stats(season)
        print(f"  Loaded {len(weekly_stats)} weekly records for {nfl_season} season")
    except Exception as e:
        print(f"  Error loading NFL data: {e}")
        return

    # Load Snap Counts
    print("  Loading snap counts...")
    try:
        snap_counts = nfl.load_snap_counts(season)
        # Create lookup: (player_name, team, week) -> offense_pct
        snap_lookup = {}
        for row in snap_counts.iter_rows(named=True):
            # Normalize names if needed, but try direct match first
            p_name = row.get('player')
            p_team = row.get('team')
            p_week = row.get('week')
            if p_name and p_team and p_week:
                snap_lookup[(p_name, p_team, p_week)] = row.get('offense_pct', 0)
        print(f"  Loaded snap counts for {len(snap_lookup)} player-weeks")
    except Exception as e:
        print(f"  Error loading snap counts: {e}")
        snap_lookup = {}

    # Load Roster Data for Age
    print("  Loading roster data for player ages...")
    player_ages = {}
    try:
        roster = nfl.load_rosters(season)
        for row in roster.iter_rows(named=True):
            p_id = row.get('gsis_id')
            birth_date_str = row.get('birth_date')
            if p_id and birth_date_str:
                try:
                    bd_str = str(birth_date_str).split(' ')[0]
                    birth_date = datetime.strptime(bd_str, '%Y-%m-%d')
                    today = datetime.today()
                    age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
                    player_ages[p_id] = age
                except (ValueError, TypeError):
                    continue
        print(f"  Loaded ages for {len(player_ages)} players")
    except Exception as e:
        print(f"  Error loading roster data: {e}")

    # Load Ownership Data from Sleeper Leagues
    print("  Loading ownership data from Sleeper leagues...")
    from core_data import SleeperAPI
    
    # League IDs
    DYNASTY_LEAGUE_ID = "1263579037352079360"
    CHOPPED_LEAGUE_ID = "1264304480178950144"
    
    player_ownership = {}  # player_id -> {'dynasty_owner': str, 'chopped_owner': str}
    
    try:
        # Load Sleeper player mapping
        sleeper_players = SleeperAPI.get_all_players()
        # Create gsis_id -> sleeper_id mapping
        gsis_to_sleeper = {}
        for sleeper_id, p_data in sleeper_players.items():
            gsis_id = p_data.get('gsis_id')
            if gsis_id:
                gsis_to_sleeper[gsis_id] = sleeper_id
        
        # Load Dynasty league rosters
        dynasty_api = SleeperAPI(DYNASTY_LEAGUE_ID)
        dynasty_rosters = dynasty_api.get_rosters()
        dynasty_users = dynasty_api.get_users()
        dynasty_user_map = {u['user_id']: u['display_name'] for u in dynasty_users}
        
        # Load Chopped league rosters
        chopped_api = SleeperAPI(CHOPPED_LEAGUE_ID)
        chopped_rosters = chopped_api.get_rosters()
        chopped_users = chopped_api.get_users()
        chopped_user_map = {u['user_id']: u['display_name'] for u in chopped_users}
        
        # Map players to owners
        for roster in dynasty_rosters:
            owner_id = roster.get('owner_id')
            owner_name = dynasty_user_map.get(owner_id, 'Unknown')
            for sleeper_id in roster.get('players', []):
                # Find GSIS ID for this Sleeper ID
                gsis_id = None
                for gid, sid in gsis_to_sleeper.items():
                    if sid == sleeper_id:
                        gsis_id = gid
                        break
                if gsis_id:
                    if gsis_id not in player_ownership:
                        player_ownership[gsis_id] = {}
                    player_ownership[gsis_id]['dynasty_owner'] = owner_name
        
        for roster in chopped_rosters:
            owner_id = roster.get('owner_id')
            owner_name = chopped_user_map.get(owner_id, 'Unknown')
            for sleeper_id in roster.get('players', []):
                # Find GSIS ID for this Sleeper ID
                gsis_id = None
                for gid, sid in gsis_to_sleeper.items():
                    if sid == sleeper_id:
                        gsis_id = gid
                        break
                if gsis_id:
                    if gsis_id not in player_ownership:
                        player_ownership[gsis_id] = {}
                    player_ownership[gsis_id]['chopped_owner'] = owner_name
        
        print(f"  Loaded ownership for {len(player_ownership)} players")
    except Exception as e:
        print(f"  Error loading ownership data: {e}")

    # Load Defense Stats for Opponent Points Allowed
    print("  Loading defense stats for opponent matchups...")
    defense_map = {}
    try:
        with open(f"{OUTPUT_DIR}/defense_stats.json", 'r') as f:
            def_data = json.load(f)
            for team in def_data.get('defenses', []):
                t_name = team.get('team')
                if t_name:
                    defense_map[t_name] = {
                        'QB': team.get('qb1_ppg', team.get('qb_ppg', 0)),
                        'RB': team.get('rb1_ppg', team.get('rb_ppg', 0)),
                        'WR': team.get('wr1_ppg', team.get('wr_ppg', 0)),
                        'TE': team.get('te1_ppg', team.get('te_ppg', 0))
                    }
        print(f"  Loaded defense stats for {len(defense_map)} teams")
    except Exception as e:
        print(f"  Error loading defense stats: {e}")
    
    # Calculate player statistics
    print("  Calculating player statistics...")
    player_stats = {}
    
    for row in weekly_stats.iter_rows(named=True):
        player_id = row.get('player_id')
        if not player_id:
            continue
        
        position = row.get('position', '')
        if position not in ROSTERABLE_POSITIONS:
            continue
        
        # Initialize player if needed
        if player_id not in player_stats:
            player_stats[player_id] = {
                'player_id': player_id,
                'player_name': row.get('player_display_name', 'Unknown'),
                'position': position,
                'team': row.get('team', 'FA'),
                'games_played': 0,
                'total_points': 0,
                'weekly_points': []
            }
        
        # Calculate fantasy points
        pts = calculate_fantasy_points(row)
        
        week = row.get('week')
        if week and pts > 0:
            player_stats[player_id]['total_points'] += pts
            player_stats[player_id]['games_played'] += 1
            
            # Get snap count
            player_name = row.get('player_display_name')
            team = row.get('team')
            snap_pct = snap_lookup.get((player_name, team, week), 0)
            
            # Get opponent stats
            opponent = row.get('opponent_team', 'N/A')
            opp_avg_allowed = defense_map.get(opponent, {}).get(position, 0)

            # Store raw stats for client-side recalculation
            raw_stats = {
                'passing_yards': row.get('passing_yards', 0) or 0,
                'passing_tds': row.get('passing_tds', 0) or 0,
                'passing_2pt': row.get('passing_2pt_conversions', 0) or 0,
                'interceptions': row.get('interceptions', 0) or 0,
                'rushing_yards': row.get('rushing_yards', 0) or 0,
                'rushing_tds': row.get('rushing_tds', 0) or 0,
                'rushing_2pt': row.get('rushing_2pt_conversions', 0) or 0,
                'receptions': row.get('receptions', 0) or 0,
                'receiving_yards': row.get('receiving_yards', 0) or 0,
                'receiving_tds': row.get('receiving_tds', 0) or 0,
                'receiving_2pt': row.get('receiving_2pt_conversions', 0) or 0,
                'fumbles_lost': row.get('fumbles_lost', 0) or 0,
                # Advanced Stats (kept for detail pages if needed, but focus is consistency)
                'targets': row.get('targets', 0) or 0,
                'offense_pct': snap_pct,
            }
            
            player_stats[player_id]['weekly_points'].append({
                'week': week,
                'points': round(pts, 2),
                'opponent': opponent,
                'opp_avg_allowed': round(opp_avg_allowed, 1),
                'raw_stats': raw_stats
            })
    
    # Calculate averages, consistency, and filter
    players_list = []
    
    # First pass: Calculate individual stats
    position_totals = {}
    position_counts = {}
    
    for player_id, stats in player_stats.items():
        if stats['games_played'] > 0:
            # Sort weekly points by week
            stats['weekly_points'].sort(key=lambda x: x['week'])
            points_list = [wp['points'] for wp in stats['weekly_points']]
            
            # Basic Averages
            avg_ppg = stats['total_points'] / stats['games_played']
            stats['avg_points_per_game'] = avg_ppg
            
            # Consistency Metrics
            stats['best_game'] = max(points_list)
            stats['worst_game'] = min(points_list)
            stats['median'] = statistics.median(points_list)
            
            if len(points_list) > 1:
                std_dev = statistics.stdev(points_list)
            else:
                std_dev = 0
            stats['std_dev'] = std_dev
            
            if std_dev > 0:
                stats['consistency'] = avg_ppg / std_dev
            else:
                stats['consistency'] = 0
                
            # % Above Average
            above_avg_count = sum(1 for p in points_list if p > avg_ppg)
            stats['pct_above_avg'] = (above_avg_count / len(points_list)) * 100
            
            # Snap Count Average
            snap_counts = [wp['raw_stats'].get('offense_pct', 0) for wp in stats['weekly_points']]
            avg_snap_pct = sum(snap_counts) / len(snap_counts) if snap_counts else 0
            stats['avg_snap_pct'] = round(avg_snap_pct * 100, 1)
            
            # Add NFL Stats (Age, Snap %)
            stats['nfl_stats'] = {
                'age': player_ages.get(player_id, '-'),
                'avg_snap_pct': stats['avg_snap_pct']
            }
            
            # Add Ownership Data
            ownership = player_ownership.get(player_id, {})
            stats['dynasty_owner'] = ownership.get('dynasty_owner', 'Free Agent')
            stats['chopped_owner'] = ownership.get('chopped_owner', 'Free Agent')

            # Trend (Last 4 weeks vs Season Avg)
            last_4_weeks = stats['weekly_points'][-4:]
            if last_4_weeks:
                last_4_avg = sum(w['points'] for w in last_4_weeks) / len(last_4_weeks)
                trend_diff = last_4_avg - avg_ppg
                trend_pct = (trend_diff / avg_ppg * 100) if avg_ppg > 0 else 0
                stats['trend_pct'] = trend_pct
                stats['trend_dir'] = "▲" if trend_diff > 0 else "▼"
            else:
                stats['trend_pct'] = 0
                stats['trend_dir'] = "-"
            
            # Collect for position averages
            pos = stats['position']
            if pos not in position_totals:
                position_totals[pos] = 0
                position_counts[pos] = 0
            position_totals[pos] += avg_ppg
            position_counts[pos] += 1
            
            players_list.append(stats)
            
    # Calculate position averages
    position_avgs = {pos: total / position_counts[pos] for pos, total in position_totals.items()}
    
    # Second pass: Add position comparison stats
    for stats in players_list:
        pos = stats['position']
        pos_avg = position_avgs.get(pos, 0)
        stats['position_avg'] = pos_avg
        stats['vs_position_avg'] = stats['avg_points_per_game'] - pos_avg
    
    # Sort by total points
    players_list.sort(key=lambda x: x['total_points'], reverse=True)
    
    print(f"  Calculated stats for {len(players_list)} players")

    # Generate individual player pages
    print("  Generating individual player pages...")
    website_public_dir = "website/public"
    # Ensure website/public exists
    if not os.path.exists(website_public_dir):
        os.makedirs(website_public_dir)
        
    # Generate individual player page (DEPRECATED - Now handled by Astro)
    # for player in players_list:
    #     # Prepare data for detail page
    #     player_data = {
    #         'position': player['position'],
    #         'team': player['team'],
    #         'total_points': player['total_points'],
    #         'avg_ppg': player['avg_points_per_game'],
    #         'games': player['games_played'],
    #         'consistency': player['consistency'],
    #         'std_dev': player['std_dev'],
    #         'pct_above_avg': player['pct_above_avg'],
    #         'trend_pct': player['trend_pct'],
    #         'trend_dir': player['trend_dir'],
    #         'vs_position_avg': player['vs_position_avg'],
    #         'nfl_stats': {
    #             'age': player_ages.get(player['player_id'], '-'),
    #             'avg_snap_pct': player.get('avg_snap_pct', 0)
    #         }
    #     }
    #     weekly_performances = {
    #         wp['week']: {
    #             'points': wp['points'],
    #             'opponent': wp['opponent'],
    #             'opp_avg_allowed': wp.get('opp_avg_allowed', 0)
    #         } 
    #         for wp in player['weekly_points']
    #     }
    #     
    #     generate_player_detail_page(
    #         player['player_name'], 
    #         player_data, 
    #         weekly_performances, 
    #         output_dir=website_public_dir
    #     )
    
    # Prepare output data
    output_data = {
        'season': str(nfl_season),
        'generated_at': __import__('datetime').datetime.now().isoformat(),
        'players': players_list
    }
    
    # Save JSON files
    save_json(output_data, f"{OUTPUT_DIR}/player_stats.json")
    save_json(output_data, f"{ASTRO_DATA_DIR}/player_stats.json")
    
    print("✅ Player statistics generated successfully!")


if __name__ == "__main__":
    generate_player_stats_json()
