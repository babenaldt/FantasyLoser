"""Core data fetching and processing for Fantasy Football site."""

import requests
import json
import os
import certifi

# Configuration
OUTPUT_DIR = "output"
ASTRO_DATA_DIR = "website/public/data"

# Proxy configuration
PROXIES = {
    'http': os.environ.get('HTTP_PROXY', os.environ.get('http_proxy')),
    'https': os.environ.get('HTTPS_PROXY', os.environ.get('https_proxy', os.environ.get('HTTP_PROXY', os.environ.get('http_proxy'))))
}
PROXIES = {k: v for k, v in PROXIES.items() if v}

# Scoring Presets
SCORING_PRESETS = {
    'standard': {
        'name': 'Standard (No PPR)',
        'passing_yards': 0.04,
        'passing_tds': 4,
        'passing_2pt': 2,
        'interceptions': -2,
        'rushing_yards': 0.1,
        'rushing_tds': 6,
        'rushing_2pt': 2,
        'receptions': 0,
        'receiving_yards': 0.1,
        'receiving_tds': 6,
        'receiving_2pt': 2,
        'fumbles_lost': -2,
        # Kicker scoring (distance-based)
        'fg_0_19': 3,
        'fg_20_29': 3,
        'fg_30_39': 3,
        'fg_40_49': 4,
        'fg_50_59': 5,
        'fg_60_plus': 6,
        'fg_missed': -1,
        'pat_made': 1,
        'pat_missed': -1,
        # Defense scoring
        'def_td': 6,
        # Special teams defense scoring (Sleeper)
        'kr_td': 6,
        'st_td': 6,
        'def_int': 2,
        'def_fumble_recovery': 2,
        'def_fumble_forced': 1,
        'st_fumble_recovery': 1,
        'st_fumble_forced': 1,
        'def_sack': 1,
        'def_safety': 2,
        'def_blocked_kick': 2,
        'points_allowed_0': 10,
        'points_allowed_1_6': 7,
        'points_allowed_7_13': 4,
        'points_allowed_14_20': 1,
        'points_allowed_21_27': 0,
        'points_allowed_28_34': -1,
        'points_allowed_35_plus': -4
    },
    'half_ppr': {
        'name': 'Half PPR',
        'passing_yards': 0.04,
        'passing_tds': 4,
        'passing_2pt': 2,
        'interceptions': -2,
        'rushing_yards': 0.1,
        'rushing_tds': 6,
        'rushing_2pt': 2,
        'receptions': 0.5,
        'receiving_yards': 0.1,
        'receiving_tds': 6,
        'receiving_2pt': 2,
        'fumbles_lost': -2,
        # Kicker scoring (distance-based)
        'fg_0_19': 3,
        'fg_20_29': 3,
        'fg_30_39': 3,
        'fg_40_49': 4,
        'fg_50_59': 5,
        'fg_60_plus': 6,
        'fg_missed': -1,
        'pat_made': 1,
        'pat_missed': -1,
        # Defense scoring
        'def_td': 6,
        # Special teams defense scoring (Sleeper)
        'kr_td': 6,
        'st_td': 6,
        'def_int': 2,
        'def_fumble_recovery': 2,
        'def_fumble_forced': 1,
        'st_fumble_recovery': 1,
        'st_fumble_forced': 1,
        'def_sack': 1,
        'def_safety': 2,
        'def_blocked_kick': 2,
        'points_allowed_0': 10,
        'points_allowed_1_6': 7,
        'points_allowed_7_13': 4,
        'points_allowed_14_20': 1,
        'points_allowed_21_27': 0,
        'points_allowed_28_34': -1,
        'points_allowed_35_plus': -4
    },
    'ppr': {
        'name': 'Full PPR',
        'passing_yards': 0.04,
        'passing_tds': 4,
        'passing_2pt': 2,
        'interceptions': -2,
        'rushing_yards': 0.1,
        'rushing_tds': 6,
        'rushing_2pt': 2,
        'receptions': 1,
        'receiving_yards': 0.1,
        'receiving_tds': 6,
        'receiving_2pt': 2,
        'fumbles_lost': -2,
        # Kicker scoring (distance-based)
        'fg_0_19': 3,
        'fg_20_29': 3,
        'fg_30_39': 3,
        'fg_40_49': 4,
        'fg_50_59': 5,
        'fg_60_plus': 6,
        'fg_missed': -1,
        'pat_made': 1,
        'pat_missed': -1,
        # Defense scoring
        'def_td': 6,
        # Special teams defense scoring (Sleeper)
        'kr_td': 6,
        'st_td': 6,
        'def_int': 2,
        'def_fumble_recovery': 2,
        'def_fumble_forced': 1,
        'st_fumble_recovery': 1,
        'st_fumble_forced': 1,
        'def_sack': 1,
        'def_safety': 2,
        'def_blocked_kick': 2,
        'points_allowed_0': 10,
        'points_allowed_1_6': 7,
        'points_allowed_7_13': 4,
        'points_allowed_14_20': 1,
        'points_allowed_21_27': 0,
        'points_allowed_28_34': -1,
        'points_allowed_35_plus': -4
    }
}

