"""
Generate playoff predictions using simple 2025 season averages.

This uses actual PPG and standard deviation from the 2025 season,
adjusted for defensive matchup favorability, instead of the V7 model.
"""

import json
import os
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Tuple
import numpy as np
from scipy.stats import t as t_dist
import requests
import nflreadpy as nfl
import statistics
import datetime

from core_data import SleeperAPI
from nfl_week_helper import get_current_nfl_week


@dataclass
class SimpleMatchupPrediction:
    """Prediction for a single matchup."""
    roster_id_1: int
    roster_id_2: int
    user_name_1: str
    user_name_2: str
    # Current lineup projections
    projected_points_1: float
    projected_points_2: float
    projected_std_1: float
    projected_std_2: float
    win_prob_1: float
    win_prob_2: float
    # Optimal lineup projections
    optimal_points_1: float = 0.0
    optimal_points_2: float = 0.0
    optimal_std_1: float = 0.0
    optimal_std_2: float = 0.0
    optimal_win_prob_1: float = 0.0
    optimal_win_prob_2: float = 0.0


@dataclass
class SimpleTeamPrediction:
    """Simple team prediction based on season averages."""
    roster_id: int
    user_name: str
    current_projected: float
    current_std: float
    optimal_projected: float = 0.0
    optimal_std: float = 0.0
    improvement_points: float = 0.0


