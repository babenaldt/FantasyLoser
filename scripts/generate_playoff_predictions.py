"""
Generate matchup win probabilities and playoff championship predictions.
Uses V7 model predictions with Monte Carlo simulation.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
import numpy as np
import requests
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from scipy.stats import t as t_dist

from player_score_model_v7 import PlayerScoreModelV7
from core_data import SleeperAPI, SCORING_PRESETS
from nfl_week_helper import get_current_nfl_week


@dataclass
class MatchupPrediction:
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
class TeamPrediction:
    """Prediction for a team's current and optimal lineup."""
    roster_id: int
    user_name: str
    current_lineup: List[str]
    optimal_lineup: List[str]
    current_projected: float
    optimal_projected: float
    current_std: float
    optimal_std: float
    improvement_points: float


class PlayoffSimulator:
    """Simulate playoff outcomes using Monte Carlo."""
    
    # Roster slot configuration for dynasty superflex
    ROSTER_SLOTS = {
        'QB': 1,
        'RB': 2,
        'WR': 3,
        'TE': 1,
        'FLEX': 1,  # RB/WR/TE
        'SUPERFLEX': 1,  # QB/RB/WR/TE
    }
    
    def __init__(self, league_id: str, season: int = 2025, num_simulations: int = 10000):
        self.league_id = league_id
        self.season = season
        self.num_simulations = num_simulations
        
        # Initialize API and model
        self.api = SleeperAPI(league_id)
        self.model = PlayerScoreModelV7(season=season, verbose=False)
        
        # Cache data
        self._league = None
        self._rosters = None
        self._users = None
        self._user_map = None
        self._roster_map = None
        self._matchups = None
        self._winners_bracket = None
        self._losers_bracket = None
        self._sleeper_players = None
        self._player_predictions = {}
        self._sleeper_to_nflreadr = None
        self._actual_player_points = {}  # Sleeper ID -> actual points for players who have played
        
    def _load_data(self, week: int):
        """Load all necessary data from Sleeper API."""
        print("  Loading league data...")
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
        
        # Load sleeper to nflreadr mapping
        mapping_path = os.path.join(os.path.dirname(__file__), '..', 'output', 'sleeper_to_nflreadr_mapping.json')
        if os.path.exists(mapping_path):
            with open(mapping_path, 'r') as f:
                self._sleeper_to_nflreadr = json.load(f)
            print(f"  Loaded {len(self._sleeper_to_nflreadr)} player ID mappings")
        else:
            print(f"  Warning: Could not find sleeper_to_nflreadr_mapping.json")
            self._sleeper_to_nflreadr = {}
        
        # Build map of actual player points (for players who have already played this week)
        self._actual_player_points = {}
        for m in self._matchups:
            players_points = m.get('players_points', {})
            for pid, pts in players_points.items():
                if pts is not None and pts > 0:
                    self._actual_player_points[pid] = pts
        
        if self._actual_player_points:
            print(f"  Found {len(self._actual_player_points)} players with actual week {week} points (already played)")
        
        print(f"  Loaded {len(self._rosters)} rosters, {len(self._matchups)} matchups")
        
    def _get_player_prediction(self, sleeper_id: str, week: int, use_actual: bool = True) -> Tuple[float, float]:
        """
        Get prediction for a player (mean, std). Returns (0, 0) if unavailable.
        
        If use_actual=True and player has actual points for this week (already played),
        returns (actual_points, 0.0) since there's no uncertainty.
        """
        cache_key = f"{sleeper_id}_{week}_{use_actual}"
        if cache_key in self._player_predictions:
            return self._player_predictions[cache_key]
        
        # Check for actual points first (player already played this week)
        if use_actual and sleeper_id in self._actual_player_points:
            actual_pts = self._actual_player_points[sleeper_id]
            result = (actual_pts, 0.0)  # No uncertainty for actual scores
            self._player_predictions[cache_key] = result
            return result
        
        # Get player info from Sleeper
        player_info = self._sleeper_players.get(sleeper_id, {})
        if not player_info:
            self._player_predictions[cache_key] = (0.0, 0.0)
            return (0.0, 0.0)
        
        # Map Sleeper ID to nflreadr ID using our mapping file
        mapping_entry = self._sleeper_to_nflreadr.get(sleeper_id, {})
        nflreadr_id = mapping_entry.get('nflreadr_id') if isinstance(mapping_entry, dict) else None
        
        if nflreadr_id:
            pred = self.model.predict_player_for_week(nflreadr_id, week)
            if pred and pred.mean > 0:
                result = (pred.mean, pred.std_dev)
                self._player_predictions[cache_key] = result
                return result
        
        # Fallback to Sleeper projections if model fails
        self._player_predictions[cache_key] = (0.0, 0.0)
        return (0.0, 0.0)
    
    def _get_sleeper_projections(self, week: int) -> Dict[str, float]:
        """Get Sleeper projections for the week."""
        try:
            url = f"https://api.sleeper.com/projections/nfl/{self.season}/{week}"
            url += "?season_type=regular&position[]=QB&position[]=RB&position[]=WR&position[]=TE"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                projections = response.json()
                return {
                    p.get('player_id'): p.get('stats', {}).get('pts_ppr', 0)
                    for p in projections if p.get('player_id')
                }
        except Exception:
            pass
        return {}
    
    def _build_optimal_lineup(self, roster_players: List[str], week: int) -> Tuple[List[str], float, float]:
        """
        Build optimal lineup from available players.
        Returns: (lineup_player_ids, total_projected_points, combined_std)
        """
        # Handle None or empty roster
        if not roster_players:
            return [], 0.0, 0.0
        
        # Get predictions for all players
        player_preds = []
        for pid in roster_players:
            mean, std = self._get_player_prediction(pid, week)
            player_info = self._sleeper_players.get(pid, {})
            position = player_info.get('position', '')
            if mean > 0:
                player_preds.append({
                    'id': pid,
                    'position': position,
                    'mean': mean,
                    'std': std,
                })
        
        # Sort by projected points within each position
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
        
        # Fill slots
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
        
        # FLEX (best remaining RB/WR/TE)
        flex_options = rbs + wrs + tes
        flex_options.sort(key=lambda x: x['mean'], reverse=True)
        if flex_options:
            p = flex_options.pop(0)
            lineup.append(p['id'])
            total_mean += p['mean']
            total_var += p['std'] ** 2
            # Remove from original lists
            if p in rbs: rbs.remove(p)
            elif p in wrs: wrs.remove(p)
            elif p in tes: tes.remove(p)
        
        # SUPERFLEX (best remaining QB or flex eligible)
        sflex_options = qbs + flex_options
        sflex_options.sort(key=lambda x: x['mean'], reverse=True)
        if sflex_options:
            p = sflex_options.pop(0)
            lineup.append(p['id'])
            total_mean += p['mean']
            total_var += p['std'] ** 2
        
        return lineup, total_mean, np.sqrt(total_var)
    
    def _calculate_lineup_projection(self, starters: List[str], week: int) -> Tuple[float, float]:
        """Calculate projected points and std for a lineup."""
        total_mean = 0.0
        total_var = 0.0
        
        for pid in starters:
            mean, std = self._get_player_prediction(pid, week)
            total_mean += mean
            total_var += std ** 2
        
        return total_mean, np.sqrt(total_var)
    
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
    
    def get_current_matchups(self, week: int) -> List[MatchupPrediction]:
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
            
            predictions.append(MatchupPrediction(
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
    
    def get_team_predictions(self, week: int) -> List[TeamPrediction]:
        """Get current vs optimal lineup predictions for all teams."""
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
            
            predictions.append(TeamPrediction(
                roster_id=rid,
                user_name=roster_info['user_name'],
                current_lineup=current_starters,
                optimal_lineup=optimal_lineup,
                current_projected=current_mean,
                optimal_projected=optimal_mean,
                current_std=current_std,
                optimal_std=optimal_std,
                improvement_points=optimal_mean - current_mean,
            ))
        
        return predictions
    
    def simulate_playoffs(self, current_week: int) -> Dict[int, Dict[str, float]]:
        """
        Simulate entire playoff bracket.
        Returns: Dict[roster_id] -> {'championship': prob, 'loser_finals': prob, ...}
        """
        if self._winners_bracket is None:
            self._load_data(current_week)
        
        settings = self._league.get('settings', {})
        playoff_start = settings.get('playoff_week_start', 15)
        playoff_teams = settings.get('playoff_teams', 6)
        
        # Track outcomes across simulations
        championship_wins = {rid: 0 for rid in self._roster_map.keys()}
        loser_wins = {rid: 0 for rid in self._roster_map.keys()}
        
        print(f"  Running {self.num_simulations:,} playoff simulations...")
        
        for sim in range(self.num_simulations):
            if sim > 0 and sim % 2000 == 0:
                print(f"    Completed {sim:,} simulations...")
            
            # Simulate this playoff run
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
            
            # Track winner
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
        """
        Simulate a bracket (winners or losers).
        Returns dict with 'champion' = roster_id of winner.
        """
        # Create a working copy of bracket state
        bracket = [dict(m) for m in bracket]
        
        # Process rounds in order
        max_round = max(m['r'] for m in bracket)
        
        for round_num in range(1, max_round + 1):
            round_matchups = [m for m in bracket if m['r'] == round_num]
            
            for matchup in round_matchups:
                # Get teams for this matchup
                t1 = matchup.get('t1')
                t2 = matchup.get('t2')
                
                # Resolve TBD teams from previous rounds
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
                
                # Skip if matchup already decided
                if matchup.get('w') is not None:
                    continue
                
                # Skip if teams not yet determined
                if t1 is None or t2 is None:
                    continue
                
                # Simulate the matchup
                # Use projections for the actual week this matchup occurs
                matchup_week = playoff_start + round_num - 1
                
                # Get projections for both teams
                roster1 = self._roster_map.get(t1, {}).get('players', [])
                roster2 = self._roster_map.get(t2, {}).get('players', [])
                
                _, mean1, std1 = self._build_optimal_lineup(roster1, matchup_week)
                _, mean2, std2 = self._build_optimal_lineup(roster2, matchup_week)
                
                # Single simulation for this matchup
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
        
        # Find champion (winner of final round with p=1)
        final_matchup = next((m for m in bracket if m.get('p') == 1), None)
        champion = final_matchup.get('w') if final_matchup else None
        
        return {'champion': champion}
    
    def generate_predictions(self, output_path: str = None):
        """Generate all predictions and save to JSON."""
        current_week = get_current_nfl_week()
        
        print(f"\n{'='*80}")
        print(f"DYNASTY LEAGUE PLAYOFF PREDICTIONS")
        print(f"{'='*80}")
        print(f"Week: {current_week}")
        
        # Initialize
        self._load_data(current_week)
        
        league_name = self._league.get('name', 'Dynasty League')
        settings = self._league.get('settings', {})
        playoff_start = settings.get('playoff_week_start', 15)
        is_playoffs = current_week >= playoff_start
        
        print(f"League: {league_name}")
        print(f"Playoff Start Week: {playoff_start}")
        print(f"Currently in Playoffs: {is_playoffs}")
        
        # Get matchup predictions
        print(f"\n{'='*80}")
        print("CURRENT WEEK MATCHUP PREDICTIONS")
        print("="*80)
        
        matchup_predictions = self.get_current_matchups(current_week)
        
        for mp in matchup_predictions:
            print(f"\n{mp.user_name_1} vs {mp.user_name_2}")
            print(f"  Current Lineups:")
            print(f"    {mp.user_name_1}: {mp.projected_points_1:.1f} ± {mp.projected_std_1:.1f} pts")
            print(f"    {mp.user_name_2}: {mp.projected_points_2:.1f} ± {mp.projected_std_2:.1f} pts")
            print(f"    Win Prob: {mp.user_name_1} {mp.win_prob_1*100:.1f}% - {mp.win_prob_2*100:.1f}% {mp.user_name_2}")
            print(f"  Optimal Lineups:")
            print(f"    {mp.user_name_1}: {mp.optimal_points_1:.1f} ± {mp.optimal_std_1:.1f} pts")
            print(f"    {mp.user_name_2}: {mp.optimal_points_2:.1f} ± {mp.optimal_std_2:.1f} pts")
            print(f"    Win Prob: {mp.user_name_1} {mp.optimal_win_prob_1*100:.1f}% - {mp.optimal_win_prob_2*100:.1f}% {mp.user_name_2}")
        
        # Get optimal lineup predictions
        print(f"\n{'='*80}")
        print("LINEUP OPTIMIZATION")
        print("="*80)
        
        team_predictions = self.get_team_predictions(current_week)
        team_predictions.sort(key=lambda x: x.improvement_points, reverse=True)
        
        for tp in team_predictions:
            improve_str = f"+{tp.improvement_points:.1f}" if tp.improvement_points > 0 else f"{tp.improvement_points:.1f}"
            print(f"\n{tp.user_name}:")
            print(f"  Current Lineup: {tp.current_projected:.1f} ± {tp.current_std:.1f} pts")
            print(f"  Optimal Lineup: {tp.optimal_projected:.1f} ± {tp.optimal_std:.1f} pts")
            if tp.improvement_points > 0.5:
                print(f"  ⚠️  Improvement Available: {improve_str} pts")
        
        # Run playoff simulations
        print(f"\n{'='*80}")
        print(f"PLAYOFF CHAMPIONSHIP PROBABILITIES ({self.num_simulations:,} simulations)")
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
        
        # Build output data
        output_data = {
            'league_id': self.league_id,
            'league_name': league_name,
            'current_week': current_week,
            'playoff_start_week': playoff_start,
            'is_playoffs': is_playoffs,
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
        
        print(f"\n💾 Saved predictions to: {output_path}")
        
        return output_data


def main():
    """Run playoff predictions for Dynasty league."""
    # Only Dynasty league has traditional playoffs
    # Chopped league uses a different format (last_chopped_leg) without playoff brackets
    DYNASTY_LEAGUE_ID = "1264304480178950144"
    
    print(f"\n\n{'#'*80}")
    print(f"# DYNASTY LEAGUE PLAYOFF PREDICTIONS")
    print(f"{'#'*80}")
    
    simulator = PlayoffSimulator(
        league_id=DYNASTY_LEAGUE_ID,
        season=2025,
        num_simulations=10000
    )
    
    # Use absolute path based on script location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, '..', 'website', 'public', 'data', 'dynasty_playoff_predictions.json')
    
    simulator.generate_predictions(output_path=output_path)


if __name__ == "__main__":
    main()
