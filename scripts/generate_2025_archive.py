#!/usr/bin/env python3
"""
One-time script to generate archived 2025 player/kicker/DST/defense stats
with correct ownership (2025 league IDs) and postseason data.
"""

import json
import os
import sys
import statistics
from datetime import datetime

import nflreadpy as nfl
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core_data import (
    calculate_fantasy_points, SCORING_PRESETS, SleeperAPI,
    ROSTERABLE_POSITIONS, save_json
)

ARCHIVE_DIR = "website/public/data/archive/2025"
SEASON = 2025

# 2025 league IDs
DYNASTY_LEAGUE_ID_2025 = "1264304480178950144"
CHOPPED_LEAGUE_ID_2025 = "1263579037352079360"

TEAM_CODE_MAP = {'LAR': 'LA', 'JAX': 'JAC'}

PLAYOFF_ROUND_NAMES = {
    19: 'Wild Card', 20: 'Divisional', 21: 'Conference', 22: 'Super Bowl'
}


def normalize_team(team_code):
    if not team_code:
        return team_code
    return TEAM_CODE_MAP.get(team_code, team_code)


def load_ownership_2025():
    """Load player ownership from 2025 Sleeper leagues."""
    print("  Loading 2025 ownership data...")
    ownership = {}

    try:
        sleeper_players = SleeperAPI.get_all_players()
        if not sleeper_players:
            print("  Warning: Could not load Sleeper players")
            return {}

        for league_id, league_label in [
            (DYNASTY_LEAGUE_ID_2025, 'dynasty_owner'),
            (CHOPPED_LEAGUE_ID_2025, 'chopped_owner')
        ]:
            api = SleeperAPI(league_id)
            users = api.get_users() or []
            user_map = {u['user_id']: u['display_name'] for u in users}
            rosters = api.get_rosters() or []

            mapped = 0
            for roster in rosters:
                if not roster:
                    continue
                owner_id = roster.get('owner_id')
                owner_name = user_map.get(owner_id, 'Unknown')
                players_list = roster.get('players')
                if not players_list:
                    continue
                for sid in players_list:
                    pd_ = sleeper_players.get(sid)
                    if pd_:
                        first = (pd_.get('first_name') or '').strip()
                        last = (pd_.get('last_name') or '').strip()
                        team = normalize_team((pd_.get('team') or '').strip())
                        if first and last and team:
                            key = (f"{first} {last}", team)
                            if key not in ownership:
                                ownership[key] = {}
                            ownership[key][league_label] = owner_name
                            mapped += 1
            print(f"    {league_label}: mapped {mapped} roster spots")
    except Exception as e:
        print(f"  Error loading ownership: {e}")

    return ownership


