import requests
import json
import os
from datetime import datetime
import certifi
import statistics
from html_report_generator import generate_html_report
from player_stats_generator import generate_player_stats_report
from player_detail_generator import generate_player_detail_page
from defense_stats_generator import generate_defense_stats_report

# Try to import nflreadpy for advanced stats
try:
    import nflreadpy as nfl
    NFL_DATA_AVAILABLE = True
except ImportError:
    NFL_DATA_AVAILABLE = False

# --- Configuration ---
MY_LEAGUES = ["1263579037352079360", "1264304480178950144"]
MY_USERNAME = "seanrabenaldt"
OUTPUT_DIR = "output"
DATA_DIR = os.path.join(OUTPUT_DIR, "league_data")

# Proxy configuration - will auto-detect from system
PROXIES = {
    'http': os.environ.get('HTTP_PROXY', os.environ.get('http_proxy')),
    'https': os.environ.get('HTTPS_PROXY', os.environ.get('https_proxy', os.environ.get('HTTP_PROXY', os.environ.get('http_proxy'))))
}
# Clean up None values
PROXIES = {k: v for k, v in PROXIES.items() if v}
# ---------------------

class SleeperAdvisor:
    BASE_URL = "https://api.sleeper.app/v1"
    PLAYERS_FILE = os.path.join(OUTPUT_DIR, "players_data.json")

    def __init__(self, league_id=None):
        self.league_id = league_id
        self.players = self.load_players()
        self.rosters = None
        self.users = None
        self.league_settings = None
        self.league_name = None
       
        # Create output and data directories if they don't exist
        if not os.path.exists(OUTPUT_DIR):
            os.makedirs(OUTPUT_DIR)
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)

    def _get_request(self, endpoint, timeout=30):
        """Helper to make requests with error handling."""
        try:
            response = requests.get(
                f"{self.BASE_URL}/{endpoint}",
                timeout=timeout,
                verify=certifi.where(),
                proxies=PROXIES
            )
            response.raise_for_status()
            return response
        except requests.exceptions.Timeout:
            print(f"Request timed out for {endpoint}")
            return None
        except requests.exceptions.RequestException as e:
            print(f"Request failed for {endpoint}: {e}")
            return None

    def fetch_all_players(self):
        """Fetches all NFL players from Sleeper API using streaming."""
        print("Downloading player database (this may take 30-60 seconds)...")
        try:
            response = requests.get(
                f"{self.BASE_URL}/players/nfl",
                stream=True,
                timeout=(30, 120),
                verify=certifi.where(),
                proxies=PROXIES
            )
            response.raise_for_status()
           
            # Write in chunks
            with open(self.PLAYERS_FILE, 'wb') as f:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=16384):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if downloaded % (1024 * 1024) == 0:  # Print every MB
                            print(f"Downloaded {downloaded // (1024*1024)} MB...")
           
            print("Player database downloaded successfully.")
            with open(self.PLAYERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
               
        except Exception as e:
            print(f"Could not download player database: {e}")
            print("Continuing with Player IDs only.")
            return {}

    def load_players(self):
        """Loads players from local file or fetches if not exists/outdated."""
        if os.path.exists(self.PLAYERS_FILE):
            try:
                file_time = os.path.getmtime(self.PLAYERS_FILE)
                file_size = os.path.getsize(self.PLAYERS_FILE)
               
                # Check if file is valid (not empty and not too old)
                if file_size > 1000 and (datetime.now().timestamp() - file_time) < (86400 * 7):
                    print("Loading player database from cache...")
                    with open(self.PLAYERS_FILE, 'r', encoding='utf-8') as f:
                        return json.load(f)
            except Exception as e:
                print(f"Error loading cached players: {e}")
       
        # Need to fetch
        return self.fetch_all_players()

    def fetch_league_info(self):
        if not self.league_id:
            return

        cache_file = os.path.join(DATA_DIR, f"league_{self.league_id}.json")
       
        # Try to load from cache first (cache for 1 hour)
        if os.path.exists(cache_file):
            file_time = os.path.getmtime(cache_file)
            if (datetime.now().timestamp() - file_time) < 3600:
                print(f"Loading league {self.league_id} from cache...")
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        self.league_settings = data.get('settings')
                        self.rosters = data.get('rosters')
                        self.users = data.get('users')
                        self.league_name = self.league_settings.get('name', self.league_id) if self.league_settings else self.league_id
                        return
                except:
                    pass  # Cache corrupted, fetch fresh

        print(f"Fetching data for league {self.league_id}...")
       
        # Fetch from API
        league_data = {}
       
        # League Settings
        resp = self._get_request(f"league/{self.league_id}")
        if resp:
            self.league_settings = resp.json()
            self.league_name = self.league_settings.get('name', self.league_id)
            league_data['settings'] = self.league_settings
       
        # Rosters
        resp = self._get_request(f"league/{self.league_id}/rosters")
        if resp:
            self.rosters = resp.json()
            league_data['rosters'] = self.rosters

        # Users
        resp = self._get_request(f"league/{self.league_id}/users")
        if resp:
            self.users = resp.json()
            league_data['users'] = self.users
       
        # Save to cache
        if league_data:
            try:
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(league_data, f, indent=2)
            except Exception as e:
                print(f"Warning: Could not save league cache: {e}")

    def get_player_details(self, player_id):
        # If we have player data, use it
        if self.players and player_id in self.players:
            p = self.players[player_id]
            team = p.get('team', 'FA') or 'FA'
            return {
                "name": f"{p['first_name']} {p['last_name']}",
                "position": p['position'],
                "team": team
            }
        # Fallback if no player data
        return {"name": f"PlayerID:{player_id}", "position": "UNK", "team": "UNK"}

    def get_user_id_by_name(self, username):
        if not self.users: return None
        target = username.lower().replace('@', '')
        for user in self.users:
            if user['display_name'].lower() == target:
                return user['user_id']
        return None

    def get_available_players(self, positions=None, limit=200):
        """Get available free agents (not rostered in this league)."""
        if not self.rosters or not self.players:
            return []
       
        # Get all rostered player IDs
        rostered_ids = set()
        for roster in self.rosters:
            for pid in roster.get('players', []) or []:
                if pid and pid != '0':
                    rostered_ids.add(pid)
            for pid in roster.get('taxi', []) or []:
                if pid and pid != '0':
                    rostered_ids.add(pid)
            for pid in roster.get('reserve', []) or []:
                if pid and pid != '0':
                    rostered_ids.add(pid)
       
        # Filter players who are available
        available = []
        for pid, player in self.players.items():
            # Skip if rostered
            if pid in rostered_ids:
                continue
           
            # Skip if not an active NFL player
            if not player.get('active'):
                continue
           
            # Filter by position if specified
            if positions:
                if player.get('position') not in positions:
                    continue
           
            # Only include relevant positions
            if player.get('position') not in ['QB', 'RB', 'WR', 'TE', 'K', 'DEF']:
                continue
           
            available.append({
                "player_id": pid,
                "name": f"{player['first_name']} {player['last_name']}",
                "position": player['position'],
                "team": player.get('team', 'FA') or 'FA',
                "age": player.get('age'),
                "injury_status": player.get('injury_status')
            })
       
        # Sort by position, then name
        available.sort(key=lambda x: (x['position'], x['name']))
       
        return available[:limit]

    def get_season_stats(self):
        """Fetch and analyze historical matchup data for the season."""
        if not self.league_id or not self.league_settings:
            return None
       
        current_week = self.league_settings.get('settings', {}).get('leg', 14)
       
        # Detect if this is a Chopped league
        is_chopped = self.league_settings.get('settings', {}).get('last_chopped_leg') is not None
       
        season_stats = {
            "league_id": self.league_id,
            "league_name": self.league_name,
            "current_week": current_week,
            "is_chopped_league": is_chopped,
            "rosters": {},
            "best_theoretical_lineups": []  # Track best possible lineup each week
        }
       
        print(f"Fetching matchup history through week {current_week}...")
       
        # Get waiver budget from league settings
        waiver_budget = self.league_settings.get('settings', {}).get('waiver_budget', 0)
        roster_positions = self.league_settings.get('roster_positions', [])
       
        # Initialize stats for each roster
        for roster in self.rosters:
            roster_id = roster['roster_id']
            owner_name = next((u['display_name'] for u in self.users if u['user_id'] == roster['owner_id']), "Unknown")
            eliminated_week = roster['settings'].get('eliminated')  # Week eliminated for Chopped leagues
           
            season_stats["rosters"][roster_id] = {
                "roster_id": roster_id,
                "owner_id": roster['owner_id'],
                "owner_name": owner_name,
                "eliminated_week": eliminated_week,
                "wins": roster['settings'].get('wins', 0),
                "losses": roster['settings'].get('losses', 0),
                "weeks": [],
                "total_points_scored": 0,
                "total_bench_points": 0,
                "optimal_points": 0,
                "points_left_on_bench": 0,
                "best_week": {"week": 0, "points": 0},
                "worst_week": {"week": 0, "points": 999},
                "efficiency_rate": 0,
                "weekly_trends": [],
                "waiver_budget_used": roster['settings'].get('waiver_budget_used', 0),
                "waiver_budget_total": waiver_budget,
                "points_for": 0,
                "points_against": 0,
                "all_play_wins": 0,
                "all_play_losses": 0,
                "close_calls": 0,  # Weeks where scored within 10 pts of elimination
                "avg_margin_above_last": 0,  # Average margin above last place each week
                "total_margin_above_last": 0,
                "waiver_player_points": 0,  # Points from players acquired via FAAB
                "waiver_players": set()  # Track player IDs acquired via waivers
            }
       
        # Fetch transactions to track waiver pickups
        print("Fetching transaction history...")
        for week in range(1, current_week + 1):
            resp = self._get_request(f"league/{self.league_id}/transactions/{week}", timeout=15)
            if resp:
                transactions = resp.json()
                for txn in transactions:
                    # Only count waiver claims with FAAB spent
                    if txn.get('type') == 'waiver' and txn.get('settings', {}).get('waiver_bid', 0) > 0:
                        roster_id = txn.get('roster_ids', [None])[0]
                        if roster_id in season_stats["rosters"]:
                            # Track all players added in this transaction
                            adds = txn.get('adds', {})
                            for player_id in adds.keys():
                                season_stats["rosters"][roster_id]["waiver_players"].add(player_id)
       
        # Fetch matchup data for each week
        all_weekly_scores = {}  # Track all scores per week for strength of schedule
       
        for week in range(1, current_week + 1):
            cache_file = os.path.join(DATA_DIR, f"matchups_{self.league_id}_week{week}.json")
           
            # Try cache first (1 hour for recent weeks, longer for past weeks)
            cache_age = 3600 if week >= current_week - 1 else 86400
            if os.path.exists(cache_file):
                file_time = os.path.getmtime(cache_file)
                if (datetime.now().timestamp() - file_time) < cache_age:
                    try:
                        with open(cache_file, 'r', encoding='utf-8') as f:
                            matchups = json.load(f)
                    except:
                        matchups = None
                else:
                    matchups = None
            else:
                matchups = None
           
            # Fetch if no valid cache
            if not matchups:
                resp = self._get_request(f"league/{self.league_id}/matchups/{week}", timeout=15)
                if resp:
                    matchups = resp.json()
                    # Save to cache
                    try:
                        with open(cache_file, 'w', encoding='utf-8') as f:
                            json.dump(matchups, f, indent=2)
                    except:
                        pass
                else:
                    continue  # Skip this week if fetch failed
           
            # Store all scores for this week
            all_weekly_scores[week] = {}
            matchup_pairs = {}  # Track matchup_id -> [roster_ids]
            for matchup in matchups:
                all_weekly_scores[week][matchup['roster_id']] = matchup.get('points', 0)
                mid = matchup.get('matchup_id')
                if mid:
                    if mid not in matchup_pairs:
                        matchup_pairs[mid] = []
                    matchup_pairs[mid].append(matchup['roster_id'])
           
            # Process matchup data
            for matchup in matchups:
                roster_id = matchup['roster_id']
                if roster_id not in season_stats["rosters"]:
                    continue
               
                points = matchup.get('points', 0)
               
                # Skip weeks with 0 points (eliminated teams in Chopped league)
                # This prevents counting weeks after elimination in averages
                if points == 0:
                    continue
               
                starters = matchup.get('starters', []) or []
                players_points = matchup.get('players_points', {})
               
                # Calculate bench points
                all_players = matchup.get('players', []) or []
                bench_points = sum(players_points.get(pid, 0) for pid in all_players if pid not in starters)
               
                # Calculate optimal lineup (best possible points)
                optimal_points = sum(sorted([players_points.get(pid, 0) for pid in all_players], reverse=True)[:len(starters)])
               
                # Calculate points from waiver-acquired players
                waiver_players = season_stats["rosters"][roster_id]["waiver_players"]
                waiver_points = sum(players_points.get(pid, 0) for pid in starters if pid in waiver_players)
               
                week_data = {
                    "week": week,
                    "points": points,
                    "bench_points": bench_points,
                    "optimal_points": optimal_points,
                    "efficiency": (points / optimal_points * 100) if optimal_points > 0 else 0
                }
               
                season_stats["rosters"][roster_id]["weeks"].append(week_data)
                season_stats["rosters"][roster_id]["total_points_scored"] += points
                season_stats["rosters"][roster_id]["total_bench_points"] += bench_points
                season_stats["rosters"][roster_id]["optimal_points"] += optimal_points
                season_stats["rosters"][roster_id]["points_left_on_bench"] += (optimal_points - points)
                season_stats["rosters"][roster_id]["points_for"] += points
                season_stats["rosters"][roster_id]["waiver_player_points"] += waiver_points
               
                # Find opponent and add their points to points_against
                mid = matchup.get('matchup_id')
                if mid and mid in matchup_pairs:
                    opponent_id = [r for r in matchup_pairs[mid] if r != roster_id]
                    if opponent_id and opponent_id[0] in all_weekly_scores[week]:
                        opponent_points = all_weekly_scores[week][opponent_id[0]]
                        if opponent_points > 0:  # Only count non-eliminated opponents
                            season_stats["rosters"][roster_id]["points_against"] += opponent_points
               
                # Track best/worst weeks (only non-zero weeks)
                if points > season_stats["rosters"][roster_id]["best_week"]["points"]:
                    season_stats["rosters"][roster_id]["best_week"] = {"week": week, "points": points}
                if points < season_stats["rosters"][roster_id]["worst_week"]["points"] and points > 0:
                    season_stats["rosters"][roster_id]["worst_week"] = {"week": week, "points": points}
       
        # Calculate all-play record (wins if you would have beat each other team that week)
        # For Chopped leagues, also calculate elimination-related stats
        for week, scores in all_weekly_scores.items():
            # Find lowest score this week (excluding 0s which are eliminated teams)
            active_scores = [s for s in scores.values() if s > 0]
            if active_scores:
                lowest_score = min(active_scores)
            else:
                lowest_score = 0
           
            for roster_id, score in scores.items():
                if score == 0:  # Skip eliminated teams
                    continue
                if roster_id in season_stats["rosters"]:
                    wins = sum(1 for other_score in scores.values() if other_score > 0 and score > other_score)
                    losses = sum(1 for other_score in scores.values() if other_score > 0 and score < other_score)
                    season_stats["rosters"][roster_id]["all_play_wins"] += wins
                    season_stats["rosters"][roster_id]["all_play_losses"] += losses
                   
                    # Chopped-specific: track margin above elimination
                    if is_chopped and lowest_score > 0:
                        margin = score - lowest_score
                        season_stats["rosters"][roster_id]["total_margin_above_last"] += margin
                        # Only count close calls if you weren't the one eliminated (margin > 0)
                        if margin > 0 and margin <= 10:  # Close call: within 10 points of elimination
                            season_stats["rosters"][roster_id]["close_calls"] += 1
       
        # Calculate final stats for each roster
        for roster_id, stats in season_stats["rosters"].items():
            weeks_played = len(stats["weeks"])
            if weeks_played > 0:
                stats["weeks_played"] = weeks_played
                stats["average_points"] = stats["total_points_scored"] / weeks_played
                stats["average_bench_points"] = stats["total_bench_points"] / weeks_played
                stats["efficiency_rate"] = (stats["total_points_scored"] / stats["optimal_points"] * 100) if stats["optimal_points"] > 0 else 0
               
                # FAAB efficiency: points per dollar spent (only from waiver-acquired players)
                waiver_spent = stats["waiver_budget_used"]
                if waiver_spent > 0:
                    stats["faab_efficiency"] = stats["waiver_player_points"] / waiver_spent
                else:
                    stats["faab_efficiency"] = 0
               
                stats["faab_remaining"] = stats["waiver_budget_total"] - stats["waiver_budget_used"]
               
                # Pythagorean expectation (using exponent of 2.54 for fantasy football)
                # Higher exponent reduces variance and better fits high-scoring fantasy games
                pf = stats["points_for"]
                pa = stats["points_against"]
                if pf > 0 and pa > 0:
                    pythag_exp = (pf ** 2.54) / ((pf ** 2.54) + (pa ** 2.54))
                    pythag_wins = pythag_exp * weeks_played
                    actual_wins = stats["wins"]
                    luck_factor = actual_wins - pythag_wins
                   
                    stats["pythagorean_expectation"] = round(pythag_exp, 3)
                    stats["pythagorean_wins"] = round(pythag_wins, 2)
                    stats["luck_factor"] = round(luck_factor, 2)  # Positive = lucky, negative = unlucky
                else:
                    stats["pythagorean_expectation"] = 0
                    stats["pythagorean_wins"] = 0
                    stats["luck_factor"] = 0
               
                # All-play win percentage
                total_all_play = stats["all_play_wins"] + stats["all_play_losses"]
                if total_all_play > 0:
                    stats["all_play_pct"] = round(stats["all_play_wins"] / total_all_play, 3)
                else:
                    stats["all_play_pct"] = 0
               
                # Scoring consistency (standard deviation)
                weekly_scores = [w["points"] for w in stats["weeks"]]
                if len(weekly_scores) > 1:
                    mean = sum(weekly_scores) / len(weekly_scores)
                    variance = sum((x - mean) ** 2 for x in weekly_scores) / len(weekly_scores)
                    std_dev = variance ** 0.5
                    stats["scoring_std_dev"] = round(std_dev, 2)
                    stats["consistency_score"] = round((mean / std_dev) if std_dev > 0 else 0, 2)
                else:
                    stats["scoring_std_dev"] = 0
                    stats["consistency_score"] = 0
               
                # Chopped-specific stats
                if is_chopped and weeks_played > 0:
                    # Calculate average margin only for weeks survived
                    # Don't include the elimination week (margin = 0) in the average
                    if stats["eliminated_week"] is not None:
                        # Team was eliminated - divide by (weeks_played - 1) to exclude elimination week
                        survival_weeks = max(weeks_played - 1, 1)
                        stats["avg_margin_above_last"] = round(stats["total_margin_above_last"] / survival_weeks, 2)
                    else:
                        # Team still alive - divide by all weeks played
                        stats["avg_margin_above_last"] = round(stats["total_margin_above_last"] / weeks_played, 2)
               
                # Calculate weekly trends (last 4 weeks vs first half) - only for active teams
                if weeks_played >= 8 and stats["eliminated_week"] is None:
                    recent_weeks = stats["weeks"][-4:]
                    early_weeks = stats["weeks"][:weeks_played//2]
                    recent_avg = sum(w["points"] for w in recent_weeks) / len(recent_weeks)
                    early_avg = sum(w["points"] for w in early_weeks) / len(early_weeks)
                    trend_change = ((recent_avg - early_avg) / early_avg * 100) if early_avg > 0 else 0
                   
                    stats["trend_analysis"] = {
                        "recent_avg_4wk": round(recent_avg, 2),
                        "early_season_avg": round(early_avg, 2),
                        "trend_percentage": round(trend_change, 1),
                        "trending": "up" if trend_change > 5 else ("down" if trend_change < -5 else "stable")
                    }
                elif stats["eliminated_week"] is not None:
                    stats["trend_analysis"] = {
                        "trending": "eliminated",
                        "eliminated_after_week": stats["eliminated_week"]
                    }
       
        # Convert sets to lists for JSON serialization
        for roster_id, stats in season_stats["rosters"].items():
            stats["waiver_players"] = list(stats["waiver_players"])
       
        return season_stats

    def get_trending_players(self, type='add', lookback_hours=24, limit=25):
        cache_file = os.path.join(DATA_DIR, f"trending_{type}.json")
        raw_cache_file = os.path.join(DATA_DIR, f"trending_{type}_raw.json")
       
        # Try formatted cache first (cache for 30 minutes)
        if os.path.exists(cache_file):
            file_time = os.path.getmtime(cache_file)
            if (datetime.now().timestamp() - file_time) < 1800:
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except:
                    pass
       
        # Try to load from raw cache and format it
        if os.path.exists(raw_cache_file):
            try:
                with open(raw_cache_file, 'r', encoding='utf-8') as f:
                    trending = json.load(f)
                    results = []
                    for t in trending:
                        pid = t['player_id']
                        details = self.get_player_details(pid)
                        results.append(f"{details['name']} ({details['position']}-{details['team']}) - Count: {t['count']}")
                   
                    # Save formatted version
                    with open(cache_file, 'w', encoding='utf-8') as f:
                        json.dump(results, f, indent=2)
                   
                    return results
            except Exception as e:
                print(f"Error processing cached trending data: {e}")
       
        # Try to fetch from API
        print(f"Fetching trending {type}s from API...")
        resp = self._get_request(f"players/nfl/trending/{type}?lookback_hours={lookback_hours}&limit={limit}", timeout=15)
        if resp:
            trending = resp.json()
            results = []
            for t in trending:
                pid = t['player_id']
                details = self.get_player_details(pid)
                results.append(f"{details['name']} ({details['position']}-{details['team']}) - Count: {t['count']}")
           
            # Save to cache
            try:
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(results, f, indent=2)
                with open(raw_cache_file, 'w', encoding='utf-8') as f:
                    json.dump(trending, f, indent=2)
            except:
                pass
           
            return results
       
        print(f"No trending {type} data available (network issue or no cache)")
        return []

def generate_copilot_context():
    print("Initializing Advisor...")
    advisor = SleeperAdvisor()
   
    # Build comprehensive JSON structure
    fantasy_data = {
        "generated_at": datetime.now().isoformat(),
        "username": MY_USERNAME,
        "leagues": [],
        "prompt_instructions": {
            "purpose": "Fantasy Football Analysis and Advice",
            "instructions": [
                "This data contains my fantasy football league information from Sleeper.",
                "Please analyze my rosters, provide start/sit recommendations, waiver wire advice, and trade suggestions.",
                "Consider player matchups, recent performance, injury status, and rest-of-season outlook.",
                "Use real-time data from the internet to check: current week matchups, weather conditions, injury reports, Vegas lines, expert consensus rankings.",
                "When making recommendations, explain your reasoning including matchup difficulty, target share, recent trends, and playoff implications."
            ],
            "key_questions": [
                "Who should I start this week at each position?",
                "Which trending players should I prioritize on waivers?",
                "Are there any trade opportunities based on my roster construction and league standings?",
                "What are my team's biggest weaknesses and how can I address them?",
                "Who are my best playoff assets and should I be buying or selling?"
            ]
        }
    }

    for league_id in MY_LEAGUES:
        advisor.league_id = league_id
        advisor.fetch_league_info()
       
        league_data = {
            "league_id": league_id,
            "league_name": advisor.league_name if advisor.league_name else league_id,
            "league_type": advisor.league_settings.get('settings', {}).get('type', 'redraft') if advisor.league_settings else 'redraft',
            "scoring_settings": {
                "type": advisor.league_settings.get('scoring_settings', {}).get('rec', 0.5) if advisor.league_settings else None,
                "pass_td": advisor.league_settings.get('scoring_settings', {}).get('pass_td', 4) if advisor.league_settings else None,
                "bonus_rec_te": advisor.league_settings.get('scoring_settings', {}).get('bonus_rec_te', 0) if advisor.league_settings else None
            } if advisor.league_settings else {},
            "roster_positions": advisor.league_settings.get('roster_positions', []) if advisor.league_settings else [],
            "playoff_week_start": advisor.league_settings.get('settings', {}).get('playoff_week_start') if advisor.league_settings else None,
            "total_rosters": advisor.league_settings.get('total_rosters') if advisor.league_settings else None,
            "waiver_budget": advisor.league_settings.get('settings', {}).get('waiver_budget', 0) if advisor.league_settings else 0,
            "users": [],
            "rosters": [],
            "my_roster": None,
            "my_user_info": None,
            "analysis_context": {
                "current_week": advisor.league_settings.get('settings', {}).get('leg', 1) if advisor.league_settings else None,
                "season": advisor.league_settings.get('season') if advisor.league_settings else None
            }
        }
       
        if not advisor.rosters or not advisor.users:
            league_data["error"] = "Could not fetch league data"
            fantasy_data["leagues"].append(league_data)
            continue

        # Add all users with enriched data
        for user in advisor.users:
            user_roster = next((r for r in advisor.rosters if r['owner_id'] == user['user_id']), None)
            league_data["users"].append({
                "user_id": user['user_id'],
                "display_name": user['display_name'],
                "avatar": user.get('avatar'),
                "metadata": user.get('metadata', {}),
                "record": {
                    "wins": user_roster['settings']['wins'] if user_roster else 0,
                    "losses": user_roster['settings']['losses'] if user_roster else 0,
                    "ties": user_roster['settings'].get('ties', 0) if user_roster else 0,
                    "fpts": user_roster['settings']['fpts'] if user_roster else 0,
                    "fpts_against": user_roster['settings'].get('fpts_against', 0) if user_roster else 0
                } if user_roster else None
            })

        # Add all rosters with player details
        waiver_budget = league_data.get('waiver_budget', 0)
        for roster in advisor.rosters:
            owner_name = next((u['display_name'] for u in league_data["users"] if u['user_id'] == roster['owner_id']), "Unknown")
           
            # Calculate remaining FAAB budget
            budget_used = roster['settings'].get('waiver_budget_used', 0)
            budget_remaining = waiver_budget - budget_used
           
            roster_data = {
                "roster_id": roster['roster_id'],
                "owner_id": roster['owner_id'],
                "owner_name": owner_name,
                "settings": roster['settings'],
                "waiver_budget_remaining": budget_remaining,
                "starters": [],
                "bench": [],
                "taxi": [],
                "reserve": []
            }
           
            # Get starter details
            for pid in roster.get('starters', []) or []:
                if pid and pid != '0':
                    player_details = advisor.get_player_details(pid)
                    roster_data["starters"].append({
                        "player_id": pid,
                        **player_details
                    })
           
            # Get bench details
            all_players = roster.get('players', []) or []
            all_starters = roster.get('starters', []) or []
            bench_ids = [pid for pid in all_players if pid not in all_starters]
            for pid in bench_ids:
                if pid and pid != '0':
                    player_details = advisor.get_player_details(pid)
                    roster_data["bench"].append({
                        "player_id": pid,
                        **player_details
                    })
           
            # Taxi squad
            for pid in roster.get('taxi', []) or []:
                if pid and pid != '0':
                    player_details = advisor.get_player_details(pid)
                    roster_data["taxi"].append({
                        "player_id": pid,
                        **player_details
                    })
           
            # Reserve/IR
            for pid in roster.get('reserve', []) or []:
                if pid and pid != '0':
                    player_details = advisor.get_player_details(pid)
                    roster_data["reserve"].append({
                        "player_id": pid,
                        **player_details
                    })
           
            league_data["rosters"].append(roster_data)
       
        # Find my roster
        user_id = advisor.get_user_id_by_name(MY_USERNAME)
        if user_id:
            my_user = next((u for u in league_data["users"] if u['user_id'] == user_id), None)
            my_roster = next((r for r in league_data["rosters"] if r['owner_id'] == user_id), None)
           
            league_data["my_user_info"] = my_user
            league_data["my_roster"] = my_roster
       
        # Get available free agents
        print(f"Finding available free agents for {advisor.league_name}...")
        league_data["available_players"] = {
            "QB": advisor.get_available_players(['QB'], limit=30),
            "RB": advisor.get_available_players(['RB'], limit=50),
            "WR": advisor.get_available_players(['WR'], limit=50),
            "TE": advisor.get_available_players(['TE'], limit=30),
            "K": advisor.get_available_players(['K'], limit=20),
            "DEF": advisor.get_available_players(['DEF'], limit=20)
        }

        fantasy_data["leagues"].append(league_data)

    # Add trending players with more context
    fantasy_data["trending"] = {
        "last_updated": datetime.now().isoformat(),
        "timeframe_hours": 24,
        "adds": [],
        "drops": [],
        "analysis_notes": [
            "These are the most added/dropped players across ALL Sleeper leagues in the last 24 hours.",
            "High add counts may indicate injury news, breakout performances, or favorable upcoming matchups.",
            "Use internet search to find WHY these players are trending (injury replacements, coaching changes, etc.)"
        ]
    }
   
    print("Fetching trending adds...")
    adds = advisor.get_trending_players('add')
    for add_str in adds:
        parts = add_str.split(' - Count: ')
        if len(parts) == 2:
            player_info = parts[0]
            count = parts[1]
            fantasy_data["trending"]["adds"].append({
                "player_info": player_info,
                "count": int(count)
            })
   
    print("Fetching trending drops...")
    drops = advisor.get_trending_players('drop')
    for drop_str in drops:
        parts = drop_str.split(' - Count: ')
        if len(parts) == 2:
            player_info = parts[0]
            count = parts[1]
            fantasy_data["trending"]["drops"].append({
                "player_info": player_info,
                "count": int(count)
            })

    # Write comprehensive JSON
    output_file = os.path.join(OUTPUT_DIR, "fantasy_context.json")
    with open(output_file, "w", encoding='utf-8') as f:
        json.dump(fantasy_data, f, indent=2, ensure_ascii=False)
   
    # Also create a simplified prompt file for LLMs
    prompt_file = os.path.join(OUTPUT_DIR, "fantasy_prompt.txt")
    with open(prompt_file, "w", encoding='utf-8') as f:
        f.write("# Fantasy Football Analysis Request\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Username: {MY_USERNAME}\n\n")
       
        f.write("## Instructions\n")
        f.write("I need fantasy football advice based on my league data. Please:\n")
        f.write("1. Search the internet for current NFL news, injury reports, and week matchups\n")
        f.write("2. Analyze my roster strengths and weaknesses\n")
        f.write("3. Provide start/sit recommendations for this week\n")
        f.write("4. Suggest waiver wire pickups from the trending players\n")
        f.write("5. Identify potential trade targets based on my needs and league standings\n\n")
       
        for idx, league in enumerate(fantasy_data["leagues"], 1):
            f.write(f"## League {idx}: {league['league_name']}\n")
            f.write(f"Type: {league.get('league_type', 'Unknown')}\n")
            f.write(f"Scoring: {league.get('scoring_settings', {}).get('type', 'Unknown')} PPR\n")
            if league.get('my_user_info'):
                record = league['my_user_info']['record']
                f.write(f"My Record: {record['wins']}-{record['losses']} ({record['fpts']} points)\n")
            f.write(f"\nRoster Positions: {', '.join(league.get('roster_positions', []))}\n\n")
           
            if league.get('my_roster'):
                f.write("### My Current Lineup\n")
                f.write("Starters:\n")
                for p in league['my_roster']['starters']:
                    f.write(f"  - {p['name']} ({p['position']}, {p['team']})\n")
                f.write("\nBench:\n")
                for p in league['my_roster']['bench']:
                    f.write(f"  - {p['name']} ({p['position']}, {p['team']})\n")
                f.write("\n")
           
            # Add top available players
            if league.get('available_players'):
                f.write("### Top Available Free Agents\n")
                for pos in ['QB', 'RB', 'WR', 'TE']:
                    players = league['available_players'].get(pos, [])
                    if players:
                        f.write(f"\n{pos}s:\n")
                        for p in players[:10]:  # Top 10 per position
                            injury = f" [{p['injury_status']}]" if p.get('injury_status') else ""
                            f.write(f"  - {p['name']} ({p['team']}){injury}\n")
                f.write("\n")
       
        f.write("## Trending Players (Last 24h)\n")
        f.write("Top Adds:\n")
        for add in fantasy_data["trending"]["adds"][:10]:
            f.write(f"  - {add['player_info']} (Added by {add['count']} teams)\n")
        f.write("\nTop Drops:\n")
        for drop in fantasy_data["trending"]["drops"][:10]:
            f.write(f"  - {drop['player_info']} (Dropped by {drop['count']} teams)\n")
       
        f.write("\n## Questions to Answer\n")
        f.write("1. Who should I start at each position this week?\n")
        f.write("2. Which trending players should I target on waivers?\n")
        f.write("3. What trades should I pursue?\n")
        f.write("4. What are my biggest roster concerns?\n")
        f.write("5. Playoff outlook and strategy?\n\n")
        f.write("See attached fantasy_context.json for complete league data.\n")
   
    print(f"\nSuccessfully generated:")
    print(f"  - '{output_file}' (complete data)")
    print(f"  - '{prompt_file}' (LLM-optimized prompt)")
    print("\nUpload both files to ChatGPT, Claude, or another LLM for internet-connected analysis.")

def generate_season_stats():
    """Generate comprehensive season statistics and efficiency analysis."""
    print("Generating Season Statistics Report...")
   
    # Store league data to cross-reference
    all_league_data = {}
   
    # First pass: collect all league data
    for league_id in MY_LEAGUES:
        print(f"\nAnalyzing league {league_id}...")
        advisor = SleeperAdvisor(league_id)  # Create separate instance for each league
        advisor.fetch_league_info()
       
        if not advisor.rosters or not advisor.users:
            print(f"  Could not fetch league data, skipping...")
            continue
       
        # Get season stats
        season_stats = advisor.get_season_stats()
        if not season_stats:
            print(f"  Could not fetch season stats, skipping...")
            continue
       
        all_league_data[league_id] = {
            "advisor": advisor,
            "season_stats": season_stats,
            "is_chopped": season_stats.get("is_chopped_league", False),
            "roster_positions": advisor.league_settings.get('roster_positions', [])
        }
   
    # Second pass: generate reports (now we can cross-reference leagues)
    for league_id, data in all_league_data.items():
        season_stats = data["season_stats"]
        is_chopped = data["is_chopped"]
        advisor = data["advisor"]
       
        # If this is a Chopped league, find the Dynasty league for player pool
        dynasty_matchups = None
        if is_chopped:
            for other_id, other_data in all_league_data.items():
                if not other_data["is_chopped"]:
                    # Found Dynasty league - get its matchup data
                    dynasty_matchups = {}
                    print(f"  Using Dynasty league {other_id} as player pool source...")
                    for week in range(1, season_stats["current_week"] + 1):
                        cache_file = os.path.join(DATA_DIR, f"matchups_{other_id}_week{week}.json")
                       
                        # Try cache first
                        if os.path.exists(cache_file):
                            try:
                                with open(cache_file, 'r', encoding='utf-8') as f:
                                    matchups = json.load(f)
                                    dynasty_matchups[week] = matchups
                            except:
                                pass
                    break
       
        # Calculate detailed best theoretical lineups for Chopped using Dynasty player pool
        if is_chopped and dynasty_matchups:
            season_stats["best_theoretical_lineups"] = []
            roster_positions = data["roster_positions"]
           
            for week in range(1, season_stats["current_week"] + 1):
                matchups = dynasty_matchups.get(week, [])
                if not matchups:
                    continue
               
                all_player_scores = {}
                for matchup in matchups:
                    if matchup.get('points', 0) > 0:
                        players_points = matchup.get('players_points', {})
                        for player_id, pts in players_points.items():
                            if player_id and pts > 0:
                                all_player_scores[player_id] = pts
               
                # Calculate best possible lineup
                if all_player_scores and roster_positions:
                    position_players = {}
                   
                    # Group players by position
                    for player_id, pts in all_player_scores.items():
                        player_info = advisor.players.get(player_id, {})
                        position = player_info.get('position', 'UNKNOWN')
                        if position not in position_players:
                            position_players[position] = []
                        position_players[position].append({
                            'player_id': player_id,
                            'name': f"{player_info.get('first_name', '')} {player_info.get('last_name', 'Unknown')}".strip(),
                            'position': position,
                            'team': player_info.get('team', 'FA'),
                            'points': pts
                        })
                   
                    # Sort each position by points descending
                    for pos in position_players:
                        position_players[pos].sort(key=lambda x: x['points'], reverse=True)
                   
                    # Fill roster positions with best available players
                    best_lineup = []
                    used_players = set()
                   
                    for roster_slot in roster_positions:
                        if roster_slot == 'BN':
                            continue
                       
                        eligible_positions = []
                        if roster_slot == 'FLEX':
                            eligible_positions = ['RB', 'WR', 'TE']
                        elif roster_slot == 'SUPER_FLEX':
                            eligible_positions = ['QB', 'RB', 'WR', 'TE']
                        elif roster_slot == 'REC_FLEX':
                            eligible_positions = ['WR', 'TE']
                        else:
                            eligible_positions = [roster_slot]
                       
                        best_player = None
                        for pos in eligible_positions:
                            if pos in position_players:
                                for player in position_players[pos]:
                                    if player['player_id'] not in used_players:
                                        if best_player is None or player['points'] > best_player['points']:
                                            best_player = player
                       
                        if best_player:
                            used_players.add(best_player['player_id'])
                            best_lineup.append({
                                'slot': roster_slot,
                                'player': best_player['name'],
                                'team': best_player['team'],
                                'position': best_player['position'],
                                'points': best_player['points']
                            })
                   
                    total_points = sum(p['points'] for p in best_lineup)
                    season_stats["best_theoretical_lineups"].append({
                        "week": week,
                        "points": round(total_points, 1),
                        "lineup": best_lineup
                    })
           
            # Calculate average
            if season_stats["best_theoretical_lineups"]:
                avg_best_theoretical = sum(w["points"] for w in season_stats["best_theoretical_lineups"]) / len(season_stats["best_theoretical_lineups"])
                season_stats["avg_best_theoretical_lineup"] = round(avg_best_theoretical, 1)
       
        league_data = {
            "league_id": league_id,
            "league_name": advisor.league_name,
            "current_week": season_stats["current_week"],
            "is_chopped_league": is_chopped,
            "season": advisor.league_settings.get('season', '2025'),
            "avg_best_theoretical_lineup": season_stats.get("avg_best_theoretical_lineup", 0),
            "best_theoretical_lineups": season_stats.get("best_theoretical_lineups", []),
            "season_stats": []
        }
       
        # Convert to list and sort by efficiency
        for roster_id, stats in season_stats["rosters"].items():
            league_data["season_stats"].append(stats)
       
        league_data["season_stats"].sort(key=lambda x: x.get("efficiency_rate", 0), reverse=True)
       
        # Generate HTML report for this league
        generate_html_report(league_data, OUTPUT_DIR)
   
    print(f"\n{'='*80}")
    print(f"Season stats reports successfully generated!")
    print(f"Check the HTML files for interactive charts and detailed analysis.")
    print(f"{'='*80}\n")

def generate_player_stats():
    """Generate advanced player statistics report based on Dynasty league."""
    print("Generating Player Statistics Report...")
   
    # Load both leagues to track ownership
    dynasty_advisor = None
    chopped_advisor = None
    dynasty_league_id = None
    chopped_league_id = None
    
    for league_id in MY_LEAGUES:
        advisor = SleeperAdvisor(league_id)
        advisor.fetch_league_info()
       
        if not advisor.rosters or not advisor.users:
            continue
       
        # Check if this is chopped or dynasty
        season_stats = advisor.get_season_stats()
        if season_stats and season_stats.get("is_chopped_league", False):
            chopped_advisor = advisor
            chopped_league_id = league_id
        else:
            dynasty_advisor = advisor
            dynasty_league_id = league_id
    
    if not dynasty_advisor:
        print("  Could not find Dynasty league, skipping...")
        return
   
    print(f"\nUsing Dynasty league {dynasty_league_id} for player stats...")
    if chopped_advisor:
        print(f"Also tracking Chopped league {chopped_league_id} ownership...")
    advisor = dynasty_advisor
   
    if not advisor.rosters or not advisor.users:
        print(f"  Could not fetch league data, skipping...")
        return
   
    # Load NFL weekly stats and snap counts if available
    nfl_stats = {}
    snap_counts = {}
    player_ids = {}
    if NFL_DATA_AVAILABLE:
        try:
            print("Loading NFL weekly player stats, snap counts, and rosters...")
            # Get current season from nflreadpy
            nfl_season = nfl.get_current_season()
            print(f"  Detected current NFL season: {nfl_season}")
            
            season = int(advisor.league_settings.get('season', str(nfl_season)))
            
            # Load weekly stats using nflreadpy
            weekly_stats = nfl.load_player_stats(season)
            print(f"  Loaded weekly data for {season} season ({len(weekly_stats)} records)")
            
            # Load snap counts
            try:
                snap_data = nfl.load_snap_counts(season)
                print(f"  Loaded snap count data for {len(snap_data)} records")
            except Exception as e:
                print(f"  Note: Snap counts not available: {e}")
                snap_data = None
            
            # Load seasonal rosters for player info (age, team, etc.)
            try:
                rosters = nfl.load_rosters(season)
                print(f"  Loaded roster data for {len(rosters)} players")
            except Exception as e:
                print(f"  Note: Roster data not available: {e}")
                rosters = None
           
            # Create a lookup dictionary: (player_name, week) -> stats
            # nflreadpy returns polars DataFrames, convert to pandas-like access
            for row in weekly_stats.iter_rows(named=True):
                player_name = row.get('player_display_name', '')
                player_id = row.get('player_id', '')
                week = row.get('week')
                if player_name and week:
                    key = (player_name, week)
                    nfl_stats[key] = {
                        'targets': row.get('targets', 0),
                        'receptions': row.get('receptions', 0),
                        'rushing_attempts': row.get('carries', 0),
                        'rushing_yards': row.get('rushing_yards', 0),
                        'receiving_yards': row.get('receiving_yards', 0),
                        'passing_yards': row.get('passing_yards', 0),
                        'passing_tds': row.get('passing_tds', 0),
                        'rushing_tds': row.get('rushing_tds', 0),
                        'receiving_tds': row.get('receiving_tds', 0),
                        'passing_2pt_conversions': row.get('passing_2pt_conversions', 0),
                        'rushing_2pt_conversions': row.get('rushing_2pt_conversions', 0),
                        'receiving_2pt_conversions': row.get('receiving_2pt_conversions', 0),
                        'interceptions': row.get('interceptions', 0),
                        'fumbles_lost': row.get('fumbles_lost', 0),
                        'team': row.get('team', ''),
                        'position': row.get('position', ''),
                        'opponent_team': row.get('opponent_team', ''),
                        'completions': row.get('completions', 0),
                        'attempts': row.get('attempts', 0)
                    }
                    if player_id:
                        player_ids[player_name] = player_id
            
            # Process snap counts data
            if snap_data is not None:
                for row in snap_data.iter_rows(named=True):
                    player_name = row.get('player', '') or row.get('player_name', '')
                    week = row.get('week')
                    if player_name and week:
                        key = (player_name, week)
                        snap_counts[key] = {
                            'offense_snaps': row.get('offense_snaps', 0),
                            'offense_pct': row.get('offense_pct', 0),
                            'defense_snaps': row.get('defense_snaps', 0),
                            'defense_pct': row.get('defense_pct', 0),
                            'st_snaps': row.get('st_snaps', 0),
                            'st_pct': row.get('st_pct', 0)
                        }
            
            # Process roster data for player ages and additional info
            if rosters is not None:
                from datetime import datetime
                current_year = datetime.now().year
                
                for row in rosters.iter_rows(named=True):
                    player_name = row.get('full_name', '')
                    if not player_name:
                        continue
                    
                    # Calculate age from birth_date
                    birth_date = row.get('birth_date')
                    age = None
                    if birth_date:
                        try:
                            if isinstance(birth_date, str):
                                birth_year = int(birth_date.split('-')[0])
                            else:
                                birth_year = birth_date.year
                            age = current_year - birth_year
                        except:
                            pass
                    
                    # Store player biographical info (use week 0 as bio data)
                    if (player_name, 0) not in nfl_stats:
                        nfl_stats[(player_name, 0)] = {}
                    
                    nfl_stats[(player_name, 0)]['age'] = age
                    nfl_stats[(player_name, 0)]['draft_number'] = row.get('draft_number')
                    nfl_stats[(player_name, 0)]['years_exp'] = row.get('years_exp')
                    nfl_stats[(player_name, 0)]['height'] = row.get('height')
                    nfl_stats[(player_name, 0)]['weight'] = row.get('weight')
                    nfl_stats[(player_name, 0)]['college'] = row.get('college')
            
            print(f"  Loaded stats for {len(set(k[0] for k in nfl_stats.keys() if k[1] > 0))} players")
            if snap_counts:
                print(f"  Loaded snap counts for {len(set(k[0] for k in snap_counts.keys()))} players")
        except Exception as e:
            print(f"  Warning: Could not load NFL stats: {e}")
            import traceback
            traceback.print_exc()
            nfl_stats = {}
            snap_counts = {}
   
    # Collect all player stats from nflverse weekly data and calculate PPR fantasy points
    player_performances = {}
    current_week = advisor.league_settings.get('leg', advisor.league_settings.get('settings', {}).get('leg', 18))
    
    # Process nflverse weekly data to calculate fantasy points
    print("Calculating fantasy points from NFL stats using standard PPR scoring...")
    
    # Standard PPR scoring based on screenshot
    PPR_SCORING = {
        'passing_yards': 0.04,  # 1 point per 25 yards
        'passing_tds': 4,
        'passing_2pt': 2,
        'interceptions': -1,
        'rushing_yards': 0.1,  # 1 point per 10 yards
        'rushing_tds': 6,
        'rushing_2pt': 2,
        'receptions': 1,  # PPR
        'receiving_yards': 0.1,  # 1 point per 10 yards
        'receiving_tds': 6,
        'receiving_2pt': 2,
        'fumbles_lost': -2
    }
    
    # Calculate fantasy points from nflverse data for ALL players who played (not just rostered)
    # Build a set of all unique player names from the nflverse data
    # Only include rosterable positions: QB, RB, WR, TE
    ROSTERABLE_POSITIONS = {'QB', 'RB', 'WR', 'TE'}
    all_nfl_players = {}  # name -> {position, team, player_id}
    for (player_name, week), stats in nfl_stats.items():
        if week > 0 and player_name:  # week > 0 means actual game data, not bio data
            position = stats.get('position', 'UNKNOWN')
            # Filter out invalid players and non-rosterable positions
            if (position in ROSTERABLE_POSITIONS and 
                player_name not in all_nfl_players and
                not player_name.isdigit() and  # Exclude numeric IDs
                len(player_name) > 2):  # Exclude very short names
                all_nfl_players[player_name] = {
                    'position': position,
                    'team': stats.get('team', 'FA'),
                    'player_id': player_ids.get(player_name)
                }
    
    print(f"  Found {len(all_nfl_players)} unique NFL players with game stats (rosterable positions only)")
    
    # Calculate fantasy points for all NFL players
    for week in range(1, current_week + 1):
        for player_name in all_nfl_players.keys():
                
            key = (player_name, week)
            if key in nfl_stats:
                stats = nfl_stats[key]
                
                # Calculate fantasy points using standard PPR scoring (screenshot values)
                pts = 0
                pts += (stats.get('passing_yards', 0) or 0) * PPR_SCORING['passing_yards']
                pts += (stats.get('passing_tds', 0) or 0) * PPR_SCORING['passing_tds']
                pts += (stats.get('passing_2pt_conversions', 0) or 0) * PPR_SCORING['passing_2pt']
                pts += (stats.get('interceptions', 0) or 0) * PPR_SCORING['interceptions']
                pts += (stats.get('rushing_yards', 0) or 0) * PPR_SCORING['rushing_yards']
                pts += (stats.get('rushing_tds', 0) or 0) * PPR_SCORING['rushing_tds']
                pts += (stats.get('rushing_2pt_conversions', 0) or 0) * PPR_SCORING['rushing_2pt']
                pts += (stats.get('receptions', 0) or 0) * PPR_SCORING['receptions']
                pts += (stats.get('receiving_yards', 0) or 0) * PPR_SCORING['receiving_yards']
                pts += (stats.get('receiving_tds', 0) or 0) * PPR_SCORING['receiving_tds']
                pts += (stats.get('receiving_2pt_conversions', 0) or 0) * PPR_SCORING['receiving_2pt']
                pts += (stats.get('fumbles_lost', 0) or 0) * PPR_SCORING['fumbles_lost']
                
                if pts > 0:
                    if player_name not in player_performances:
                        player_performances[player_name] = {}  # Use dict to track week->points
                    player_performances[player_name][week] = pts
    
    print(f"  Calculated fantasy points for {len(player_performances)} players from NFL stats")
    
    # Calculate advanced stats for each player (first pass - collect all data)
    dynasty_ownership = {}  # player_name -> owner_name
    chopped_ownership = {}  # player_name -> owner_name
    
    # Map Dynasty league ownership
    if advisor.rosters:
        for roster in advisor.rosters:
            if not roster or not isinstance(roster, dict):
                continue
            owner_id = roster.get('owner_id')
            owner_name = "Unknown"
            if advisor.users:
                for user in advisor.users:
                    if user and user.get('user_id') == owner_id:
                        owner_name = user.get('display_name', user.get('username', 'Unknown'))
                        break
            
            players_list = roster.get('players')
            if not players_list:
                continue
            for player_id in players_list:
                if player_id in advisor.players:
                    player_info = advisor.players[player_id]
                    player_name = f"{player_info.get('first_name', '')} {player_info.get('last_name', '')}".strip()
                    if player_name:
                        dynasty_ownership[player_name] = owner_name
    
    # Map Chopped league ownership if available
    if chopped_advisor and chopped_advisor.rosters:
        for roster in chopped_advisor.rosters:
            if not roster or not isinstance(roster, dict):
                continue
            owner_id = roster.get('owner_id')
            owner_name = "Unknown"
            if chopped_advisor.users:
                for user in chopped_advisor.users:
                    if user and user.get('user_id') == owner_id:
                        owner_name = user.get('display_name', user.get('username', 'Unknown'))
                        break
            
            players_list = roster.get('players')
            if not players_list:
                continue
            for player_id in players_list:
                if player_id in chopped_advisor.players:
                    player_info = chopped_advisor.players[player_id]
                    player_name = f"{player_info.get('first_name', '')} {player_info.get('last_name', '')}".strip()
                    if player_name:
                        chopped_ownership[player_name] = owner_name
    
    # Calculate advanced stats for each player (first pass - collect all data)
    all_player_data = []
    position_averages = {}
    seen_players = {}  # Track players by name to avoid duplicates
   
    for player_name, weekly_scores in player_performances.items():
        # Convert dict to list of scores for calculations
        scores = list(weekly_scores.values())
        if len(scores) < 1:
            continue
       
        # Get player info from NFL data
        player_nfl_info = all_nfl_players.get(player_name, {})
        position = player_nfl_info.get('position', 'UNKNOWN')
        team = player_nfl_info.get('team', 'FA')
        
        # Skip duplicates - keep the player with more fantasy points
        if player_name in seen_players:
            existing_total = seen_players[player_name]['total_points']
            current_total = sum(scores)
            if current_total <= existing_total:
                continue  # Skip this duplicate, we have a better version
            else:
                # Remove the old version and replace with this one
                all_player_data = [p for p in all_player_data if p['name'] != player_name]
        
        seen_players[player_name] = {'total_points': sum(scores)}
       
        total_points = sum(scores)
        avg_ppg = total_points / len(scores)
        std_dev = statistics.stdev(scores) if len(scores) > 1 else 0
        consistency = avg_ppg / std_dev if std_dev > 0 else 0
        best_game = max(scores)
        worst_game = min(scores)
        median = statistics.median(scores)
        above_avg_count = sum(1 for s in scores if s > avg_ppg)
        pct_above_avg = (above_avg_count / len(scores)) * 100
       
        # Calculate trend (last 4 weeks vs earlier weeks)
        trend_pct = 0
        if len(scores) >= 8:
            num_recent = min(4, len(scores) // 2)
            recent_avg = statistics.mean(scores[-num_recent:])
            early_avg = statistics.mean(scores[:-num_recent])
            if early_avg > 0:
                trend_pct = ((recent_avg - early_avg) / early_avg) * 100
        
        # Get NFL advanced stats for this player
        player_nfl_stats = {}
        total_targets = 0
        total_receptions = 0
        total_rushes = 0
        total_rushing_yds = 0
        total_receiving_yds = 0
        total_snaps = 0
        snap_weeks = 0
        active_weeks = 0  # Count weeks where player was actually active
        team_targets_by_week = {}
        team_rushes_by_week = {}
        
        # Aggregate stats across all weeks (only for THIS season)
        for week in range(1, current_week + 1):
            key = (player_name, week)
            if key in nfl_stats:
                stats = nfl_stats[key]
                targets = stats.get('targets', 0) or 0
                receptions = stats.get('receptions', 0) or 0
                rushes = stats.get('rushing_attempts', 0) or 0
                rush_yds = stats.get('rushing_yards', 0) or 0
                rec_yds = stats.get('receiving_yards', 0) or 0
                
                # Only count weeks where player had any activity
                if targets > 0 or receptions > 0 or rushes > 0 or rush_yds > 0 or rec_yds > 0:
                    active_weeks += 1
                    total_targets += targets
                    total_receptions += receptions
                    total_rushes += rushes
                    total_rushing_yds += rush_yds
                    total_receiving_yds += rec_yds
                
                # Track team totals for share calculations
                if stats.get('team'):
                    week_team = stats['team']
                    if week_team not in team_targets_by_week:
                        team_targets_by_week[week_team] = []
                        team_rushes_by_week[week_team] = []
            
            if key in snap_counts:
                snaps = snap_counts[key]
                offense_snaps = snaps.get('offense_snaps', 0) or 0
                offense_pct = snaps.get('offense_pct', 0) or 0
                if offense_snaps > 0 and offense_pct > 0:
                    # offense_pct is a decimal (0.84 = 84%), so multiply by 100
                    total_snaps += (offense_pct * 100)
                    snap_weeks += 1
        
        # Get biographical info (age, etc.) if available
        bio_key = (player_name, 0)
        if bio_key in nfl_stats:
            bio = nfl_stats[bio_key]
            player_nfl_stats['age'] = bio.get('age')
            player_nfl_stats['years_exp'] = bio.get('years_exp')
            player_nfl_stats['draft_round'] = bio.get('draft_round')
            player_nfl_stats['college'] = bio.get('college')
        
        # Calculate averages based on active weeks only (not including inactive weeks)
        if active_weeks > 0:
            player_nfl_stats['avg_targets'] = round(total_targets / active_weeks, 1)
            player_nfl_stats['avg_receptions'] = round(total_receptions / active_weeks, 1)
            player_nfl_stats['avg_rushes'] = round(total_rushes / active_weeks, 1)
            player_nfl_stats['avg_rushing_yds'] = round(total_rushing_yds / active_weeks, 1)
            player_nfl_stats['avg_receiving_yds'] = round(total_receiving_yds / active_weeks, 1)
            player_nfl_stats['avg_snap_pct'] = round(total_snaps / snap_weeks, 1) if snap_weeks > 0 else 0
            player_nfl_stats['total_targets'] = total_targets
            player_nfl_stats['total_receptions'] = total_receptions
            player_nfl_stats['total_rushes'] = total_rushes
            player_nfl_stats['total_rushing_yds'] = total_rushing_yds
            player_nfl_stats['total_receiving_yds'] = total_receiving_yds
            player_nfl_stats['active_weeks'] = active_weeks
        else:
            # Set defaults if no active weeks
            player_nfl_stats['avg_targets'] = 0
            player_nfl_stats['avg_receptions'] = 0
            player_nfl_stats['avg_rushes'] = 0
            player_nfl_stats['avg_rushing_yds'] = 0
            player_nfl_stats['avg_receiving_yds'] = 0
            player_nfl_stats['avg_snap_pct'] = 0
            player_nfl_stats['active_weeks'] = 0
       
        # Track position averages for later calculation
        if position not in position_averages:
            position_averages[position] = []
        position_averages[position].append(avg_ppg)
       
        all_player_data.append({
            'name': player_name,
            'position': position,
            'team': team,
            'games': len(scores),
            'total_points': total_points,
            'avg_ppg': avg_ppg,
            'std_dev': std_dev,
            'consistency': consistency,
            'best_game': best_game,
            'worst_game': worst_game,
            'median': median,
            'pct_above_avg': pct_above_avg,
            'trend_pct': trend_pct,
            'nfl_stats': player_nfl_stats,
            'dynasty_owner': dynasty_ownership.get(player_name, 'Free Agent'),
            'chopped_owner': chopped_ownership.get(player_name, 'Free Agent'),
            'weekly_scores': weekly_scores  # Store weekly scores dict (week->points) for detail pages
        })
   
    # Calculate position averages and add vs_position_avg metric
    pos_avg_values = {}
    for pos, avg_list in position_averages.items():
        pos_avg_values[pos] = statistics.mean(avg_list) if avg_list else 0
   
    # Add vs_position_avg to each player
    for player in all_player_data:
        pos_avg = pos_avg_values.get(player['position'], 0)
        player['vs_position_avg'] = player['avg_ppg'] - pos_avg if pos_avg > 0 else 0
        player['position_avg'] = pos_avg
   
    # Generate single report for Dynasty league
    league_data = {
        "league_id": dynasty_league_id,
        "league_name": advisor.league_name,
        "current_week": current_week,
        "season": advisor.league_settings.get('season', '2025')
    }
   
    generate_player_stats_report(league_data, all_player_data, OUTPUT_DIR)
    
    # Generate individual player detail pages
    print("\nGenerating individual player detail pages...")
    detail_pages_created = 0
    for player in all_player_data:
        try:
            generate_player_detail_page(
                player['name'],
                player,
                player.get('weekly_scores', []),
                OUTPUT_DIR
            )
            detail_pages_created += 1
        except Exception as e:
            print(f"  Error generating page for {player['name']}: {e}")
    
    print(f"  Created {detail_pages_created} player detail pages")
   
    print(f"\n{'='*80}")
    print(f"Player stats reports successfully generated!")
    print(f"Check the HTML files for detailed player analysis.")
    print(f"{'='*80}\n")

def generate_defense_stats():
    """Generate defensive statistics report."""
    print("Generating Defense Statistics Report...")
    
    if not NFL_DATA_AVAILABLE:
        print("  NFL data (nflreadpy) not available, cannot generate defense stats.")
        return
    
    try:
        print("Loading NFL weekly player stats...")
        nfl_season = nfl.get_current_season()
        print(f"  Detected current NFL season: {nfl_season}")
        
        season = nfl_season
        weekly_stats = nfl.load_player_stats(season)
        print(f"  Loaded weekly data for {season} season ({len(weekly_stats)} records)")
        
        # Track defensive stats by team and position
        defense_stats = {}
        
        # Standard PPR scoring
        PPR_SCORING = {
            'passing_yards': 0.04,
            'passing_tds': 4,
            'passing_2pt': 2,
            'interceptions': -1,
            'rushing_yards': 0.1,
            'rushing_tds': 6,
            'rushing_2pt': 2,
            'receptions': 1,
            'receiving_yards': 0.1,
            'receiving_tds': 6,
            'receiving_2pt': 2,
            'fumbles_lost': -2
        }
        
        ROSTERABLE_POSITIONS = {'QB', 'RB', 'WR', 'TE'}
        
        print("Calculating defensive statistics...")
        
        # Process weekly stats
        for row in weekly_stats.iter_rows(named=True):
            opponent = row.get('opponent_team')
            if not opponent:
                continue
            
            position = row.get('position', '')
            if position not in ROSTERABLE_POSITIONS:
                continue
            
            # Initialize defense stats if needed
            if opponent not in defense_stats:
                defense_stats[opponent] = {
                    'team': opponent,
                    'games': 0,
                    'total_points_allowed': 0,
                    'qb_points_allowed': 0,
                    'rb_points_allowed': 0,
                    'wr_points_allowed': 0,
                    'te_points_allowed': 0,
                    'rushing_yards_allowed': 0,
                    'rushing_tds_allowed': 0,
                    'receiving_yards_allowed': 0,
                    'receiving_tds_allowed': 0,
                    'passing_tds_allowed': 0,
                    'weeks_played': set()
                }
            
            week = row.get('week')
            if week:
                defense_stats[opponent]['weeks_played'].add(week)
            
            # Calculate fantasy points
            pts = 0
            pts += (row.get('passing_yards', 0) or 0) * PPR_SCORING['passing_yards']
            pts += (row.get('passing_tds', 0) or 0) * PPR_SCORING['passing_tds']
            pts += (row.get('passing_2pt_conversions', 0) or 0) * PPR_SCORING['passing_2pt']
            pts += (row.get('interceptions', 0) or 0) * PPR_SCORING['interceptions']
            pts += (row.get('rushing_yards', 0) or 0) * PPR_SCORING['rushing_yards']
            pts += (row.get('rushing_tds', 0) or 0) * PPR_SCORING['rushing_tds']
            pts += (row.get('rushing_2pt_conversions', 0) or 0) * PPR_SCORING['rushing_2pt']
            pts += (row.get('receptions', 0) or 0) * PPR_SCORING['receptions']
            pts += (row.get('receiving_yards', 0) or 0) * PPR_SCORING['receiving_yards']
            pts += (row.get('receiving_tds', 0) or 0) * PPR_SCORING['receiving_tds']
            pts += (row.get('receiving_2pt_conversions', 0) or 0) * PPR_SCORING['receiving_2pt']
            pts += (row.get('fumbles_lost', 0) or 0) * PPR_SCORING['fumbles_lost']
            
            # Track stats
            defense_stats[opponent]['total_points_allowed'] += pts
            
            if position == 'QB':
                defense_stats[opponent]['qb_points_allowed'] += pts
                defense_stats[opponent]['passing_tds_allowed'] += (row.get('passing_tds', 0) or 0)
            elif position == 'RB':
                defense_stats[opponent]['rb_points_allowed'] += pts
            elif position == 'WR':
                defense_stats[opponent]['wr_points_allowed'] += pts
            elif position == 'TE':
                defense_stats[opponent]['te_points_allowed'] += pts
            
            # Yards and TDs
            defense_stats[opponent]['rushing_yards_allowed'] += (row.get('rushing_yards', 0) or 0)
            defense_stats[opponent]['rushing_tds_allowed'] += (row.get('rushing_tds', 0) or 0)
            defense_stats[opponent]['receiving_yards_allowed'] += (row.get('receiving_yards', 0) or 0)
            defense_stats[opponent]['receiving_tds_allowed'] += (row.get('receiving_tds', 0) or 0)
        
        # Calculate games played for each defense
        for team, stats in defense_stats.items():
            stats['games'] = len(stats['weeks_played'])
            del stats['weeks_played']  # Remove set before JSON serialization
        
        # Convert to list
        defense_data = list(defense_stats.values())
        
        print(f"  Calculated stats for {len(defense_data)} defenses")
        
        # Generate report
        generate_defense_stats_report(defense_data, OUTPUT_DIR)
        
        print(f"\n{'='*80}")
        print(f"Defense stats report successfully generated!")
        print(f"Check defense_stats.html for detailed defensive analysis.")
        print(f"{'='*80}\n")
        
    except Exception as e:
        print(f"  Error generating defense stats: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--season-stats":
        generate_season_stats()
    elif len(sys.argv) > 1 and sys.argv[1] == "--player-stats":
        generate_player_stats()
    elif len(sys.argv) > 1 and sys.argv[1] == "--defense-stats":
        generate_defense_stats()
    else:
        generate_copilot_context()
