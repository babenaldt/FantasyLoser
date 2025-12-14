"""
Generate player score predictions for Dynasty League matchups.
Uses the V7 model with red-zone features and calibration.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
from player_score_model_v7 import PlayerScoreModelV7
from scipy.stats import norm


def generate_dynasty_predictions():
    """Generate predictions for all dynasty league matchups."""
    print("\n" + "="*80)
    print("GENERATING PREDICTIONS FOR DYNASTY LEAGUE")
    print("="*80 + "\n")
    
    # Load dynasty league data
    print("Loading dynasty league data...")
    with open('../website/public/data/user_lineups_dynasty.json', 'r') as f:
        dynasty_data = json.load(f)
    
    current_week = dynasty_data['current_week']
    users = dynasty_data['users']
    
    print(f"League: {dynasty_data['league_name']}")
    print(f"Current Week: {current_week}")
    print(f"Users: {len(users)}\n")
    
    # Initialize model
    print("Initializing prediction model...")
    model = PlayerScoreModelV7(season=2025, verbose=False)
    print("✅ Model ready\n")
    
    # Generate predictions for each user's players
    print("Generating predictions for current week...")
    print("-" * 80)
    
    total_predictions = 0
    failed_predictions = 0
    
    # Update each player with predictions
    for user in users:
        for player in user['players']:
            player_id = player.get('player_id')
            player_name = player.get('player_name')
            
            if not player_id:
                continue
            
            try:
                pred = model.predict_player_for_week(player_id, current_week)
                if pred and pred.mean > 0:
                    player['predicted_points'] = round(pred.mean, 2)
                    player['predicted_std_dev'] = round(pred.std_dev, 2)
                    player['prob_10plus'] = round(100 * (1 - norm.cdf(10, pred.mean, pred.std_dev)), 1)
                    player['prob_15plus'] = round(100 * (1 - norm.cdf(15, pred.mean, pred.std_dev)), 1)
                    player['prob_20plus'] = round(100 * (1 - norm.cdf(20, pred.mean, pred.std_dev)), 1)
                    total_predictions += 1
                else:
                    player['predicted_points'] = None
                    failed_predictions += 1
            except Exception as e:
                player['predicted_points'] = None
                failed_predictions += 1
    
    print(f"\n✅ Generated {total_predictions} predictions")
    print(f"⚠️  Failed: {failed_predictions} players")
    
    # Save updated dynasty data
    output_path = '../website/public/data/user_lineups_dynasty_predictions.json'
    with open(output_path, 'w') as f:
        json.dump(dynasty_data, f, indent=2)
    print(f"\n💾 Saved to: {output_path}")
    
    # Calculate optimal lineups
    print("\n" + "="*80)
    print(f"RECOMMENDED STARTING LINEUPS (WEEK {current_week})")
    print("="*80)
    
    user_projections = []
    
    for user in users:
        user_name = user['user_name']
        players = user['players']
        
        # Get available players with predictions
        available = [p for p in players if p.get('predicted_points') and p.get('opponent') != 'BYE']
        
        # Sort by prediction
        qbs = sorted([p for p in available if p.get('position') == 'QB'], 
                     key=lambda x: x.get('predicted_points', 0), reverse=True)
        rbs = sorted([p for p in available if p.get('position') == 'RB'], 
                     key=lambda x: x.get('predicted_points', 0), reverse=True)
        wrs = sorted([p for p in available if p.get('position') == 'WR'], 
                     key=lambda x: x.get('predicted_points', 0), reverse=True)
        tes = sorted([p for p in available if p.get('position') == 'TE'], 
                     key=lambda x: x.get('predicted_points', 0), reverse=True)
        
        # Build lineup: 1 QB, 2 RB, 3 WR, 1 TE, 1 FLEX, 1 SUPERFLEX
        lineup = []
        total_projected = 0
        
        # QB
        if qbs:
            lineup.append(('QB', qbs[0]))
            total_projected += qbs[0].get('predicted_points', 0)
            qbs = qbs[1:]
        
        # RBs
        for i, rb in enumerate(rbs[:2]):
            lineup.append((f'RB{i+1}', rb))
            total_projected += rb.get('predicted_points', 0)
        rbs = rbs[2:]
        
        # WRs
        for i, wr in enumerate(wrs[:3]):
            lineup.append((f'WR{i+1}', wr))
            total_projected += wr.get('predicted_points', 0)
        wrs = wrs[3:]
        
        # TE
        if tes:
            lineup.append(('TE', tes[0]))
            total_projected += tes[0].get('predicted_points', 0)
            tes = tes[1:]
        
        # FLEX (best remaining RB/WR/TE)
        flex_options = rbs + wrs + tes
        flex_options.sort(key=lambda x: x.get('predicted_points', 0), reverse=True)
        if flex_options:
            flex = flex_options[0]
            lineup.append(('FLEX', flex))
            total_projected += flex.get('predicted_points', 0)
            flex_options = [f for f in flex_options if f['player_name'] != flex['player_name']]
        
        # SUPERFLEX (best remaining QB or flex eligible)
        sflex_options = qbs + flex_options
        sflex_options.sort(key=lambda x: x.get('predicted_points', 0), reverse=True)
        if sflex_options:
            sflex = sflex_options[0]
            lineup.append(('SFLEX', sflex))
            total_projected += sflex.get('predicted_points', 0)
        
        user_projections.append({
            'user_name': user_name,
            'total': total_projected,
            'lineup': lineup
        })
    
    # Sort by projected total
    user_projections.sort(key=lambda x: x['total'], reverse=True)
    
    print(f"\n{'Rank':<6} {'User':<25} {'Projected Points':>18}")
    print("-" * 52)
    for i, up in enumerate(user_projections, 1):
        print(f"{i:<6} {up['user_name']:<25} {up['total']:>18.1f}")
    
    # Print detailed lineups for top teams
    print("\n" + "="*80)
    print("DETAILED LINEUPS")
    print("="*80)
    
    for up in user_projections[:5]:
        print(f"\n{up['user_name']}: {up['total']:.1f} pts")
        print("-" * 60)
        for slot, player in up['lineup']:
            pts = player.get('predicted_points', 0)
            std = player.get('predicted_std_dev', 0)
            prob20 = player.get('prob_20plus', 0)
            print(f"  {slot:<6} {player['player_name']:<25} {player['position']:<4} {pts:>6.1f} ± {std:>4.1f}  ({prob20:>4.1f}% >20pts)")
    
    print("\n" + "="*80)
    print("PREDICTIONS COMPLETE")
    print("="*80)


if __name__ == "__main__":
    generate_dynasty_predictions()
