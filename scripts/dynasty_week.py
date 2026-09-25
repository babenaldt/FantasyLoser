"""Weekly Dynasty roster and FAAB brief for SeanRabenaldt.

Reads the live Sleeper league plus the saved 2025 bid archive (winning and
losing bids). Does not write temp scripts.

    python scripts/dynasty_week.py
    python scripts/dynasty_week.py --refresh-history

The text report is the thing to use for weekly advice. A JSON copy is written
to output/dynasty_week_brief.json.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core_data import OUTPUT_DIR, SleeperAPI, make_request
from nfl_week_helper import get_current_nfl_week, get_last_completed_nfl_week
import xcheck

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

LEAGUE_ID = "1312064104759844864"
LEAGUE_2025_ID = "1264304480178950144"
OWNER = "SeanRabenaldt"
HISTORY_PATH = os.path.join(
    "website", "public", "data", "archive", "2025", "dynasty_faab_all_bids_2025.json"
)
BRIEF_PATH = os.path.join(OUTPUT_DIR, "dynasty_week_brief.json")

TEAM_ALIASES = {"LAR": "LA", "WSH": "WAS", "JAC": "JAX"}

SLOT_ELIGIBILITY = {
    "QB": {"QB"},
    "RB": {"RB"},
    "WR": {"WR"},
    "TE": {"TE"},
    "FLEX": {"RB", "WR", "TE"},
    "SUPER_FLEX": {"QB", "RB", "WR", "TE"},
    "WRRB_FLEX": {"RB", "WR"},
    "REC_FLEX": {"RB", "WR", "TE"},
}


def nfl_abbr(team: str | None) -> str | None:
    if not team:
        return None
    return TEAM_ALIASES.get(team, team)


def player_name(players: dict, pid: str) -> str:
    p = players.get(str(pid), {})
    name = p.get("full_name")
    if name:
        return name
    first = p.get("first_name") or ""
    last = p.get("last_name") or ""
    return f"{first} {last}".strip() or str(pid)


def load_schedule(week: int) -> dict:
    """Map sleeper team abbr -> opponent abbr for one week."""
    try:
        import nflreadpy as nfl
    except ImportError:
        print("Schedule unavailable: nflreadpy is not installed")
        return {}
    opponents = {}
    schedules = nfl.load_schedules([2026])
    for game in schedules.iter_rows(named=True):
        if game.get("week") != week or game.get("game_type") not in ("REG", "", None):
            continue
        home = game.get("home_team")
        away = game.get("away_team")
        if not home or not away:
            continue
        opponents[home] = away
        opponents[away] = home
        opponents[TEAM_ALIASES.get(home, home)] = away
        opponents[TEAM_ALIASES.get(away, away)] = home
        if home == "LA":
            opponents["LAR"] = away
        if away == "LA":
            opponents["LAR"] = home
    return opponents


def load_defense_ranks() -> dict:
    """Rank 1 = most fantasy points allowed at that position (softest)."""
    path = os.path.join(OUTPUT_DIR, "defense_stats.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as handle:
        defenses = json.load(handle).get("defenses") or []
    ranks = {}
    for key, label in (
        ("qb_points_allowed", "QB"),
        ("rb_points_allowed", "RB"),
        ("wr_points_allowed", "WR"),
        ("te_points_allowed", "TE"),
    ):
        ordered = sorted(defenses, key=lambda row: row.get(key) or 0, reverse=True)
        for index, row in enumerate(ordered, start=1):
            games = row.get("games") or 1
            ranks.setdefault(row["team"], {})[label] = {
                "rank": index,
                "of": len(ordered),
                "ppg": round((row.get(key) or 0) / games, 1),
            }
            alias = next((src for src, dst in TEAM_ALIASES.items() if dst == row["team"]), None)
            if alias:
                ranks[alias] = ranks[row["team"]]
    return ranks


def fetch_bids(league_id: str, players: dict, through_week: int = 18) -> list[dict]:
    api = SleeperAPI(league_id)
    users = {u["user_id"]: u.get("display_name") or u.get("username") for u in (api.get_users() or [])}
    bids = []
    for week in range(1, through_week + 1):
        for txn in api.get_transactions(week) or []:
            if txn.get("type") != "waiver":
                continue
            if txn.get("status") not in ("complete", "failed", "pending"):
                continue
            settings = txn.get("settings") or {}
            bid = settings.get("waiver_bid") or 0
            owner = users.get(txn.get("creator"), "Unknown")
            adds = txn.get("adds") or {}
            drops = txn.get("drops") or {}
            drop_names = [player_name(players, pid) for pid in drops]
            for pid in adds:
                bids.append({
                    "week": week,
                    "status": txn.get("status"),
                    "bid": bid,
                    "owner": owner,
                    "player_id": str(pid),
                    "player_name": player_name(players, pid),
                    "position": (players.get(str(pid)) or {}).get("position") or "",
                    "dropped": drop_names,
                })
    return bids


def save_history(players: dict) -> dict:
    print("Refreshing 2025 Dynasty waiver bids (wins and losses)...")
    api = SleeperAPI(LEAGUE_2025_ID)
    league = api.get_league() or {}
    budget = (league.get("settings") or {}).get("waiver_budget")
    bids = fetch_bids(LEAGUE_2025_ID, players, through_week=18)
    payload = {
        "league_id": LEAGUE_2025_ID,
        "season": 2025,
        "waiver_budget": budget,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "bids": bids,
    }
    os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
    with open(HISTORY_PATH, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    print(f"Saved {len(bids)} bids to {HISTORY_PATH}")
    return payload


def load_history(players: dict, refresh: bool) -> dict:
    if refresh or not os.path.exists(HISTORY_PATH):
        return save_history(players)
    with open(HISTORY_PATH, encoding="utf-8") as handle:
        return json.load(handle)


def auctions_from(bids: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for bid in bids:
        grouped[(bid["week"], bid["player_id"])].append(bid)
    auctions = []
    for (week, pid), rows in grouped.items():
        rows = sorted(rows, key=lambda row: (-row["bid"], row["status"] != "complete"))
        winner = next((row for row in rows if row["status"] == "complete"), None)
        ordered = sorted(rows, key=lambda row: -row["bid"])
        second = ordered[1]["bid"] if len(ordered) > 1 else None
        winning_bid = winner["bid"] if winner else None
        clearing = (second + 1) if second is not None else 0
        auctions.append({
            "week": week,
            "player_id": pid,
            "player_name": rows[0]["player_name"],
            "position": rows[0]["position"],
            "winner": winner["owner"] if winner else None,
            "winning_bid": winning_bid,
            "second_bid": second,
            "clearing_price": clearing if winner else None,
            "overpay": (winning_bid - clearing) if winner and winning_bid is not None else None,
            "bids": [
                {"owner": row["owner"], "bid": row["bid"], "status": row["status"]}
                for row in ordered
            ],
        })
    auctions.sort(key=lambda row: (row["week"], -(row["winning_bid"] or row["bids"][0]["bid"])))
    return auctions


def market_summary(auctions: list[dict], owner: str) -> dict:
    weeks = {}
    for auction in auctions:
        if auction["winner"] is None:
            continue
        bucket = weeks.setdefault(auction["week"], {
            "wins": 0,
            "spent": 0,
            "winning_bids": [],
            "clearing_prices": [],
            "overpays": [],
            "owner_spent": 0,
            "owner_wins": 0,
        })
        bucket["wins"] += 1
        bucket["spent"] += auction["winning_bid"] or 0
        bucket["winning_bids"].append(auction["winning_bid"] or 0)
        bucket["clearing_prices"].append(auction["clearing_price"] or 0)
        bucket["overpays"].append(auction["overpay"] or 0)
        if any(bid["owner"] == owner and bid["status"] == "complete" for bid in auction["bids"]):
            bucket["owner_spent"] += auction["winning_bid"] or 0
            bucket["owner_wins"] += 1
    summary = []
    for week in sorted(weeks):
        bucket = weeks[week]
        def median(values):
            ordered = sorted(values)
            mid = len(ordered) // 2
            if not ordered:
                return 0
            if len(ordered) % 2:
                return ordered[mid]
            return round((ordered[mid - 1] + ordered[mid]) / 2, 1)
        summary.append({
            "week": week,
            "wins": bucket["wins"],
            "spent": bucket["spent"],
            "median_winning_bid": median(bucket["winning_bids"]),
            "median_clearing_price": median(bucket["clearing_prices"]),
            "median_overpay": median(bucket["overpays"]),
            "owner_spent": bucket["owner_spent"],
            "owner_wins": bucket["owner_wins"],
        })
    return {"weeks": summary}


def proj_points(stats: dict, rec_points: float) -> float:
    if not stats:
        return 0
    if rec_points >= 1:
        return stats.get("pts_ppr") or 0
    if rec_points >= 0.5:
        return stats.get("pts_half_ppr") or stats.get("pts_ppr") or 0
    return stats.get("pts_std") or 0


def optimal_lineup(slots: list[str], candidates: list[dict]) -> dict:
    """Greedy best-projection assignment. Returns {player_id: slot}."""
    remaining = sorted(candidates, key=lambda row: -row["proj"])
    assigned: dict[str, str] = {}
    for slot in slots:
        if slot in ("BN", "TAXI", "IR"):
            continue
        eligible = SLOT_ELIGIBILITY.get(slot, set())
        for row in remaining:
            if row["id"] in assigned:
                continue
            if row["pos"] in eligible:
                assigned[row["id"]] = slot
                break
    return assigned


def build_brief(owner_name: str, refresh_history: bool) -> dict:
    week = get_current_nfl_week()
    completed = get_last_completed_nfl_week()
    api = SleeperAPI(LEAGUE_ID)
    league = api.get_league() or {}
    settings = league.get("settings") or {}
    scoring = league.get("scoring_settings") or {}
    rec_points = scoring.get("rec", 0) or 0
    budget = settings.get("waiver_budget") or 100
    roster_positions = league.get("roster_positions") or []
    players = SleeperAPI.get_all_players() or {}
    history = load_history(players, refresh_history)
    users = {u["user_id"]: u.get("display_name") or u.get("username") for u in (api.get_users() or [])}
    rosters = api.get_rosters() or []

    projections = make_request(
        "https://api.sleeper.com/projections/nfl/2026/"
        f"{week}?season_type=regular&position[]=QB&position[]=RB&position[]=WR&position[]=TE"
    ) or []
    proj_by_id = {str(row.get("player_id")): (row.get("stats") or {}) for row in projections}
    opponents = load_schedule(week)
    defense = load_defense_ranks()

    week_points = {}
    for played in range(1, completed + 1):
        for matchup in api.get_matchups(played) or []:
            rid = matchup.get("roster_id")
            week_points.setdefault(rid, {})[played] = {
                "total": matchup.get("points") or 0,
                "starters": [str(pid) for pid in (matchup.get("starters") or [])],
                "players": {str(pid): pts for pid, pts in (matchup.get("players_points") or {}).items()},
            }

    owned = {}
    views = []
    for roster in rosters:
        name = users.get(roster.get("owner_id"), "Unknown")
        ids = [str(pid) for pid in (roster.get("players") or [])]
        for pid in ids:
            owned[pid] = name
        used = (roster.get("settings") or {}).get("waiver_budget_used") or 0
        rsettings = roster.get("settings") or {}
        scores = {played: (week_points.get(roster["roster_id"], {}).get(played) or {}).get("total") or 0
                  for played in range(1, completed + 1)}
        views.append({
            "roster_id": roster["roster_id"],
            "owner": name,
            "record": f"{rsettings.get('wins', 0)}-{rsettings.get('losses', 0)}",
            "faab_remaining": budget - used,
            "scores": scores,
            "player_ids": ids,
            "starters": [str(pid) for pid in (roster.get("starters") or [])],
        })

    def describe(pid: str, roster_id: int | None = None) -> dict:
        info = players.get(pid, {})
        team = info.get("team")
        pos = info.get("position")
        opp = opponents.get(team)
        rank_key = pos if pos in ("QB", "RB", "WR", "TE") else None
        matchup = None
        if opp and rank_key:
            matchup = (defense.get(nfl_abbr(opp)) or {}).get(rank_key)
        points = {}
        for played in range(1, completed + 1):
            if roster_id is not None:
                blob = week_points.get(roster_id, {}).get(played) or {}
                points[f"w{played}"] = round((blob.get("players") or {}).get(pid, 0) or 0, 2)
            else:
                best = 0
                for blob in week_points.values():
                    played_blob = blob.get(played) or {}
                    best = max(best, (played_blob.get("players") or {}).get(pid, 0) or 0)
                points[f"w{played}"] = round(best, 2)
        return {
            "id": pid,
            "name": player_name(players, pid),
            "pos": pos,
            "team": team,
            "opponent": opp,
            "injury": info.get("injury_status"),
            "injury_body": info.get("injury_body_part"),
            "proj": round(proj_points(proj_by_id.get(pid, {}), rec_points), 2),
            "matchup_rank": matchup["rank"] if matchup else None,
            "matchup_ppg": matchup["ppg"] if matchup else None,
            "matchup_of": matchup["of"] if matchup else None,
            **points,
        }

    sean = next(view for view in views if view["owner"] == owner_name)
    sean_players = []
    for pid in sean["player_ids"]:
        row = describe(pid, sean["roster_id"])
        row["starting"] = pid in sean["starters"]
        sean_players.append(row)

    start_slots = [s for s in roster_positions if s not in ("BN", "TAXI", "IR")]
    best = optimal_lineup(start_slots, sean_players)
    for row in sean_players:
        row["optimal_slot"] = best.get(row["id"])
    sean_players.sort(key=lambda row: (not row["starting"], row["pos"] or "", -row["proj"]))

    sit_start_diffs = []
    for row in sean_players:
        optimal = row["optimal_slot"]
        if row["starting"] and optimal is None:
            sit_start_diffs.append({**row, "suggestion": "SIT"})
        elif not row["starting"] and optimal is not None:
            sit_start_diffs.append({**row, "suggestion": f"START ({optimal})"})

    # This week's matchup
    matchup_id = None
    for matchup in api.get_matchups(week) or []:
        if matchup.get("roster_id") == sean["roster_id"]:
            matchup_id = matchup.get("matchup_id")
            break
    opponent = None
    if matchup_id is not None:
        for matchup in api.get_matchups(week) or []:
            if matchup.get("matchup_id") == matchup_id and matchup.get("roster_id") != sean["roster_id"]:
                opp_view = next((v for v in views if v["roster_id"] == matchup.get("roster_id")), None)
                if opp_view:
                    opp_players = [describe(pid, opp_view["roster_id"]) for pid in opp_view["player_ids"]]
                    opp_best = optimal_lineup(start_slots, opp_players)
                    opp_proj = round(sum(r["proj"] for r in opp_players if r["id"] in opp_best), 2)
                    opponent = {
                        "owner": opp_view["owner"],
                        "record": opp_view["record"],
                        "projected": opp_proj,
                    }
                break
    sean_proj = round(sum(r["proj"] for r in sean_players if r["id"] in best), 2)

    current_bids = fetch_bids(LEAGUE_ID, players, through_week=max(week, 1))
    history_auctions = auctions_from(history.get("bids") or [])
    current_auctions = auctions_from(current_bids)

    pool = []
    seen = set()
    for pid, stats in proj_by_id.items():
        if pid in owned or pid in seen:
            continue
        points = proj_points(stats, rec_points)
        info = players.get(pid, {})
        if points < 6 or info.get("position") not in {"QB", "RB", "WR", "TE"}:
            continue
        if not info.get("team"):
            continue
        seen.add(pid)
        row = describe(pid)
        row["source"] = "free agent"
        pool.append(row)
    pool.sort(key=lambda row: -row["proj"])

    # Second-opinion projections: ESPN (free, no key) vs Sleeper.
    sleeper_universe = []
    for pid, stats in proj_by_id.items():
        info = players.get(pid, {})
        pos = info.get("position")
        team = info.get("team")
        proj = proj_points(stats, rec_points)
        if proj > 0 and pos in ("QB", "RB", "WR", "TE") and team:
            sleeper_universe.append(
                {"name": player_name(players, pid), "team": team,
                 "pos": pos, "proj": round(proj, 2)}
            )
    xc_table = xcheck.build_xcheck(sleeper_universe, week, rec_points)

    def xc_row(row: dict) -> dict | None:
        key = (xcheck.norm_name(row["name"]),
               xcheck.norm_team(row.get("team")), row.get("pos"))
        return xc_table.get(key)

    for row in sit_start_diffs:
        xc = xc_row(row)
        row["espn_proj"] = xc["espn_proj"] if xc else None
        row["espn_rank"] = xc["espn_rank"] if xc else None
        row["xcheck_mean"] = xc["mean"] if xc else None
        row["xcheck_disagree"] = xc["disagree"] if xc else None

    xcheck_rows = []
    for row in sorted(sean_players, key=lambda r: -r["proj"])[:24]:
        xc = xc_row(row)
        if not xc or xc["espn_proj"] is None:
            continue
        xcheck_rows.append({
            "name": row["name"], "pos": row.get("pos"), "team": row.get("team"),
            "starting": row["starting"],
            "sleeper_proj": xc["sleeper_proj"], "sleeper_rank": xc["sleeper_rank"],
            "espn_proj": xc["espn_proj"], "espn_rank": xc["espn_rank"],
            "mean": xc["mean"], "disagree": xc["disagree"],
        })

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "week": week,
        "last_completed_week": completed,
        "league_name": league.get("name"),
        "live_roster_positions": roster_positions,
        "open_spots": max(0, len(roster_positions) - len(sean["player_ids"])),
        "scoring_rec": rec_points,
        "waiver_budget": budget,
        "waiver_day_of_week": settings.get("waiver_day_of_week"),
        "waiver_clear_days": settings.get("waiver_clear_days"),
        "trade_deadline": settings.get("trade_deadline"),
        "sean": {
            "owner": owner_name,
            "record": sean["record"],
            "faab_remaining": sean["faab_remaining"],
            "scores": sean["scores"],
            "projected": sean_proj,
            "players": sean_players,
        },
        "opponent": opponent,
        "sit_start_diffs": sit_start_diffs,
        "xcheck": xcheck_rows,
        "xcheck_note": (
            "ESPN standard-scoring projections converted to league PPR via "
            "projected receptions. Ranks are positional. '!' = sources differ "
            "by 3+ pts or 6+ rank spots."
            if xcheck_rows else "ESPN cross-check unavailable (fetch failed)"
        ),
        "pool": pool[:30],
        "auctions_this_season": current_auctions,
        "auctions_last_season_this_week": [row for row in history_auctions if row["week"] == week],
        "market_2025": market_summary(history_auctions, owner_name),
        "market_2026": market_summary(current_auctions, owner_name),
    }


def fmt_player(row: dict) -> str:
    injury = f" {row['injury']}" if row.get("injury") else ""
    body = f" {row['injury_body']}" if row.get("injury_body") else ""
    opp = f" vs {row['opponent']}" if row.get("opponent") else ""
    matchup = ""
    if row.get("matchup_rank"):
        matchup = (
            f" opp {row['matchup_rank']}/{row['matchup_of']} "
            f"(1=softest, {row['matchup_ppg']} pts/g)"
        )
    weeks = " ".join(f"W{n}={row.get(f'w{n}', 0)}" for n in (1, 2, 3) if f"w{n}" in row)
    if row.get("suggestion"):
        flag = row["suggestion"]
    else:
        flag = "START" if row.get("starting") else "bench"
    return (
        f"  {flag:14} {row['name']:<24} {row.get('pos') or '':<3} {row.get('team') or '':<4}"
        f"{opp:<8} proj {row['proj']:<6} {weeks}{injury}{body}{matchup}"
    )


def print_auctions(title: str, auctions: list[dict], limit: int | None = None) -> None:
    print(f"\n{title}")
    shown = auctions if limit is None else auctions[:limit]
    if not shown:
        print("  none")
        return
    for auction in shown:
        if auction["winner"] is None:
            top = auction["bids"][0]
            print(
                f"  W{auction['week']} {auction['player_name']} ({auction['position']}) "
                f"no winner. High bid ${top['bid']} {top['status']} {top['owner']}"
            )
        else:
            print(
                f"  W{auction['week']} {auction['player_name']} ({auction['position']}) "
                f"won ${auction['winning_bid']} by {auction['winner']}  "
                f"clearing ${auction['clearing_price']}  overpay ${auction['overpay']}"
            )
        for bid in auction["bids"]:
            print(f"      ${bid['bid']:<4} {bid['status']:<8} {bid['owner']}")


def print_report(brief: dict) -> None:
    sean = brief["sean"]
    opp = brief["opponent"] or {}
    print("=" * 72)
    print(f"DYNASTY WEEK {brief['week']}  owner {sean['owner']}  ({sean['record']})")
    print(
        f"Matchup vs {opp.get('owner')} ({opp.get('record')})  "
        f"proj {sean['projected']} vs {opp.get('projected')}"
    )
    print(f"Slots {brief['live_roster_positions']}")
    print(f"Open spots {brief['open_spots']}")
    print(
        f"FAAB ${sean['faab_remaining']} of ${brief['waiver_budget']}  "
        f"scoring rec={brief['scoring_rec']}  trade deadline week {brief['trade_deadline']}"
    )
    print("Scores", sean["scores"])
    print("\nROSTER (optimal slot by projection)")
    for row in sean["players"]:
        print(fmt_player(row))
    if brief["sit_start_diffs"]:
        print("\nSTART/SIT FLAGS (projection vs current lineup)")
        for row in brief["sit_start_diffs"]:
            print(fmt_player(row))
    else:
        print("\nSTART/SIT: optimal lineup matches current starters")
    print("\nPROJECTION CROSS-CHECK (Sleeper vs ESPN)")
    print(f"  {brief['xcheck_note']}")
    for row in brief["xcheck"]:
        flag = " !" if row["disagree"] else "  "
        start = "starting" if row["starting"] else "bench   "
        print(
            f" {flag} {start} {row['name']:<24} {row['pos']:<3} {row['team']:<4}"
            f"Sleeper {row['sleeper_proj']:<6} (#{row['sleeper_rank']})  "
            f"ESPN {row['espn_proj']:<6} (#{row['espn_rank']})  mean {row['mean']}"
        )
    print("\nAVAILABLE (free agents, proj >= 6)")
    for row in brief["pool"][:20]:
        print(fmt_player(row))
    print_auctions("THIS SEASON, EVERY BID", brief["auctions_this_season"])
    print_auctions(
        f"2025 WEEK {brief['week']}, EVERY BID (clearing = 2nd bid + $1)",
        brief["auctions_last_season_this_week"],
    )
    print("\n2025 MARKET BY WEEK (winning auctions only)")
    print(f"  {'Wk':>3} {'wins':>5} {'spent':>6} {'medWin':>7} {'medClear':>9} {'medOver':>8} {OWNER}")
    for row in brief["market_2025"]["weeks"]:
        print(
            f"  {row['week']:3} {row['wins']:5} {row['spent']:6} {row['median_winning_bid']:7} "
            f"{row['median_clearing_price']:9} {row['median_overpay']:8} "
            f"spent ${row['owner_spent']} won {row['owner_wins']}"
        )
    print("=" * 72)


def main():
    parser = argparse.ArgumentParser(description="Dynasty weekly roster and FAAB brief")
    parser.add_argument("--refresh-history", action="store_true",
                        help="Re-download 2025 winning and losing waiver bids")
    parser.add_argument("--owner", default=OWNER)
    args = parser.parse_args()
    brief = build_brief(args.owner, args.refresh_history)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(BRIEF_PATH, "w", encoding="utf-8") as handle:
        json.dump(brief, handle, indent=2)
    print_report(brief)
    print(f"JSON brief: {BRIEF_PATH}")


if __name__ == "__main__":
    main()
