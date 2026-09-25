"""Second-opinion projections for the weekly briefs.

Pulls ESPN's free fantasy projections (no API key) and lines them up against
Sleeper's projections for the same players. ESPN publishes standard-scoring
weekly numbers, so they are converted to the league's PPR via each player's
projected receptions (ESPN stat id 53).

Usage from a brief script:

    from xcheck import build_xcheck
    universe = [{"name": ..., "team": ..., "pos": ..., "proj": ...}, ...]  # Sleeper universe
    table = build_xcheck(universe, week, rec_points)  # {(name, team, pos): row}
    # row: sleeper_proj, sleeper_rank, espn_proj, espn_rank, mean, disagree

Ranks are positional, 1-based, computed over each source's full universe.
`disagree` is True when the sources differ by >= 3 points or rank the player
more than 6 spots apart at his position. If ESPN is unreachable the table is
empty and callers should print "cross-check unavailable" rather than fail.
"""

from __future__ import annotations

import json
import os
import re
import urllib.request

ESPN_POS = {1: "QB", 2: "RB", 3: "WR", 4: "TE"}
ESPN_REC_STAT = "53"  # projected receptions, used for the PPR conversion
PROJ_DIFF_FLAG = 3.0
RANK_DIFF_FLAG = 6

_SUFFIX_RE = re.compile(r"\b(jr|sr|ii|iii|iv|v)\.?$", re.IGNORECASE)

# Sleeper uses a few non-standard abbreviations; normalize to ESPN's.
TEAM_ALIASES = {"LA": "LAR", "ARZ": "ARI", "BLT": "BAL", "CLV": "CLE", "HST": "HOU"}


def norm_name(name: str | None) -> str:
    n = (name or "").lower().replace("'", "").replace(".", "").replace("-", " ")
    n = re.sub(r"\s+", " ", n).strip()
    return _SUFFIX_RE.sub("", n).strip()


def norm_team(team: str | None) -> str | None:
    if not team:
        return None
    t = team.upper().strip()
    return TEAM_ALIASES.get(t, t)


def _get_json(url: str, headers: dict | None = None, timeout: int = 30) -> dict:
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0", **(headers or {})}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def fetch_espn(week: int, season: int = 2026, cache_dir: str = "output") -> list[dict]:
    """Full ESPN projection universe for a week.

    Returns [{name, team, pos, proj_std, rec}] with standard-scoring
    projections. Cached under cache_dir (gitignored output/).
    """
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, f"espn_projections_{season}_w{week}.json")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, ValueError):
            pass

    teams_url = (
        f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{season}"
        "?view=proTeamSchedules_wl"
    )
    team_data = _get_json(teams_url)
    team_map = {
        t["id"]: t["abbrev"] for t in team_data["settings"]["proTeams"]
    }

    filt = {
        "players": {
            "filterStatus": {"value": ["FREEAGENT", "WAIVERS", "ONTEAM"]},
            "filterSlotIds": {
                "value": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13,
                          14, 15, 16, 17, 18, 19, 23, 24]
            },
            # ESPN rejects a limit without a sort.
            "sortPercOwned": {"sortPriority": 3, "sortAsc": False},
            "limit": 1000,
        }
    }
    players_url = (
        f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{season}"
        f"/segments/0/leaguedefaults/1?view=kona_player_info"
    )
    player_data = _get_json(
        players_url, headers={"x-fantasy-filter": json.dumps(filt)}
    )

    universe = []
    for entry in player_data.get("players", []):
        pl = entry.get("player", {})
        pos = ESPN_POS.get(pl.get("defaultPositionId"))
        if pos is None:
            continue
        proj_std, rec = 0.0, 0.0
        for stat in pl.get("stats", []):
            if (
                stat.get("seasonId") == season
                and stat.get("statSourceId") == 1
                and stat.get("statSplitTypeId") == 1
                and stat.get("scoringPeriodId") == week
            ):
                proj_std = stat.get("appliedTotal") or 0.0
                rec = (stat.get("stats") or {}).get(ESPN_REC_STAT) or 0.0
                break
        universe.append(
            {
                "name": pl.get("fullName"),
                "team": team_map.get(pl.get("proTeamId")),
                "pos": pos,
                "proj_std": round(proj_std, 2),
                "rec": round(rec, 2),
            }
        )

    with open(cache_path, "w", encoding="utf-8") as handle:
        json.dump(universe, handle)
    return universe


