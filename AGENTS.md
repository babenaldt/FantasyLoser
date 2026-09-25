# Dynasty weekly roster and FAAB

Use this when Sean asks for Dynasty lineup, roster, or waiver advice.

His Sleeper name is `SeanRabenaldt`. The 2026 league id is `1312064104759844864`
(GM Chassis Controls Dynasty, superflex). Scoring is full PPR. The 2025 season
of the same league is `1264304480178950144`, used only for FAAB bid history.

## Start here

From the repo root:

```bash
PYTHONIOENCODING='utf-8' python scripts/dynasty_week.py
```

Read that report before giving advice. Do not write temp scripts, one-off API
dumps, or extra snapshot files. The report already has the matchup, a
projection-optimal lineup, start/sit flags, the waiver pool, and every bid.

If `website/public/data/archive/2025/dynasty_faab_all_bids_2025.json` is
missing, run once:

```bash
python scripts/dynasty_week.py --refresh-history
```

## How to use the start/sit flags

The script assigns the projection-optimal lineup greedily (best proj into each
eligible slot, FLEX = RB/WR/TE, SUPER_FLEX = QB/RB/WR/TE). Flags mark where the
live Sleeper lineup differs. Apply injury judgment on top: a Questionable tag
can override a small projection edge (e.g. a Q Nico Collins at 14.09 vs a
healthy Jaylen Waddle at 13.17 is a real call, not an auto-start).

## Projection cross-check

The report's cross-check section lines up Sleeper's projections against ESPN's
(free, no key; standard scoring converted to league PPR via projected
receptions). Both sources usually agree; a `!` flag means they differ by 3+
points or 6+ positional rank spots — treat that as a real second opinion, not
a tiebreak. ESPN sometimes zeroes out players it expects to miss, which is
signal, not a bug. Shared logic lives in `scripts/xcheck.py`.

## FAAB posture

No standing doctrine yet like Chopped's. Default posture: Sean is 2-0 with a
deep roster, so treat FAAB as precious and bid only for players who would crack
the starting lineup or cover a starter's injury. Price against clearing
(second bid + $1), not the winning bid.

# Chopped weekly roster and FAAB

Use this when Sean asks for Chopped lineup, roster, waiver, or FAAB advice.

His Sleeper name is `SeanRabenaldt`. The 2026 league id is `1383538112403095552`. Scoring is full PPR (confirm `rec` on the brief; it was 1.0). Pass touchdowns are 4. The site JSON is not the source of truth for a live waiver week. The script below reads Sleeper directly.

## Start here

From the repo root, on Windows:

```powershell
$env:PYTHONIOENCODING='utf-8'
python scripts/chopped_week.py
```

Read that report before giving advice. Do not write temp scripts, one-off API dumps, or extra snapshot files. The report already has the roster, last week's scores, the open bench spot, roster caps, the waiver pool, and every bid.

If `website/public/data/archive/2025/chopped_faab_all_bids_2025.json` is missing, run once:

```powershell
python scripts/chopped_week.py --refresh-history
```

That file is every 2025 waiver bid, including bids that lost. The winning-only archive (`archive_faab_chopped_2025.json`) is for the website and is the wrong file for pricing.

`python scripts/generate_data.py --quick` refreshes the site. It is not required for the weekly advice. Dynasty playoff projections can fail on a local NumPy/SciPy mismatch; ignore that for Chopped.

## Projection cross-check

Same as Dynasty's: the report carries a Sleeper-vs-ESPN section (see above).
`!` flags mark real disagreements — useful for the wire, where ESPN sometimes
zeroes out a player it expects benched (e.g. a backup QB Sleeper still
projects). Shared logic lives in `scripts/xcheck.py`.

## How to price a bid

A bid only has to beat the second-highest bid. The report's clearing price is second bid + $1. Overpay is what the winner spent above that.

Use both of these, not the winning bid alone:

- This year's auctions on the report (wins and losses).
- The same week last year, plus the 2025 week-by-week market table.

Failed bids do not spend FAAB.

## FAAB rules

Sean is in survival mode, and FAAB is more valuable later. Default to spending $0.

**Two-tier spending (guillotine consensus: never pay for mediocrity, overpay for the best):**
1. **Stars — overspend to win.** When a genuine difference-maker hits the wire (top-30ish fantasy player, clear every-week role — the Jefferson/Henry/JT tier), bid to WIN, not to value. 20-30% of remaining budget is fair; more for the last starting-caliber RB. Blind bidding means the clearing price *is* the winning bid — there is no "vanity number" at this tier. Why: cut lines rise every week, only the very best give an edge late, and in a shrinking league you are also denying a rival the star.
2. **Everything else — $0 or $1.** The real budget killer is not one big swing, it is death by a thousand papercuts: ten $8-15 bids on flex-tier players vaporizes half the budget with no game-changer to show. Kill the middle tier entirely. If the lineup is safe, the only acceptable claims are $0/$1 on a player he would actually start, ordered so a lucky win fills the open spot. Losing those claims is the intended result.

