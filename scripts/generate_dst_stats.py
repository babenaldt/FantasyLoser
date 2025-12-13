#!/usr/bin/env python3
"""
Generate DST (Defense/Special Teams) fantasy statistics from nflverse team stats and schedules.
This generates fantasy points FOR defenses (sacks, INTs, TDs, etc), not points allowed.
"""

import json
import os
from datetime import datetime
import pandas as pd
import nflreadpy as nfl
from core_data import calculate_fantasy_points, SCORING_PRESETS
# from player_detail_generator import generate_player_detail_page


ST_PLAY_TYPES = {
    'kickoff',
    'punt',
    'field_goal',
    'extra_point',
}


def _is_success(value: str | None) -> bool:
    if not value:
        return False
    return str(value).strip().lower() in {'success', 'good'}


def _calc_defensive_points_against(pbp_game: pd.DataFrame) -> dict[str, int]:
    """Return mapping: team -> points scored BY OPPONENT DEFENSE against that team's offense.

    This is used to convert scoreboard opponent points into Sleeper DST `PT ALLOW` by subtracting
    opponent defensive scores (pick-6/fumble return TD + PAT/2pt + safeties).
    """

    points_against: dict[str, int] = {}

    if pbp_game.empty:
        return points_against

    g = pbp_game.sort_values('play_id', kind='mergesort')

    # Defensive TDs: scoring team == defteam and offense team == posteam, and not a special teams play.
    td_mask = (
        (g.get('touchdown') == 1)
        & (g.get('td_team').notna())
        & (g.get('defteam').notna())
        & (g.get('posteam').notna())
        & (g['td_team'] == g['defteam'])
        & (g['posteam'] != g['defteam'])
        & (~g.get('play_type').isin(ST_PLAY_TYPES))
    )

    td_rows = g[td_mask][['play_id', 'td_team', 'posteam']].copy()

    # Sleeper-style PT ALLOW adjustment: subtract 6 points for each opponent defensive TD
    # (PAT/2pt conversions appear to still count toward PT ALLOW).
    for _, r in td_rows.iterrows():
        scored_on = str(r['posteam'])
        points_against[scored_on] = points_against.get(scored_on, 0) + 6

    # Safeties: 2 points scored by defense against offense (exclude special teams plays)
    if 'safety' in g.columns:
        safety_mask = (
            (g['safety'] == 1)
            & (g.get('defteam').notna())
            & (g.get('posteam').notna())
            & (~g.get('play_type').isin(ST_PLAY_TYPES))
        )
        for _, r in g[safety_mask][['defteam', 'posteam']].iterrows():
            scored_on = str(r['posteam'])
            points_against[scored_on] = points_against.get(scored_on, 0) + 2

    return points_against


def _calc_fumbles_by_team_week(pbp: pd.DataFrame) -> pd.DataFrame:
    """Return DataFrame with per-team-week fumble forced/recovery split into DEF vs ST."""

    if pbp.empty:
        return pd.DataFrame(columns=['week', 'team', 'def_ff', 'def_fr', 'st_ff', 'st_fr'])

    g = pbp.copy()
    g = g[g.get('fumble') == 1]
    if g.empty:
        return pd.DataFrame(columns=['week', 'team', 'def_ff', 'def_fr', 'st_ff', 'st_fr'])

    # Identify forced fumble team (can have up to 2)
    forced_cols = [c for c in ['forced_fumble_player_1_team', 'forced_fumble_player_2_team'] if c in g.columns]
    rec_cols = [c for c in ['fumble_recovery_1_team', 'fumble_recovery_2_team'] if c in g.columns]

    # Special teams classification based on play_type
    g['is_st'] = g.get('play_type').isin(ST_PLAY_TYPES)

    rows = []

    # Forced fumbles (dedupe per play+team to avoid double-counting when multiple forced fumble players exist)
    if forced_cols:
        forced_melt = g[['game_id', 'play_id', 'week', 'is_st', *forced_cols]].melt(
            id_vars=['game_id', 'play_id', 'week', 'is_st'],
            value_vars=forced_cols,
            value_name='team',
        )
        forced_melt = forced_melt.dropna(subset=['team']).drop_duplicates(subset=['game_id', 'play_id', 'team'])
        forced_melt['def_ff'] = (~forced_melt['is_st']).astype(int)
        forced_melt['st_ff'] = (forced_melt['is_st']).astype(int)
        forced_melt['def_fr'] = 0
        forced_melt['st_fr'] = 0
        rows.append(forced_melt[['week', 'team', 'def_ff', 'def_fr', 'st_ff', 'st_fr']])

    # Fumble recoveries (only count when offense lost it; dedupe per play+team)
    if 'fumble_lost' in g.columns and rec_cols:
        lost = g[(g['fumble_lost'] == 1)].copy()
        rec_melt = lost[['game_id', 'play_id', 'week', 'is_st', *rec_cols]].melt(
            id_vars=['game_id', 'play_id', 'week', 'is_st'],
            value_vars=rec_cols,
            value_name='team',
        )
        rec_melt = rec_melt.dropna(subset=['team']).drop_duplicates(subset=['game_id', 'play_id', 'team'])
        rec_melt['def_fr'] = (~rec_melt['is_st']).astype(int)
        rec_melt['st_fr'] = (rec_melt['is_st']).astype(int)
        rec_melt['def_ff'] = 0
        rec_melt['st_ff'] = 0
        rows.append(rec_melt[['week', 'team', 'def_ff', 'def_fr', 'st_ff', 'st_fr']])

    if not rows:
        return pd.DataFrame(columns=['week', 'team', 'def_ff', 'def_fr', 'st_ff', 'st_fr'])

    out = pd.concat(rows, ignore_index=True)
    out = out.groupby(['week', 'team'], as_index=False)[['def_ff', 'def_fr', 'st_ff', 'st_fr']].sum()
    return out


