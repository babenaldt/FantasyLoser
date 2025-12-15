import requests
import json

# Get week 2 transactions for Sean Rabenaldt
txns = requests.get('https://api.sleeper.app/v1/league/1263579037352079360/transactions/2').json()

# Get rosters
rosters = requests.get('https://api.sleeper.app/v1/league/1263579037352079360/rosters').json()
users = requests.get('https://api.sleeper.app/v1/league/1263579037352079360/users').json()
user_map = {u['user_id']: u['display_name'] for u in users}

# Find SeanRabenaldt's roster
sean_user_id = '992533962855608320'
sean_roster = next((r for r in rosters if r['owner_id'] == sean_user_id), None)
sean_roster_id = sean_roster['roster_id']

print(f"Sean's roster ID: {sean_roster_id}")
print(f"\nWeek 2 transactions for Sean:")

for txn in txns:
    adds = txn.get('adds') or {}
    drops = txn.get('drops') or {}
    
    # Check if this transaction involves Sean's roster
    sean_involved = False
    for player_id, roster_id in adds.items():
        if roster_id == sean_roster_id:
            sean_involved = True
            break
    for player_id, roster_id in drops.items():
        if roster_id == sean_roster_id:
            sean_involved = True
            break
    
    if sean_involved:
        print(f"\nTransaction ID: {txn['transaction_id']}")
        print(f"  Status: {txn['status']}")
        print(f"  Type: {txn['type']}")
        print(f"  Adds: {adds}")
        print(f"  Drops: {drops}")
        settings = txn.get('settings')
        if settings:
            print(f"  FAAB: {settings.get('waiver_bid', 0)}")
