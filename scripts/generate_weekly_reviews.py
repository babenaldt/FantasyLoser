"""Generate weekly review data for both Dynasty and Chopped leagues.

Produces weekly_reviews_dynasty.json and weekly_reviews_chopped.json with:
- Per-week matchup scoreboard with opponent names
- 11 weekly awards per week
- All-play rankings
- FAAB activity (transactions with player names and bids)
- League-wide FAAB summary
- Chopped: elimination details
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core_data import (
    ensure_directories, save_json, SleeperAPI,
    OUTPUT_DIR, ASTRO_DATA_DIR
)
from nfl_week_helper import get_last_completed_nfl_week

# League configurations (must match generate_season_stats.py)
LEAGUES = {
    'dynasty': {
        'id': '1312064104759844864',
        'name': 'Dynasty League',
        'faab_budget': 100,
    },
    'chopped': {
        'id': '1383538112403095552',
        'name': 'Chopped League',
        'faab_budget': 150,
    }
}


def load_player_data():
    """Load Sleeper player database for name resolution."""
    path = os.path.join(ASTRO_DATA_DIR, 'players_data.json')
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    path2 = os.path.join(OUTPUT_DIR, 'players_data.json')
    if os.path.exists(path2):
        with open(path2, 'r') as f:
            return json.load(f)
    return {}


def player_name(player_data, pid):
    """Resolve a Sleeper player ID to a display name."""
    if not pid or pid == '0':
        return 'Unknown'
    p = player_data.get(str(pid), {})
    if not p:
        return str(pid)
    first = p.get('first_name', '')
    last = p.get('last_name', '')
    if first and last:
        return f"{first} {last}"
    return p.get('full_name', str(pid))


def player_position(player_data, pid):
    """Get a player's position."""
    if not pid or pid == '0':
        return ''
    return player_data.get(str(pid), {}).get('position', '')


def calculate_optimal_score(matchup, roster_positions, player_data):
    """Calculate optimal (best possible) lineup score."""
    players_points = matchup.get('players_points', {}) or {}
    if not players_points or not player_data:
        return matchup.get('points', 0)

    available = []
    for pid, pts in players_points.items():
        pos = player_data.get(str(pid), {}).get('position', '')
        if pos:
            available.append({'id': pid, 'pos': pos, 'points': pts})
    available.sort(key=lambda x: x['points'], reverse=True)

    used = set()
    optimal = 0
    starter_slots = [p for p in roster_positions if p != 'BN']

    for slot in starter_slots:
        if slot in ('FLEX', 'SUPER_FLEX', 'WRTQ', 'REC_FLEX'):
            continue
        for p in available:
            if p['id'] not in used and p['pos'] == slot:
                optimal += p['points']
                used.add(p['id'])
                break

    flex_slots = [s for s in starter_slots if s in ('FLEX', 'SUPER_FLEX', 'WRTQ', 'REC_FLEX')]
    flex_eligible = {'FLEX': ['RB', 'WR', 'TE'],
                     'SUPER_FLEX': ['QB', 'RB', 'WR', 'TE'],
                     'WRTQ': ['QB', 'WR', 'RB', 'TE'],
                     'REC_FLEX': ['WR', 'TE']}
    for slot in flex_slots:
        eligible = flex_eligible.get(slot, ['RB', 'WR', 'TE'])
        for p in available:
            if p['id'] not in used and p['pos'] in eligible:
                optimal += p['points']
                used.add(p['id'])
                break

    return max(optimal, matchup.get('points', 0))