def _calc_return_tds_by_team_week(pbp: pd.DataFrame) -> pd.DataFrame:
    """Return DataFrame with per-team-week kickoff return TDs (kr_td) and other ST return TDs (st_td)."""

    if pbp.empty:
        return pd.DataFrame(columns=['week', 'team', 'kr_td', 'st_td'])

    # Note: `return_touchdown=1` includes defensive returns (pick-6 / fumble return).
    # For Sleeper-style ST TD columns, only count special teams play types.
    # Also include plays where the defensive team (receiving team) scores a TD on a ST play (e.g. muffed punt recovery, onside kick recovery)
    g = pbp[
        (pbp.get('touchdown') == 1)
        & (pbp.get('td_team').notna())
        & (pbp.get('play_type').isin({'kickoff', 'punt', 'field_goal'}))
        & (
            (pbp.get('return_touchdown') == 1)
            | (pbp.get('play_type').isin({'field_goal', 'punt', 'kickoff'}) & (pbp.get('td_team') == pbp.get('defteam')))
        )
    ].copy()
    if g.empty:
        return pd.DataFrame(columns=['week', 'team', 'kr_td', 'st_td'])

    g['team'] = g['td_team'].astype(str)
    g['kr_td'] = (g.get('play_type') == 'kickoff').astype(int)
    # Punt return TDs and blocked-FG return TDs
    g['st_td'] = (g.get('play_type').isin({'punt', 'field_goal'})).astype(int)

    out = g.groupby(['week', 'team'], as_index=False)[['kr_td', 'st_td']].sum()
    return out


def _calc_blocked_kicks_by_team_week(pbp: pd.DataFrame) -> pd.DataFrame:
    """Return DataFrame with per-team-week blocked kicks (def_blocked_kick)."""
    
    if pbp.empty:
        return pd.DataFrame(columns=['week', 'team', 'def_blocked_kick'])
        
    # Blocked kicks: field_goal_result='blocked', punt_blocked=1, extra_point_result='blocked'
    # The team credited with the block is usually 'defteam'.
    
    mask = (
        (pbp.get('field_goal_result') == 'blocked')
        | (pbp.get('punt_blocked') == 1)
        | (pbp.get('extra_point_result') == 'blocked')
    ) & (pbp.get('defteam').notna())
    
    g = pbp[mask].copy()
    
    if g.empty:
        return pd.DataFrame(columns=['week', 'team', 'def_blocked_kick'])
        
    g['team'] = g['defteam']
    g['def_blocked_kick'] = 1
    
    out = g.groupby(['week', 'team'], as_index=False)['def_blocked_kick'].sum()
    return out