def generate_player_archive(weekly_stats, post_stats, schedule_lookup,
                            snap_lookup, player_ages, ownership, defense_map):
    """Generate player_stats.json for 2025 archive."""
    print("\n  Generating player stats archive...")

    player_stats = {}

    def process_rows(rows, is_postseason=False):
        for row in rows.iter_rows(named=True):
            player_id = row.get('player_id')
            if not player_id:
                continue
            position = row.get('position', '')
            if position not in ROSTERABLE_POSITIONS or position in ('K', 'DEF'):
                continue

            if player_id not in player_stats:
                player_stats[player_id] = {
                    'player_id': player_id,
                    'player_name': row.get('player_display_name', 'Unknown'),
                    'position': position,
                    'team': row.get('team', 'FA'),
                    'games_played': 0,
                    'total_points': 0,
                    'weekly_points': [],
                    'postseason': {
                        'games_played': 0,
                        'total_points': 0,
                        'weekly_points': []
                    }
                }

            pts = calculate_fantasy_points(row)
            week = row.get('week')
            if not week or pts <= 0:
                continue

            opponent = row.get('opponent_team', 'N/A')
            opp_avg = defense_map.get(opponent, {}).get(position, 0)
            player_name = row.get('player_display_name')
            team = row.get('team')
            snap_pct = snap_lookup.get((player_name, team, week), 0)

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
                'targets': row.get('targets', 0) or 0,
                'offense_pct': snap_pct,
            }

            entry = {
                'week': week,
                'points': round(pts, 2),
                'opponent': opponent,
                'opp_avg_allowed': round(opp_avg, 1),
                'projected_points': None,
                'raw_stats': raw_stats
            }

            if is_postseason:
                entry['round'] = PLAYOFF_ROUND_NAMES.get(week, f'Week {week}')
                player_stats[player_id]['postseason']['weekly_points'].append(entry)
                player_stats[player_id]['postseason']['total_points'] += pts
                player_stats[player_id]['postseason']['games_played'] += 1
            else:
                player_stats[player_id]['weekly_points'].append(entry)
                player_stats[player_id]['total_points'] += pts
                player_stats[player_id]['games_played'] += 1

    process_rows(weekly_stats, is_postseason=False)
    if post_stats is not None and len(post_stats) > 0:
        process_rows(post_stats, is_postseason=True)

    # Calculate derived stats
    position_totals = {}
    position_counts = {}
    players_list = []

    for pid, stats in player_stats.items():
        if stats['games_played'] == 0:
            continue
        stats['weekly_points'].sort(key=lambda x: x['week'])

        # Expand to 18-week schedule
        played = {wp['week']: wp for wp in stats['weekly_points']}
        full_schedule = []
        for w in range(1, 19):
            if w in played:
                full_schedule.append(played[w])
            else:
                opp = schedule_lookup.get((stats['team'], w))
                if opp is None:
                    opp = 'BYE'
                    opp_avg = 0
                else:
                    opp_avg = defense_map.get(opp, {}).get(stats['position'], 0)
                full_schedule.append({
                    'week': w, 'points': None, 'opponent': opp,
                    'opp_avg_allowed': round(opp_avg, 1),
                    'projected_points': None, 'raw_stats': None
                })
        stats['weekly_points'] = full_schedule

        points_list = [wp['points'] for wp in full_schedule if wp['points'] is not None]
        if not points_list:
            continue

        avg_ppg = stats['total_points'] / stats['games_played']
        stats['avg_points_per_game'] = avg_ppg
        stats['best_game'] = max(points_list)
        stats['worst_game'] = min(points_list)
        stats['median'] = statistics.median(points_list)
        std_dev = statistics.stdev(points_list) if len(points_list) > 1 else 0
        stats['std_dev'] = std_dev
        stats['consistency'] = avg_ppg / std_dev if std_dev > 0 else 0
        above = sum(1 for p in points_list if p > avg_ppg)
        stats['pct_above_avg'] = (above / len(points_list)) * 100

        snaps = [wp['raw_stats'].get('offense_pct', 0) for wp in full_schedule if wp['raw_stats']]
        stats['avg_snap_pct'] = round(sum(snaps) / len(snaps) * 100, 1) if snaps else 0
        stats['nfl_stats'] = {'age': player_ages.get(pid, '-'), 'avg_snap_pct': stats['avg_snap_pct']}

        okey = (stats['player_name'], stats['team'])
        own = ownership.get(okey, {})
        stats['dynasty_owner'] = own.get('dynasty_owner', 'Free Agent')
        stats['chopped_owner'] = own.get('chopped_owner', 'Free Agent')

        played_weeks = [w for w in full_schedule if w['points'] is not None and w['points'] > 0]
        if len(played_weeks) >= 4:
            l2 = played_weeks[-2:]
            p2 = played_weeks[-4:-2]
            l2a = sum(w['points'] for w in l2) / 2
            p2a = sum(w['points'] for w in p2) / 2
            diff = l2a - p2a
            stats['trend_pct'] = abs((diff / p2a * 100) if p2a > 0 else 0)
            stats['trend_dir'] = "▲" if diff > 1 else ("▼" if diff < -1 else "-")
        elif len(played_weeks) >= 2:
            l2 = played_weeks[-2:]
            l2a = sum(w['points'] for w in l2) / 2
            diff = l2a - avg_ppg
            stats['trend_pct'] = abs((diff / avg_ppg * 100) if avg_ppg > 0 else 0)
            stats['trend_dir'] = "▲" if diff > 1 else ("▼" if diff < -1 else "-")
        else:
            stats['trend_pct'] = 0
            stats['trend_dir'] = "-"

        pos = stats['position']
        position_totals[pos] = position_totals.get(pos, 0) + avg_ppg
        position_counts[pos] = position_counts.get(pos, 0) + 1

        # Clean up postseason
        if stats['postseason']['games_played'] == 0:
            stats['postseason'] = None
        else:
            ps = stats['postseason']
            ps['avg_points_per_game'] = round(ps['total_points'] / ps['games_played'], 2)
            ps['total_points'] = round(ps['total_points'], 2)
            ps['weekly_points'].sort(key=lambda x: x['week'])

        players_list.append(stats)

    pos_avgs = {p: t / position_counts[p] for p, t in position_totals.items()}
    for s in players_list:
        pa = pos_avgs.get(s['position'], 0)
        s['position_avg'] = pa
        s['vs_position_avg'] = s['avg_points_per_game'] - pa

    players_list.sort(key=lambda x: x['total_points'], reverse=True)
    print(f"    {len(players_list)} players processed")

    return {
        'season': str(SEASON),
        'generated_at': datetime.now().isoformat(),
        'players': players_list
    }