def build_week_data(week, matchups, transactions, roster_map, user_map,
                    player_data, roster_positions, league_type, elims_for_week_fn=None):
    """Build the complete data object for a single week.

    Args:
        week: NFL week number
        matchups: list from Sleeper matchups API
        transactions: list from Sleeper transactions API
        roster_map: {roster_id: roster_obj}
        user_map: {user_id: user_obj}
        player_data: Sleeper player database dict
        roster_positions: list of position slots for the league
        league_type: 'dynasty' or 'chopped'
        elims_for_week_fn: callable(week) -> int, how many teams eliminated (chopped only)
    """

    # --- Resolve owner names ---
    def owner_name(roster_id):
        roster = roster_map.get(roster_id, {})
        uid = roster.get('owner_id', '')
        user = user_map.get(uid, {})
        return user.get('display_name', user.get('metadata', {}).get('team_name', f'Team {roster_id}'))

    # --- Build matchup pairs ---
    teams_by_matchup = {}
    all_team_scores = []

    for m in matchups:
        rid = m.get('roster_id')
        mid = m.get('matchup_id')
        pts = m.get('points', 0) or 0
        starters = m.get('starters', []) or []
        players_points = m.get('players_points', {}) or {}

        bench_pts = sum(v for k, v in players_points.items() if k not in starters)
        optimal = calculate_optimal_score(m, roster_positions, player_data)
        efficiency = round((pts / optimal * 100), 1) if optimal > 0 else 0

        # Find top individual starter
        starter_scores = []
        for pid in starters:
            if pid and str(pid) != '0':
                sp = players_points.get(str(pid), 0)
                starter_scores.append({
                    'player_id': str(pid),
                    'player_name': player_name(player_data, pid),
                    'position': player_position(player_data, pid),
                    'points': round(sp, 2),
                })

        # Projected total
        proj = 0  # projections not fetched here; we use delta from optimal/actual

        team_entry = {
            'roster_id': rid,
            'owner_name': owner_name(rid),
            'points': round(pts, 2),
            'optimal': round(optimal, 2),
            'bench_points': round(bench_pts, 2),
            'efficiency': efficiency,
            'top_starters': sorted(starter_scores, key=lambda x: x['points'], reverse=True)[:3],
        }

        all_team_scores.append(team_entry)

        if mid is not None:
            teams_by_matchup.setdefault(mid, []).append(team_entry)

    # --- Build scoreboard matchups ---
    scoreboard = []
    for mid, teams in sorted(teams_by_matchup.items()):
        if len(teams) == 2:
            teams_sorted = sorted(teams, key=lambda t: t['points'], reverse=True)
            scoreboard.append({
                'matchup_id': mid,
                'winner': teams_sorted[0],
                'loser': teams_sorted[1],
                'margin': round(teams_sorted[0]['points'] - teams_sorted[1]['points'], 2),
            })
        else:
            scoreboard.append({
                'matchup_id': mid,
                'teams': teams,
                'margin': 0,
            })

    # --- All-Play Rankings ---
    all_points = [t['points'] for t in all_team_scores]
    all_play = []
    for t in all_team_scores:
        wins = sum(1 for p in all_points if t['points'] > p) - (1 if t['points'] in all_points else 0)
        # Subtract self-comparison
        wins = sum(1 for other in all_team_scores if other['roster_id'] != t['roster_id'] and t['points'] > other['points'])
        losses = sum(1 for other in all_team_scores if other['roster_id'] != t['roster_id'] and t['points'] < other['points'])
        ties = sum(1 for other in all_team_scores if other['roster_id'] != t['roster_id'] and t['points'] == other['points'])
        all_play.append({
            'owner_name': t['owner_name'],
            'points': t['points'],
            'all_play_wins': wins,
            'all_play_losses': losses,
            'all_play_ties': ties,
        })
    all_play.sort(key=lambda x: x['all_play_wins'], reverse=True)

    # --- Awards ---
    awards = compute_awards(all_team_scores, scoreboard, league_type, elims_for_week_fn, week)

    # --- FAAB Activity ---
    faab_activity = []
    week_faab_total = 0
    if transactions:
        for t in transactions:
            if t.get('status') != 'complete':
                continue
            if t.get('type') != 'waiver':
                continue
            bid = t.get('settings', {}).get('waiver_bid', 0)
            creator = t.get('creator', '')
            # Resolve creator to owner name
            creator_rid = None
            for rid, roster in roster_map.items():
                if roster.get('owner_id') == creator:
                    creator_rid = rid
                    break
            txn_owner = owner_name(creator_rid) if creator_rid else 'Unknown'

            adds = t.get('adds', {}) or {}
            drops = t.get('drops', {}) or {}

            added_players = []
            for pid in adds:
                added_players.append({
                    'player_id': str(pid),
                    'player_name': player_name(player_data, pid),
                    'position': player_position(player_data, pid),
                })
            dropped_players = []
            for pid in drops:
                dropped_players.append({
                    'player_id': str(pid),
                    'player_name': player_name(player_data, pid),
                    'position': player_position(player_data, pid),
                })

            faab_activity.append({
                'owner': txn_owner,
                'bid': bid,
                'added': added_players,
                'dropped': dropped_players,
            })
            week_faab_total += bid

    faab_activity.sort(key=lambda x: x['bid'], reverse=True)

    # --- Chopped Elimination ---
    elimination = None
    if league_type == 'chopped' and elims_for_week_fn:
        num_elim = elims_for_week_fn(week)
        sorted_scores = sorted(all_team_scores, key=lambda t: t['points'])
        eliminated = sorted_scores[:num_elim]
        threshold = sorted_scores[num_elim]['points'] if len(sorted_scores) > num_elim else 0
        elimination = {
            'num_eliminated': num_elim,
            'eliminated_teams': [{
                'owner_name': e['owner_name'],
                'points': e['points'],
            } for e in eliminated],
            'survival_threshold': round(threshold, 2),
        }

    week_data = {
        'week': week,
        'scoreboard': scoreboard,
        'all_play': all_play,
        'awards': awards,
        'faab_activity': faab_activity,
        'faab_week_total': week_faab_total,
        'team_scores': sorted(all_team_scores, key=lambda t: t['points'], reverse=True),
    }
    if elimination:
        week_data['elimination'] = elimination

    return week_data