**Vulture system (the guillotine edge).** Every week the brief's CHOP WATCH ranks the likeliest chop victims by projected starters and lists their best players. Pre-rank those targets before waivers run — treat each week like a second draft. The signal is bye-week depletion: a good roster projecting low is both likely to get chopped *and* holding the best players to vulture. Prefer targets whose byes have already passed (they're available for every remaining elimination round) and players with clear existing roles over buried upside.

**FAAB bullying.** The enviable late-season position is having the most money when stars clear for cheap (2025: Taylor, Amon-Ra, Kittle went $0-8 from week 11 because he still had budget). Stay in the top FAAB tier; never drop out of it chasing tier-2 players.

Spend triggers (exceptions to $0 default): the week-5 bye hole, fewer than 2 startable RBs entering week 9, or an injury to a starter. The 2025 bids that mattered — Josh Allen $41 in week 5, Puka Nacua $31 in week 7 — were tier-1 overspends, and they were correct.

### Waiver shopping list (from the starter-slot chart)
Positional demand ramps as starters grow 5 -> 11. Build in this order:
1. **RB** — the scarce one. Needed: week 5 bye cover (Walker + Hubbard both out), a 2nd startable RB from week 9, a 3rd from week 13. Never feel "done" at RB; every upside stash should be an RB first.
2. **WR** — 2nd WR slot opens week 5, 3rd WR week 8, 3 per week from 13.
3. **QB** — a 2nd QB is only *startable* from week 11 (WRTQ superflex slots), not week 5. Add one on the week 10/11 waivers; QBs are cheap. The old "planned Week 5 QB spend" is obsolete: week 5's expansion spot goes to RB/WR.
4. **TE** — 2nd TE slot opens week 11; Kraft + Juwan Johnson already cover it.

Spend triggers (exceptions to $0 default): the week-5 bye hole, fewer than 2 startable RBs entering week 9, or an injury to a starter. Expansion weeks (5, 7, 9, 11, 13, 15) need no drop — prefer adds then; on must-drop weeks (4, 6, 8, 10, 12, 14) only add windfalls (chopped teams' drops).

## League chart

Sleeper's `roster_positions` are the starting slots. The chart caps are separate, and the script enforces them. Do not recommend a player at a capped position.

Teams entering the week: 20, 18, 16, 14, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1.

Chops: 2 teams in weeks 1-4, then 1 team in weeks 5-15. Week 16 has 1 team left.

Roster size: 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13, 14, 14, 15, 15. An expansion week adds one bench spot, so he can add without a drop. On a non-expansion week he must drop.

Roster caps: weeks 1-4 max 1 QB and 2 TE. Weeks 5-9 max 2 QB and 2 TE. Weeks 10+ max 3 QB and 3 TE.

Starter slots (full chart transcribed from the commissioner's photo, 2026-09-25; also encoded as CHART_SLOTS in scripts/chopped_week.py, and the brief lists upcoming changes):
- Weeks 1-3: QB, RB, WR, TE, WRT (5 starters)
- Week 4: adds a 2nd WRT (6)
- Week 5: 2nd WR replaces a WRT -> QB, RB, WR, WR, TE, WRT (6)
- Week 6-7: 2nd WRT back (7)
- Week 8: 3rd WR (8)
- Weeks 9-10: 2nd RB replaces a WR (8)
- Week 11: 2nd TE and 2 WRTQ replace the WRTs (9)
- Week 12: QB, RB, RB, WR, WR, TE, TE, WRT, WRTQ, WRTQ (10)
- Weeks 13-14: 3rd RB and 3rd WR, WRTQ single (10)
- Weeks 15-16: QB, RB x3, WR x3, TE, WRT x2, WRTQ (11)

Week 5 adds the second WR starter and opens the second QB roster spot. That week was the planned QB spend, but the 2026 Week 5 RB bye crunch (Walker + Hubbard both out) deprioritized it.

## What to answer

1. Where he finished last week against the cut line, and whether this week is survival or a pass.
2. The lineup, including the Nabers-or-backup decision and which bench player stays benched.
3. Claims in priority order, with a dollar amount, the clearing-price comp, and what losing the claim preserves.
4. Who not to bid on, especially capped QBs and TEs, injured players who would waste the only open spot, and stars he does not need this week.
