import requests
import json

# Get players
players = requests.get('https://api.sleeper.app/v1/players/nfl', timeout=10).json()

# Search for specific players from the image
search_names = [
    'Travis Etienne',
    'Patrick Mahomes',
    'Ja\'Marr Chase',
    'DeVonta Smith',
    'George Kittle',
    'Nico Collins',
    'George Pickens',
    'Javonte Williams',
    'Drake Maye',
    'Travis Kelce',
    'Matthew Stafford',
    'Jalen Hurts',
    'James Cook',
    'Josh Jacobs'
]

print("=== Player ID Lookup ===")
for player_id, pdata in players.items():
    full_name = f"{pdata.get('first_name', '')} {pdata.get('last_name', '')}".strip()
    if full_name in search_names:
        print(f"{player_id}: {full_name} ({pdata.get('position')}-{pdata.get('team')})")
