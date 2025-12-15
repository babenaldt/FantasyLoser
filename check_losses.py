import json

with open('website/public/data/season_stats_dynasty.json', 'r') as f:
    data = json.load(f)

print("Checking for losses in weekly data:\n")
current_week = data.get('current_week', 15)

losses = []
for team in data['teams']:
    for week in team['weekly_scores']:
        if week['week'] >= current_week:
            continue  # Skip current week
        
        win_loss_margin = week.get('win_loss_margin', 0)
        points = week.get('points', 0)
        
        if win_loss_margin < 0 and points > 0:
            losses.append({
                'owner': team['owner_name'],
                'week': week['week'],
                'points': points,
                'margin': win_loss_margin
            })

if losses:
    print(f"Found {len(losses)} losses")
    # Sort by points descending
    losses.sort(key=lambda x: x['points'], reverse=True)
    print("\nTop 5 highest scoring losses:")
    for i, loss in enumerate(losses[:5]):
        print(f"{i+1}. {loss['owner']} - Week {loss['week']}: {loss['points']:.1f} pts (lost by {abs(loss['margin']):.1f})")
else:
    print("No losses found with negative win_loss_margin!")
    print("\nSample weekly data:")
    team = data['teams'][0]
    for week in team['weekly_scores'][:3]:
        print(f"Week {week['week']}: points={week['points']:.1f}, win_loss_margin={week.get('win_loss_margin', 'MISSING')}, opponent_points={week.get('opponent_points', 'MISSING')}")
