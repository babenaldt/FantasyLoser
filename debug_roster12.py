import requests
import json

# Get rosters
rosters = requests.get('https://api.sleeper.app/v1/league/1263579037352079360/rosters').json()
users = requests.get('https://api.sleeper.app/v1/league/1263579037352079360/users').json()
user_map = {u['user_id']: u['display_name'] for u in users}

# Find roster 12
roster_12 = next((r for r in rosters if r['roster_id'] == 12), None)
print(f"Roster 12: {user_map.get(roster_12['owner_id'], 'Unknown')}")

# Also roster 6
roster_6 = next((r for r in rosters if r['roster_id'] == 6), None)
print(f"Roster 6: {user_map.get(roster_6['owner_id'], 'Unknown')}")

# Check week 12 transactions more carefully
print("\n\nWeek 12 transactions (complete only):")
txns = requests.get('https://api.sleeper.app/v1/league/1263579037352079360/transactions/12').json()
for txn in txns:
    if txn.get('status') == 'complete':
        print(f"\nTransaction ID: {txn['transaction_id']}")
        adds = txn.get('adds') or {}
        drops = txn.get('drops') or {}
        print(f"  Adds: {adds}")
        print(f"  Drops: {drops}")
        print(f"  Type: {txn.get('type')}")
        settings = txn.get('settings')
        if settings:
            print(f"  FAAB: {settings.get('waiver_bid', 0)}")
