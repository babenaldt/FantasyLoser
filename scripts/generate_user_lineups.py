"""Generate user lineup advisor data."""

import json
import requests
from core_data import OUTPUT_DIR, ASTRO_DATA_DIR, SleeperAPI, ensure_directories
from nfl_week_helper import get_current_nfl_week


def get_sleeper_projections(week):
    """Fetch weekly projections from Sleeper API."""
    try:
        url = f"https://api.sleeper.com/projections/nfl/2025/{week}?season_type=regular&position[]=QB&position[]=RB&position[]=WR&position[]=TE"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            projections = response.json()
            # Index by player_id for quick lookup
            proj_by_player = {}
            for proj in projections:
                player_id = proj.get('player_id')
                stats = proj.get('stats', {})
                if player_id and stats:
                    proj_by_player[player_id] = {
                        'pts_ppr': stats.get('pts_ppr', 0),
                        'pts_half_ppr': stats.get('pts_half_ppr', 0),
                        'pts_std': stats.get('pts_std', 0),
                    }
            return proj_by_player
    except Exception as e:
        print(f"    Warning: Could not fetch Sleeper projections: {e}")
    return {}


def fetch_league_transactions(league_id, current_week):
    """Fetch all transactions for a league from Sleeper API."""
    print(f"    Fetching transaction history...")
    all_transactions = []
    
    # Fetch transactions for each week
    for week in range(1, current_week + 1):
        try:
            url = f"https://api.sleeper.app/v1/league/{league_id}/transactions/{week}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                week_transactions = response.json()
                all_transactions.extend(week_transactions)
        except Exception as e:
            # Silently skip errors to avoid spam
            pass
    
    print(f"    Loaded {len(all_transactions)} transactions")
    return all_transactions


def build_weekly_rosters(rosters, transactions, max_week):
    """Build full roster for each user for each week by working backwards from current roster."""
    weekly_rosters = {}  # {user_id: {week: [player_ids]}}
    
    # Start with current rosters
    for roster in rosters:
        owner_id = roster.get('owner_id')
        if not owner_id:
            continue
        
        weekly_rosters[owner_id] = {}
        # Current roster becomes the baseline
        players_list = roster.get('players') or []
        current_players = set(players_list) if players_list else set()
        weekly_rosters[owner_id][max_week] = list(current_players)
    
    # Sort transactions by week in reverse
    sorted_txns = sorted(transactions, key=lambda t: t.get('leg', 0), reverse=True)
    
    # Build roster_id to owner_id mapping
    roster_to_owner = {}
    for roster in rosters:
        roster_id = roster.get('roster_id')
        owner_id = roster.get('owner_id')
        if roster_id and owner_id:
            roster_to_owner[roster_id] = owner_id
    
    # Work backwards through transactions to reconstruct historical rosters
    for week in range(max_week - 1, 0, -1):
        # Copy previous week as starting point
        for owner_id in weekly_rosters:
            weekly_rosters[owner_id][week] = weekly_rosters[owner_id].get(week + 1, []).copy()
        
        # Apply transactions for this week (in reverse) - only complete ones
        week_txns = [t for t in sorted_txns if t.get('leg') == week and t.get('status') == 'complete']
        for txn in week_txns:
            adds = txn.get('adds') or {}
            drops = txn.get('drops') or {}
            
            for player_id, roster_id in adds.items():
                owner_id = roster_to_owner.get(roster_id)
                if owner_id and owner_id in weekly_rosters:
                    # Remove the add (it didn't exist before)
                    if player_id in weekly_rosters[owner_id][week]:
                        weekly_rosters[owner_id][week].remove(player_id)
            
            for player_id, roster_id in drops.items():
                owner_id = roster_to_owner.get(roster_id)
                if owner_id and owner_id in weekly_rosters:
                    # Add back the drop (it existed before)
                    if player_id not in weekly_rosters[owner_id][week]:
                        weekly_rosters[owner_id][week].append(player_id)
    
    return weekly_rosters


