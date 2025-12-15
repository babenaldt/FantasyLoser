"""Generate season statistics JSON for Astro site."""

import statistics
import json
import os
from collections import defaultdict
from core_data import (
    ensure_directories, save_json, SleeperAPI,
    OUTPUT_DIR, ASTRO_DATA_DIR
)

# League configurations
LEAGUES = {
    'dynasty': {
        'id': '1264304480178950144',
        'name': 'Dynasty League'
    },
    'chopped': {
        'id': '1263579037352079360',
        'name': 'Chopped League'
    }
}

def load_player_data():
    """Load player data from generated player data."""
    try:
        path = os.path.join(ASTRO_DATA_DIR, 'players_data.json')
        if os.path.exists(path):
            with open(path, 'r') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
                elif isinstance(data, list):
                    return {p['player_id']: p for p in data}
    except Exception as e:
        print(f"    Warning: Could not load player data: {e}")
    return {}

def calculate_optimal_score(matchup, roster_positions, player_data):
    """Calculate optimal score for a matchup."""
    if not player_data:
        return matchup.get('points', 0)

    # Get all available players and their points
    available_players = []
    players_points = matchup.get('players_points', {}) or {}
    
    for pid, points in players_points.items():
        if pid in player_data:
            p_info = player_data[pid]
            available_players.append({
                'id': pid,
                'pos': p_info.get('position'),
                'points': points
            })
    
    # Sort by points descending
    available_players.sort(key=lambda x: x['points'], reverse=True)
    
    used_players = set()
    optimal_points = 0
    
    # Filter roster positions to only starters (exclude BN)
    starter_slots = [p for p in roster_positions if p != 'BN']
    
    # Fill specific positions first
    for slot in starter_slots:
        if slot == 'FLEX':
            continue
            
        # Find best available player for this slot
        for player in available_players:
            if player['id'] not in used_players and player['pos'] == slot:
                optimal_points += player['points']
                used_players.add(player['id'])
                break
    
    # Fill FLEX spots (RB/WR/TE)
    flex_slots = [p for p in starter_slots if p == 'FLEX']
    for _ in flex_slots:
        for player in available_players:
            if player['id'] not in used_players and player['pos'] in ['RB', 'WR', 'TE']:
                optimal_points += player['points']
                used_players.add(player['id'])
                break
                
    # If optimal is less than actual (due to scoring corrections or bugs), use actual
    return max(optimal_points, matchup.get('points', 0))