def generate_kicker_archive(team_stats_df, rosters_df, post_team_stats_df=None):
    """Generate kicker_stats.json for 2025 archive."""
    import pandas as pd
    print("\n  Generating kicker stats archive...")

    kickers = rosters_df[rosters_df['position'] == 'K'][['team', 'full_name', 'gsis_id', 'birth_date']].copy()
    kickers = kickers.rename(columns={'full_name': 'player_name', 'gsis_id': 'player_id'})

    reg_stats = team_stats_df[team_stats_df['season_type'] == 'REG'].copy()
    kicker_stats = reg_stats.merge(kickers, on='team', how='inner')

    players_dict = {}

    def process_kicker_rows(df, is_postseason=False):
        for _, row in df.iterrows():
            pid = row['player_id']
            if pid not in players_dict:
                players_dict[pid] = {
                    'player_name': row['player_name'],
                    'player_id': pid,
                    'position': 'K',
                    'team': row['team'],
                    'birth_date': str(row.get('birth_date')) if row.get('birth_date') else None,
                    'games_played': 0,
                    'total_points': 0,
                    'weekly_stats': [],
                    'postseason': {'games_played': 0, 'total_points': 0, 'weekly_stats': []}
                }
            player = players_dict[pid]
            raw = {
                'fg_0_19': int(row.get('fg_made_0_19', 0) or 0),
                'fg_20_29': int(row.get('fg_made_20_29', 0) or 0),
                'fg_30_39': int(row.get('fg_made_30_39', 0) or 0),
                'fg_40_49': int(row.get('fg_made_40_49', 0) or 0),
                'fg_50_59': int(row.get('fg_made_50_59', 0) or 0),
                'fg_60_plus': int(row.get('fg_made_60_', 0) or 0),
                'fg_missed': int(row.get('fg_missed', 0) or 0),
                'fg_att': int(row.get('fg_att', 0) or 0),
                'pat_made': int(row.get('pat_made', 0) or 0),
                'pat_missed': int(row.get('pat_missed', 0) or 0),
                'pat_att': int(row.get('pat_att', 0) or 0),
            }
            pts = calculate_fantasy_points(raw, SCORING_PRESETS['ppr'])
            entry = {
                'week': int(row['week']),
                'opponent': row.get('opponent_team', 'N/A'),
                'points': round(pts, 2),
                'raw_stats': raw
            }
            if is_postseason:
                entry['round'] = PLAYOFF_ROUND_NAMES.get(int(row['week']), f"Week {int(row['week'])}")
                player['postseason']['weekly_stats'].append(entry)
                player['postseason']['total_points'] += pts
                player['postseason']['games_played'] += 1
            else:
                player['weekly_stats'].append(entry)
                player['total_points'] += pts
                player['games_played'] += 1

    process_kicker_rows(kicker_stats, is_postseason=False)

    if post_team_stats_df is not None and len(post_team_stats_df) > 0:
        post_kicker = post_team_stats_df.merge(kickers, on='team', how='inner')
        if len(post_kicker) > 0:
            process_kicker_rows(post_kicker, is_postseason=True)

    players = []
    for pid, pd_ in players_dict.items():
        pd_['weekly_stats'].sort(key=lambda x: x['week'])
        total_fg = sum(
            w['raw_stats']['fg_0_19'] + w['raw_stats']['fg_20_29'] +
            w['raw_stats']['fg_30_39'] + w['raw_stats']['fg_40_49'] +
            w['raw_stats']['fg_50_59'] + w['raw_stats']['fg_60_plus']
            for w in pd_['weekly_stats']
        )
        total_fg_att = sum(w['raw_stats']['fg_att'] for w in pd_['weekly_stats'])
        total_pat = sum(w['raw_stats']['pat_made'] for w in pd_['weekly_stats'])
        total_pat_att = sum(w['raw_stats']['pat_att'] for w in pd_['weekly_stats'])

        pd_['aggregate_stats'] = {
            'fg_0_19': sum(w['raw_stats']['fg_0_19'] for w in pd_['weekly_stats']),
            'fg_20_29': sum(w['raw_stats']['fg_20_29'] for w in pd_['weekly_stats']),
            'fg_30_39': sum(w['raw_stats']['fg_30_39'] for w in pd_['weekly_stats']),
            'fg_40_49': sum(w['raw_stats']['fg_40_49'] for w in pd_['weekly_stats']),
            'fg_50_59': sum(w['raw_stats']['fg_50_59'] for w in pd_['weekly_stats']),
            'fg_60_plus': sum(w['raw_stats']['fg_60_plus'] for w in pd_['weekly_stats']),
            'total_fg_made': total_fg,
            'total_fg_att': total_fg_att,
            'total_fg_missed': sum(w['raw_stats']['fg_missed'] for w in pd_['weekly_stats']),
            'fg_pct': round(total_fg / total_fg_att * 100, 1) if total_fg_att > 0 else 0,
            'total_pat_made': total_pat,
            'total_pat_att': total_pat_att,
            'total_pat_missed': sum(w['raw_stats']['pat_missed'] for w in pd_['weekly_stats']),
            'pat_pct': round(total_pat / total_pat_att * 100, 1) if total_pat_att > 0 else 0
        }

        age = '-'
        if pd_.get('birth_date'):
            try:
                bd = datetime.strptime(str(pd_['birth_date']).split(' ')[0], '%Y-%m-%d')
                today = datetime.today()
                age = today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
            except (ValueError, TypeError):
                pass
        pd_['nfl_stats'] = {'age': age}
        pd_['avg_points'] = round(pd_['total_points'] / pd_['games_played'], 2) if pd_['games_played'] > 0 else 0
        pd_['total_points'] = round(pd_['total_points'], 2)

        if pd_['postseason']['games_played'] == 0:
            pd_['postseason'] = None
        else:
            ps = pd_['postseason']
            ps['avg_points_per_game'] = round(ps['total_points'] / ps['games_played'], 2)
            ps['total_points'] = round(ps['total_points'], 2)
            ps['weekly_stats'].sort(key=lambda x: x['week'])

        players.append(pd_)

    players.sort(key=lambda x: x['total_points'], reverse=True)
    print(f"    {len(players)} kickers processed")

    return {
        'season': SEASON,
        'generated_at': datetime.now().isoformat(),
        'players': players
    }