class SimplePlayoffSimulator:
    """Simulate playoffs using simple 2025 season averages."""
    
    ROSTER_SLOTS = {
        'QB': 1,
        'RB': 2,
        'WR': 3,
        'TE': 1,
        'FLEX': 1,
        'SUPERFLEX': 1,
    }
    
    def __init__(self, league_id: str, season: int = 2025, num_simulations: int = 10000):
        self.league_id = league_id
        self.season = season
        self.num_simulations = num_simulations
        
        self.api = SleeperAPI(league_id)
        
        # Cache
        self._league = None
        self._rosters = None
        self._users = None
        self._user_map = None
        self._roster_map = None
        self._matchups = None
        self._winners_bracket = None
        self._losers_bracket = None
        self._sleeper_players = None
        self._player_stats = {}  # player_id -> {avg_ppg, std_dev}
        self._defense_stats = {}  # team -> {avg_points_allowed, std_dev}
        self._actual_player_points = {}
        self._schedule_lookup = {}  # (team, week) -> opponent
        self._current_week = None  # Track which week's actual points are loaded
        
    def _load_data(self, week: int):
        """Load league data and season statistics."""
        print("  Loading league data...")
        self._current_week = week  # Track which week we're analyzing
        self._league = self.api.get_league()
        self._rosters = self.api.get_rosters()
        self._users = self.api.get_users()
        self._matchups = self.api.get_matchups(week)
        
        # Get brackets
        self._winners_bracket = requests.get(
            f"https://api.sleeper.app/v1/league/{self.league_id}/winners_bracket"
        ).json()
        self._losers_bracket = requests.get(
            f"https://api.sleeper.app/v1/league/{self.league_id}/losers_bracket"
        ).json()
        
        # Build maps
        self._user_map = {u['user_id']: u['display_name'] for u in self._users}
        self._roster_map = {}
        for r in self._rosters:
            owner_id = r.get('owner_id')
            self._roster_map[r['roster_id']] = {
                'owner_id': owner_id,
                'user_name': self._user_map.get(owner_id, 'Unknown'),
                'players': r.get('players', []),
                'roster': r,
            }
        
        # Get Sleeper player info
        print("  Loading Sleeper player database...")
        self._sleeper_players = SleeperAPI.get_all_players() or {}
        
        # Load NFL schedule to check game status
        # Only use actual points for players whose games are COMPLETE
        completed_game_teams = set()
        try:
            schedules = nfl.load_schedules([self.season])
            for game in schedules.iter_rows(named=True):
                game_week = game.get('week')
                if game_week == week:
                    # Check if game is complete (has final scores or game_type indicates complete)
                    home_score = game.get('home_score')
                    away_score = game.get('away_score')
                    game_type = game.get('game_type', '')
                    
                    # If game has final scores, both teams' players have completed games
                    if home_score is not None and away_score is not None:
                        home_team = game.get('home_team')
                        away_team = game.get('away_team')
                        if home_team:
                            completed_game_teams.add(home_team)
                            # Also add Sleeper variants
                            if home_team == 'LA':
                                completed_game_teams.add('LAR')
                        if away_team:
                            completed_game_teams.add(away_team)
                            if away_team == 'LA':
                                completed_game_teams.add('LAR')
            
            print(f"  Found {len(completed_game_teams)} teams with completed games")
        except Exception as e:
            print(f"  Warning: Could not load schedule to check game status: {e}")
            # Fallback: treat all games as potentially complete
            completed_game_teams = None
        
        # Load actual player points for this week
        # Only include players whose games are COMPLETE (have final scores)
        self._actual_player_points = {}
        for m in self._matchups:
            players_points = m.get('players_points', {})
            for pid, pts in players_points.items():
                if pts is not None and pts > 0:
                    # Check if this player's team has completed their game
                    player_info = self._sleeper_players.get(pid, {})
                    player_team = player_info.get('team', '')
                    
                    # If we couldn't load schedule, accept all non-zero points
                    # Otherwise, only accept if team's game is complete
                    if completed_game_teams is None or player_team in completed_game_teams:
                        self._actual_player_points[pid] = pts
                    else:
                        # Game in progress - skip this player's actual points
                        pass
        
        if self._actual_player_points:
            print(f"  Found {len(self._actual_player_points)} players with FINAL week {week} points (completed games only)")
            # Log a few sample players for debugging
            sample_players = list(self._actual_player_points.items())[:5]
            print(f"  Sample actual points: {[(self._sleeper_players.get(pid, {}).get('full_name', pid), pts) for pid, pts in sample_players]}")
        else:
            print(f"  WARNING: No actual player points found for week {week}!")
        
        # Load 2025 season stats
        print("  Loading 2025 season statistics...")
        self._load_season_stats()
        
        # Load defense stats
        print("  Loading defense statistics...")
        self._load_defense_stats()
        
        print(f"  Loaded {len(self._rosters)} rosters, {len(self._matchups)} matchups")
    
    def _load_season_stats(self):
        """Load actual 2025 season stats for all players from their matchup history."""
        # Calculate season averages from actual matchup history
        # Go through past weeks and collect points for each player
        current_week = get_current_nfl_week()
        player_weekly_points = defaultdict(list)
        
        for week_num in range(1, current_week):
            try:
                matchups = self.api.get_matchups(week_num)
                for matchup in matchups:
                    players_points = matchup.get('players_points', {})
                    for player_id, points in players_points.items():
                        if points is not None and points > 0:
                            player_weekly_points[player_id].append(points)
            except:
                pass  # Skip weeks that don't exist
        
        # Calculate averages
        for player_id, weekly_points in player_weekly_points.items():
            if len(weekly_points) >= 3:  # Need at least 3 games
                avg_ppg = np.mean(weekly_points)
                std_dev = np.std(weekly_points, ddof=1) if len(weekly_points) > 1 else 5.0
                
                player_info = self._sleeper_players.get(player_id, {})
                self._player_stats[player_id] = {
                    'avg_ppg': avg_ppg,
                    'std_dev': std_dev,
                    'games_played': len(weekly_points),
                    'name': player_info.get('full_name', 'Unknown')
                }
        
        print(f"  Loaded season averages for {len(self._player_stats)} players")
    
    def _load_defense_stats(self):
        """Load defensive stats from nflverse to adjust projections."""
        print(f"  Loading defense statistics...")
        
        # Sleeper to nflverse team abbreviation mapping
        sleeper_to_nflverse = {
            'LAR': 'LA',  # Rams
            'LV': 'LV',   # Raiders
            # Most teams match, but add any other differences if found
        }
        
        # Load NFL schedule for weeks 15-17
        try:
            schedules = nfl.load_schedules([self.season])
            for game in schedules.iter_rows(named=True):
                week = game.get('week')
                if week and week >= 15 and week <= 17:
                    home_team = game.get('home_team')
                    away_team = game.get('away_team')
                    if home_team and away_team:
                        # Store with nflverse abbreviations
                        self._schedule_lookup[(home_team, week)] = away_team
                        self._schedule_lookup[(away_team, week)] = home_team
                        
                        # Also store with Sleeper abbreviations for lookup
                        for sleeper_abbr, nflverse_abbr in sleeper_to_nflverse.items():
                            if home_team == nflverse_abbr:
                                self._schedule_lookup[(sleeper_abbr, week)] = away_team
                            if away_team == nflverse_abbr:
                                self._schedule_lookup[(sleeper_abbr, week)] = home_team
        except Exception as e:
            print(f"  Warning: Could not load NFL schedules: {e}")
        
        # Calculate defensive stats from nflverse weekly stats (weeks 1-14)
        # Use actual game data to see how defenses performed
        try:
            from core_data import calculate_fantasy_points, PPR_SCORING
            
            weekly_stats = nfl.load_player_stats([self.season])
            defense_data = defaultdict(lambda: defaultdict(lambda: {'points': [], 'games': 0}))
            
            for row in weekly_stats.iter_rows(named=True):
                week = row.get('week')
                if not week or week >= 15:
                    continue
                
                position = row.get('position', '')
                if position not in ['QB', 'RB', 'WR', 'TE']:
                    continue
                
                opponent_team = row.get('opponent_team', '')
                if not opponent_team:
                    continue
                
                # Calculate fantasy points for this game
                pts = calculate_fantasy_points(row, PPR_SCORING)
                if pts > 0:
                    defense_data[opponent_team][position]['points'].append(pts)
                    defense_data[opponent_team][position]['games'] += 1
            
            # Calculate average and std dev of points allowed per game by position
            for defense, positions in defense_data.items():
                self._defense_stats[defense] = {}
                for pos, data in positions.items():
                    if data['points']:
                        avg_allowed = statistics.mean(data['points'])
                        self._defense_stats[defense][pos] = avg_allowed
            
            print(f"  Loaded defensive stats for {len(self._defense_stats)} teams")
        except Exception as e:
            print(f"  Warning: Could not load defensive stats from nflverse: {e}")
            print(f"  Loaded defensive stats for {len(self._defense_stats)} teams")
    
    def _get_player_projection(self, sleeper_id: str, week: int, current_week: int = None) -> Tuple[float, float]:
        """
        Get projection for a player using season averages with defensive matchup adjustment.
        Returns (mean, std).
        """
        # Check if player already played THIS SPECIFIC week (only for current week)
        if current_week and week == current_week and sleeper_id in self._actual_player_points:
            actual = self._actual_player_points[sleeper_id]
            return actual, 0.0  # No variance for actual scores
        
        # Get season stats
        if sleeper_id not in self._player_stats:
            return 0.0, 0.0
        
        stats = self._player_stats[sleeper_id]
        base_ppg = stats['avg_ppg']
        std_dev = stats['std_dev']
        
        # Apply defensive matchup adjustment
        player_info = self._sleeper_players.get(sleeper_id, {})
        position = player_info.get('position', '')
        team = player_info.get('team', '')
        
        # Get opponent from schedule
        opponent = self._schedule_lookup.get((team, week), None)
        
        if opponent and position in ['QB', 'RB', 'WR', 'TE']:
            # Get league average points allowed at this position
            league_avg = 0.0
            count = 0
            for def_team, positions in self._defense_stats.items():
                if position in positions:
                    league_avg += positions[position]
                    count += 1
            
            if count > 0:
                league_avg /= count
                
                # Get opponent's defensive strength
                opp_defense = self._defense_stats.get(opponent, {})
                opp_avg_allowed = opp_defense.get(position, league_avg)
                
                # Adjust projection: if defense allows more than average, boost projection
                # If defense is tough (allows less), reduce projection
                if league_avg > 0:
                    defense_factor = opp_avg_allowed / league_avg
                    # Cap adjustment to ±20%
                    defense_factor = max(0.8, min(1.2, defense_factor))
                    adjusted_ppg = base_ppg * defense_factor
                    return adjusted_ppg, std_dev
        
        return base_ppg, std_dev
    
    def _calculate_lineup_projection(self, starter_ids: List[str], week: int) -> Tuple[float, float]:
        """Calculate projection for a specific lineup (list of player IDs)."""
        if not starter_ids:
            return 0.0, 0.0
        
        total_mean = 0.0
        total_var = 0.0
        
        for pid in starter_ids:
            mean, std = self._get_player_projection(pid, week, current_week=self._current_week)
            total_mean += mean
            total_var += std ** 2
        
        return total_mean, total_var ** 0.5
    
    def _simulate_matchup(self, mean1: float, std1: float, mean2: float, std2: float) -> float:
        """
        Simulate matchup win probability using Monte Carlo.
        Returns probability that team 1 wins.
        """
        if std1 <= 0:
            std1 = 5.0  # Default std
        if std2 <= 0:
            std2 = 5.0
        
        # Use t-distribution for heavier tails (df=6 based on model)
        df = 6.0
        
        # Sample from t-distributions
        scores1 = mean1 + std1 * t_dist.rvs(df, size=self.num_simulations)
        scores2 = mean2 + std2 * t_dist.rvs(df, size=self.num_simulations)
        
        wins1 = np.sum(scores1 > scores2)
        ties = np.sum(scores1 == scores2)
        
        # Win probability (ties split 50/50)
        return (wins1 + 0.5 * ties) / self.num_simulations
    
    def _build_optimal_lineup(self, roster_players: List[str], week: int) -> Tuple[List[str], float, float]:
        """Build optimal lineup using season averages."""
        if not roster_players:
            return [], 0.0, 0.0
        
        # Get projections for all players (filtering injuries for future weeks)
        player_preds = []
        for pid in roster_players:
            player_info = self._sleeper_players.get(pid, {})
            
            # Check if player already has actual points (game played)
            has_actual_points = (pid in self._actual_player_points)
            
            # Skip inactive/injured players UNLESS they already played this week
            if not has_actual_points:
                active = player_info.get('active', True)
                injury_status = player_info.get('injury_status', None)
                if not active or injury_status in ['IR', 'Out', 'Doubtful']:
                    # Player is injured and hasn't played - skip them
                    continue
            
            mean, std = self._get_player_projection(pid, week, current_week=self._current_week)
            position = player_info.get('position', '')
            if mean > 0:
                player_preds.append({
                    'id': pid,
                    'position': position,
                    'mean': mean,
                    'std': std,
                })
        
        # Sort by projected points within position
        qbs = sorted([p for p in player_preds if p['position'] == 'QB'], 
                     key=lambda x: x['mean'], reverse=True)
        rbs = sorted([p for p in player_preds if p['position'] == 'RB'], 
                     key=lambda x: x['mean'], reverse=True)
        wrs = sorted([p for p in player_preds if p['position'] == 'WR'], 
                     key=lambda x: x['mean'], reverse=True)
        tes = sorted([p for p in player_preds if p['position'] == 'TE'], 
                     key=lambda x: x['mean'], reverse=True)
        
        lineup = []
        total_mean = 0.0
        total_var = 0.0
        
        # 1 QB
        if qbs:
            p = qbs.pop(0)
            lineup.append(p['id'])
            total_mean += p['mean']
            total_var += p['std'] ** 2
        
        # 2 RB
        for _ in range(2):
            if rbs:
                p = rbs.pop(0)
                lineup.append(p['id'])
                total_mean += p['mean']
                total_var += p['std'] ** 2
        
        # 3 WR
        for _ in range(3):
            if wrs:
                p = wrs.pop(0)
                lineup.append(p['id'])
                total_mean += p['mean']
                total_var += p['std'] ** 2
        
        # 1 TE
        if tes:
            p = tes.pop(0)
            lineup.append(p['id'])
            total_mean += p['mean']
            total_var += p['std'] ** 2
        
        # FLEX
        flex_options = rbs + wrs + tes
        flex_options.sort(key=lambda x: x['mean'], reverse=True)
        if flex_options:
            p = flex_options.pop(0)
            lineup.append(p['id'])
            total_mean += p['mean']
            total_var += p['std'] ** 2
            if p in rbs: rbs.remove(p)
            elif p in wrs: wrs.remove(p)
            elif p in tes: tes.remove(p)
        
        # SUPERFLEX
        sflex_options = qbs + flex_options
        sflex_options.sort(key=lambda x: x['mean'], reverse=True)
        if sflex_options:
            p = sflex_options.pop(0)
            lineup.append(p['id'])
            total_mean += p['mean']
            total_var += p['std'] ** 2
        
        return lineup, total_mean, np.sqrt(total_var)
    
    def get_matchup_predictions(self, week: int) -> List[SimpleMatchupPrediction]:
        """Get predictions for all current week matchups."""
        self._load_data(week)
        
        # Group matchups by matchup_id
        matchup_groups = {}
        for m in self._matchups:
            mid = m.get('matchup_id')
            if mid is None:
                continue  # Bye week or eliminated
            if mid not in matchup_groups:
                matchup_groups[mid] = []
            matchup_groups[mid].append(m)
        
        predictions = []
        
        for mid, teams in matchup_groups.items():
            if len(teams) != 2:
                continue
            
            t1, t2 = teams[0], teams[1]
            rid1, rid2 = t1['roster_id'], t2['roster_id']
            
            # Get current starters
            starters1 = t1.get('starters', [])
            starters2 = t2.get('starters', [])
            
            # Calculate current lineup projections
            mean1, std1 = self._calculate_lineup_projection(starters1, week)
            mean2, std2 = self._calculate_lineup_projection(starters2, week)
            
            # Calculate current lineup win probability
            win_prob_1 = self._simulate_matchup(mean1, std1, mean2, std2)
            
            # Calculate optimal lineup projections
            roster1 = self._roster_map.get(rid1, {}).get('players', [])
            roster2 = self._roster_map.get(rid2, {}).get('players', [])
            
            _, opt_mean1, opt_std1 = self._build_optimal_lineup(roster1, week)
            _, opt_mean2, opt_std2 = self._build_optimal_lineup(roster2, week)
            
            # Calculate optimal lineup win probability
            opt_win_prob_1 = self._simulate_matchup(opt_mean1, opt_std1, opt_mean2, opt_std2)
            
            predictions.append(SimpleMatchupPrediction(
                roster_id_1=rid1,
                roster_id_2=rid2,
                user_name_1=self._roster_map[rid1]['user_name'],
                user_name_2=self._roster_map[rid2]['user_name'],
                projected_points_1=mean1,
                projected_points_2=mean2,
                projected_std_1=std1,
                projected_std_2=std2,
                win_prob_1=win_prob_1,
                win_prob_2=1 - win_prob_1,
                optimal_points_1=opt_mean1,
                optimal_points_2=opt_mean2,
                optimal_std_1=opt_std1,
                optimal_std_2=opt_std2,
                optimal_win_prob_1=opt_win_prob_1,
                optimal_win_prob_2=1 - opt_win_prob_1,
            ))
        
        return predictions
    
    def get_team_predictions(self, week: int) -> List[SimpleTeamPrediction]:
        """Get simple predictions for all teams."""
        if self._matchups is None:
            self._load_data(week)
        
        predictions = []
        
        for m in self._matchups:
            rid = m['roster_id']
            roster_info = self._roster_map.get(rid)
            if not roster_info:
                continue
            
            # Current lineup
            current_starters = m.get('starters', [])
            current_mean, current_std = self._calculate_lineup_projection(current_starters, week)
            
            # Optimal lineup
            all_players = roster_info['players']
            optimal_lineup, optimal_mean, optimal_std = self._build_optimal_lineup(all_players, week)
            
            predictions.append(SimpleTeamPrediction(
                roster_id=rid,
                user_name=roster_info['user_name'],
                current_projected=current_mean,
                optimal_projected=optimal_mean,
                current_std=current_std,
                optimal_std=optimal_std,
                improvement_points=optimal_mean - current_mean,
            ))
        
        return predictions
    
    def _finalize_completed_matchups(self, bracket: List[dict], current_week: int, playoff_start: int):
        """Check if matchups are complete and mark winners if all players have played."""
        for matchup in bracket:
            # Only check matchups for the current week
            matchup_week = playoff_start + matchup['r'] - 1
            if matchup_week != current_week:
                continue
            
            # Skip if already decided
            if matchup.get('w') is not None:
                continue
            
            t1 = matchup.get('t1')
            t2 = matchup.get('t2')
            
            if t1 is None or t2 is None:
                continue
            
            # Get starters for both teams
            matchup1 = next((m for m in self._matchups if m['roster_id'] == t1), None)
            matchup2 = next((m for m in self._matchups if m['roster_id'] == t2), None)
            
            if not matchup1 or not matchup2:
                continue
            
            starters1 = matchup1.get('starters', [])
            starters2 = matchup2.get('starters', [])
            
            # Check if all players have finished
            all_complete_1 = all(pid in self._actual_player_points for pid in starters1 if pid)
            all_complete_2 = all(pid in self._actual_player_points for pid in starters2 if pid)
            
            if all_complete_1 and all_complete_2:
                # Calculate final scores
                score1 = sum(self._actual_player_points.get(pid, 0) for pid in starters1 if pid)
                score2 = sum(self._actual_player_points.get(pid, 0) for pid in starters2 if pid)
                
                # Mark winner
                if score1 > score2:
                    matchup['w'] = t1
                    matchup['l'] = t2
                    print(f"  ✓ Finalized: {self._roster_map[t1]['user_name']} ({score1:.1f}) defeats {self._roster_map[t2]['user_name']} ({score2:.1f})")
                else:
                    matchup['w'] = t2
                    matchup['l'] = t1
                    print(f"  ✓ Finalized: {self._roster_map[t2]['user_name']} ({score2:.1f}) defeats {self._roster_map[t1]['user_name']} ({score1:.1f})")
    
    def simulate_playoffs(self, current_week: int) -> Dict[int, Dict[str, float]]:
        """Run Monte Carlo playoff simulation."""
        self._load_data(current_week)
        
        playoff_start = self._league.get('settings', {}).get('playoff_week_start', 15)
        
        # Finalize any completed matchups before simulating
        print(f"\nChecking for completed matchups in week {current_week}...")
        self._finalize_completed_matchups(self._winners_bracket, current_week, playoff_start)
        self._finalize_completed_matchups(self._losers_bracket, current_week, playoff_start)
        
        championship_wins = defaultdict(int)
        loser_wins = defaultdict(int)
        
        print(f"  Running {self.num_simulations:,} playoff simulations...")
        
        for sim in range(self.num_simulations):
            if sim > 0 and sim % 2000 == 0:
                print(f"    Completed {sim:,} simulations...")
            
            # Simulate brackets
            winner_results = self._simulate_bracket(
                self._winners_bracket.copy(),
                current_week,
                playoff_start
            )
            loser_results = self._simulate_bracket(
                self._losers_bracket.copy(),
                current_week,
                playoff_start
            )
            
            champ_rid = winner_results.get('champion')
            if champ_rid:
                championship_wins[champ_rid] += 1
            
            loser_champ_rid = loser_results.get('champion')
            if loser_champ_rid:
                loser_wins[loser_champ_rid] += 1
        
        # Convert to probabilities
        results = {}
        for rid in self._roster_map.keys():
            results[rid] = {
                'championship_prob': championship_wins[rid] / self.num_simulations,
                'loser_bracket_prob': loser_wins[rid] / self.num_simulations,
            }
        
        return results
    
    def _simulate_bracket(self, bracket: List[dict], current_week: int, 
                          playoff_start: int) -> Dict[str, int]:
        """Simulate a bracket."""
        bracket = [dict(m) for m in bracket]
        
        max_round = max(m['r'] for m in bracket)
        
        for round_num in range(1, max_round + 1):
            round_matchups = [m for m in bracket if m['r'] == round_num]
            
            for matchup in round_matchups:
                t1 = matchup.get('t1')
                t2 = matchup.get('t2')
                
                # Resolve TBD teams
                if t1 is None and 't1_from' in matchup:
                    t1_from = matchup['t1_from']
                    source_matchup = next((m for m in bracket if m['m'] == 
                                          (t1_from.get('w') or t1_from.get('l'))), None)
                    if source_matchup:
                        if 'w' in t1_from:
                            t1 = source_matchup.get('w')
                        else:
                            t1 = source_matchup.get('l')
                
                if t2 is None and 't2_from' in matchup:
                    t2_from = matchup['t2_from']
                    source_id = t2_from.get('w') or t2_from.get('l')
                    source_matchup = next((m for m in bracket if m['m'] == source_id), None)
                    if source_matchup:
                        if 'w' in t2_from:
                            t2 = source_matchup.get('w')
                        else:
                            t2 = source_matchup.get('l')
                
                matchup['t1'] = t1
                matchup['t2'] = t2
                
                if matchup.get('w') is not None:
                    continue
                
                if t1 is None or t2 is None:
                    continue
                
                # Simulate matchup
                matchup_week = playoff_start + round_num - 1
                
                # For current week, use actual lineup; for future weeks, use optimal
                if matchup_week == current_week:
                    # Use actual current lineup
                    matchup1 = next((m for m in self._matchups if m['roster_id'] == t1), None)
                    matchup2 = next((m for m in self._matchups if m['roster_id'] == t2), None)
                    
                    starters1 = matchup1.get('starters', []) if matchup1 else []
                    starters2 = matchup2.get('starters', []) if matchup2 else []
                    
                    mean1, std1 = self._calculate_lineup_projection(starters1, matchup_week)
                    mean2, std2 = self._calculate_lineup_projection(starters2, matchup_week)
                else:
                    # Use optimal lineup for future weeks
                    roster1 = self._roster_map.get(t1, {}).get('players', [])
                    roster2 = self._roster_map.get(t2, {}).get('players', [])
                    
                    _, mean1, std1 = self._build_optimal_lineup(roster1, matchup_week)
                    _, mean2, std2 = self._build_optimal_lineup(roster2, matchup_week)
                
                if std1 <= 0:
                    std1 = 5.0
                if std2 <= 0:
                    std2 = 5.0
                
                score1 = mean1 + std1 * t_dist.rvs(6.0)
                score2 = mean2 + std2 * t_dist.rvs(6.0)
                
                if score1 > score2:
                    matchup['w'] = t1
                    matchup['l'] = t2
                else:
                    matchup['w'] = t2
                    matchup['l'] = t1
        
        final_matchup = next((m for m in bracket if m.get('p') == 1), None)
        champion = final_matchup.get('w') if final_matchup else None
        
        return {'champion': champion}
    
    def generate_predictions(self, output_path: str = None):
        """Generate predictions and save to JSON."""
        current_week = get_current_nfl_week()
        
        print(f"\n{'='*80}")
        print(f"SIMPLE SEASON AVERAGE PLAYOFF PREDICTIONS")
        print("="*80)
        print(f"Week: {current_week}")
        print(f"Current timestamp: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}")
        
        # Initialize
        self._load_data(current_week)
        
        settings = self._league.get('settings', {})
        league_name = self._league.get('name', 'Unknown')
        
        print(f"  Loaded {len(self._roster_map)} rosters, {len(self._matchups)} matchups")
        print(f"League: {league_name}")
        print()
        
        # Get current week matchup predictions
        matchup_predictions = self.get_matchup_predictions(current_week)
        
        # Team projections
        print(f"\n{'='*80}")
        print(f"TEAM PROJECTIONS (Current Week {current_week})")
        print("="*80)
        print(f"\n{'Team':<20} {'Projection':>15}")
        print("-" * 37)
        
        team_predictions = self.get_team_predictions(current_week)
        team_predictions.sort(key=lambda x: x.current_projected, reverse=True)
        
        for tp in team_predictions:
            print(f"{tp.user_name:<20} {tp.current_projected:>6.1f} ± {tp.current_std:>5.1f} pts")
        
        # Run playoff simulations
        print(f"\n{'='*80}")
        print(f"PLAYOFF PROBABILITIES ({self.num_simulations:,} simulations)")
        print("="*80)
        
        playoff_results = self.simulate_playoffs(current_week)
        
        # Sort by championship probability
        sorted_results = sorted(
            playoff_results.items(),
            key=lambda x: x[1]['championship_prob'],
            reverse=True
        )
        
        print(f"\n{'User':<20} {'Championship':>15} {'Loser Bracket':>15}")
        print("-" * 52)
        for rid, probs in sorted_results:
            user_name = self._roster_map[rid]['user_name']
            champ_pct = probs['championship_prob'] * 100
            loser_pct = probs['loser_bracket_prob'] * 100
            if champ_pct > 0 or loser_pct > 0:
                print(f"{user_name:<20} {champ_pct:>14.1f}% {loser_pct:>14.1f}%")
        
        # Build output data structure
        output_data = {
            'generated_at': current_week,
            'league_name': league_name,
            'model': 'Simple Season Average',
            'is_playoffs': True,
            'matchups': [
                {
                    'roster_id_1': mp.roster_id_1,
                    'roster_id_2': mp.roster_id_2,
                    'user_name_1': mp.user_name_1,
                    'user_name_2': mp.user_name_2,
                    'current_lineup': {
                        'projected_1': round(mp.projected_points_1, 1),
                        'projected_2': round(mp.projected_points_2, 1),
                        'std_1': round(mp.projected_std_1, 1),
                        'std_2': round(mp.projected_std_2, 1),
                        'win_prob_1': round(mp.win_prob_1, 3),
                        'win_prob_2': round(mp.win_prob_2, 3),
                    },
                    'optimal_lineup': {
                        'projected_1': round(mp.optimal_points_1, 1),
                        'projected_2': round(mp.optimal_points_2, 1),
                        'std_1': round(mp.optimal_std_1, 1),
                        'std_2': round(mp.optimal_std_2, 1),
                        'win_prob_1': round(mp.optimal_win_prob_1, 3),
                        'win_prob_2': round(mp.optimal_win_prob_2, 3),
                    },
                }
                for mp in matchup_predictions
            ],
            'team_predictions': [
                {
                    'roster_id': tp.roster_id,
                    'user_name': tp.user_name,
                    'current_projected': round(tp.current_projected, 1),
                    'optimal_projected': round(tp.optimal_projected, 1),
                    'current_std': round(tp.current_std, 1),
                    'optimal_std': round(tp.optimal_std, 1),
                    'improvement_points': round(tp.improvement_points, 1),
                }
                for tp in team_predictions
            ],
            'playoff_probabilities': {
                self._roster_map[rid]['user_name']: {
                    'roster_id': rid,
                    'championship_prob': round(probs['championship_prob'], 4),
                    'loser_bracket_prob': round(probs['loser_bracket_prob'], 4),
                }
                for rid, probs in playoff_results.items()
            }
        }
        
        # Save output
        if output_path is None:
            output_path = '../website/public/data/dynasty_playoff_predictions.json'
        
        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        print(f"\n💾 Saved predictions to: {os.path.abspath(output_path)}")
        
        return output_data


def main():
    """Run simple playoff predictions."""
    league_id = "1264304480178950144"  # IBAC Dynasty
    
    simulator = SimplePlayoffSimulator(league_id, season=2025, num_simulations=10000)
    
    # Use absolute path based on script location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, '..', 'website', 'public', 'data', 'dynasty_playoff_predictions.json')
    
    simulator.generate_predictions(output_path=output_path)


if __name__ == "__main__":
    main()