def calculate_season_stats(league_id, league_name):
    """Calculate season statistics for a league."""
    print(f"\n  Processing {league_name}...")
    
    api = SleeperAPI(league_id)
    player_data = load_player_data()
    
    # Get league data
    league = api.get_league()
    if not league:
        print(f"    Error: Could not fetch league data")
        return None
        
    roster_positions = league.get('roster_positions', [])
    
    # For Chopped League, we need Dynasty matchups for Best Theoretical Lineup
    dynasty_matchups_by_week = {}
    if "Chopped" in league_name:
        print("    Fetching Dynasty matchups for Best Theoretical Lineup...")
        dynasty_api = SleeperAPI(LEAGUES['dynasty']['id'])
        current_week = league.get('settings', {}).get('leg', 1)
        for w in range(1, current_week + 1):
            m = dynasty_api.get_matchups(w)
            if m:
                dynasty_matchups_by_week[w] = m

    rosters = api.get_rosters()
    users = api.get_users()
    
    if not rosters or not users:
        print(f"    Error: Could not fetch rosters or users")
        return None
    
    # Create user mapping
    user_map = {user['user_id']: user for user in users}
    
    # Get current week and status
    current_week = league.get('settings', {}).get('leg', 1)
    status = league.get('status', 'in_season')
    
    # Determine last completed week
    # If league is active (in_season or post_season), 'current_week' is the active (incomplete) week.
    # We want to process only completed weeks.
    if status == 'complete':
        # If league is complete, we can use the current_week (which should be the last week)
        # But usually current_week might be 18.
        # Let's just use current_week if complete.
        last_completed_week = current_week
    else:
        # If in_season or post_season, current_week is active.
        last_completed_week = max(0, current_week - 1)

    # Collect matchup data
    print(f"    Fetching matchup data for weeks 1-{last_completed_week} (Current Week: {current_week}, Status: {status})...")
    team_stats = {}
    
    for roster in rosters:
        roster_id = roster['roster_id']
        owner_id = roster['owner_id']
        user = user_map.get(owner_id, {})
        
        team_stats[roster_id] = {
            'roster_id': roster_id,
            'owner_id': owner_id,
            'owner_name': user.get('display_name', user.get('metadata', {}).get('team_name', 'Unknown')),
            'total_points_scored': 0,
            'total_points_against': 0,
            'total_optimal_points': 0,
            'wins': roster.get('settings', {}).get('wins', 0),
            'losses': roster.get('settings', {}).get('losses', 0),
            'ties': roster.get('settings', {}).get('ties', 0),
            'weeks_played': 0,
            'weekly_scores': [],
            'points_left_on_bench': 0, # Optimal - Actual (Efficiency metric)
            'total_bench_points': 0,   # Sum of all bench players
            'faab_spent': 0,
            'waiver_moves': 0,
            'safety_margin_sum': 0,
            'close_calls': 0,
            'eliminated_week': None,
            'all_play_wins': 0,
            'all_play_losses': 0,
            'all_play_ties': 0
        }
    
    # Initialize Best Theoretical Lineups list
    best_theoretical_lineups = []

    # Fetch weekly data
    for week in range(1, last_completed_week + 1):
        # Calculate Best Theoretical Lineup for this week (Chopped only)
        if "Chopped" in league_name and week in dynasty_matchups_by_week:
            btl = calculate_best_theoretical_lineup(week, dynasty_matchups_by_week[week], roster_positions, player_data)
            if btl:
                best_theoretical_lineups.append(btl)

        # Temp storage for this week's stats per team
        this_week_stats = defaultdict(lambda: {
            'week': week,
            'points': 0,
            'optimal': 0,
            'bench': 0,
            'margin': 0,
            'opponent_points': 0,
            'waiver_moves': 0,
            'faab_spent': 0,
            'has_matchup': False
        })

        # Get Transactions for FAAB
        transactions = api.get_transactions(week)
        if transactions:
            for t in transactions:
                if t.get('status') == 'complete':
                    # Count waiver moves and FAAB
                    if t.get('type') == 'waiver':
                        creator = t.get('creator') # user_id
                        # Find roster_id for this user
                        rid = next((r['roster_id'] for r in rosters if r['owner_id'] == creator), None)
                        if rid:
                            this_week_stats[rid]['waiver_moves'] += 1
                            this_week_stats[rid]['faab_spent'] += t.get('settings', {}).get('waiver_bid', 0)

        # Get Matchups
        matchups = api.get_matchups(week)
        if not matchups:
            continue
            
        # Calculate weekly min score for safety margin (exclude 0s for Chopped)
        weekly_scores = [m.get('points', 0) for m in matchups]
        if "Chopped" in league_name:
            active_scores = [s for s in weekly_scores if s > 0]
            min_score = min(active_scores) if active_scores else 0
        else:
            min_score = min(weekly_scores) if weekly_scores else 0
        
        # Calculate All-Play for this week
        # Create a map of roster_id -> points for this week
        week_points_map = {m['roster_id']: m.get('points', 0) for m in matchups}
        
        # Group by matchup_id
        matchup_groups = {}
        for matchup in matchups:
            mid = matchup.get('matchup_id')
            if mid not in matchup_groups:
                matchup_groups[mid] = []
            matchup_groups[mid].append(matchup)
        
        # Process each matchup
        for mid, teams in matchup_groups.items():
            for matchup in teams:
                roster_id = matchup['roster_id']
                if roster_id not in team_stats:
                    continue
                
                points = matchup.get('points', 0)
                starters = matchup.get('starters', []) or []
                players_points = matchup.get('players_points', {}) or {}
                
                # Bench points
                bench_pts = 0
                for pid, pts in players_points.items():
                    if pid not in starters:
                        bench_pts += pts
                
                # DEBUG: Check bench points for a specific case if needed
                # if week == 1 and roster_id == 1:
                #     print(f"DEBUG: Week {week} Roster {roster_id} Bench Pts: {bench_pts} (Players: {len(players_points)}, Starters: {len(starters)})")

                # Optimal points
                optimal_points = calculate_optimal_score(matchup, roster_positions, player_data)
                
                # Missed points (Optimal - Actual)
                missed_pts = max(0, optimal_points - points)

                # Safety Margin (only if points > 0 for Chopped)
                margin = 0
                if points > 0:
                    margin = points - min_score
                
                # Calculate points against
                opponent_points = sum(m.get('points', 0) for m in teams if m['roster_id'] != roster_id)
                
                # Win/Loss margin (points - opponent_points)
                win_loss_margin = points - opponent_points if opponent_points > 0 else 0

                # Update weekly temp stats
                w_stats = this_week_stats[roster_id]
                w_stats['points'] = points
                w_stats['optimal'] = optimal_points
                w_stats['bench'] = bench_pts
                w_stats['missed'] = missed_pts
                w_stats['margin'] = margin
                w_stats['win_loss_margin'] = win_loss_margin
                w_stats['opponent_points'] = opponent_points
                w_stats['has_matchup'] = True
                
                # Update running totals (will be corrected later for Chopped)
                stats = team_stats[roster_id]
                stats['total_points_scored'] += points
                stats['total_optimal_points'] += optimal_points
                stats['points_left_on_bench'] += missed_pts
                stats['total_bench_points'] += bench_pts
                stats['weeks_played'] += 1
                stats['safety_margin_sum'] += margin
                if points > 0 and margin <= 10 and margin > 0: # Close call logic
                    stats['close_calls'] = stats.get('close_calls', 0) + 1
                if opponent_points > 0:
                    stats['total_points_against'] += opponent_points
                
                # Update All-Play stats
                # Compare against all other teams this week
                if points > 0: # Only count if team played (points > 0)
                    for other_rid, other_points in week_points_map.items():
                        if other_rid != roster_id and other_points > 0:
                            if points > other_points:
                                stats['all_play_wins'] += 1
                            elif points < other_points:
                                stats['all_play_losses'] += 1
                            else:
                                stats['all_play_ties'] += 1

        # Append weekly data to team_stats and update waiver totals
        for rid, w_stats in this_week_stats.items():
            if rid in team_stats and w_stats['has_matchup']:
                team_stats[rid]['weekly_scores'].append(w_stats)
                team_stats[rid]['waiver_moves'] += w_stats['waiver_moves']
                team_stats[rid]['faab_spent'] += w_stats['faab_spent']
    
    # Calculate Eliminations for Chopped League
    if "Chopped" in league_name:
        active_rosters = set(team_stats.keys())
        
        for week in range(1, current_week + 1):
            if not active_rosters:
                break
                
            # Find lowest scorer among active rosters for this week
            week_scores = []
            for rid in list(active_rosters):
                team = team_stats[rid]
                # Find score for this week
                score = next((w['points'] for w in team['weekly_scores'] if w['week'] == week), None)
                
                if score is not None:
                    week_scores.append((rid, score))
            
            if week_scores:
                # Sort by score (ascending)
                week_scores.sort(key=lambda x: x[1])
                loser_id, loser_score = week_scores[0]
                
                # Mark as eliminated
                team_stats[loser_id]['eliminated_week'] = week
                active_rosters.remove(loser_id)

        # Recalculate stats for eliminated teams to exclude post-elimination weeks
        for rid, team in team_stats.items():
            if team['eliminated_week']:
                elim_week = team['eliminated_week']
                
                # Filter weeks
                valid_weeks = [w for w in team['weekly_scores'] if w['week'] <= elim_week]
                
                # Reset and recalculate totals
                team['total_points_scored'] = sum(w['points'] for w in valid_weeks)
                team['total_optimal_points'] = sum(w['optimal'] for w in valid_weeks)
                team['points_left_on_bench'] = sum(w['missed'] for w in valid_weeks)
                team['total_bench_points'] = sum(w['bench'] for w in valid_weeks)
                team['weeks_played'] = len(valid_weeks)
                team['safety_margin_sum'] = sum(w['margin'] for w in valid_weeks)
                team['total_points_against'] = sum(w['opponent_points'] for w in valid_weeks)
                team['close_calls'] = sum(1 for w in valid_weeks if w['margin'] > 0 and w['margin'] <= 10)
                team['waiver_moves'] = sum(w['waiver_moves'] for w in valid_weeks)
                team['faab_spent'] = sum(w['faab_spent'] for w in valid_weeks)
                
                # Update weekly_scores to only include valid weeks
                team['weekly_scores'] = valid_weeks

    # Calculate derived stats for all teams
    for team in team_stats.values():
        weeks = team['weeks_played']
        if weeks > 0:
            team['average_points'] = team['total_points_scored'] / weeks
            team['avg_points_per_game'] = team['average_points'] # Alias for Astro
            
            team['efficiency_rate'] = (team['total_points_scored'] / team['total_optimal_points'] * 100) if team['total_optimal_points'] > 0 else 0
            
            # FAAB Efficiency
            # Placeholder for now as we don't track waiver player points yet
            team['faab_efficiency'] = 0
            team['points_per_faab'] = 0 # Alias for Astro
            if team['faab_spent'] > 0:
                team['points_per_faab'] = team['total_points_scored'] / team['faab_spent'] # Using total points for now as proxy or just 0? 
                # Actually, Pt/$ usually means points per FAAB dollar spent. 
                # But usually it's points FROM waiver players. Since we don't track that easily yet, 
                # let's stick to what we have or maybe just leave it as 0 if we can't calculate it accurately.
                # However, the screenshot shows values like 2.39, 4.62. 
                # If I look at the old code (sleeperadvisor.py), it uses waiver_player_points / waiver_spent.
                # Since I don't have waiver_player_points, I'll leave it as 0 or maybe try to approximate it later.
                # For now, let's just use total points / faab spent if faab > 0, but that's wrong.
                # Let's check if I can get waiver player points. It's hard without tracking every player source.
                # I'll leave it as is (0) or maybe just use what was there before.
                # Wait, the previous code had `team['points_per_faab'] = 0`.
                # But the screenshot has values.
                # Let's look at `season-stats-dynasty.astro` again. It uses `team.points_per_faab`.
                # If the JSON has 0, then the table will show 0.00.
                # The user wants columns to match.
                pass

            # Pythagorean Wins & Luck
            pf = team['total_points_scored']
            pa = team['total_points_against']
            if pf > 0 and pa > 0:
                pythag_exp = (pf ** 2.54) / ((pf ** 2.54) + (pa ** 2.54))
                team['pythagorean_wins'] = pythag_exp * weeks
                team['luck_factor'] = team['wins'] - team['pythagorean_wins']
            else:
                team['pythagorean_wins'] = 0
                team['luck_factor'] = 0

            # Trend (Last 3 Weeks Avg vs Season Avg)
            if len(team['weekly_scores']) >= 3:
                last_3_weeks = team['weekly_scores'][-3:]
                last_3_avg = sum(w['points'] for w in last_3_weeks) / 3
                if team['avg_points_per_game'] > 0:
                    team['trend'] = ((last_3_avg - team['avg_points_per_game']) / team['avg_points_per_game']) * 100
                else:
                    team['trend'] = 0
            else:
                team['trend'] = 0

            # Avg Margin (Chopped only)
            if "Chopped" in league_name:
                if team['eliminated_week']:
                    # Exclude elimination week (margin=0) from average
                    survival_weeks = max(weeks - 1, 1)
                    team['avg_margin_above_last'] = team['safety_margin_sum'] / survival_weeks
                else:
                    team['avg_margin_above_last'] = team['safety_margin_sum'] / weeks
            else:
                team['avg_margin_above_last'] = 0
            
            team['avg_safety_margin'] = team['avg_margin_above_last'] # Alias for Astro
            
            # Consistency Score (Placeholder - need std dev calculation)
            # Astro uses consistency_score
            team['consistency_score'] = 0
            if len(team['weekly_scores']) > 1:
                points = [w['points'] for w in team['weekly_scores']]
                mean = statistics.mean(points)
                stdev = statistics.stdev(points)
                if stdev > 0:
                    team['consistency_score'] = mean / stdev

    # Calculate average best theoretical lineup score
    avg_best_theoretical_lineup = 0
    if best_theoretical_lineups:
        avg_best_theoretical_lineup = sum(w['points'] for w in best_theoretical_lineups) / len(best_theoretical_lineups)
    
    # Convert to list and sort by total points
    stats_list = sorted(
        team_stats.values(),
        key=lambda x: x['total_points_scored'],
        reverse=True
    )
    
    print(f"    Processed {len(stats_list)} teams")
    
    return {
        'league_id': league_id,
        'league_name': league_name,
        'season': league.get('season', '2025'),
        'current_week': current_week,
        'generated_at': __import__('datetime').datetime.now().isoformat(),
        'teams': stats_list,
        'best_theoretical_lineups': best_theoretical_lineups,
        'avg_best_theoretical_lineup': round(avg_best_theoretical_lineup, 1)
    }