def generate_dst_stats():
    """Generate comprehensive DST fantasy statistics."""
    print("Loading data from nflverse...")
    
    # Get current season
    current_season = nfl.get_current_season()
    print(f"Using season: {current_season}")
    
    # Load team stats, schedules, and play-by-play
    team_stats = nfl.load_team_stats([current_season]).to_pandas()
    schedules = nfl.load_schedules([current_season]).to_pandas()
    pbp = nfl.load_pbp([current_season]).to_pandas()
    
    # Filter to regular season only
    team_stats = team_stats[team_stats['season_type'] == 'REG'].copy()
    pbp = pbp[pbp['season_type'] == 'REG'].copy()
    schedules = schedules[schedules['game_type'] == 'REG'].copy()
    
    # Expand schedules to team-week rows.
    # Note: DST `points_allowed` in Sleeper is not always the final opponent score.
    # We will adjust it by subtracting opponent defensive points scored against this team's offense.
    schedules_expanded = []
    for _, game in schedules.iterrows():
        if pd.notna(game['home_score']) and pd.notna(game['away_score']):
            # Home team perspective
            schedules_expanded.append({
                'week': game['week'],
                'game_id': game['game_id'],
                'team': game['home_team'],
                'opponent': game['away_team'],
                'points_allowed': game['away_score']
            })
            # Away team perspective
            schedules_expanded.append({
                'week': game['week'],
                'game_id': game['game_id'],
                'team': game['away_team'],
                'opponent': game['home_team'],
                'points_allowed': game['home_score']
            })
    
    schedules_df = pd.DataFrame(schedules_expanded)
    
    # Pre-compute per-game defensive points scored against each team (to adjust points allowed)
    print("Computing defense-only points allowed (Sleeper PT ALLOW)...")
    def_points_against_by_game_team: dict[tuple[str, str], int] = {}
    for game_id, g in pbp.groupby('game_id', sort=False):
        pts_against = _calc_defensive_points_against(g)
        for team, pts in pts_against.items():
            def_points_against_by_game_team[(str(game_id), team)] = pts

    # Compute DEF vs ST fumbles forced/recovered from pbp
    print("Computing DEF vs ST fumbles (Sleeper stat definitions)...")
    fumbles_week = _calc_fumbles_by_team_week(pbp)

    # Compute return TDs from pbp (kickoff vs other)
    return_tds_week = _calc_return_tds_by_team_week(pbp)

    # Compute blocked kicks from pbp
    blocked_kicks_week = _calc_blocked_kicks_by_team_week(pbp)

    # Merge team stats with schedule data
    defense_stats = team_stats.merge(schedules_df, on=['week', 'team'], how='left')
    defense_stats = defense_stats.merge(fumbles_week, on=['week', 'team'], how='left')
    defense_stats = defense_stats.merge(return_tds_week, on=['week', 'team'], how='left')
    defense_stats = defense_stats.merge(blocked_kicks_week, on=['week', 'team'], how='left')

    # Fill pbp-derived stats
    for col in ['def_ff', 'def_fr', 'st_ff', 'st_fr', 'kr_td', 'st_td', 'def_blocked_kick']:
        if col in defense_stats.columns:
            defense_stats[col] = defense_stats[col].fillna(0)
    
    print(f"Processing {len(defense_stats)} team-week records")
    
    # Build team data structure
    teams_dict = {}
    
    for _, row in defense_stats.iterrows():
        team = row['team']
        
        if team not in teams_dict:
            teams_dict[team] = {
                'team': team,
                'position': 'DEF',
                'games_played': 0,
                'total_points': 0,
                'weekly_stats': []
            }
        
        team_data = teams_dict[team]
        
        # Sleeper "PT ALLOW" excludes opponent defensive scores against this team's offense.
        game_id = str(row['game_id']) if pd.notna(row.get('game_id')) else None
        points_allowed_total = int(row['points_allowed']) if pd.notna(row.get('points_allowed')) else 0
        defensive_points_scored_on_offense = 0
        if game_id:
            defensive_points_scored_on_offense = def_points_against_by_game_team.get((game_id, team), 0)
        points_allowed_adjusted = max(points_allowed_total - defensive_points_scored_on_offense, 0)

        # Defensive TDs from team_stats (def_tds + fumble_recovery_tds) match Sleeper DEF TD column.
        total_def_tds = int(row['def_tds']) + int(row['fumble_recovery_tds'])
        
        raw_stats = {
            'def_td': total_def_tds,
            'kr_td': int(row.get('kr_td', 0) or 0),
            'st_td': int(row.get('st_td', 0) or 0),
            'def_int': int(row['def_interceptions']),
            # Sleeper shows DEF-only FF/FR in the main defense columns, but scores ST FF/FR separately.
            'def_fumble_recovery': int(row.get('def_fr', 0) or 0),
            'def_fumble_forced': int(row.get('def_ff', 0) or 0),
            'st_fumble_recovery': int(row.get('st_fr', 0) or 0),
            'st_fumble_forced': int(row.get('st_ff', 0) or 0),
            'def_sack': float(row['def_sacks']),
            'def_safety': int(row['def_safeties']),
            'def_blocked_kick': int(row.get('def_blocked_kick', 0) or 0),
            'points_allowed': points_allowed_adjusted,
            '_points_allowed_total': points_allowed_total,
            '_points_allowed_def_scored': defensive_points_scored_on_offense,
        }
        
        weekly_points = calculate_fantasy_points(raw_stats, SCORING_PRESETS['ppr'])
        
        team_data['weekly_stats'].append({
            'week': int(row['week']),
            'opponent': row['opponent'] if pd.notna(row['opponent']) else row['opponent_team'],
            'points': round(weekly_points, 2),
            'raw_stats': raw_stats
        })
        
        team_data['games_played'] += 1
        team_data['total_points'] += weekly_points
    
    # Convert to list and calculate aggregate stats
    teams = []
    for team, team_data in teams_dict.items():
        # Sort weekly stats by week
        team_data['weekly_stats'].sort(key=lambda x: x['week'])
        
        # Calculate aggregate stats
        team_data['aggregate_stats'] = {
            'total_sacks': sum(w['raw_stats']['def_sack'] for w in team_data['weekly_stats']),
            'total_interceptions': sum(w['raw_stats']['def_int'] for w in team_data['weekly_stats']),
            'total_fumble_recoveries': sum(w['raw_stats']['def_fumble_recovery'] for w in team_data['weekly_stats']),
            'total_fumbles_forced': sum(w['raw_stats']['def_fumble_forced'] for w in team_data['weekly_stats']),
            'total_st_fumble_recoveries': sum(w['raw_stats'].get('st_fumble_recovery', 0) for w in team_data['weekly_stats']),
            'total_st_fumbles_forced': sum(w['raw_stats'].get('st_fumble_forced', 0) for w in team_data['weekly_stats']),
            'total_kr_tds': sum(w['raw_stats'].get('kr_td', 0) for w in team_data['weekly_stats']),
            'total_st_tds': sum(w['raw_stats'].get('st_td', 0) for w in team_data['weekly_stats']),
            'total_tds': sum(w['raw_stats']['def_td'] for w in team_data['weekly_stats']),
            'total_safeties': sum(w['raw_stats']['def_safety'] for w in team_data['weekly_stats']),
            'total_blocked_kicks': sum(w['raw_stats']['def_blocked_kick'] for w in team_data['weekly_stats']),
            'total_points_allowed': sum(w['raw_stats']['points_allowed'] for w in team_data['weekly_stats']),
            'total_points_allowed_total': sum(w['raw_stats'].get('_points_allowed_total', 0) for w in team_data['weekly_stats']),
            'total_points_allowed_def_scored': sum(w['raw_stats'].get('_points_allowed_def_scored', 0) for w in team_data['weekly_stats']),
            'avg_points_allowed': round(
                sum(w['raw_stats']['points_allowed'] for w in team_data['weekly_stats']) / len(team_data['weekly_stats']),
                1
            ) if team_data['weekly_stats'] else 0
        }
        
        team_data['avg_points'] = round(team_data['total_points'] / team_data['games_played'], 2) if team_data['games_played'] > 0 else 0
        team_data['total_points'] = round(team_data['total_points'], 2)
        
        teams.append(team_data)
    
    # Sort by total points
    teams.sort(key=lambda x: x['total_points'], reverse=True)
    
    print(f"Calculated stats for {len(teams)} defenses")
    
    # Create output structure
    output = {
        'season': current_season,
        'generated_at': datetime.now().isoformat(),
        'teams': teams
    }
    
    # Write to JSON file
    output_path = 'website/public/data/dst_stats.json'
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"DST stats written to {output_path}")
    
    # Generate individual team pages (DEPRECATED - Now handled by Astro)
    # print("Generating individual DST pages...")
    # website_public_dir = "website/public"
    # if not os.path.exists(website_public_dir):
    #     os.makedirs(website_public_dir)

    # for team in teams:
    #     # Prepare data for detail page
    #     player_data = {
    #         'position': 'DEF',
    #         'team': team['team'],
    #         'total_points': team['total_points'],
    #         'avg_ppg': team['avg_points'],
    #         'games': team['games_played'],
    #         'consistency': 0,
    #         'nfl_stats': {}
    #     }
    #     weekly_performances = {wp['week']: wp['points'] for wp in team['weekly_stats']}
    #     
    #     generate_player_detail_page(
    #         team['team'], # Use team name as player name
    #         player_data, 
    #         weekly_performances, 
    #         output_dir=website_public_dir
    #     )
    
    # Print top 10 defenses
    print("\nTop 10 Defenses:")
    for i, team in enumerate(teams[:10], 1):
        stats = team['aggregate_stats']
        print(f"{i}. {team['team']} - {team['total_points']} pts, {team['avg_points']} PPG "
              f"({stats['total_sacks']:.1f} sacks, {stats['total_interceptions']} INT, "
              f"{stats['total_fumble_recoveries']} FR, {stats['total_fumbles_forced']} FF, "
              f"{stats['total_tds']} TD, {stats['total_blocked_kicks']} BLK)")

if __name__ == '__main__':
    generate_dst_stats()