def build_weekly_transactions_by_user(transactions, rosters, user_map, sleeper_players):
    """Build weekly transaction timeline for each user showing both adds and drops."""
    user_transactions = {}  # {user_id: [{week, adds: [], drops: []}]}
    
    # Build roster_id to owner_id mapping
    roster_to_owner_id = {}
    roster_to_owner_name = {}
    for roster in rosters:
        roster_id = roster.get('roster_id')
        owner_id = roster.get('owner_id')
        if roster_id and owner_id:
            roster_to_owner_id[roster_id] = owner_id
            roster_to_owner_name[roster_id] = user_map.get(owner_id, 'Unknown')
    
    # Build a map of all player drops: {player_id: [(week, owner_name)]}
    # Only track drops from complete transactions
    player_drop_history = {}
    for txn in transactions:
        # Skip failed transactions
        if txn.get('status') != 'complete':
            continue
        
        week = txn.get('leg', 0)
        drops = txn.get('drops') or {}
        for player_id, roster_id in drops.items():
            owner_name = roster_to_owner_name.get(roster_id, 'Unknown')
            if player_id not in player_drop_history:
                player_drop_history[player_id] = []
            player_drop_history[player_id].append((week, owner_name))
    
    # Sort each player's drop history by week
    for player_id in player_drop_history:
        player_drop_history[player_id].sort(key=lambda x: x[0])
    
    # Process each transaction (only complete ones)
    for txn in transactions:
        # Skip failed transactions
        if txn.get('status') != 'complete':
            continue
        
        week = txn.get('leg', 0)
        adds = txn.get('adds') or {}
        drops = txn.get('drops') or {}
        settings = txn.get('settings') or {}
        waiver_bid = settings.get('waiver_bid', 0)
        txn_type = txn.get('type', 'free_agent')
        
        # Process adds
        for player_id, roster_id in adds.items():
            owner_id = roster_to_owner_id.get(roster_id)
            if not owner_id:
                continue
                
            if owner_id not in user_transactions:
                user_transactions[owner_id] = {}
            if week not in user_transactions[owner_id]:
                user_transactions[owner_id][week] = {'adds': [], 'drops': []}
            
            # Get player info
            player_info = sleeper_players.get(player_id, {})
            player_name = f"{player_info.get('first_name', '')} {player_info.get('last_name', '')}".strip() or player_id
            position = player_info.get('position', '?')
            team = player_info.get('team', '?')
            
            # Determine previous owner - look backwards through drop history
            prev_owner = None
            if player_id in drops:
                # Player was dropped in this same transaction (swap)
                prev_roster_id = drops[player_id]
                prev_owner = roster_to_owner_name.get(prev_roster_id)
            elif player_id in player_drop_history:
                # Find most recent drop in this week or earlier
                # (handles elimination/chopped drops in same week)
                for drop_week, dropper in reversed(player_drop_history[player_id]):
                    if drop_week <= week:
                        prev_owner = dropper
                        break
            
            user_transactions[owner_id][week]['adds'].append({
                'player_id': player_id,
                'player_name': player_name,
                'position': position,
                'team': team,
                'faab_spent': waiver_bid,
                'prev_owner': prev_owner,
                'txn_type': txn_type
            })
        
        # Process drops
        for player_id, roster_id in drops.items():
            owner_id = roster_to_owner_id.get(roster_id)
            if not owner_id:
                continue
                
            if owner_id not in user_transactions:
                user_transactions[owner_id] = {}
            if week not in user_transactions[owner_id]:
                user_transactions[owner_id][week] = {'adds': [], 'drops': []}
            
            # Get player info
            player_info = sleeper_players.get(player_id, {})
            player_name = f"{player_info.get('first_name', '')} {player_info.get('last_name', '')}".strip() or player_id
            position = player_info.get('position', '?')
            team = player_info.get('team', '?')
            
            user_transactions[owner_id][week]['drops'].append({
                'player_id': player_id,
                'player_name': player_name,
                'position': position,
                'team': team
            })
    
    return user_transactions