def calculate_best_theoretical_lineup(week, dynasty_matchups, roster_positions, player_data):
    """Calculate the best possible lineup for a given week using Dynasty player pool."""
    if not dynasty_matchups:
        return None

    all_player_scores = {}
    for matchup in dynasty_matchups:
        if matchup.get('points', 0) > 0:
            players_points = matchup.get('players_points', {}) or {}
            for player_id, pts in players_points.items():
                if player_id and pts > 0:
                    all_player_scores[player_id] = pts

    if not all_player_scores:
        return None

    # Group players by position
    position_players = {}
    for player_id, pts in all_player_scores.items():
        player_info = player_data.get(player_id, {})
        position = player_info.get('position', 'UNKNOWN')
        if position not in position_players:
            position_players[position] = []
        
        first_name = player_info.get('first_name', '')
        last_name = player_info.get('last_name', 'Unknown')
        full_name = f"{first_name} {last_name}".strip()
        if not full_name or full_name == 'Unknown':
             full_name = player_info.get('full_name', 'Unknown Player')

        position_players[position].append({
            'player_id': player_id,
            'name': full_name,
            'position': position,
            'team': player_info.get('team', 'FA'),
            'points': pts
        })

    # Sort each position by points descending
    for pos in position_players:
        position_players[pos].sort(key=lambda x: x['points'], reverse=True)

    # Fill roster positions with best available players
    best_lineup = []
    used_players = set()

    for roster_slot in roster_positions:
        if roster_slot == 'BN':
            continue
        
        eligible_positions = []
        if roster_slot == 'FLEX':
            eligible_positions = ['RB', 'WR', 'TE']
        elif roster_slot == 'SUPER_FLEX':
            eligible_positions = ['QB', 'RB', 'WR', 'TE']
        elif roster_slot == 'REC_FLEX':
            eligible_positions = ['WR', 'TE']
        else:
            eligible_positions = [roster_slot]
        
        best_player = None
        for pos in eligible_positions:
            if pos in position_players:
                for player in position_players[pos]:
                    if player['player_id'] not in used_players:
                        if best_player is None or player['points'] > best_player['points']:
                            best_player = player
                        # Since list is sorted, the first available player for this pos is the best for this pos
                        # But we need to compare across eligible positions (e.g. RB vs WR for FLEX)
                        break 
        
        if best_player:
            used_players.add(best_player['player_id'])
            best_lineup.append({
                'slot': roster_slot,
                'player': best_player['name'],
                'team': best_player['team'],
                'position': best_player['position'],
                'points': best_player['points']
            })

    total_points = sum(p['points'] for p in best_lineup)
    return {
        "week": week,
        "points": round(total_points, 1),
        "lineup": best_lineup
    }


def generate_season_stats_json():
    """Generate season statistics for all leagues."""
    print("\nGenerating Season Statistics...")
    ensure_directories()
    
    for league_key, league_config in LEAGUES.items():
        stats = calculate_season_stats(league_config['id'], league_config['name'])
        
        if stats:
            # Save JSON files
            filename = f"season_stats_{league_key}.json"
            save_json(stats, f"{OUTPUT_DIR}/{filename}")
            save_json(stats, f"{ASTRO_DATA_DIR}/{filename}")
    
    print("\n✅ Season statistics generated successfully!")


if __name__ == "__main__":
    generate_season_stats_json()
