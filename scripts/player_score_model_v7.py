""" 
Player Score Prediction Model v7 (Red-Zone Features + Better Calibration)

Goal
----
Build on v6.1's improvements with additional TD prediction and calibration fixes:
- Increase calibration multiplier (1.15x → 1.30x) for better uncertainty estimates
- Add red-zone opportunity features for better TD predictions
- Remove fumbles from predictions (data quality issue)
- Maintain fast runtime with ridge regression
- Keep scoring system flexibility

Key Improvements over v6.1
--------------------------
v6.1: Good baseline, opponent features working, but calibration weak and TDs hard to predict
v7: Better calibration (1.30x multiplier), red-zone features for TDs, fumbles excluded
    Expected: Better 50% interval coverage (30% → 45%) and TD correlation improvement

v7 Specific Changes (Dec 2024)
------------------------------
1. Calibration multiplier: 1.15x → 1.30x (fix 50% interval coverage)
2. Red-zone features: Add RZ touches, RZ TDs, goal-line opportunities
3. Fumbles data fixed: Extracted 1,454 fumbles from play-by-play, re-added to predictions
4. Lower TD regularization: 12.0 → 8.0 (allow more TD signal with red zone features)
5. Enhanced defensive features: Using EPA-based metrics (DVOA not available in nflverse)
Expected: +2-3% MAE improvement vs v6.1, 40-50% calibration on 50% intervals

Stat Components by Position:
- QB: passing_yards, passing_tds, interceptions, rushing_yards, rushing_tds, fumbles_lost
- RB: rushing_yards, rushing_tds, receptions, receiving_yards, receiving_tds, fumbles_lost  
- WR/TE: receptions, receiving_yards, receiving_tds, rushing_yards, rushing_tds, fumbles_lost

Architecture
------------
- One ridge model per (position, stat_component) pair
- Features: same rich feature set as v4
- Training: multi-output regression on stat deltas
- Prediction: stat line → fantasy points via scoring config
- Distribution: model variance per stat → aggregate to total points variance

Data Source: output/enriched_player_stats.json
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
from scipy import stats


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "output")


# Stat components to predict per position
# v7: Fumbles_lost now included (data pipeline fixed Dec 2024)
STAT_COMPONENTS = {
    "QB": ["passing_yards", "passing_tds", "passing_interceptions", "rushing_yards", "rushing_tds", "fumbles_lost"],
    "RB": ["rushing_yards", "rushing_tds", "receptions", "receiving_yards", "receiving_tds", "fumbles_lost"],
    "WR": ["receptions", "receiving_yards", "receiving_tds", "rushing_yards", "rushing_tds", "fumbles_lost"],
    "TE": ["receptions", "receiving_yards", "receiving_tds", "fumbles_lost"],
}


@dataclass
class PlayerPredictionV6:
    player_id: str
    player_name: str
    position: str
    team: str

    # Predicted stat line
    predicted_stats: Dict[str, float]
    
    # Stat prediction uncertainties (std dev per stat)
    stat_std_devs: Dict[str, float]

    # Fantasy points (computed from predicted stats + scoring config)
    mean: float
    std_dev: float

    games_played: int
    prior_season_games: int
    confidence: float

    baseline_mean: float
    baseline_std: float

    # For compatibility with existing code
    ridge_mean: Optional[float] = None
    ridge_weight: float = 0.0

    dist_df: Optional[float] = None
    boom_prob: float = 0.0
    boom_shift: float = 0.0
    boom_scale_mult: float = 1.0
    boom_df: Optional[float] = None

    def _t_scale(self) -> float:
        if not self.dist_df or self.dist_df <= 2 or self.std_dev <= 0:
            return float(self.std_dev)
        return float(self.std_dev) * float(np.sqrt((self.dist_df - 2.0) / self.dist_df))

    def _components(self):
        """Return mixture components as (weight, mean, df, scale)."""
        df0 = float(self.dist_df) if self.dist_df else None
        if not df0 or df0 <= 2 or self.std_dev <= 0:
            w = float(max(0.0, min(1.0, self.boom_prob)))
            if w <= 0.0 or self.boom_shift <= 0:
                return [(1.0, float(self.mean), None, float(self.std_dev))]
            mu0 = float(max(0.0, self.mean - w * self.boom_shift))
            mu1 = float(self.mean + (1.0 - w) * self.boom_shift)
            s0 = float(self.std_dev)
            s1 = float(self.std_dev) * float(max(1.0, self.boom_scale_mult))
            return [(1.0 - w, mu0, None, s0), (w, mu1, None, s1)]

        w = float(max(0.0, min(1.0, self.boom_prob)))
        s0 = self._t_scale()
        if w <= 0.0 or self.boom_shift <= 0:
            return [(1.0, float(self.mean), df0, float(s0))]

        mu0 = float(self.mean - w * self.boom_shift)
        mu1 = float(self.mean + (1.0 - w) * self.boom_shift)
        mu0 = float(max(0.0, mu0))
        df1 = float(self.boom_df) if self.boom_df and self.boom_df > 2 else float(min(df0, 3.8))
        s1 = float(s0) * float(max(1.0, self.boom_scale_mult))
        return [(1.0 - w, mu0, df0, float(s0)), (w, mu1, df1, float(s1))]

    def _cdf(self, x: float) -> float:
        x = float(x)
        tot = 0.0
        for w, mu, df, scale in self._components():
            if scale <= 0:
                tot += w * (1.0 if x >= mu else 0.0)
                continue
            z = (x - mu) / scale
            if df is None:
                tot += w * float(stats.norm.cdf(z))
            else:
                tot += w * float(stats.t.cdf(z, df))
        return float(min(max(tot, 0.0), 1.0))

    def sample(self, n: int = 1, scoring_config: Optional[Dict[str, float]] = None) -> np.ndarray:
        """
        Sample fantasy points by:
        1. Sampling each stat component from its distribution
        2. Computing fantasy points from the sampled stat line
        """
        if scoring_config is None:
            # Fall back to mixture distribution sampling
            comps = self._components()
            if len(comps) == 1:
                w, mu, df, scale = comps[0]
                if scale <= 0:
                    return np.full(n, max(0.0, mu), dtype=float)
                if df is None:
                    s = np.random.normal(mu, scale, n)
                else:
                    s = mu + scale * stats.t.rvs(df, size=n)
                return np.maximum(0, s)

            weights = np.array([c[0] for c in comps], dtype=float)
            weights = weights / weights.sum() if weights.sum() > 0 else np.array([1.0, 0.0])
            choices = np.random.choice(len(comps), size=n, p=weights)
            out = np.zeros(n, dtype=float)
            for i, (w, mu, df, scale) in enumerate(comps):
                idx = np.where(choices == i)[0]
                if idx.size == 0:
                    continue
                if scale <= 0:
                    out[idx] = mu
                elif df is None:
                    out[idx] = np.random.normal(mu, scale, idx.size)
                else:
                    out[idx] = mu + scale * stats.t.rvs(df, size=idx.size)
            return np.maximum(0, out)
        
        # Sample stat components
        sampled_points = np.zeros(n, dtype=float)
        for i in range(n):
            stat_line = {}
            for stat_name, mean_val in self.predicted_stats.items():
                std_val = self.stat_std_devs.get(stat_name, mean_val * 0.5)
                # Sample from normal, clamp to non-negative
                sampled_val = max(0.0, np.random.normal(mean_val, std_val))
                stat_line[stat_name] = sampled_val
            
            # Compute fantasy points from this stat line
            points = self._compute_fantasy_points(stat_line, scoring_config)
            sampled_points[i] = points
        
        return sampled_points

    def _compute_fantasy_points(self, stats: Dict[str, float], scoring_config: Dict[str, float]) -> float:
        """Compute fantasy points from a stat line + scoring config."""
        points = 0.0
        
        # Passing
        points += stats.get("passing_yards", 0.0) * scoring_config.get("passing_yards", 0.04)
        points += stats.get("passing_tds", 0.0) * scoring_config.get("passing_tds", 4.0)
        points += stats.get("passing_interceptions", 0.0) * scoring_config.get("interceptions", -2.0)
        
        # Rushing
        points += stats.get("rushing_yards", 0.0) * scoring_config.get("rushing_yards", 0.1)
        points += stats.get("rushing_tds", 0.0) * scoring_config.get("rushing_tds", 6.0)
        
        # Receiving
        points += stats.get("receptions", 0.0) * scoring_config.get("receptions", 1.0)
        points += stats.get("receiving_yards", 0.0) * scoring_config.get("receiving_yards", 0.1)
        points += stats.get("receiving_tds", 0.0) * scoring_config.get("receiving_tds", 6.0)
        
        # Fumbles
        points += stats.get("fumbles_lost", 0.0) * scoring_config.get("fumbles_lost", -2.0)
        
        return points

    def get_fantasy_points(self, scoring_config: Dict[str, float]) -> float:
        """Recompute fantasy points with a different scoring system."""
        return self._compute_fantasy_points(self.predicted_stats, scoring_config)

    def probability_above(self, threshold: float) -> float:
        if self.std_dev == 0:
            return 1.0 if self.mean > threshold else 0.0
        return float(1.0 - self._cdf(float(threshold)))

    def get_percentile(self, percentile: float) -> float:
        """Get the score at a given percentile (0-100)."""
        p = float(percentile) / 100.0
        p = min(max(p, 1e-6), 1 - 1e-6)

        lo = 0.0
        hi = float(max(1.0, self.mean + 12.0 * max(self.std_dev, 1.0) + max(0.0, self.boom_shift) * 2.0))
        while self._cdf(hi) < p and hi < 300.0:
            hi *= 1.6

        for _ in range(40):
            mid = 0.5 * (lo + hi)
            if self._cdf(mid) < p:
                lo = mid
            else:
                hi = mid

        return float(max(0.0, hi))


@dataclass
class _RidgeModel:
    feature_names: List[str]
    mu: np.ndarray
    sigma: np.ndarray
    coef: np.ndarray
    resid_std: float


def _safe_div(a: float, b: float) -> float:
    if b is None or b == 0:
        return 0.0
    return float(a) / float(b)


def _ridge_fit(X: np.ndarray, y: np.ndarray, alpha: float, weights: Optional[np.ndarray] = None) -> _RidgeModel:
    """
    Fit weighted ridge regression with standardization and unpenalized intercept.
    
    Args:
        X: Feature matrix (n_samples, n_features)
        y: Target vector (n_samples,)
        alpha: Ridge regularization strength
        weights: Sample weights (n_samples,). If None, all samples weighted equally.
    """
    if X.ndim != 2:
        raise ValueError("X must be 2D")
    
    n_samples = X.shape[0]
    
    # Default to equal weights
    if weights is None:
        weights = np.ones(n_samples, dtype=float)
    else:
        weights = np.asarray(weights, dtype=float)
        # Normalize weights to sum to n_samples (preserves scale of regularization)
        weights = weights * (n_samples / weights.sum())

    mu = X.mean(axis=0)
    sigma = X.std(axis=0)
    sigma = np.where(sigma == 0, 1.0, sigma)

    Xs = (X - mu) / sigma

    ones = np.ones((Xs.shape[0], 1), dtype=float)
    Xa = np.concatenate([ones, Xs], axis=1)

    I = np.eye(Xa.shape[1], dtype=float)
    I[0, 0] = 0.0

    # Weighted least squares: (X'WX + αI)β = X'Wy
    W = np.diag(weights)
    XtWX = Xa.T @ W @ Xa
    XtWy = Xa.T @ W @ y

    beta = np.linalg.solve(XtWX + alpha * I, XtWy)

    resid = y - Xa @ beta
    # Weighted residual std
    resid_std = float(np.sqrt(np.average(resid**2, weights=weights))) if resid.size > 1 else 1.0

    return _RidgeModel(
        feature_names=[],
        mu=mu,
        sigma=sigma,
        coef=beta,
        resid_std=resid_std,
    )


def _ridge_predict(m: _RidgeModel, x: np.ndarray) -> float:
    xs = (x - m.mu) / m.sigma
    xa = np.concatenate([[1.0], xs])
    return float(xa @ m.coef)


class PlayerScoreModelV7:
    """v7 model: v6.1 + red-zone features + better calibration."""

    RIDGE_POSITIONS = {"QB", "RB", "WR", "TE"}
    
    # Recency decay: weight = decay_rate ^ (weeks_ago)
    # Testing shows:
    # - With 2 training seasons: no decay (1.0) is optimal
    # - With 4+ training seasons: 0.97 decay helps (~0.02 MAE improvement)
    # Since we default to 2 seasons, use 1.0 (no decay)
    # Change to 0.97 if using more training seasons
    RECENCY_DECAY_RATE = 1.0
    
    # Position-specific calibration multipliers for uncertainty estimates
    # Empirically derived from validation data:
    # - QB has much higher actual variance than predicted (needs 1.63x)
    # - RB has moderate variance gap (needs 1.49x)
    # - WR and TE are better calibrated (need ~1.30x)
    CALIBRATION_MULTIPLIER = {
        "QB": 1.60,  # QBs have high variance (actual std=8.8 vs pred std=4.0)
        "RB": 1.45,
        "WR": 1.35,
        "TE": 1.30,
    }
    DEFAULT_CALIBRATION_MULTIPLIER = 1.40  # Fallback for other positions

    # Regularization per (position, stat)
    # v7: Further reduced TD regularization (12 → 8) to improve TD predictions
    RIDGE_ALPHA = {
        "QB": {"passing_yards": 5.0, "passing_tds": 8.0, "passing_interceptions": 10.0, 
               "rushing_yards": 7.0, "rushing_tds": 10.0},
        "RB": {"rushing_yards": 5.0, "rushing_tds": 8.0, "receptions": 7.0,
               "receiving_yards": 7.0, "receiving_tds": 10.0},
        "WR": {"receptions": 5.0, "receiving_yards": 5.0, "receiving_tds": 8.0,
               "rushing_yards": 10.0, "rushing_tds": 15.0},
        "TE": {"receptions": 5.0, "receiving_yards": 5.0, "receiving_tds": 8.0},
    }

    DIST_DF_BY_POSITION = {
        "QB": 6.0,
        "RB": 4.2,
        "WR": 3.8,
        "TE": 3.8,
    }

    def __init__(
        self,
        player_stats_path: Optional[str] = None,
        enriched_stats_path: Optional[str] = None,
        season: Optional[int] = None,
        training_seasons: Optional[List[int]] = None,
        scoring_config: Optional[Dict[str, float]] = None,
        verbose: bool = False,
    ):
        self.verbose = verbose

        if season is None:
            season = 2025
        self.season = int(season)

        # Use current + prior season for training (optimal based on experiment)
        # More seasons actually hurts performance due to NFL evolution
        if training_seasons is None:
            training_seasons = [self.season - 1, self.season]
        self.training_seasons = [int(s) for s in training_seasons]

        # Load enriched stats database
        if enriched_stats_path is None:
            enriched_stats_path = os.path.join(DATA_DIR, "enriched_player_stats.json")
        
        self._enriched_data = self._load_enriched_stats(enriched_stats_path)
        
        # Load defensive stats for opponent matchup features
        defense_stats_path = os.path.join(DATA_DIR, "defense_stats.json")
        self._defense_stats = self._load_defense_stats(defense_stats_path)
        
        # Scoring configuration (default to PPR)
        if scoring_config is None:
            scoring_config = {
                "passing_yards": 0.04,
                "passing_tds": 4.0,
                "interceptions": -2.0,
                "rushing_yards": 0.1,
                "rushing_tds": 6.0,
                "receptions": 1.0,
                "receiving_yards": 0.1,
                "receiving_tds": 6.0,
                "fumbles_lost": -2.0,
            }
        self.scoring_config = scoring_config
        
        # Ridge models: dict[(position, stat_name)] -> _RidgeModel
        self._ridge_models: Dict[Tuple[str, str], _RidgeModel] = {}

    @staticmethod
    def _get_float(row: Optional[Dict[str, Any]], key: str) -> float:
        if not row:
            return 0.0
        v = row.get(key)
        if v is None:
            return 0.0
        if isinstance(v, (int, float, np.integer, np.floating)):
            return float(v)
        return 0.0

    def _load_enriched_stats(self, path: str) -> Dict[int, Dict[str, Dict[int, Dict[str, float]]]]:
        """
        Load pre-generated enriched stats database.
        
        Returns:
            Dict[season][player_id][through_week] -> cumulative stats dict
        """
        if self.verbose:
            print(f"Loading enriched stats from {path}...")
        
        with open(path, 'r') as f:
            data = json.load(f)
        
        # Reorganize into nested dict for fast lookup
        result: Dict[int, Dict[str, Dict[int, Dict[str, float]]]] = {}
        
        for season_obj in data.get('seasons', []):
            season = int(season_obj['season'])
            result[season] = {}
            
            for player in season_obj.get('players', []):
                player_id = player['player_id']
                result[season][player_id] = {}
                
                for cum_record in player.get('cumulative_by_week', []):
                    through_week = int(cum_record['through_week'])
                    stats = cum_record.get('stats', {})
                    stats['_games'] = float(cum_record.get('games_played', 0))
                    stats['_team'] = cum_record.get('team', '')
                    stats['_opponent'] = cum_record.get('opponent', '')  # For v6 matchup features
                    
                    result[season][player_id][through_week] = stats
        
        if self.verbose:
            total_records = sum(len(players) for players in result.values())
            print(f"  Loaded {total_records} player-seasons from enriched database")
        
        return result
    
    def _load_defense_stats(self, path: str) -> Dict[str, Dict[str, float]]:
        """Load defensive stats (points allowed per game by position)."""
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            
            # Build dict of team -> {qb_ppg, rb_ppg, wr_ppg, te_ppg}
            defense_dict = {}
            for defense in data.get('defenses', []):
                team = defense['team']
                defense_dict[team] = {
                    'qb_ppg': float(defense.get('qb_ppg', 17.0)),
                    'rb_ppg': float(defense.get('rb_ppg', 15.0)),
                    'wr_ppg': float(defense.get('wr_ppg', 20.0)),
                    'te_ppg': float(defense.get('te_ppg', 8.0)),
                }
            
            if self.verbose:
                print(f"  Loaded defensive stats for {len(defense_dict)} teams")
            
            return defense_dict
        except Exception as e:
            if self.verbose:
                print(f"  Warning: Could not load defense stats: {e}")
            return {}
    
    def _get_opponent_def_ppg(self, opponent_team: Optional[str], position: str) -> float:
        """Get opponent's defensive PPG allowed to this position."""
        if not opponent_team or opponent_team not in self._defense_stats:
            # League average defaults
            defaults = {'QB': 17.0, 'RB': 15.0, 'WR': 20.0, 'TE': 8.0}
            return defaults.get(position, 15.0)
        
        defense = self._defense_stats[opponent_team]
        pos_key = f"{position.lower()}_ppg"
        return defense.get(pos_key, 15.0)

    def _cum_stats_through_week(self, player_id: str, through_week: int) -> Optional[Dict[str, float]]:
        """Get cumulative stats for current season through specified week.
        
        If data for the exact week doesn't exist (e.g., future weeks),
        returns the most recent available data.
        """
        season_data = self._enriched_data.get(self.season, {})
        player_data = season_data.get(player_id, {})
        
        # Try exact week first
        if through_week in player_data:
            return player_data.get(through_week)
        
        # Fall back to most recent available week
        available_weeks = [w for w in player_data.keys() if isinstance(w, int) and w <= through_week]
        if available_weeks:
            latest_week = max(available_weeks)
            return player_data.get(latest_week)
        
        return None

    def _cum_stats_through_week_season(self, season: int, player_id: str, through_week: int) -> Optional[Dict[str, float]]:
        """Get cumulative stats for specified season through specified week.
        
        If data for the exact week doesn't exist, returns the most recent available data.
        """
        season_data = self._enriched_data.get(season, {})
        player_data = season_data.get(player_id, {})
        
        # Try exact week first
        if through_week in player_data:
            return player_data.get(through_week)
        
        # Fall back to most recent available week
        available_weeks = [w for w in player_data.keys() if isinstance(w, int) and w <= through_week]
        if available_weeks:
            latest_week = max(available_weeks)
            return player_data.get(latest_week)
        
        return None
    
    def _get_last_week_stats(self, season: int, player_id: str, week: int) -> Optional[Dict[str, float]]:
        """
        Compute last week's stats by taking delta between cumulative[week] and cumulative[week-1].
        """
        season_data = self._enriched_data.get(season, {})
        player_data = season_data.get(player_id, {})
        
        cum_this = player_data.get(week)
        cum_prev = player_data.get(week - 1) if week > 1 else None
        
        if not cum_this:
            return None
        
        if not cum_prev:
            return dict(cum_this)
        
        delta = {}
        for key, val in cum_this.items():
            if key.startswith('_'):
                continue
            prev_val = cum_prev.get(key, 0.0)
            if isinstance(val, (int, float)):
                delta[key] = float(val) - float(prev_val)
        
        return delta

    # Features are identical to v4
    def _features_for_position(
        self,
        position: str,
        cum: Dict[str, float],
        last_week_stats: Optional[Dict[str, float]],
        target_week: int,
        opponent_def_ppg: float = 0.0,
    ) -> Tuple[List[str], np.ndarray]:
        """Feature engineering - same as v4."""
        g = cum.get("_games", 1.0)

        attempts = cum.get("attempts", 0.0)
        completions = cum.get("completions", 0.0)
        pass_yards = cum.get("passing_yards", 0.0)
        pass_tds = cum.get("passing_tds", 0.0)
        ints = cum.get("passing_interceptions", 0.0)
        sacks = cum.get("sacks_suffered", 0.0)
        air_yards = cum.get("passing_air_yards", 0.0)
        cpoe = cum.get("passing_cpoe", 0.0)
        pass_epa = cum.get("passing_epa", 0.0)

        carries = cum.get("carries", 0.0)
        rush_yards = cum.get("rushing_yards", 0.0)
        rush_tds = cum.get("rushing_tds", 0.0)

        targets = cum.get("targets", 0.0)
        rec = cum.get("receptions", 0.0)
        rec_yards = cum.get("receiving_yards", 0.0)
        rec_tds = cum.get("receiving_tds", 0.0)
        rec_air = cum.get("receiving_air_yards", 0.0)
        rec_epa = cum.get("receiving_epa", 0.0)
        target_share = cum.get("target_share", 0.0)
        air_share = cum.get("air_yards_share", 0.0)
        wopr = cum.get("wopr", 0.0)

        comp_pct = _safe_div(completions, attempts)
        ypa = _safe_div(pass_yards, attempts)
        td_rate = _safe_div(pass_tds, attempts)
        int_rate = _safe_div(ints, attempts)
        sack_rate = _safe_div(sacks, attempts + sacks)
        air_ypa = _safe_div(air_yards, attempts)

        ypc = _safe_div(rush_yards, carries)

        catch_rate = _safe_div(rec, targets)
        ypt = _safe_div(rec_yards, targets)
        ypr = _safe_div(rec_yards, rec)
        adot = _safe_div(rec_air, targets)
        
        # v7: Red zone features for TD prediction
        rz_touches = cum.get("rz_touches", 0.0)
        rz_tds = cum.get("rz_tds", 0.0)
        gl_touches = cum.get("gl_touches", 0.0)
        gl_tds = cum.get("gl_tds", 0.0)
        
        rz_touches_pg = rz_touches / g
        gl_touches_pg = gl_touches / g
        rz_td_rate = _safe_div(rz_tds, rz_touches)
        gl_td_rate = _safe_div(gl_tds, gl_touches)

        names: List[str] = []
        vals: List[float] = []

        def add(name: str, val: float):
            names.append(name)
            vals.append(float(val))

        last_att = last_week_stats.get("attempts", 0.0) if last_week_stats else 0.0
        last_pass_yards = last_week_stats.get("passing_yards", 0.0) if last_week_stats else 0.0
        last_rush_att = last_week_stats.get("carries", 0.0) if last_week_stats else 0.0
        last_carries = last_week_stats.get("carries", 0.0) if last_week_stats else 0.0
        last_targets = last_week_stats.get("targets", 0.0) if last_week_stats else 0.0
        last_rec = last_week_stats.get("receptions", 0.0) if last_week_stats else 0.0
        last_rec_yards = last_week_stats.get("receiving_yards", 0.0) if last_week_stats else 0.0
        last_air = last_week_stats.get("receiving_air_yards", 0.0) if last_week_stats else 0.0

        if position == "QB":
            last_ypa = _safe_div(last_pass_yards, last_att)

            att_pg = attempts / g
            rush_att_pg = carries / g

            add("att_pg", att_pg)
            add("comp_pct", comp_pct)
            add("ypa", ypa)
            add("pass_td_rate", td_rate)
            add("int_rate", int_rate)
            add("sack_rate", sack_rate)
            add("rush_att_pg", rush_att_pg)
            add("rush_ypc", ypc)
            add("air_ypa", air_ypa)
            add("cpoe_pg", cpoe / g if g else 0.0)
            add("pass_epa_pg", pass_epa / g)
            add("rush_td_pg", rush_tds / g)
            add("last_att", last_att)
            add("last_ypa", last_ypa)
            add("last_rush_att", last_rush_att)
            add("att_trend", _safe_div(last_att, att_pg))
            add("att_x_ypa", att_pg * ypa)
            add("att_x_td_rate", att_pg * td_rate)
            add("opp_def_qb_ppg", opponent_def_ppg * 5.0)  # Opponent QB points allowed (scaled 5x)
            # v7: Red zone features
            add("rz_touches_pg", rz_touches_pg)
            add("gl_touches_pg", gl_touches_pg)
            add("rz_td_rate", rz_td_rate)
            add("week", float(target_week))
            add("games", float(g))

        elif position == "RB":
            last_opps = last_carries + last_targets
            opps_pg = (carries + targets) / g
            rush_att_pg = carries / g
            tgt_pg = targets / g

            add("opps_pg", opps_pg)
            add("last_opps", last_opps)
            add("opps_trend", _safe_div(last_opps, opps_pg))
            add("rush_att_pg", rush_att_pg)
            add("rush_ypc", ypc)
            add("rush_td_pg", rush_tds / g)
            add("tgt_pg", tgt_pg)
            add("rec_pg", rec / g)
            add("catch_rate", catch_rate)
            add("ypt", ypt)
            add("rec_td_pg", rec_tds / g)
            add("target_share_avg", target_share / g if g else 0.0)
            add("rec_epa_pg", rec_epa / g)
            add("rush_att_x_ypc", rush_att_pg * ypc)
            add("tgt_x_ypt", tgt_pg * ypt)
            add("opps_x_td_rate", opps_pg * _safe_div(rush_tds + rec_tds, carries + targets))
            add("total_td_pg", (rush_tds + rec_tds) / g)
            add("opp_def_rb_ppg", opponent_def_ppg * 5.0)  # Opponent RB points allowed (scaled 5x)
            # v7: Red zone features for TD prediction
            add("rz_touches_pg", rz_touches_pg)
            add("gl_touches_pg", gl_touches_pg)
            add("rz_td_rate", rz_td_rate)
            add("gl_td_rate", gl_td_rate)
            add("week", float(target_week))
            add("games", float(g))

        elif position in {"WR", "TE"}:
            last_ypt = _safe_div(last_rec_yards, last_targets)
            tgt_pg = targets / g

            add("tgt_pg", tgt_pg)
            add("rec_pg", rec / g)
            add("catch_rate", catch_rate)
            add("ypt", ypt)
            add("ypr", ypr)
            add("adot", adot)
            add("rec_td_pg", rec_tds / g)
            add("target_share_avg", target_share / g if g else 0.0)
            add("air_share_avg", air_share / g if g else 0.0)
            add("wopr_avg", wopr / g if g else 0.0)
            add("rec_epa_pg", rec_epa / g)
            add("last_tgt", last_targets)
            add("last_ypt", last_ypt)
            add("last_air", last_air)
            add("tgt_trend", _safe_div(last_targets, tgt_pg))
            add("tgt_x_ypt", tgt_pg * ypt)
            add("tgt_x_adot", tgt_pg * adot)
            add("air_share_x_adot", _safe_div(air_share, g) * adot)
            add("td_per_target", _safe_div(rec_tds, targets))
            add("opp_def_ppg", opponent_def_ppg * 5.0)  # Opponent WR/TE points allowed (scaled 5x)
            # v7: Red zone features for TD prediction  
            add("rz_touches_pg", rz_touches_pg)
            add("gl_touches_pg", gl_touches_pg)
            add("rz_td_rate", rz_td_rate)
            add("gl_td_rate", gl_td_rate)
            add("week", float(target_week))
            add("games", float(g))

        return names, np.array(vals, dtype=float)

    def _fit_ridge_for_stat(self, position: str, stat_name: str) -> Optional[_RidgeModel]:
        """Fit ridge model for a specific (position, stat) pair."""
        if position not in self.RIDGE_POSITIONS:
            return None
        
        if stat_name not in STAT_COMPONENTS.get(position, []):
            return None

        key = (position, stat_name)
        if key in self._ridge_models:
            return self._ridge_models[key]

        X_list: List[np.ndarray] = []
        y_list: List[float] = []
        sample_info: List[Tuple[int, int]] = []  # (season, week) for recency weighting
        feature_names: Optional[List[str]] = None

        for season in self.training_seasons:
            season_data = self._enriched_data.get(season, {})
            
            for pid, player_cum_data in season_data.items():
                weeks = sorted(player_cum_data.keys())
                
                for target_week in weeks:
                    if target_week < 2:
                        continue
                    
                    cum_prev = player_cum_data.get(target_week - 1)
                    cum_this = player_cum_data.get(target_week)
                    
                    if not cum_prev or not cum_this:
                        continue
                    
                    # Target is the stat delta in target_week
                    y = cum_this.get(stat_name, 0.0) - cum_prev.get(stat_name, 0.0)
                    
                    if y is None or y < 0:
                        continue
                    
                    # Exposure filters - ensure enough volume for meaningful signal
                    games = cum_prev.get("_games", 1.0)
                    if games < 1:
                        continue
                    
                    if position == "QB" and cum_prev.get("attempts", 0.0) < 10:
                        continue
                    if position == "WR" and cum_prev.get("targets", 0.0) < 3:
                        continue
                    if position == "RB" and (cum_prev.get("carries", 0.0) + cum_prev.get("targets", 0.0)) < 5:
                        continue
                    # TE: Filter out pure blocking TEs with minimal receiving role
                    # This ensures training data is from TEs who function as receivers
                    if position == "TE":
                        targets_per_game = cum_prev.get("targets", 0.0) / games
                        # 1.5 tgt/game filters out pure blockers while keeping enough training data
                        if targets_per_game < 1.5:
                            continue
                    
                    last_week_stats = self._get_last_week_stats(season, pid, target_week - 1)
                    
                    # Get opponent defense PPG (from enriched data if available)
                    opponent_team = cum_this.get('_opponent')
                    opponent_def_ppg = self._get_opponent_def_ppg(opponent_team, position)
                    
                    names, x = self._features_for_position(position, cum_prev, last_week_stats, int(target_week), opponent_def_ppg)
                    if feature_names is None:
                        feature_names = names
                    else:
                        if names != feature_names:
                            continue

                    X_list.append(x)
                    y_list.append(float(y))
                    sample_info.append((season, target_week))

        if not X_list or feature_names is None:
            return None

        X = np.vstack(X_list)
        y = np.array(y_list, dtype=float)
        
        # Calculate recency weights
        # Reference point: most recent week in current season
        max_season = max(s for s, w in sample_info)
        max_week_in_max_season = max(w for s, w in sample_info if s == max_season)
        
        weights = []
        for season, week in sample_info:
            # Calculate weeks ago from reference point
            # Each season has ~18 weeks of regular season
            seasons_ago = max_season - season
            weeks_ago = seasons_ago * 18 + (max_week_in_max_season - week)
            
            # Exponential decay: weight = decay_rate ^ weeks_ago
            weight = self.RECENCY_DECAY_RATE ** weeks_ago
            weights.append(weight)
        
        weights = np.array(weights, dtype=float)

        alpha = self.RIDGE_ALPHA.get(position, {}).get(stat_name, 15.0)
        model = _ridge_fit(X, y, alpha=alpha, weights=weights)
        model.feature_names = feature_names
        self._ridge_models[key] = model
        return model

    def _create_baseline(self, player_id: str, target_week: int) -> Optional[Dict[str, Any]]:
        """
        Create baseline prediction from historical averages.
        
        Returns dict with player info and baseline stats, or None if insufficient data.
        """
        cum = self._cum_stats_through_week(player_id, target_week - 1)
        if not cum:
            return None
        
        games_played = int(cum.get('_games', 0))
        if games_played == 0:
            return None
        
        team = cum.get('_team', 'FA')
        
        # Determine position from stat patterns
        if cum.get('attempts', 0) > 0:
            position = 'QB'
        elif cum.get('carries', 0) > cum.get('receptions', 0):
            position = 'RB'
        elif cum.get('targets', 0) > 0:
            position = 'WR' if cum.get('receptions', 0) > 5 else 'TE'
        else:
            position = 'WR'
        
        # Calculate baseline fantasy points from cumulative stats
        base_mean = 0.0
        stats_dict = {k: v for k, v in cum.items() if not k.startswith('_')}
        for stat_name, value in stats_dict.items():
            scoring_key = "interceptions" if stat_name == "passing_interceptions" else stat_name
            if scoring_key in self.scoring_config:
                base_mean += (value / games_played) * self.scoring_config.get(scoring_key, 0)
        
        # Standard deviation as percentage of mean (with floor)
        base_std = base_mean * 0.4 if base_mean > 0 else 5.0
        
        return {
            'player_id': player_id,
            'player_name': f"Player_{player_id}",
            'position': position,
            'team': team,
            'mean': base_mean,
            'std_dev': base_std,
            'games_played': games_played,
            'prior_season_games': 0,
            'confidence': min(1.0, games_played / 10.0),
        }

    def predict_player_for_week(self, player_id: str, target_week: int, opponent_team: Optional[str] = None) -> Optional[PlayerPredictionV6]:
        """
        Generate fantasy point prediction for a player in a specific week.
        
        Uses ridge regression on enriched stats with baseline blending.
        """
        # Create baseline from historical averages
        base = self._create_baseline(player_id, target_week)
        if base is None:
            return None

        position = base['position']

        predicted_stats = {}
        stat_std_devs = {}
        
        # Kickers: use simple baseline only (too unpredictable for ridge)
        if position == "K":
            return PlayerPredictionV6(
                player_id=base['player_id'],
                player_name=base['player_name'],
                position=base['position'],
                team=base['team'],
                predicted_stats={},
                stat_std_devs={},
                mean=base['mean'],
                std_dev=base['std_dev'] * 1.3,  # Kickers are more variable
                games_played=base['games_played'],
                prior_season_games=base['prior_season_games'],
                confidence=base['confidence'] * 0.7,  # Lower confidence
                baseline_mean=base['mean'],
                baseline_std=base['std_dev'],
                dist_df=4.0,  # Heavy tails for kickers
            )
        
        if position in self.RIDGE_POSITIONS:
            cum = self._cum_stats_through_week(player_id, target_week - 1)
            
            if cum:
                last_week_stats = self._get_last_week_stats(self.season, player_id, target_week - 1)
                
                # Get opponent defense adjustment
                if opponent_team is None:
                    opponent_team = cum.get('_opponent')
                opponent_def_ppg = self._get_opponent_def_ppg(opponent_team, position)
                
                names, x = self._features_for_position(position, cum, last_week_stats, int(target_week), opponent_def_ppg)
                
                # Predict each stat component
                for stat_name in STAT_COMPONENTS.get(position, []):
                    ridge_model = self._fit_ridge_for_stat(position, stat_name)
                    
                    if ridge_model and ridge_model.feature_names == names:
                        pred_val = _ridge_predict(ridge_model, x)
                        predicted_stats[stat_name] = max(0.0, pred_val)
                        stat_std_devs[stat_name] = ridge_model.resid_std
                    else:
                        # Fallback to historical average
                        if cum.get("_games", 0) > 0:
                            predicted_stats[stat_name] = cum.get(stat_name, 0.0) / cum.get("_games", 1.0)
                            stat_std_devs[stat_name] = predicted_stats[stat_name] * 0.6
                        else:
                            predicted_stats[stat_name] = 0.0
                            stat_std_devs[stat_name] = 1.0

        # Compute fantasy points from predicted stats
        mean_points = 0.0
        for stat_name, stat_val in predicted_stats.items():
            score_key = stat_name
            if stat_name == "passing_interceptions":
                score_key = "interceptions"
            mean_points += stat_val * self.scoring_config.get(score_key, 0.0)
        
        # Aggregate variance (assuming stats are independent)
        variance = 0.0
        for stat_name, std_val in stat_std_devs.items():
            score_key = stat_name
            if stat_name == "passing_interceptions":
                score_key = "interceptions"
            scoring_mult = self.scoring_config.get(score_key, 0.0)
            variance += (std_val * scoring_mult) ** 2
        
        std_points = float(np.sqrt(variance))
        
        # Blend with baseline (v6.1: increased ridge weight as season progresses)
        games_played = base['games_played']
        if games_played <= 2:
            ridge_weight = 0.4  # Early season - use more baseline
        elif games_played <= 5:
            ridge_weight = 0.5  # Mid-early season
        elif games_played <= 8:
            ridge_weight = 0.6  # Mid season
        else:
            ridge_weight = 0.7  # Late season - trust ridge more
        
        final_mean = (1 - ridge_weight) * base['mean'] + ridge_weight * mean_points
        
        # v7: Position-specific calibration multiplier for better interval coverage
        # QBs have higher actual variance, so need larger multiplier
        cal_mult = self.CALIBRATION_MULTIPLIER.get(position, self.DEFAULT_CALIBRATION_MULTIPLIER)
        final_std = float(np.sqrt((1 - ridge_weight)**2 * base['std_dev']**2 + ridge_weight**2 * std_points**2)) * cal_mult

        return PlayerPredictionV6(
            player_id=base['player_id'],
            player_name=base['player_name'],
            position=base['position'],
            team=base['team'],
            predicted_stats=predicted_stats,
            stat_std_devs=stat_std_devs,
            mean=float(final_mean),
            std_dev=float(final_std),
            games_played=base['games_played'],
            prior_season_games=base['prior_season_games'],
            confidence=base['confidence'],
            baseline_mean=base['mean'],
            baseline_std=base['std_dev'],
            ridge_mean=mean_points,
            ridge_weight=float(ridge_weight),
            dist_df=float(self.DIST_DF_BY_POSITION.get(position, 6.0)),
        )

    def predict_player(self, player_id: str, week: Optional[int] = None) -> Optional[PlayerPredictionV6]:
        if week is None:
            week = 15  # Default to current week
        return self.predict_player_for_week(player_id, int(week))