def _positional_ranks(universe: list[dict], key: str) -> dict:
    """{(norm name, team, pos): 1-based rank} within each position by key desc."""
    by_pos: dict[str, list] = {}
    for row in universe:
        if row.get("pos") not in ("QB", "RB", "WR", "TE"):
            continue
        by_pos.setdefault(row["pos"], []).append(row)
    ranks = {}
    for pos, rows in by_pos.items():
        rows.sort(key=lambda r: -(r.get(key) or 0))
        for i, row in enumerate(rows, 1):
            ranks[(norm_name(row.get("name")), norm_team(row.get("team")), pos)] = i
    return ranks


def build_xcheck(
    sleeper_universe: list[dict],
    week: int,
    rec_points: float = 1.0,
    cache_dir: str = "output",
) -> dict:
    """Cross-check table keyed by (norm name, norm team, pos).

    sleeper_universe: [{name, team, pos, proj}] with projections already in the
    league's scoring. rec_points converts ESPN standard numbers to the league.
    """
    try:
        espn_universe = fetch_espn(week, cache_dir=cache_dir)
    except Exception:
        return {}

    espn_by_key = {}
    espn_by_namepos: dict[tuple, list] = {}
    for row in espn_universe:
        row["proj"] = round(row["proj_std"] + row["rec"] * (rec_points or 0), 2)
        key = (norm_name(row.get("name")), norm_team(row.get("team")), row.get("pos"))
        espn_by_key[key] = row
        espn_by_namepos.setdefault((key[0], key[2]), []).append(row)

    espn_ranks = _positional_ranks(espn_universe, "proj")
    sleeper_ranks = _positional_ranks(sleeper_universe, "proj")

    def espn_match(key):
        hit = espn_by_key.get(key)
        if hit is not None:
            return hit, True
        # Fall back to name+pos when the two sources disagree on team
        # (mid-season trades); only when unambiguous.
        cands = espn_by_namepos.get((key[0], key[2]), [])
        if len(cands) == 1:
            return cands[0], False
        return None, False

    table = {}
    for row in sleeper_universe:
        key = (norm_name(row.get("name")), norm_team(row.get("team")), row.get("pos"))
        espn, team_ok = espn_match(key)
        s_proj = row.get("proj") or 0
        s_rank = sleeper_ranks.get(key)
        e_proj = espn["proj"] if espn else None
        e_key = (
            (norm_name(espn.get("name")), norm_team(espn.get("team")), espn.get("pos"))
            if espn
            else None
        )
        e_rank = espn_ranks.get(e_key) if e_key else None
        mean = round((s_proj + e_proj) / 2, 2) if e_proj is not None else None
        disagree = False
        if e_proj is not None and abs(s_proj - e_proj) >= PROJ_DIFF_FLAG:
            disagree = True
        if (
            s_rank is not None
            and e_rank is not None
            and min(s_rank, e_rank) <= 36
            and abs(s_rank - e_rank) >= RANK_DIFF_FLAG
        ):
            disagree = True
        table[key] = {
            "name": row.get("name"),
            "team": row.get("team"),
            "pos": row.get("pos"),
            "sleeper_proj": round(s_proj, 2),
            "sleeper_rank": s_rank,
            "espn_proj": e_proj,
            "espn_rank": e_rank,
            "mean": mean,
            "disagree": disagree,
            "team_mismatch": espn is not None and not team_ok,
        }
    return table