def generate_dst_archive():
    """Generate dst_stats.json for 2025 archive (DST fantasy points scored)."""
    import pandas as pd
    print("\n  Generating DST stats archive...")

    from generate_dst_stats import (
        _calc_defensive_points_against, _calc_fumbles_by_team_week,
        _calc_return_tds_by_team_week, _calc_blocked_kicks_by_team_week
    )

    team_stats = nfl.load_team_stats([SEASON]).to_pandas()
    schedules = nfl.load_schedules([SEASON]).to_pandas()
    pbp = nfl.load_pbp([SEASON]).to_pandas()

    # Regular season
    reg_ts = team_stats[team_stats['season_type'] == 'REG'].copy()
    reg_pbp = pbp[pbp['season_type'] == 'REG'].copy()
    reg_sched = schedules[schedules['game_type'] == 'REG'].copy()

    # Postseason (schedules use WC/DIV/CON/SB, not POST)
    post_ts = team_stats[team_stats['season_type'] == 'POST'].copy()
    post_pbp = pbp[pbp['season_type'] == 'POST'].copy()
    post_sched = schedules[schedules['game_type'].isin(['WC', 'DIV', 'CON', 'SB', 'POST'])].copy()

    def build_dst_data(ts, sched, pbp_data):
        sched_expanded = []
        for _, g in sched.iterrows():
            if pd.notna(g.get('home_score')) and pd.notna(g.get('away_score')):
                sched_expanded.append({'week': g['week'], 'game_id': g['game_id'],
                                       'team': g['home_team'], 'opponent': g['away_team'],
                                       'points_allowed': g['away_score']})
                sched_expanded.append({'week': g['week'], 'game_id': g['game_id'],
                                       'team': g['away_team'], 'opponent': g['home_team'],
                                       'points_allowed': g['home_score']})
        sched_df = pd.DataFrame(sched_expanded)
        if sched_df.empty:
            return {}

        def_pts = {}
        for gid, g in pbp_data.groupby('game_id', sort=False):
            pts = _calc_defensive_points_against(g)
            for t, p in pts.items():
                def_pts[(str(gid), t)] = p

        fumbles = _calc_fumbles_by_team_week(pbp_data)
        ret_tds = _calc_return_tds_by_team_week(pbp_data)
        blocked = _calc_blocked_kicks_by_team_week(pbp_data)

        merged = ts.merge(sched_df, on=['week', 'team'], how='left')
        merged = merged.merge(fumbles, on=['week', 'team'], how='left')
        merged = merged.merge(ret_tds, on=['week', 'team'], how='left')
        merged = merged.merge(blocked, on=['week', 'team'], how='left')
        for col in ['def_ff', 'def_fr', 'st_ff', 'st_fr', 'kr_td', 'st_td', 'def_blocked_kick']:
            if col in merged.columns:
                merged[col] = merged[col].fillna(0)

        teams_dict = {}
        for _, row in merged.iterrows():
            team = row['team']
            if team not in teams_dict:
                teams_dict[team] = {'team': team, 'position': 'DEF', 'games_played': 0,
                                    'total_points': 0, 'weekly_stats': []}

            gid = str(row['game_id']) if pd.notna(row.get('game_id')) else None
            pa_total = int(row['points_allowed']) if pd.notna(row.get('points_allowed')) else 0
            def_scored = def_pts.get((gid, team), 0) if gid else 0
            pa_adj = max(pa_total - def_scored, 0)
            total_def_tds = int(row['def_tds']) + int(row['fumble_recovery_tds'])

            raw = {
                'def_td': total_def_tds,
                'kr_td': int(row.get('kr_td', 0) or 0),
                'st_td': int(row.get('st_td', 0) or 0),
                'def_int': int(row['def_interceptions']),
                'def_fumble_recovery': int(row.get('def_fr', 0) or 0),
                'def_fumble_forced': int(row.get('def_ff', 0) or 0),
                'st_fumble_recovery': int(row.get('st_fr', 0) or 0),
                'st_fumble_forced': int(row.get('st_ff', 0) or 0),
                'def_sack': float(row['def_sacks']),
                'def_safety': int(row['def_safeties']),
                'def_blocked_kick': int(row.get('def_blocked_kick', 0) or 0),
                'points_allowed': pa_adj,
                '_points_allowed_total': pa_total,
                '_points_allowed_def_scored': def_scored,
            }
            pts = calculate_fantasy_points(raw, SCORING_PRESETS['ppr'])
            teams_dict[team]['weekly_stats'].append({
                'week': int(row['week']),
                'opponent': row['opponent'] if pd.notna(row.get('opponent')) else row.get('opponent_team', 'N/A'),
                'points': round(pts, 2), 'raw_stats': raw
            })
            teams_dict[team]['games_played'] += 1
            teams_dict[team]['total_points'] += pts
        return teams_dict

    reg_dict = build_dst_data(reg_ts, reg_sched, reg_pbp)
    post_dict = build_dst_data(post_ts, post_sched, post_pbp) if len(post_ts) > 0 else {}

    teams = []
    for team, td in reg_dict.items():
        td['weekly_stats'].sort(key=lambda x: x['week'])

        # Aggregate regular season stats
        ws = td['weekly_stats']
        td['aggregate_stats'] = {
            'total_sacks': sum(w['raw_stats']['def_sack'] for w in ws),
            'total_interceptions': sum(w['raw_stats']['def_int'] for w in ws),
            'total_fumble_recoveries': sum(w['raw_stats']['def_fumble_recovery'] for w in ws),
            'total_fumbles_forced': sum(w['raw_stats']['def_fumble_forced'] for w in ws),
            'total_st_fumble_recoveries': sum(w['raw_stats'].get('st_fumble_recovery', 0) for w in ws),
            'total_st_fumbles_forced': sum(w['raw_stats'].get('st_fumble_forced', 0) for w in ws),
            'total_kr_tds': sum(w['raw_stats'].get('kr_td', 0) for w in ws),
            'total_st_tds': sum(w['raw_stats'].get('st_td', 0) for w in ws),
            'total_tds': sum(w['raw_stats']['def_td'] for w in ws),
            'total_safeties': sum(w['raw_stats']['def_safety'] for w in ws),
            'total_blocked_kicks': sum(w['raw_stats']['def_blocked_kick'] for w in ws),
            'total_points_allowed': sum(w['raw_stats']['points_allowed'] for w in ws),
            'avg_points_allowed': round(sum(w['raw_stats']['points_allowed'] for w in ws) / len(ws), 1) if ws else 0
        }
        td['avg_points'] = round(td['total_points'] / td['games_played'], 2) if td['games_played'] > 0 else 0
        td['total_points'] = round(td['total_points'], 2)

        # Postseason
        if team in post_dict:
            ptd = post_dict[team]
            ptd['weekly_stats'].sort(key=lambda x: x['week'])
            for w in ptd['weekly_stats']:
                w['round'] = PLAYOFF_ROUND_NAMES.get(w['week'], f"Week {w['week']}")
            td['postseason'] = {
                'games_played': ptd['games_played'],
                'total_points': round(ptd['total_points'], 2),
                'avg_points_per_game': round(ptd['total_points'] / ptd['games_played'], 2),
                'weekly_stats': ptd['weekly_stats']
            }
        else:
            td['postseason'] = None

        teams.append(td)

    teams.sort(key=lambda x: x['total_points'], reverse=True)
    print(f"    {len(teams)} DSTs processed")

    return {
        'season': SEASON,
        'generated_at': datetime.now().isoformat(),
        'teams': teams
    }