def compute_awards(all_team_scores, scoreboard, league_type, elims_for_week_fn, week):
    """Compute all weekly awards."""
    awards = {}

    if not all_team_scores:
        return awards

    sorted_by_pts = sorted(all_team_scores, key=lambda t: t['points'], reverse=True)

    # 1. Top Scorer
    top = sorted_by_pts[0]
    awards['top_scorer'] = {
        'owner_name': top['owner_name'],
        'points': top['points'],
    }

    # 2. Bust of the Week (lowest score)
    bust = sorted_by_pts[-1]
    awards['bust'] = {
        'owner_name': bust['owner_name'],
        'points': bust['points'],
    }

    # 3. Overachiever (highest actual - optimal gap inverted: best efficiency beyond expectations)
    # Actually: biggest positive delta = actual much higher than what?
    # Use bench boss as proxy: fewest points on bench (best lineup decisions)
    # Better: actual / optimal is efficiency. Best efficiency = overachiever
    best_eff = max(all_team_scores, key=lambda t: t['efficiency'])
    awards['efficiency_king'] = {
        'owner_name': best_eff['owner_name'],
        'efficiency': best_eff['efficiency'],
        'points': best_eff['points'],
        'optimal': best_eff['optimal'],
    }

    # 4. Overachiever: highest actual above bench expectation
    # Simplify: team that left the fewest points on bench (optimal - actual smallest)
    missed_pts = [(t, t['optimal'] - t['points']) for t in all_team_scores]
    missed_pts.sort(key=lambda x: x[1])
    overachiever = missed_pts[0]
    awards['overachiever'] = {
        'owner_name': overachiever[0]['owner_name'],
        'points': overachiever[0]['points'],
        'optimal': overachiever[0]['optimal'],
        'missed': round(overachiever[1], 2),
    }

    # 5. Underachiever (most points left on bench relative to optimal)
    underachiever = missed_pts[-1]
    awards['underachiever'] = {
        'owner_name': underachiever[0]['owner_name'],
        'points': underachiever[0]['points'],
        'optimal': underachiever[0]['optimal'],
        'missed': round(underachiever[1], 2),
    }

    # 6. Bench Boss (most total bench points)
    bench_boss = max(all_team_scores, key=lambda t: t['bench_points'])
    awards['bench_boss'] = {
        'owner_name': bench_boss['owner_name'],
        'bench_points': bench_boss['bench_points'],
        'points': bench_boss['points'],
    }

    # 7. Player of the Week (top individual starter across all rosters)
    best_player = {'player_name': '', 'points': -1, 'position': '', 'owner': ''}
    for t in all_team_scores:
        for s in t.get('top_starters', []):
            if s['points'] > best_player['points']:
                best_player = {
                    'player_name': s['player_name'],
                    'player_id': s.get('player_id', ''),
                    'points': s['points'],
                    'position': s['position'],
                    'owner': t['owner_name'],
                }
    if best_player['points'] > 0:
        awards['player_of_week'] = best_player

    # 8. FAAB Big Spender — computed later when we have transaction data
    # (set by caller or left empty)

    # Dynasty-specific awards
    if league_type == 'dynasty' and scoreboard:
        # Close Call (smallest margin of victory among H2H matchups)
        valid_matchups = [m for m in scoreboard if 'winner' in m and m['margin'] > 0]
        if valid_matchups:
            closest = min(valid_matchups, key=lambda m: m['margin'])
            awards['close_call'] = {
                'winner': closest['winner']['owner_name'],
                'loser': closest['loser']['owner_name'],
                'winner_score': closest['winner']['points'],
                'loser_score': closest['loser']['points'],
                'margin': closest['margin'],
            }

            # Blowout (largest margin)
            blowout = max(valid_matchups, key=lambda m: m['margin'])
            awards['blowout'] = {
                'winner': blowout['winner']['owner_name'],
                'loser': blowout['loser']['owner_name'],
                'winner_score': blowout['winner']['points'],
                'loser_score': blowout['loser']['points'],
                'margin': blowout['margin'],
            }

    # Chopped-specific: Lucky Escape (lowest score that survived)
    if league_type == 'chopped' and elims_for_week_fn:
        num_elim = elims_for_week_fn(week)
        sorted_asc = sorted(all_team_scores, key=lambda t: t['points'])
        if len(sorted_asc) > num_elim:
            survivor = sorted_asc[num_elim]  # first survivor (lowest among safe teams)
            eliminated_best = sorted_asc[num_elim - 1]
            awards['lucky_escape'] = {
                'owner_name': survivor['owner_name'],
                'points': survivor['points'],
                'margin': round(survivor['points'] - eliminated_best['points'], 2),
            }

    return awards


