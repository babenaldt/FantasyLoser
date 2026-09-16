"""Backfill 2025 archive data with detailed FAAB transaction history."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core_data import SleeperAPI

CHOPPED_LEAGUE_ID_2025 = "1263579037352079360"
DYNASTY_LEAGUE_ID_2025 = "1264304480178950144"

def fetch_faab_history(league_id, league_label):
    """Fetch all FAAB waiver transactions for a completed league."""
    api = SleeperAPI(league_id)
    league = api.get_league()
    if not league:
        print(f"  Error: Could not fetch {league_label} league")
        return []

    # Load player database for name resolution
    players_path = 'website/public/data/players_data.json'
    if os.path.exists(players_path):
        with open(players_path) as f:
            player_data = json.load(f)
    else:
        player_data = {}
        print("  Warning: No player database found")

    # Get user/roster mapping
    rosters = api.get_rosters() or []
    users = api.get_users() or []
    user_map = {u['user_id']: u.get('display_name', u.get('username', '')) for u in users}
    roster_owner = {}
    for r in rosters:
        owner_id = r.get('owner_id', '')
        roster_owner[r['roster_id']] = user_map.get(owner_id, f"Team {r['roster_id']}")

    def player_name(pid):
        if not pid or pid == '0':
            return 'Unknown'
        p = player_data.get(str(pid), {})
        first = p.get('first_name', '')
        last = p.get('last_name', '')
        if first and last:
            return f"{first} {last}"
        return p.get('full_name', str(pid))

    def player_pos(pid):
        return player_data.get(str(pid), {}).get('position', '')

    all_moves = []
    print(f"  Fetching transactions for {league_label}...")

    for week in range(1, 19):
        txns = api.get_transactions(week) or []
        for t in txns:
            if t.get('status') != 'complete':
                continue
            if t.get('type') != 'waiver':
                continue

            bid = t.get('settings', {}).get('waiver_bid', 0)
            creator = t.get('creator', '')

            # Find owner name
            owner = 'Unknown'
            for rid, roster in enumerate(rosters):
                if roster.get('owner_id') == creator:
                    owner = roster_owner.get(roster['roster_id'], 'Unknown')
                    break

            adds = t.get('adds', {}) or {}
            drops = t.get('drops', {}) or {}

            for pid in adds:
                dropped_names = [player_name(dp) for dp in drops]
                all_moves.append({
                    'week': week,
                    'player_name': player_name(pid),
                    'position': player_pos(pid),
                    'bid': bid,
                    'owner': owner,
                    'dropped': ', '.join(dropped_names) if dropped_names else ''
                })

    all_moves.sort(key=lambda x: (-x['bid'], x['week']))
    print(f"  Found {len(all_moves)} FAAB moves")
    return all_moves


def main():
    print("=" * 60)
    print("BACKFILLING 2025 ARCHIVE FAAB TRANSACTIONS")
    print("=" * 60)

    for league_id, label, filename in [
        (CHOPPED_LEAGUE_ID_2025, 'Chopped', 'archive_faab_chopped_2025.json'),
        (DYNASTY_LEAGUE_ID_2025, 'Dynasty', 'archive_faab_dynasty_2025.json'),
    ]:
        moves = fetch_faab_history(league_id, label)
        out_path = os.path.join('website', 'public', 'data', 'archive', '2025', filename)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, 'w') as f:
            json.dump(moves, f, indent=2)
        print(f"  Saved {len(moves)} moves to {out_path}")

    print("\nDone!")


if __name__ == '__main__':
    main()
