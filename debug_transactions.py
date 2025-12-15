import requests
import json

# Fetch week 12 transactions for Chopped league
txns = requests.get('https://api.sleeper.app/v1/league/1263579037352079360/transactions/12').json()

# Find transaction with Jonathan Taylor (6813)
for txn in txns:
    adds = txn.get('adds', {})
    if '6813' in adds:
        print("Transaction with Jonathan Taylor:")
        print(json.dumps(txn, indent=2))
        print("\n\n")

# Find transactions with Nico Collins (7569)
for txn in txns:
    adds = txn.get('adds', {})
    if '7569' in adds:
        print("Transaction with Nico Collins:")
        print(json.dumps(txn, indent=2))
        print("\n\n")