def generate_weekly_review(league_key, league_config):
    """Generate weekly review JSON for a league."""
    league_id = league_config['id']
    league_name = league_config['name']
    faab_budget = league_config['faab_budget']
    league_type = league_key  # 'dynasty' or 'chopped'

    print(f"\n  Generating Weekly Reviews for {league_name}...")

    api = SleeperAPI(league_id)
    player_data = load_player_data()

    league = api.get_league()
    if not league:
        print(f"    Error: Could not fetch league data")
        return None

    rosters = api.get_rosters()
    users = api.get_users()
    if not rosters or not users:
        print(f"    Error: Could not fetch rosters or users")
        return None

    roster_map = {r['roster_id']: r for r in rosters}
    user_map = {u['user_id']: u for u in users}
    roster_positions = league.get('roster_positions', [])
    total_teams = len(rosters)

    # Chopped elimination schedule
    elimination_weeks_total = 15
    double_elim_weeks = max(0, (total_teams - 1) - elimination_weeks_total)

    def elims_for_week(w):
        return 2 if w <= double_elim_weeks else 1

    last_completed = get_last_completed_nfl_week()
    print(f"    Last completed week: {last_completed}")

    if last_completed <= 0:
        print(f"    No completed weeks — generating empty review")
        return {
            'league_name': league_name,
            'league_type': league_type,
            'season': league.get('season', '2026'),
            'total_weeks': 0,
            'league_faab_budget': faab_budget,
            'total_teams': total_teams,
            'weeks': [],
            'faab_summary': {
                'total_league_spent': 0,
                'total_league_budget': faab_budget * total_teams,
                'cumulative_by_week': [],
                'by_team': [],
                'top_moves': [],
            }
        }

    weeks_data = []
    all_faab_moves = []  # for top moves across all weeks
    cumulative_by_week = []
    team_faab_totals = {}  # roster_id -> total spent
    cumulative_total = 0

    # Build owner name lookup for FAAB summary
    def owner_name_from_rid(rid):
        roster = roster_map.get(rid, {})
        uid = roster.get('owner_id', '')
        user = user_map.get(uid, {})
        return user.get('display_name', user.get('metadata', {}).get('team_name', f'Team {rid}'))

    for week in range(1, last_completed + 1):
        print(f"    Processing week {week}...")
        matchups = api.get_matchups(week) or []
        transactions = api.get_transactions(week) or []

        elim_fn = elims_for_week if league_type == 'chopped' else None
        week_data = build_week_data(
            week, matchups, transactions,
            roster_map, user_map, player_data, roster_positions,
            league_type, elim_fn
        )

        # Set FAAB Big Spender award from transaction data
        if week_data['faab_activity']:
            top_spender_txns = {}
            for txn in week_data['faab_activity']:
                top_spender_txns.setdefault(txn['owner'], 0)
                top_spender_txns[txn['owner']] += txn['bid']
            if top_spender_txns:
                biggest = max(top_spender_txns.items(), key=lambda x: x[1])
                week_data['awards']['faab_spender'] = {
                    'owner_name': biggest[0],
                    'total_spent': biggest[1],
                }

        weeks_data.append(week_data)

        # Track FAAB across weeks
        cumulative_total += week_data['faab_week_total']
        cumulative_by_week.append({
            'week': week,
            'spent': week_data['faab_week_total'],
            'cumulative': cumulative_total,
        })

        # Track per-team FAAB
        for txn in week_data.get('faab_activity', []):
            # Find roster_id for this owner
            for rid, roster in roster_map.items():
                uid = roster.get('owner_id', '')
                user = user_map.get(uid, {})
                name = user.get('display_name', '')
                if name == txn['owner']:
                    team_faab_totals[rid] = team_faab_totals.get(rid, 0) + txn['bid']
                    break

            # Track all moves for "top moves" list
            for added in txn.get('added', []):
                all_faab_moves.append({
                    'week': week,
                    'owner': txn['owner'],
                    'player_name': added['player_name'],
                    'position': added['position'],
                    'bid': txn['bid'],
                })

    # Build FAAB summary
    faab_by_team = []
    for rid in roster_map:
        spent = team_faab_totals.get(rid, 0)
        faab_by_team.append({
            'owner_name': owner_name_from_rid(rid),
            'spent': spent,
            'remaining': faab_budget - spent,
            'moves': 0,  # will count below
        })

    # Count moves per team
    for week_d in weeks_data:
        for txn in week_d.get('faab_activity', []):
            for entry in faab_by_team:
                if entry['owner_name'] == txn['owner']:
                    entry['moves'] += 1

    faab_by_team.sort(key=lambda x: x['spent'], reverse=True)

    # Top 10 highest bids
    top_moves = sorted(all_faab_moves, key=lambda x: x['bid'], reverse=True)[:10]

    result = {
        'league_name': league_name,
        'league_type': league_type,
        'season': league.get('season', '2026'),
        'total_weeks': last_completed,
        'league_faab_budget': faab_budget,
        'total_teams': total_teams,
        'weeks': weeks_data,
        'faab_summary': {
            'total_league_spent': cumulative_total,
            'total_league_budget': faab_budget * total_teams,
            'cumulative_by_week': cumulative_by_week,
            'by_team': faab_by_team,
            'top_moves': top_moves,
        },
    }

    return result


def generate_weekly_reviews():
    """Generate weekly review JSON files for all leagues."""
    print("\n" + "=" * 80)
    print("GENERATING WEEKLY REVIEWS")
    print("=" * 80)

    ensure_directories()

    for league_key, config in LEAGUES.items():
        result = generate_weekly_review(league_key, config)
        if result:
            filename = f"weekly_reviews_{league_key}.json"
            save_json(result, os.path.join(OUTPUT_DIR, filename))
            save_json(result, os.path.join(ASTRO_DATA_DIR, filename))
        else:
            print(f"  Warning: No data generated for {config['name']}")


if __name__ == "__main__":
    generate_weekly_reviews()
