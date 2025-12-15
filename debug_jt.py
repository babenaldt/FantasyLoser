import requests
import json

# Fetch all transactions for weeks 1-12 for Chopped league
all_txns = []
for week in range(1, 13):
    txns = requests.get(f'https://api.sleeper.app/v1/league/1263579037352079360/transactions/{week}').json()
    if txns:
        all_txns.extend([(week, t) for t in txns])

# Find all transactions involving Jonathan Taylor (6813)
print("All transactions with Jonathan Taylor (6813):")
for week, txn in all_txns:
    adds = txn.get('adds') or {}
    drops = txn.get('drops') or {}
    
    if '6813' in adds or '6813' in drops:
        print(f"\nWeek {week}: Status={txn['status']}")
        if '6813' in adds:
            print(f"  Added to roster {adds['6813']}")
        if '6813' in drops:
            print(f"  Dropped from roster {drops['6813']}")
        print(f"  Type: {txn['type']}, FAAB: {txn.get('settings', {}).get('waiver_bid', 0)}")

# Get rosters to see roster_id -> owner mapping
rosters = requests.get('https://api.sleeper.app/v1/league/1263579037352079360/rosters').json()
users = requests.get('https://api.sleeper.app/v1/league/1263579037352079360/users').json()
user_map = {u['user_id']: u['display_name'] for u in users}
roster_map = {r['roster_id']: user_map.get(r['owner_id'], 'Unknown') for r in rosters}

print("\n\nRoster ID -> Owner Name:")
for rid, name in sorted(roster_map.items()):
    print(f"  {rid}: {name}")