def generate_defense_archive(weekly_stats, post_stats):
    """Generate defense_stats.json for 2025 archive (points allowed by defenses)."""
    print("\n  Generating defense stats archive...")
    defense_stats = {}

    def process_rows(rows, is_postseason=False):
        for row in rows.iter_rows(named=True):
            opponent = row.get('opponent_team')
            if not opponent:
                continue
            position = row.get('position', '')
            if position not in ROSTERABLE_POSITIONS or position in ('K', 'DEF'):
                continue
            player_team = row.get('team')
            week = row.get('week')

            if opponent not in defense_stats:
                defense_stats[opponent] = {
                    'team': opponent, 'games': 0,
                    'total_points_allowed': 0,
                    'qb_points_allowed': 0, 'rb_points_allowed': 0,
                    'wr_points_allowed': 0, 'te_points_allowed': 0,
                    'rushing_yards_allowed': 0, 'rushing_tds_allowed': 0,
                    'receiving_yards_allowed': 0, 'receiving_tds_allowed': 0,
                    'passing_tds_allowed': 0,
                    'weeks_played': set(),
                    'weekly_breakdown': {},
                    'weekly_player_scores': {},
                    'postseason': {
                        'games': 0, 'total_points_allowed': 0,
                        'qb_points_allowed': 0, 'rb_points_allowed': 0,
                        'wr_points_allowed': 0, 'te_points_allowed': 0,
                        'weeks_played': set(), 'weekly_breakdown': {},
                        'weekly_player_scores': {}
                    }
                }

            pts = calculate_fantasy_points(row)

            target = defense_stats[opponent]['postseason'] if is_postseason else defense_stats[opponent]

            if week:
                target['weeks_played'].add(week)
                if week not in target['weekly_breakdown']:
                    target['weekly_breakdown'][week] = {
                        'week': week, 'opponent': player_team or 'N/A',
                        'total_points': 0, 'qb_points': 0, 'rb_points': 0,
                        'wr_points': 0, 'te_points': 0,
                        'rushing_yards': 0, 'receiving_yards': 0,
                        'rushing_tds': 0, 'receiving_tds': 0, 'passing_tds': 0,
                        'raw_stats': {
                            'qb': {'passing_yards': 0, 'passing_tds': 0, 'interceptions': 0, 'rushing_yards': 0, 'rushing_tds': 0, 'fumbles_lost': 0},
                            'rb': {'rushing_yards': 0, 'rushing_tds': 0, 'receptions': 0, 'receiving_yards': 0, 'receiving_tds': 0, 'fumbles_lost': 0},
                            'wr': {'receptions': 0, 'receiving_yards': 0, 'receiving_tds': 0, 'rushing_yards': 0, 'rushing_tds': 0, 'fumbles_lost': 0},
                            'te': {'receptions': 0, 'receiving_yards': 0, 'receiving_tds': 0, 'fumbles_lost': 0}
                        }
                    }
                if is_postseason:
                    target['weekly_breakdown'][week]['round'] = PLAYOFF_ROUND_NAMES.get(week, f'Week {week}')
                if week not in target.get('weekly_player_scores', {}):
                    target['weekly_player_scores'][week] = {'QB': [], 'RB': [], 'WR': [], 'TE': []}
                if player_team and target['weekly_breakdown'][week]['opponent'] == 'N/A':
                    target['weekly_breakdown'][week]['opponent'] = player_team

            target['total_points_allowed'] += pts
            if position == 'QB':
                target['qb_points_allowed'] += pts
            elif position == 'RB':
                target['rb_points_allowed'] += pts
            elif position == 'WR':
                target['wr_points_allowed'] += pts
            elif position == 'TE':
                target['te_points_allowed'] += pts

            if week and position in ['QB', 'RB', 'WR', 'TE']:
                target['weekly_player_scores'][week][position].append(pts)

            if week and week in target['weekly_breakdown']:
                wb = target['weekly_breakdown'][week]
                wb['total_points'] += pts
                if position == 'QB':
                    wb['qb_points'] += pts
                    wb['passing_tds'] += (row.get('passing_tds', 0) or 0)
                elif position == 'RB':
                    wb['rb_points'] += pts
                elif position == 'WR':
                    wb['wr_points'] += pts
                elif position == 'TE':
                    wb['te_points'] += pts
                wb['rushing_yards'] += (row.get('rushing_yards', 0) or 0)
                wb['rushing_tds'] += (row.get('rushing_tds', 0) or 0)
                wb['receiving_yards'] += (row.get('receiving_yards', 0) or 0)
                wb['receiving_tds'] += (row.get('receiving_tds', 0) or 0)

                pos_key = position.lower()
                if pos_key in wb['raw_stats']:
                    raw = wb['raw_stats'][pos_key]
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

    process_rows(weekly_stats, is_postseason=False)
    if post_stats is not None and len(post_stats) > 0:
        process_rows(post_stats, is_postseason=True)

    def finalize_section(section):
        section['games'] = len(section['weeks_played'])
        del section['weeks_played']

        for wk, wb in section['weekly_breakdown'].items():
            scores = section['weekly_player_scores'].get(wk, {})
            for pos in ['QB', 'RB', 'WR', 'TE']:
                s = scores.get(pos, [])
                wb[f'{pos.lower()}_top1_points'] = max(s) if s else 0
        del section['weekly_player_scores']

        section['weekly_breakdown'] = sorted(section['weekly_breakdown'].values(), key=lambda x: x['week'])

        g = section['games']
        if g > 0:
            section['avg_points_per_game'] = section['total_points_allowed'] / g
            section['qb_ppg'] = section['qb_points_allowed'] / g
            section['rb_ppg'] = section['rb_points_allowed'] / g
            section['wr_ppg'] = section['wr_points_allowed'] / g
            section['te_ppg'] = section['te_points_allowed'] / g
        else:
            for k in ['avg_points_per_game', 'qb_ppg', 'rb_ppg', 'wr_ppg', 'te_ppg']:
                section[k] = 0

    defenses_list = []
    for team, stats in defense_stats.items():
        finalize_section(stats)

        # Top 1 PPG for regular season
        if stats['games'] > 0:
            top1 = {'QB': 0, 'RB': 0, 'WR': 0, 'TE': 0}
            for wb in stats['weekly_breakdown']:
                for pos in ['QB', 'RB', 'WR', 'TE']:
                    top1[pos] += wb.get(f'{pos.lower()}_top1_points', 0)
            for pos in ['QB', 'RB', 'WR', 'TE']:
                stats[f'{pos.lower()}1_ppg'] = top1[pos] / stats['games']
        else:
            for pos in ['QB', 'RB', 'WR', 'TE']:
                stats[f'{pos.lower()}1_ppg'] = 0

        # Postseason
        ps = stats['postseason']
        finalize_section(ps)
        if ps['games'] == 0:
            stats['postseason'] = None
        else:
            # Remove fields not needed in postseason sub-object
            for k in ['qb_points_allowed', 'rb_points_allowed', 'wr_points_allowed', 'te_points_allowed']:
                ps.pop(k, None)

        defenses_list.append(stats)

    print(f"    {len(defenses_list)} defenses processed")

    return {
        'season': str(SEASON),
        'generated_at': datetime.now().isoformat(),
        'defenses': defenses_list
    }