# Default to Full PPR
PPR_SCORING = SCORING_PRESETS['ppr'].copy()
del PPR_SCORING['name']

ROSTERABLE_POSITIONS = ['QB', 'RB', 'WR', 'TE', 'K', 'DEF']


def ensure_directories():
    """Ensure output directories exist."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(ASTRO_DATA_DIR, exist_ok=True)


def make_request(url, timeout=30):
    """Make HTTP request with error handling."""
    try:
        response = requests.get(
            url,
            timeout=timeout,
            verify=certifi.where(),
            proxies=PROXIES
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Request failed for {url}: {e}")
        return None


def save_json(data, filepath):
    """Save data to JSON file."""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  ✓ Saved: {filepath}")


class SleeperAPI:
    """Sleeper API client."""
    BASE_URL = "https://api.sleeper.app/v1"
    
    def __init__(self, league_id):
        self.league_id = league_id
    
    def get_league(self):
        """Get league details."""
        return make_request(f"{self.BASE_URL}/league/{self.league_id}")
    
    def get_rosters(self):
        """Get league rosters."""
        return make_request(f"{self.BASE_URL}/league/{self.league_id}/rosters")
    
    def get_users(self):
        """Get league users."""
        return make_request(f"{self.BASE_URL}/league/{self.league_id}/users")
    
    def get_matchups(self, week):
        """Get matchups for a specific week."""
        return make_request(f"{self.BASE_URL}/league/{self.league_id}/matchups/{week}")
    
    def get_transactions(self, week):
        """Get transactions for a specific week."""
        return make_request(f"{self.BASE_URL}/league/{self.league_id}/transactions/{week}")

    def get_user(self, username):
        """Get user by username."""
        return make_request(f"{self.BASE_URL}/user/{username}")
    
    @staticmethod
    def get_all_players():
        """Get all NFL players."""
        return make_request(f"{SleeperAPI.BASE_URL}/players/nfl")


def calculate_fantasy_points(player_stats, scoring=PPR_SCORING):
    """Calculate fantasy points for a player based on stats."""
    pts = 0
    
    # Offensive stats
    pts += (player_stats.get('passing_yards', 0) or 0) * scoring.get('passing_yards', 0)
    pts += (player_stats.get('passing_tds', 0) or 0) * scoring.get('passing_tds', 0)
    pts += (player_stats.get('passing_2pt_conversions', 0) or 0) * scoring.get('passing_2pt', 0)
    pts += (player_stats.get('interceptions', 0) or 0) * scoring.get('interceptions', 0)
    pts += (player_stats.get('rushing_yards', 0) or 0) * scoring.get('rushing_yards', 0)
    pts += (player_stats.get('rushing_tds', 0) or 0) * scoring.get('rushing_tds', 0)
    pts += (player_stats.get('rushing_2pt_conversions', 0) or 0) * scoring.get('rushing_2pt', 0)
    pts += (player_stats.get('receptions', 0) or 0) * scoring.get('receptions', 0)
    pts += (player_stats.get('receiving_yards', 0) or 0) * scoring.get('receiving_yards', 0)
    pts += (player_stats.get('receiving_tds', 0) or 0) * scoring.get('receiving_tds', 0)
    pts += (player_stats.get('receiving_2pt_conversions', 0) or 0) * scoring.get('receiving_2pt', 0)
    pts += (player_stats.get('fumbles_lost', 0) or 0) * scoring.get('fumbles_lost', 0)
    
    # Kicker stats (distance-based FG scoring)
    if 'fg_made' in player_stats or 'fg_0_19' in player_stats:
        # Distance-based field goals
        pts += (player_stats.get('fg_0_19', 0) or 0) * scoring.get('fg_0_19', 0)
        pts += (player_stats.get('fg_20_29', 0) or 0) * scoring.get('fg_20_29', 0)
        pts += (player_stats.get('fg_30_39', 0) or 0) * scoring.get('fg_30_39', 0)
        pts += (player_stats.get('fg_40_49', 0) or 0) * scoring.get('fg_40_49', 0)
        pts += (player_stats.get('fg_50_59', 0) or 0) * scoring.get('fg_50_59', 0)
        pts += (player_stats.get('fg_60_plus', 0) or 0) * scoring.get('fg_60_plus', 0)
        
        # Legacy flat fg_made for backward compatibility
        if 'fg_made' in player_stats and 'fg_0_19' not in player_stats:
            pts += (player_stats.get('fg_made', 0) or 0) * scoring.get('fg_30_39', 3)  # default to 3 pts
        
        pts += (player_stats.get('fg_missed', 0) or 0) * scoring.get('fg_missed', 0)
        pts += (player_stats.get('pat_made', 0) or 0) * scoring.get('pat_made', 0)
        pts += (player_stats.get('pat_missed', 0) or 0) * scoring.get('pat_missed', 0)
    
    # Defense stats
    if 'def_td' in player_stats:
        pts += (player_stats.get('def_td', 0) or 0) * scoring.get('def_td', 0)
        pts += (player_stats.get('kr_td', 0) or 0) * scoring.get('kr_td', 0)
        pts += (player_stats.get('st_td', 0) or 0) * scoring.get('st_td', 0)
        pts += (player_stats.get('def_int', 0) or 0) * scoring.get('def_int', 0)
        pts += (player_stats.get('def_fumble_recovery', 0) or 0) * scoring.get('def_fumble_recovery', 0)
        pts += (player_stats.get('def_fumble_forced', 0) or 0) * scoring.get('def_fumble_forced', 0)
        pts += (player_stats.get('st_fumble_recovery', 0) or 0) * scoring.get('st_fumble_recovery', 0)
        pts += (player_stats.get('st_fumble_forced', 0) or 0) * scoring.get('st_fumble_forced', 0)
        pts += (player_stats.get('def_sack', 0) or 0) * scoring.get('def_sack', 0)
        pts += (player_stats.get('def_safety', 0) or 0) * scoring.get('def_safety', 0)
        pts += (player_stats.get('def_blocked_kick', 0) or 0) * scoring.get('def_blocked_kick', 0)
        
        # Legacy def_fumble for backward compatibility
        if 'def_fumble' in player_stats and 'def_fumble_recovery' not in player_stats:
            pts += (player_stats.get('def_fumble', 0) or 0) * scoring.get('def_fumble_recovery', 2)
        
        # Points allowed scoring (tiered)
        points_allowed = player_stats.get('points_allowed', 0) or 0
        if points_allowed == 0:
            pts += scoring.get('points_allowed_0', 0)
        elif points_allowed <= 6:
            pts += scoring.get('points_allowed_1_6', 0)
        elif points_allowed <= 13:
            pts += scoring.get('points_allowed_7_13', 0)
        elif points_allowed <= 20:
            pts += scoring.get('points_allowed_14_20', 0)
        elif points_allowed <= 27:
            pts += scoring.get('points_allowed_21_27', 0)
        elif points_allowed <= 34:
            pts += scoring.get('points_allowed_28_34', 0)
        else:  # 35+
            pts += scoring.get('points_allowed_35_plus', 0)
    
    return pts
