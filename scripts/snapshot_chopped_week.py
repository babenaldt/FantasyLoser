#!/usr/bin/env python3
"""Weekly Chopped matchup snapshot (sanity-gated, keep-first-wins).

Captures per-team scores for the just-completed Chopped week into
scripts/verified_week<N>_chopped.json BEFORE the commissioner flips roster
positions for the new week.

Why this exists: Sleeper's matchup API cannot handle mid-season roster
position changes. Once the commissioner changes positions for the new week,
historical weeks' `starters` arrays come back truncated (TE/WRT slots read
as '0'), so that week's matchup `points` are permanently undercounted in
every later fetch. Seen 2026-10-07 for week 4 (ItalianLasagna 35.42 instead
of the verified 50.92; the flip for week 5 was in place before ~3:17am ET).

Safety properties:
  * Sanity gate: refuses to save when the fetched data shows the truncation
    signature (active teams fielding fewer real starters than the
    commissioner's chart mandates for that week — e.g. 3 instead of 5 for
    week 4), so a late run can never bless corrupted data as ground truth.
  * Keep-first-wins: never overwrites an existing snapshot file.

Run weekly Tuesday ~01:00 ET (after MNF wraps, before the positions flip).
Usage: python3 scripts/snapshot_chopped_week.py [--week N]
Exit codes: 0 = snapshot saved or already exists; 2 = data failed sanity
check (REFUSED); 1 = fetch/build error.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core_data import SleeperAPI, make_request
from nfl_week_helper import get_last_completed_nfl_week
from generate_weekly_reviews import (
    LEAGUES,
    load_player_data,
    build_week_data,
)
from chopped_week import proj_points, CHART_SLOTS

CHOPPED_LEAGUE_ID = LEAGUES['chopped']['id']


def looks_corrupted(matchups, week):
    """Return (corrupted: bool, detail: str).

    Healthy week-N data has every active team fielding exactly the number of
    real starters the commissioner's chart mandates for week N. After a
    roster-position flip, Sleeper re-maps the old lineup against the NEW
    slots and blanks everything from the first mismatch — e.g. week 4 rows
    (5 chart starters) come back with only 3 real starters and deflated
    points (ItalianLasagna 35.42 vs the verified 50.92).

    Rows with zero real starters are ghost teams (already chopped); they are
    excluded by build_week_data and skipped here.
    """
    expected = len(CHART_SLOTS[week])
    bad = []
    checked = 0
    for m in matchups:
        starters = m.get('starters') or []
        real = [s for s in starters if s and str(s) != '0']
        if not real:
            continue
        checked += 1
        if len(real) != expected:
            bad.append((m.get('roster_id'), len(real)))
    if checked == 0:
        return True, "no active teams found in matchup data"
    if bad:
        return True, (f"{len(bad)}/{checked} active teams field "
                      f"!= {expected} real starters (truncation signature): "
                      f"{bad[:5]}")
    return False, f"{checked} active teams x {expected} real starters OK"


def build_snapshot(week):
    """Fetch week data and return the snapshot dict in verified_week<N> shape."""
    api = SleeperAPI(CHOPPED_LEAGUE_ID)
    player_data = load_player_data()

    league = api.get_league()
    rosters = api.get_rosters()
    users = api.get_users()
    if not league or not rosters or not users:
        raise RuntimeError("could not fetch league/rosters/users from Sleeper")

    roster_map = {r['roster_id']: r for r in rosters}
    user_map = {u['user_id']: u for u in users}
    roster_positions = league.get('roster_positions', [])

    matchups = api.get_matchups(week) or []
    transactions = api.get_transactions(week) or []

    corrupted, detail = looks_corrupted(matchups, week)
    if corrupted:
        raise ValueError(f"sanity check failed: {detail}")

    # Frozen pre-game projections (same source the weekly reviews use).
    proj_rows = make_request(
        "https://api.sleeper.com/projections/nfl/2026/"
        f"{week}?season_type=regular&position[]=QB&position[]=RB"
        "&position[]=WR&position[]=TE"
    ) or []
    proj_by_id = {str(r.get("player_id")): (r.get("stats") or {})
                  for r in proj_rows}
    rec_points = (league.get("scoring_settings") or {}).get("rec", 0) or 0

    week_data = build_week_data(
        week, matchups, transactions,
        roster_map, user_map, player_data, roster_positions,
        'chopped', None,
        proj_by_id=proj_by_id, rec_points=rec_points,
    )

    teams = {}
    for t in week_data['team_scores']:
        teams[str(t['roster_id'])] = {
            'owner_name': t['owner_name'],
            'points': t['points'],
            'optimal': t['optimal'],
            'efficiency': t['efficiency'],
            'bench_points': t['bench_points'],
            'projected': t['projected'],
        }
    return {
        'note': (
            f"VERIFIED ground truth for 2026 chopped week {week} "
            f"(snapshot_chopped_week.py, sanity-gated). Sleeper's matchup API "
            f"truncates historical starters arrays once roster positions "
            f"change for a new week; this snapshot takes precedence."
        ),
        'week': week,
        'teams': teams,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--week', type=int, default=None,
                        help='NFL week to snapshot (default: week whose MNF '
                             'just ended, i.e. last completed + 1 — correct '
                             'when run Tuesday ~01:00 ET)')
    args = parser.parse_args()

    week = args.week
    if week is None:
        week = get_last_completed_nfl_week() + 1

    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    snap_path = os.path.join(scripts_dir, f'verified_week{week}_chopped.json')

    if os.path.exists(snap_path):
        print(f"Snapshot for week {week} already exists — keeping it "
              f"(keep-first-wins).")
        return 0

    try:
        snap = build_snapshot(week)
    except ValueError as e:
        # Sanity gate tripped: corrupted data. REFUSE — never bless it.
        print(f"REFUSED to snapshot week {week}: {e}")
        return 2
    except Exception as e:
        print(f"ERROR snapshotting week {week}: {e}")
        return 1

    with open(snap_path, 'w', encoding='utf-8') as f:
        json.dump(snap, f, indent=1)
    print(f"Saved verified snapshot for chopped week {week}: "
          f"{len(snap['teams'])} teams -> {snap_path}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