def main():
    os.makedirs(ARCHIVE_DIR, exist_ok=True)

    print("=" * 70)
    print(f"GENERATING 2025 ARCHIVE DATA")
    print("=" * 70)

    # Load shared data
    print("\nLoading NFL data for 2025...")
    season = [SEASON]

    all_weekly = nfl.load_player_stats(season, summary_level='week')
    weekly_stats = all_weekly.filter(all_weekly['season_type'] == 'REG')
    print(f"  Regular season: {len(weekly_stats)} records")

    post_stats = all_weekly.filter(all_weekly['season_type'] == 'POST')
    print(f"  Postseason: {len(post_stats)} records (weeks {sorted(post_stats['week'].unique().to_list())})")

    # Schedule
    schedule_lookup = {}
    try:
        schedules = nfl.load_schedules(season)
        for row in schedules.iter_rows(named=True):
            wk = row.get('week')
            home = row.get('home_team')
            away = row.get('away_team')
            if wk and home and away:
                schedule_lookup[(home, wk)] = away
                schedule_lookup[(away, wk)] = home
    except Exception as e:
        print(f"  Schedule: {e}")

    # Snap counts
    snap_lookup = {}
    try:
        snaps = nfl.load_snap_counts(season)
        for row in snaps.iter_rows(named=True):
            p, t, w = row.get('player'), row.get('team'), row.get('week')
            if p and t and w:
                snap_lookup[(p, t, w)] = row.get('offense_pct', 0)
    except Exception as e:
        print(f"  Snap counts: {e}")

    # Ages
    player_ages = {}
    try:
        roster_polars = nfl.load_rosters(season)
        for row in roster_polars.iter_rows(named=True):
            pid = row.get('gsis_id')
            bd = row.get('birth_date')
            if pid and bd:
                try:
                    bds = str(bd).split(' ')[0]
                    bdate = datetime.strptime(bds, '%Y-%m-%d')
                    today = datetime.today()
                    player_ages[pid] = today.year - bdate.year - ((today.month, today.day) < (bdate.month, bdate.day))
                except (ValueError, TypeError):
                    pass
    except Exception as e:
        print(f"  Ages: {e}")

    # Ownership
    ownership = load_ownership_2025()

    # Defense map (for opp_avg_allowed in player stats)
    defense_map = {}

    # ---- Generate defense stats first (needed for opp_avg_allowed) ----
    defense_data = generate_defense_archive(weekly_stats, post_stats)
    save_json(defense_data, f"{ARCHIVE_DIR}/defense_stats.json")

    # Build defense_map from generated data
    for d in defense_data['defenses']:
        defense_map[d['team']] = {
            'QB': d.get('qb1_ppg', d.get('qb_ppg', 0)),
            'RB': d.get('rb1_ppg', d.get('rb_ppg', 0)),
            'WR': d.get('wr1_ppg', d.get('wr_ppg', 0)),
            'TE': d.get('te1_ppg', d.get('te_ppg', 0)),
        }

    # ---- Player stats ----
    player_data = generate_player_archive(
        weekly_stats, post_stats, schedule_lookup,
        snap_lookup, player_ages, ownership, defense_map
    )
    save_json(player_data, f"{ARCHIVE_DIR}/player_stats.json")

    # ---- Kicker stats ----
    team_stats_pd = nfl.load_team_stats([SEASON]).to_pandas()
    rosters_pd = nfl.load_rosters([SEASON]).to_pandas()
    post_team_stats = team_stats_pd[team_stats_pd['season_type'] == 'POST'].copy()
    kicker_data = generate_kicker_archive(team_stats_pd, rosters_pd, post_team_stats)
    save_json(kicker_data, f"{ARCHIVE_DIR}/kicker_stats.json")

    # ---- DST stats ----
    dst_data = generate_dst_archive()
    save_json(dst_data, f"{ARCHIVE_DIR}/dst_stats.json")

    print("\n" + "=" * 70)
    print("ARCHIVE GENERATION COMPLETE")
    print(f"  Players: {len(player_data['players'])}")
    print(f"  Kickers: {len(kicker_data['players'])}")
    print(f"  DSTs: {len(dst_data['teams'])}")
    print(f"  Defenses: {len(defense_data['defenses'])}")
    ps_players = sum(1 for p in player_data['players'] if p.get('postseason'))
    ps_kickers = sum(1 for p in kicker_data['players'] if p.get('postseason'))
    ps_dsts = sum(1 for t in dst_data['teams'] if t.get('postseason'))
    ps_defs = sum(1 for d in defense_data['defenses'] if d.get('postseason'))
    print(f"  With postseason: {ps_players} players, {ps_kickers} kickers, {ps_dsts} DSTs, {ps_defs} defenses")
    print(f"  Output: {ARCHIVE_DIR}/")
    print("=" * 70)


if __name__ == '__main__':
    main()