def build_player_transaction_map(transactions, rosters, user_map):
    """Build a map of player_id -> transaction info with previous owners for CURRENT roster."""
    # Build roster_id to owner_name and owner_id mappings
    roster_to_owner_name = {}
    roster_to_owner_id = {}
    owner_id_to_roster_id = {}
    for roster in rosters:
        roster_id = roster.get('roster_id')
        owner_id = roster.get('owner_id')
        if roster_id and owner_id:
            roster_to_owner_name[roster_id] = user_map.get(owner_id, 'Unknown')
            roster_to_owner_id[roster_id] = owner_id
            owner_id_to_roster_id[owner_id] = roster_id
    
    # Build complete history for each player: {player_id: [(week, 'add'/'drop', owner_name, roster_id, faab)]}
    player_history = {}
    for txn in transactions:
        if txn.get('status') != 'complete':
            continue
        
        week = txn.get('leg', 0)
        adds = txn.get('adds') or {}
        drops = txn.get('drops') or {}
        settings = txn.get('settings') or {}
        waiver_bid = settings.get('waiver_bid', 0)
        
        for player_id, roster_id in adds.items():
            owner_name = roster_to_owner_name.get(roster_id, 'Unknown')
            if player_id not in player_history:
                player_history[player_id] = []
            player_history[player_id].append((week, 'add', owner_name, roster_id, waiver_bid))
        
        for player_id, roster_id in drops.items():
            owner_name = roster_to_owner_name.get(roster_id, 'Unknown')
            if player_id not in player_history:
                player_history[player_id] = []
            player_history[player_id].append((week, 'drop', owner_name, roster_id, 0))
    
    # For each player currently on a roster, find their acquisition info for current owner
    player_transactions = {}
    for roster in rosters:
        roster_id = roster.get('roster_id')
        owner_id = roster.get('owner_id')
        roster_players = roster.get('players', []) or []
        
        for player_id in roster_players:
            if player_id not in player_history:
                # Never transacted, must be drafted
                continue
            
            # Find the most recent 'add' for this roster_id
            history = sorted(player_history[player_id], key=lambda x: x[0])  # Sort by week
            
            # Find most recent add for this roster
            add_week = None
            add_faab = None
            for week, action, owner_name, hist_roster_id, faab in reversed(history):
                if action == 'add' and hist_roster_id == roster_id:
                    add_week = week
                    add_faab = faab
                    break
            
            if add_week is not None:
                # Find the most recent drop at or before this add week
                prev_owner = None
                for week, action, owner_name, hist_roster_id, faab in reversed(history):
                    if action == 'drop' and week <= add_week:
                        prev_owner = owner_name
                        break
                
                player_transactions[player_id] = {
                    'acquired_week': add_week,
                    'prev_owner': prev_owner,
                    'acquisition_type': 'waiver' if add_faab > 0 else 'free_agent',
                    'faab_spent': add_faab
                }
    
    return player_transactions


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
        with open(f"{OUTPUT_DIR}/player_stats.json", 'r', encoding='utf-8') as f:
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
    
    # Load Sleeper projections
    print("  Fetching Sleeper projections...")
    sleeper_projections = get_sleeper_projections(current_week)
    print(f"  Loaded projections for {len(sleeper_projections)} players")
    
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
            
            # Fetch transaction history
            transactions = fetch_league_transactions(league_info['id'], current_week)
            player_txn_map = build_player_transaction_map(transactions, rosters, user_map)
            weekly_transactions_by_user = build_weekly_transactions_by_user(transactions, rosters, user_map, sleeper_players)
            
            # Build full weekly rosters
            print(f"    Building weekly rosters...")
            weekly_rosters_by_user = build_weekly_rosters(rosters, transactions, current_week)
            
            # For Chopped league, load season stats to ensure all teams are included (even eliminated)
            all_team_owners = []
            if league_info['name'] == 'Chopped':
                try:
                    with open(f"{OUTPUT_DIR}/season_stats_chopped.json", 'r') as f:
                        season_data = json.load(f)
                        all_team_owners = [t['owner_name'] for t in season_data['teams']]
                    print(f"    Including all {len(all_team_owners)} Chopped teams (active and eliminated)")
                except Exception as e:
                    print(f"    Warning: Could not load season stats for Chopped: {e}")
            
            # Build user lineup data
            user_lineups = []
            
            # For Chopped league, ensure we process all team owners
            owners_to_process = []
            if league_info['name'] == 'Chopped' and all_team_owners:
                # Include all owners from season stats
                for owner_name in all_team_owners:
                    # Find their roster if they have one
                    owner_id = next((uid for uid, name in user_map.items() if name == owner_name), None)
                    roster = next((r for r in rosters if r.get('owner_id') == owner_id), None) if owner_id else None
                    owners_to_process.append((owner_id, owner_name, roster))
            else:
                # For Dynasty, just process rosters
                for roster in rosters:
                    if roster:
                        owner_id = roster.get('owner_id')
                        owner_name = user_map.get(owner_id, 'Unknown')
                        owners_to_process.append((owner_id, owner_name, roster))
            
            for owner_id, owner_name, roster in owners_to_process:
                roster_players = roster.get('players', []) if roster else []
                
                # Get user's players with stats
                user_players_data = []
                
                # For Chopped league, create entry even if no roster_players (eliminated teams)
                if not roster_players and league_info['name'] != 'Chopped':
                    continue
                
                # Ensure roster_players is a list
                if roster_players is None:
                    roster_players = []
                
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
                    
                    # Get Sleeper projection
                    projection = sleeper_projections.get(sleeper_id, {})
                    proj_ppr = projection.get('pts_ppr', 0)
                    
                    # Get injury status from Sleeper
                    injury_status = player_info.get('injury_status', None)
                    injury_notes = player_info.get('injury_notes', None)
                    
                    # Get transaction history for this player
                    txn_info = player_txn_map.get(sleeper_id, {})
                    acquired_week = txn_info.get('acquired_week')
                    prev_owner = txn_info.get('prev_owner')
                    acquisition_type = txn_info.get('acquisition_type')
                    faab_spent = txn_info.get('faab_spent', 0)
                    
                    # Determine acquisition status display text
                    if acquired_week:
                        # Player was acquired via transaction
                        if prev_owner:
                            acquisition_status = f"from {prev_owner}"
                        else:
                            acquisition_status = 'Free Agent' if faab_spent == 0 else 'Waivers'
                    else:
                        # No transaction history - must be drafted
                        acquisition_status = 'Drafted'
                    
                    user_players_data.append({
                        'player_name': player_name,
                        'team': team,
                        'position': position,
                        'opponent': opponent,
                        'opp_avg_allowed': opp_avg_allowed,
                        'avg_ppg': full_stats.get('avg_points_per_game', 0),
                        'projected_points': proj_ppr,
                        'injury_status': injury_status,
                        'injury_notes': injury_notes,
                        'total_points': full_stats.get('total_points', 0),
                        'games_played': full_stats.get('games_played', 0),
                        'consistency': full_stats.get('consistency', 0),
                        'std_dev': full_stats.get('std_dev', 0),
                        'trend_dir': full_stats.get('trend_dir', '-'),
                        'trend_pct': full_stats.get('trend_pct', 0),
                        'vs_position_avg': full_stats.get('vs_position_avg', 0),
                        'player_id': full_stats.get('player_id', ''),
                        'sleeper_id': sleeper_id,
                        'acquired_week': acquired_week,
                        'prev_owner': prev_owner,
                        'acquisition_type': acquisition_type,
                        'acquisition_status': acquisition_status,
                        'faab_spent': faab_spent
                    })
                
                # Add user entry if they have players OR if it's Chopped (to include eliminated teams)
                if user_players_data or league_info['name'] == 'Chopped':
                    user_weekly_txns = weekly_transactions_by_user.get(owner_id, {})
                    # Convert to sorted list
                    weekly_txns_list = [
                        {'week': week, **txns}
                        for week, txns in sorted(user_weekly_txns.items())
                    ]
                    
                    # Build weekly rosters with player details
                    user_weekly_rosters_data = []
                    if owner_id in weekly_rosters_by_user:
                        seen_players = set()
                        for week in sorted(weekly_rosters_by_user[owner_id].keys()):
                            player_ids = weekly_rosters_by_user[owner_id][week]
                            roster_players = []
                            
                            # Get transactions for this specific week
                            week_txns = user_weekly_txns.get(week, {})
                            week_adds = {add['player_id']: add for add in week_txns.get('adds', [])}
                            
                            for player_id in player_ids:
                                player_info = sleeper_players.get(player_id, {})
                                player_name = f"{player_info.get('first_name', '')} {player_info.get('last_name', '')}".strip() or player_id
                                position = player_info.get('position', '?')
                                team = player_info.get('team', '?')
                                
                                is_new = player_id not in seen_players
                                seen_players.add(player_id)
                                
                                # Determine acquisition method and FAAB
                                acquisition = 'Drafted'  # Default for week 1 or no transaction history
                                faab = 0
                                
                                # Check if player was added this specific week
                                if player_id in week_adds:
                                    add_info = week_adds[player_id]
                                    prev_owner = add_info.get('prev_owner')
                                    faab = add_info.get('faab_spent', 0)
                                    
                                    if prev_owner:
                                        acquisition = f'from {prev_owner}'
                                    else:
                                        acquisition = 'Free Agent'
                                elif is_new and week > 1:
                                    # Player is new but not in this week's transactions (might be from earlier week)
                                    if player_id in player_txn_map:
                                        txn = player_txn_map[player_id]
                                        prev_owner = txn.get('prev_owner')
                                        faab = txn.get('faab_spent', 0)
                                        
                                        if prev_owner:
                                            acquisition = f'from {prev_owner}'
                                        else:
                                            acquisition = 'Free Agent'
                                
                                roster_players.append({
                                    'player_id': player_id,
                                    'player_name': player_name,
                                    'position': position,
                                    'team': team,
                                    'is_new': is_new and week <= current_week,
                                    'acquisition': acquisition,
                                    'faab_spent': faab
                                })
                            
                            user_weekly_rosters_data.append({
                                'week': week,
                                'players': roster_players
                            })
                    
                    user_lineups.append({
                        'user_id': owner_id or 'unknown',
                        'user_name': owner_name,
                        'players': user_players_data,
                        'weekly_transactions': weekly_txns_list,
                        'weekly_rosters': user_weekly_rosters_data
                    })
            
            # Save user lineup data
            output_data = {
                'league_name': league_info['name'],
                'current_week': current_week,
                'users': user_lineups
            }
            
            output_file = f"{OUTPUT_DIR}/{league_info['output_file']}"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            print(f"    ✓ Saved: {output_file}")
            
            astro_file = f"{ASTRO_DATA_DIR}/{league_info['output_file']}"
            with open(astro_file, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            print(f"    ✓ Saved: {astro_file}")
            
        except Exception as e:
            print(f"    Error processing {league_info['name']} league: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n✅ User lineup advisor data generated successfully!")


if __name__ == "__main__":
    generate_user_lineups()
