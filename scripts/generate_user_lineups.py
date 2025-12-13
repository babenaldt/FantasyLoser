"""Generate user lineup advisor data."""

import json
from core_data import OUTPUT_DIR, ASTRO_DATA_DIR, SleeperAPI, ensure_directories
from nfl_week_helper import get_current_nfl_week


def generate_user_lineups():
    """Generate lineup advisor data for each user in both leagues."""
    print("\nGenerating User Lineup Advisor Data...")
    ensure_directories()
    
    # League IDs
    DYNASTY_LEAGUE_ID = "1264304480178950144"
    CHOPPED_LEAGUE_ID = "1263579037352079360"
    
    current_week = get_current_nfl_week()
    print(f"  Current NFL Week: {current_week}")
    
    # Load player stats
    print("  Loading player stats...")
    try:
        with open(f"{OUTPUT_DIR}/player_stats.json", 'r') as f:
            player_data = json.load(f)
            players_by_name_team = {}
            for p in player_data['players']:
                key = (p['player_name'], p['team'])
                players_by_name_team[key] = p
        print(f"  Loaded {len(players_by_name_team)} players")
    except Exception as e:
        print(f"  Error loading player stats: {e}")
        return
    
    # Load defense stats
    print("  Loading defense stats...")
    try:
        with open(f"{OUTPUT_DIR}/defense_stats.json", 'r') as f:
            def_data = json.load(f)
            defense_stats = {d['team']: d for d in def_data['defenses']}
        print(f"  Loaded defense stats for {len(defense_stats)} teams")
    except Exception as e:
        print(f"  Error loading defense stats: {e}")
        defense_stats = {}
    
    # Process both leagues
    leagues = [
        {'id': DYNASTY_LEAGUE_ID, 'name': 'Dynasty', 'output_file': 'user_lineups_dynasty.json'},
        {'id': CHOPPED_LEAGUE_ID, 'name': 'Chopped', 'output_file': 'user_lineups_chopped.json'}
    ]
    
    for league_info in leagues:
        print(f"\n  Processing {league_info['name']} league...")
        try:
            api = SleeperAPI(league_info['id'])
            
            # Get users
            users = api.get_users() or []
            user_map = {u['user_id']: u['display_name'] for u in users}
            print(f"    Found {len(users)} users")
            
            # Get rosters
            rosters = api.get_rosters() or []
            print(f"    Found {len(rosters)} rosters")
            
            # Get Sleeper player data
            sleeper_players = SleeperAPI.get_all_players()
            
            # Get matchups for current week
            matchups = api.get_matchups(current_week) or []
            print(f"    Found {len(matchups)} matchups for week {current_week}")
            
            # Build user lineup data
            user_lineups = []
            
            for roster in rosters:
                if not roster:
                    continue
                    
                owner_id = roster.get('owner_id')
                owner_name = user_map.get(owner_id, 'Unknown')
                roster_players = roster.get('players', [])
                
                if not roster_players:
                    continue
                
                # Get user's players with stats
                user_players_data = []
                
                for sleeper_id in roster_players:
                    player_info = sleeper_players.get(sleeper_id)
                    if not player_info:
                        continue
                    
                    first = player_info.get('first_name', '')
                    last = player_info.get('last_name', '')
                    team = player_info.get('team')
                    position = player_info.get('position')
                    
                    if not (first and last and team):
                        continue
                    
                    player_name = f"{first} {last}"
                    
                    # Normalize team codes
                    if team == 'LAR':
                        team = 'LA'
                    # Note: Sleeper uses JAX, player_stats uses JAX (not JAC)
                    
                    # Get full player stats
                    player_key = (player_name, team)
                    full_stats = players_by_name_team.get(player_key)
                    
                    # If no match, try with common suffixes (Jr, Sr, II, III, IV)
                    if not full_stats:
                        for suffix in [' Jr', ' Sr', ' II', ' III', ' IV', ' Jr.', ' Sr.']:
                            alt_key = (player_name + suffix, team)
                            if alt_key in players_by_name_team:
                                full_stats = players_by_name_team[alt_key]
                                player_name = player_name + suffix  # Use the full name from player_stats
                                break
                    
                    if not full_stats or position not in ['QB', 'RB', 'WR', 'TE', 'K', 'DEF']:
                        continue
                    
                    # Get week matchup
                    weekly_data = full_stats.get('weekly_points', [])
                    week_matchup = next((w for w in weekly_data if w['week'] == current_week), None)
                    
                    opponent = week_matchup['opponent'] if week_matchup else 'Unknown'
                    opp_avg_allowed = week_matchup['opp_avg_allowed'] if week_matchup else 0
                    
                    user_players_data.append({
                        'player_name': player_name,
                        'team': team,
                        'position': position,
                        'opponent': opponent,
                        'opp_avg_allowed': opp_avg_allowed,
                        'avg_ppg': full_stats.get('avg_points_per_game', 0),
                        'total_points': full_stats.get('total_points', 0),
                        'games_played': full_stats.get('games_played', 0),
                        'consistency': full_stats.get('consistency', 0),
                        'std_dev': full_stats.get('std_dev', 0),
                        'trend_dir': full_stats.get('trend_dir', '-'),
                        'trend_pct': full_stats.get('trend_pct', 0),
                        'vs_position_avg': full_stats.get('vs_position_avg', 0),
                        'player_id': full_stats.get('player_id', '')
                    })
                
                if user_players_data:
                    user_lineups.append({
                        'user_id': owner_id,
                        'user_name': owner_name,
                        'players': user_players_data
                    })
            
            # Save user lineup data
            output_data = {
                'league_name': league_info['name'],
                'current_week': current_week,
                'users': user_lineups
            }
            
            output_file = f"{OUTPUT_DIR}/{league_info['output_file']}"
            with open(output_file, 'w') as f:
                json.dump(output_data, f, indent=2)
            print(f"    ✓ Saved: {output_file}")
            
            astro_file = f"{ASTRO_DATA_DIR}/{league_info['output_file']}"
            with open(astro_file, 'w') as f:
                json.dump(output_data, f, indent=2)
            print(f"    ✓ Saved: {astro_file}")
            
        except Exception as e:
            print(f"    Error processing {league_info['name']} league: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n✅ User lineup advisor data generated successfully!")


if __name__ == "__main__":
    generate_user_lineups()
