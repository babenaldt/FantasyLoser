"""HTML report generator for fantasy football season stats."""

def calculate_awards(season_stats, is_chopped):
    """Calculate individual awards based on stats."""
    awards = {}
   
    # Filter out teams with no weeks played
    active_stats = [s for s in season_stats if s.get("weeks_played", 0) > 0]
    if not active_stats:
        return awards
   
    # For most awards (except weekly high/low), require at least 5 games played
    qualified_stats = [s for s in active_stats if s.get("weeks_played", 0) >= 5]
   
    # Highest scorer (season total)
    if qualified_stats:
        highest_scorer = max(qualified_stats, key=lambda x: x.get("total_points_scored", 0))
        awards["Highest Scorer"] = {
            "winner": highest_scorer["owner_name"],
            "value": f"{highest_scorer.get('total_points_scored', 0):.1f} points",
            "icon": "🏆"
        }
   
    # Best efficiency
    if qualified_stats:
        best_efficiency = max(qualified_stats, key=lambda x: x.get("efficiency_rate", 0))
        awards["Best Manager"] = {
            "winner": best_efficiency["owner_name"],
            "value": f"{best_efficiency.get('efficiency_rate', 0):.1f}% efficiency",
            "icon": "🎯"
        }
   
    # Most consistent
    if qualified_stats:
        most_consistent = max(qualified_stats, key=lambda x: x.get("consistency_score", 0))
        awards["Most Consistent"] = {
            "winner": most_consistent["owner_name"],
            "value": f"{most_consistent.get('consistency_score', 0):.2f} consistency",
            "icon": "📊"
        }
   
    # Best waiver wire
    if qualified_stats:
        best_waiver = max(qualified_stats, key=lambda x: x.get("faab_efficiency", 0))
        if best_waiver.get("faab_efficiency", 0) > 0:
            awards["Waiver Wire Wizard"] = {
                "winner": best_waiver["owner_name"],
                "value": f"{best_waiver.get('faab_efficiency', 0):.2f} Pt/$",
                "icon": "🔮"
            }
   
    # Worst bench management (most points left on bench)
    if qualified_stats:
        worst_bench = max(qualified_stats, key=lambda x: x.get("points_left_on_bench", 0))
        awards["Bench Warmer Award"] = {
            "winner": worst_bench["owner_name"],
            "value": f"{worst_bench.get('points_left_on_bench', 0):.1f} pts on bench",
            "icon": "🪑"
        }
   
    # Highest single week score (all teams, no minimum games)
    best_week_team = None
    best_week_score = 0
    best_week_num = 0
    for s in active_stats:
        for week_data in s.get("weeks", []):
            if week_data["points"] > best_week_score:
                best_week_score = week_data["points"]
                best_week_team = s["owner_name"]
                best_week_num = week_data["week"]
   
    if best_week_team:
        awards["Highest Weekly Score"] = {
            "winner": best_week_team,
            "value": f"{best_week_score:.1f} pts (Week {best_week_num})",
            "icon": "🔥"
        }
   
    # Lowest single week score (all teams, no minimum games, excluding 0s from eliminated teams)
    worst_week_team = None
    worst_week_score = float('inf')
    worst_week_num = 0
    for s in active_stats:
        for week_data in s.get("weeks", []):
            if week_data["points"] > 0 and week_data["points"] < worst_week_score:
                worst_week_score = week_data["points"]
                worst_week_team = s["owner_name"]
                worst_week_num = week_data["week"]
   
    if worst_week_team and worst_week_score != float('inf'):
        awards["Lowest Weekly Score"] = {
            "winner": worst_week_team,
            "value": f"{worst_week_score:.1f} pts (Week {worst_week_num})",
            "icon": "💩"
        }
   
    if is_chopped:
        # Chopped-specific awards
        # Highest average score (for teams that got eliminated early but scored well)
        if active_stats:
            highest_avg = max(active_stats, key=lambda x: x.get("average_points", 0))
            awards["Highest Average Score"] = {
                "winner": highest_avg["owner_name"],
                "value": f"{highest_avg.get('average_points', 0):.1f} avg PPG",
                "icon": "⭐"
            }
       
        # Unluckiest Chop - team eliminated with score closest to league average
        eliminated_stats = [s for s in active_stats if s.get("eliminated_week") is not None]
        if eliminated_stats:
            unluckiest_chop = None
            smallest_diff = float('inf')
           
            for team in eliminated_stats:
                elim_week = team.get("eliminated_week")
                if elim_week:
                    # Find their score in the elimination week
                    elim_score = None
                    for week_data in team.get("weeks", []):
                        if week_data["week"] == elim_week:
                            elim_score = week_data["points"]
                            break
                   
                    if elim_score and elim_score > 0:
                        # Calculate league average for that week (excluding 0s)
                        week_scores = []
                        for s in active_stats:
                            for week_data in s.get("weeks", []):
                                if week_data["week"] == elim_week and week_data["points"] > 0:
                                    week_scores.append(week_data["points"])
                       
                        if week_scores:
                            league_avg = sum(week_scores) / len(week_scores)
                            diff = abs(elim_score - league_avg)
                           
                            if diff < smallest_diff:
                                smallest_diff = diff
                                unluckiest_chop = {
                                    "team": team,
                                    "elim_score": elim_score,
                                    "league_avg": league_avg,
                                    "elim_week": elim_week
                                }
           
            if unluckiest_chop:
                awards["Unluckiest Chop"] = {
                    "winner": unluckiest_chop["team"]["owner_name"],
                    "value": f"{unluckiest_chop['elim_score']:.1f} pts (avg: {unluckiest_chop['league_avg']:.1f}, Week {unluckiest_chop['elim_week']})",
                    "icon": "🪓"
                }
       
        # Living on the edge (lowest safety margin across all teams with 5+ weeks)
        if qualified_stats:
            closest_call = min(qualified_stats, key=lambda x: x.get("avg_margin_above_last", float('inf')))
            awards["Living on the Edge"] = {
                "winner": closest_call["owner_name"],
                "value": f"{closest_call.get('avg_margin_above_last', 0):.1f} avg safety margin",
                "icon": "🔪"
            }
       
        # Most close calls (min 5 games)
        if qualified_stats:
            most_close_calls = max(qualified_stats, key=lambda x: x.get("close_calls", 0))
            if most_close_calls.get("close_calls", 0) > 0:
                awards["Danger Zone"] = {
                    "winner": most_close_calls["owner_name"],
                    "value": f"{most_close_calls.get('close_calls', 0)} close calls",
                    "icon": "⚠️"
                }
    else:
        # Dynasty-specific awards
        # Luckiest team
        luckiest = max(active_stats, key=lambda x: x.get("luck_factor", 0))
        if luckiest.get("luck_factor", 0) > 0.5:
            awards["Luckiest Team"] = {
                "winner": luckiest["owner_name"],
                "value": f"+{luckiest.get('luck_factor', 0):.1f} wins above expected",
                "icon": "🍀"
            }
       
        # Unluckiest team
        unluckiest = min(active_stats, key=lambda x: x.get("luck_factor", 0))
        if unluckiest.get("luck_factor", 0) < -0.5:
            awards["Unluckiest Team"] = {
                "winner": unluckiest["owner_name"],
                "value": f"{unluckiest.get('luck_factor', 0):.1f} wins below expected",
                "icon": "😢"
            }
   
    # Boom or bust (lowest consistency, min 5 games)
    if qualified_stats:
        boom_bust = min(qualified_stats, key=lambda x: x.get("consistency_score", float('inf')))
        awards["Boom or Bust"] = {
            "winner": boom_bust["owner_name"],
            "value": f"{boom_bust.get('consistency_score', 0):.2f} consistency",
            "icon": "💥"
        }
   
    # Most average team (closest average PPG to league average, min 5 games)
    if qualified_stats:
        league_avg = sum(s.get("average_points", 0) for s in active_stats) / len(active_stats) if active_stats else 0
        most_average = min(qualified_stats, key=lambda x: abs(x.get("average_points", 0) - league_avg))
        awards["Most Average Team"] = {
            "winner": most_average["owner_name"],
            "value": f"{most_average.get('average_points', 0):.1f} PPG (league avg: {league_avg:.1f})",
            "icon": "😐"
        }
   
    return awards

def generate_html_report(league_data, output_dir="output"):
    """Generate an HTML report with charts for a single league."""
    import os
    league_name = league_data["league_name"]
    league_id = league_data["league_id"]
    safe_filename = os.path.join(output_dir, f"season_stats_{league_id}.html")
   
    print(f"  Generating HTML report: {safe_filename}")
   
    # Check if this is a Chopped league
    is_chopped = league_data.get("is_chopped_league", False)
   
    # Prepare data for charts
    teams = [s["owner_name"] for s in league_data["season_stats"]]
    efficiency_rates = [round(s.get("efficiency_rate", 0), 1) for s in league_data["season_stats"]]
    avg_points = [round(s.get("average_points", 0), 1) for s in league_data["season_stats"]]
    points_left = [round(s.get("points_left_on_bench", 0), 1) for s in league_data["season_stats"]]
    faab_efficiency = [round(s.get("faab_efficiency", 0), 2) for s in league_data["season_stats"]]
    faab_remaining = [s.get("faab_remaining", 0) for s in league_data["season_stats"]]
    pythag_wins = [round(s.get("pythagorean_wins", 0), 1) for s in league_data["season_stats"]]
    actual_wins = [s.get("wins", 0) for s in league_data["season_stats"]]
   
    # Weekly scoring trends for all teams (includes eliminated teams to show full season)
    weekly_data = {}
    for team_stats in league_data["season_stats"]:
        weekly_data[team_stats["owner_name"]] = [w["points"] for w in team_stats["weeks"]]
   
    # Calculate league average points per week
    max_weeks = max(len(weeks) for weeks in weekly_data.values()) if weekly_data else 0
    league_avg_by_week = []
    for week_idx in range(max_weeks):
        week_scores = []
        for team_weeks in weekly_data.values():
            if week_idx < len(team_weeks) and team_weeks[week_idx] > 0:  # Exclude 0s from eliminated teams
                week_scores.append(team_weeks[week_idx])
        if week_scores:
            league_avg_by_week.append(round(sum(week_scores) / len(week_scores), 1))
        else:
            league_avg_by_week.append(0)
   
    # Calculate awards
    awards = calculate_awards(league_data["season_stats"], is_chopped)
   
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{league_name} - Season Stats</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
        }}
        h1 {{
            margin: 0;
            font-size: 2.5em;
        }}
        .subtitle {{
            margin-top: 10px;
            opacity: 0.9;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .stat-card {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .stat-title {{
            font-size: 0.9em;
            color: #666;
            text-transform: uppercase;
            margin-bottom: 10px;
        }}
        .stat-value {{
            font-size: 2em;
            font-weight: bold;
            color: #333;
        }}
        .chart-container {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        .chart-title {{
            font-size: 1.3em;
            font-weight: bold;
            margin-bottom: 15px;
            color: #333;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        th {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px;
            text-align: left;
            cursor: pointer;
            user-select: none;
            position: relative;
        }}
        th[title] {{
            cursor: help;
        }}
        th:hover {{
            opacity: 0.9;
        }}
        th::after {{
            content: ' ⇅';
            opacity: 0.5;
            font-size: 0.9em;
        }}
        th.sort-asc::after {{
            content: ' ▲';
            opacity: 1;
        }}
        th.sort-desc::after {{
            content: ' ▼';
            opacity: 1;
        }}
        td {{
            padding: 12px 15px;
            border-bottom: 1px solid #eee;
        }}
        tr:hover {{
            background-color: #f8f9fa;
        }}
        .trend-up {{
            color: #28a745;
            font-weight: bold;
        }}
        .trend-down {{
            color: #dc3545;
            font-weight: bold;
        }}
        .trend-stable {{
            color: #ffc107;
        }}
        .eliminated {{
            color: #6c757d;
            font-style: italic;
        }}
        .team-selector {{
            margin-bottom: 15px;
            padding: 10px;
            background: #f8f9fa;
            border-radius: 5px;
        }}
        .team-checkbox {{
            margin-right: 20px;
            margin-bottom: 8px;
            display: inline-block;
        }}
        .team-checkbox input {{
            margin-right: 5px;
        }}
        .team-checkbox label {{
            cursor: pointer;
            user-select: none;
        }}
        .awards-section {{
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }}
        .awards-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }}
        .award-card {{
            background: linear-gradient(135deg, #ffeaa7 0%, #fdcb6e 100%);
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            border: 3px solid #f39c12;
        }}
        .award-icon {{
            font-size: 2.5em;
            text-align: center;
            margin-bottom: 10px;
        }}
        .award-title {{
            font-size: 1.1em;
            font-weight: bold;
            color: #2c3e50;
            text-align: center;
            margin-bottom: 10px;
        }}
        .award-winner {{
            font-size: 1.3em;
            font-weight: bold;
            color: #8e44ad;
            text-align: center;
            margin-bottom: 5px;
        }}
        .award-value {{
            font-size: 0.9em;
            color: #555;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{league_name}</h1>
        <div class="subtitle">Season Statistics Report - Week {league_data["current_week"]} | {league_data.get("season", "2025")}</div>
    </div>
   
    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-title">League Average PPG</div>
            <div class="stat-value">{sum(avg_points) / len(avg_points):.1f}</div>
        </div>
        <div class="stat-card">
            <div class="stat-title">Highest Efficiency</div>
            <div class="stat-value">{max(efficiency_rates):.1f}%</div>
        </div>
        <div class="stat-card">
            <div class="stat-title">Total Points Left on Bench</div>
            <div class="stat-value">{sum(points_left):.0f}</div>
        </div>
        <div class="stat-card">
            <div class="stat-title">Most FAAB Remaining</div>
            <div class="stat-value">${max(faab_remaining)}</div>
        </div>"""
   
    # Add Best Theoretical Lineup stat for Chopped leagues only
    if is_chopped and league_data.get("avg_best_theoretical_lineup", 0) > 0:
        avg_best_theoretical = league_data["avg_best_theoretical_lineup"]
        html_content += f"""
        <div class="stat-card">
            <div class="stat-title">Best Theoretical Lineup (Avg)</div>
            <div class="stat-value">{avg_best_theoretical:.1f}</div>
        </div>"""
   
    html_content += """
    </div>
   
    <div class="chart-container">
        <div class="chart-title">Detailed Team Statistics</div>
        <table id="statsTable">
            <thead>
"""
   
    # Different headers for Chopped vs regular leagues
    if is_chopped:
        html_content += """                <tr>
                    <th onclick="sortTable(0)" title="Team owner name">Team</th>
                    <th onclick="sortTable(1)" title="Week eliminated (blank if still alive)">Eliminated</th>
                    <th onclick="sortTable(2)" title="Average points scored per game">Avg PPG</th>
                    <th onclick="sortTable(3)" title="Average margin above last place each week. Higher = safer from elimination.">Avg Safety Margin</th>
                    <th onclick="sortTable(4)" title="Number of weeks within 10 points of being eliminated">Close Calls</th>
                    <th onclick="sortTable(5)" title="Lineup efficiency: (Actual Points / Optimal Points) × 100. Measures how well you set your lineup.">Efficiency</th>
                    <th onclick="sortTable(6)" title="Total points left on bench across all weeks. Lower is better.">Bench Pts</th>
                    <th onclick="sortTable(7)" title="Scoring consistency: Mean/StdDev. Higher = more consistent week-to-week. >5 is very consistent, <3 is boom-or-bust.">Consistency</th>
                    <th onclick="sortTable(8)" title="Total FAAB (waiver budget) spent on acquisitions">FAAB Used</th>
                    <th onclick="sortTable(9)" title="Points per dollar: Points scored by waiver-acquired players / FAAB spent. Higher is better waiver efficiency.">Pt/$</th>
                </tr>
"""
    else:
        html_content += """                <tr>
                    <th onclick="sortTable(0)" title="Team ranking in the table">Rank</th>
                    <th onclick="sortTable(1)" title="Team owner name">Team</th>
                    <th onclick="sortTable(2)" title="Win-Loss record">W-L</th>
                    <th onclick="sortTable(3)" title="Average points scored per game">Avg PPG</th>
                    <th onclick="sortTable(4)" title="Lineup efficiency: (Actual Points / Optimal Points) × 100. Measures how well you set your lineup.">Efficiency</th>
                    <th onclick="sortTable(5)" title="Total points left on bench across all weeks. Lower is better.">Bench Pts</th>
                    <th onclick="sortTable(6)" title="Expected wins-losses based on Pythagorean formula (PF^2.54 / (PF^2.54 + PA^2.54)). Shows what your record 'should be' based on scoring.">Pythag W-L</th>
                    <th onclick="sortTable(7)" title="Luck factor: Actual wins minus expected wins. Positive (green) = lucky, Negative (red) = unlucky.">Luck</th>
                    <th onclick="sortTable(8)" title="Hypothetical record if you played every team each week. Better indicator of true team strength than head-to-head record.">All-Play</th>
                    <th onclick="sortTable(9)" title="Scoring consistency: Mean/StdDev. Higher = more consistent week-to-week. >5 is very consistent, <3 is boom-or-bust.">Consistency</th>
                    <th onclick="sortTable(10)" title="Total FAAB (waiver budget) spent on acquisitions">FAAB Used</th>
                    <th onclick="sortTable(11)" title="Points per dollar: Points scored by waiver-acquired players / FAAB spent. Higher is better waiver efficiency.">Pt/$</th>
                    <th onclick="sortTable(12)" title="Recent trend: Last 4 weeks vs early season average. ▲ = heating up, ▼ = cooling down">Trend</th>
                </tr>
"""
   
    html_content += """            </thead>
            <tbody>
"""
   
    # Add table rows
    for idx, stats in enumerate(league_data["season_stats"], 1):
        trend = stats.get("trend_analysis", {})
        trend_status = trend.get("trending", "")
       
        if trend_status == "up":
            trend_display = f'<span class="trend-up">▲ {trend.get("trend_percentage", 0)}%</span>'
        elif trend_status == "down":
            trend_display = f'<span class="trend-down">▼ {abs(trend.get("trend_percentage", 0))}%</span>'
        elif trend_status == "eliminated":
            trend_display = f'<span class="eliminated">Eliminated (Wk {trend.get("eliminated_after_week", "?")})</span>'
        else:
            trend_display = '<span class="trend-stable">—</span>'
       
        faab_used = stats.get("waiver_budget_used", 0)
        # Use the pre-calculated faab_efficiency from stats (points from waiver players only)
        points_per_dollar = stats.get("faab_efficiency", 0)
        consistency = stats.get("consistency_score", 0)
       
        if is_chopped:
            # Chopped league specific row
            eliminated_week = stats.get("eliminated_week")
            elim_display = f"Week {eliminated_week}" if eliminated_week else "—"
            avg_margin = stats.get("avg_margin_above_last", 0)
            close_calls = stats.get("close_calls", 0)
           
            html_content += f"""                <tr>
                    <td><strong>{stats['owner_name']}</strong></td>
                    <td>{elim_display}</td>
                    <td>{stats.get('average_points', 0):.1f}</td>
                    <td>{avg_margin:.1f}</td>
                    <td>{close_calls}</td>
                    <td>{stats.get('efficiency_rate', 0):.1f}%</td>
                    <td>{stats.get('points_left_on_bench', 0):.1f}</td>
                    <td>{consistency:.2f}</td>
                    <td>${faab_used}</td>
                    <td>{points_per_dollar:.2f}</td>
                </tr>
"""
        else:
            # Regular league row
            # Pythagorean W-L display
            team_pythag_wins = stats.get("pythagorean_wins", 0)
            team_actual_wins = stats.get("wins", 0)
            pythag_display = f"{team_pythag_wins:.1f}-{stats.get('weeks_played', 0) - team_pythag_wins:.1f}"
           
            # Luck factor (positive = lucky, negative = unlucky)
            luck = stats.get("luck_factor", 0)
            if luck > 0.5:
                luck_display = f'<span class="trend-up">+{luck:.1f}</span>'
            elif luck < -0.5:
                luck_display = f'<span class="trend-down">{luck:.1f}</span>'
            else:
                luck_display = f'{luck:.1f}'
           
            # All-play record
            all_play_wins = stats.get("all_play_wins", 0)
            all_play_losses = stats.get("all_play_losses", 0)
            all_play_pct = stats.get("all_play_pct", 0)
            all_play_display = f"{all_play_wins}-{all_play_losses} ({all_play_pct:.3f})"
           
            html_content += f"""                <tr>
                    <td>{idx}</td>
                    <td><strong>{stats['owner_name']}</strong></td>
                    <td>{team_actual_wins}-{stats.get('losses', 0)}</td>
                    <td>{stats.get('average_points', 0):.1f}</td>
                    <td>{stats.get('efficiency_rate', 0):.1f}%</td>
                    <td>{stats.get('points_left_on_bench', 0):.1f}</td>
                    <td>{pythag_display}</td>
                    <td>{luck_display}</td>
                    <td>{all_play_display}</td>
                    <td>{consistency:.2f}</td>
                    <td>${faab_used}</td>
                    <td>{points_per_dollar:.2f}</td>
                    <td>{trend_display}</td>
                </tr>
"""
   
    html_content += """            </tbody>
        </table>
    </div>
   
    <div class="awards-section">
        <div class="chart-title">🏆 Season Awards 🏆</div>
        <div class="awards-grid">
"""
   
    # Add award cards
    for award_name, award_info in awards.items():
        html_content += f"""            <div class="award-card">
                <div class="award-icon">{award_info['icon']}</div>
                <div class="award-title">{award_name}</div>
                <div class="award-winner">{award_info['winner']}</div>
                <div class="award-value">{award_info['value']}</div>
            </div>
"""
   
    html_content += """        </div>
    </div>
"""
   
    # Add Best Theoretical Lineup table for Chopped leagues
    if is_chopped and league_data.get("best_theoretical_lineups"):
        html_content += """
    <div class="chart-container">
        <div class="chart-title">📊 Best Theoretical Lineup by Week</div>
        <p style="text-align: center; color: #666; margin-bottom: 15px;">
            Based on Dynasty league player pool - shows the optimal lineup each week using the best performer at each position
        </p>
        <table id="theoreticalLineupTable">
            <thead>
                <tr>
                    <th>Week</th>
                    <th>Total Points</th>
                    <th>Lineup Details</th>
                </tr>
            </thead>
            <tbody>
"""
       
        for week_data in league_data["best_theoretical_lineups"]:
            week = week_data['week']
            points = week_data['points']
            lineup = week_data.get('lineup', [])
           
            # Build lineup details string
            lineup_html = "<div style='text-align: left;'>"
            for player in lineup:
                lineup_html += f"<div style='margin: 2px 0;'><strong>{player['slot']}:</strong> {player['player']} ({player['team']}) - {player['points']:.1f} pts</div>"
            lineup_html += "</div>"
           
            html_content += f"""                <tr>
                    <td style="text-align: center; font-weight: bold;">{week}</td>
                    <td style="text-align: center; font-weight: bold; color: #667eea;">{points}</td>
                    <td>{lineup_html}</td>
                </tr>
"""
       
        html_content += """            </tbody>
        </table>
    </div>
"""
   
    html_content += """
    <div class="chart-container">
        <div class="chart-title">Weekly Scoring Trends (All Teams)</div>
        <div class="team-selector" id="teamSelector">
            <strong>Select teams to display:</strong><br>
        </div>
        <canvas id="weeklyTrendsChart"></canvas>
    </div>
   
    <div class="chart-container">
        <div class="chart-title">Sit/Start Efficiency by Team</div>
        <canvas id="efficiencyChart"></canvas>
    </div>
   
    <div class="chart-container">
        <div class="chart-title">Average Points Per Game</div>
        <canvas id="avgPointsChart"></canvas>
    </div>
   
    <div class="chart-container">
        <div class="chart-title">FAAB Efficiency (Points per $ Spent)</div>
        <canvas id="faabEfficiencyChart"></canvas>
    </div>
"""
   
    # Only add Pythagorean Expectation chart for non-Chopped leagues
    if not is_chopped:
        html_content += """
    <div class="chart-container">
        <div class="chart-title">Pythagorean Expectation (Actual vs Expected Wins)</div>
        <canvas id="pythagChart"></canvas>
    </div>
"""
   
    html_content += """
    <div class="chart-container">
        <div class="chart-title">League Average Points Per Week</div>
        <canvas id="leagueAvgChart"></canvas>
    </div>
   
    <script>"""
   
    html_content += """
        // Efficiency Chart
        new Chart(document.getElementById('efficiencyChart'), {
            type: 'bar',
            data: {
                labels: """ + str(teams) + """,
                datasets: [{
                    label: 'Efficiency Rate (%)',
                    data: """ + str(efficiency_rates) + """,
                    backgroundColor: 'rgba(102, 126, 234, 0.7)',
                    borderColor: 'rgba(102, 126, 234, 1)',
                    borderWidth: 2
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        max: 100,
                        title: { display: true, text: 'Efficiency %' }
                    }
                }
            }
        });
       
        // Average Points Chart
        new Chart(document.getElementById('avgPointsChart'), {
            type: 'bar',
            data: {
                labels: """ + str(teams) + """,
                datasets: [{
                    label: 'Avg Points Per Game',
                    data: """ + str(avg_points) + """,
                    backgroundColor: 'rgba(118, 75, 162, 0.7)',
                    borderColor: 'rgba(118, 75, 162, 1)',
                    borderWidth: 2
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        title: { display: true, text: 'Points' }
                    }
                }
            }
        });
       
        // FAAB Efficiency Chart
        new Chart(document.getElementById('faabEfficiencyChart'), {
            type: 'bar',
            data: {
                labels: """ + str(teams) + """,
                datasets: [{
                    label: 'Points per Dollar Spent',
                    data: """ + str(faab_efficiency) + """,
                    backgroundColor: 'rgba(40, 167, 69, 0.7)',
                    borderColor: 'rgba(40, 167, 69, 1)',
                    borderWidth: 2
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        title: { display: true, text: 'Points/$' }
                    }
                }
            }
        });
"""
   
    # Only add Pythagorean Expectation chart JavaScript for non-Chopped leagues
    if not is_chopped:
        html_content += """
        // Pythagorean Expectation Chart
        new Chart(document.getElementById('pythagChart'), {
            type: 'bar',
            data: {
                labels: """ + str(teams) + """,
                datasets: [
                    {
                        label: 'Actual Wins',
                        data: """ + str(actual_wins) + """,
                        backgroundColor: 'rgba(102, 126, 234, 0.7)',
                        borderColor: 'rgba(102, 126, 234, 1)',
                        borderWidth: 2
                    },
                    {
                        label: 'Expected Wins (Pythag)',
                        data: """ + str(pythag_wins) + """,
                        backgroundColor: 'rgba(255, 159, 64, 0.7)',
                        borderColor: 'rgba(255, 159, 64, 1)',
                        borderWidth: 2
                    }
                ]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                plugins: {
                    legend: { display: true, position: 'top' },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return context.dataset.label + ': ' + context.parsed.x.toFixed(1);
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        title: { display: true, text: 'Wins' }
                    }
                }
            }
        });
"""
   
    html_content += """
        // Weekly Trends Chart with team selection
        const allColors = [
            'rgba(255, 99, 132, 1)', 'rgba(54, 162, 235, 1)', 'rgba(255, 206, 86, 1)',
            'rgba(75, 192, 192, 1)', 'rgba(153, 102, 255, 1)', 'rgba(255, 159, 64, 1)',
            'rgba(255, 159, 132, 1)', 'rgba(99, 255, 132, 1)', 'rgba(132, 99, 255, 1)',
            'rgba(255, 206, 132, 1)', 'rgba(132, 206, 255, 1)', 'rgba(206, 132, 255, 1)'
        ];
       
        const weeklyTeamData = {"""
   
    # Add team data
    for idx, (team_name, points) in enumerate(weekly_data.items()):
        html_content += f"""
            '{team_name}': {points},"""
   
    html_content += """
        };
       
        // Create team selector checkboxes
        const teamSelector = document.getElementById('teamSelector');
        const teamNames = Object.keys(weeklyTeamData);
       
        teamNames.forEach((team, idx) => {
            const checkbox = document.createElement('div');
            checkbox.className = 'team-checkbox';
            checkbox.innerHTML = `
                <input type="checkbox" id="team_${idx}" value="${team}"
                    ${idx < 6 ? 'checked' : ''} onchange="updateWeeklyChart()">
                <label for="team_${idx}">${team}</label>
            `;
            teamSelector.appendChild(checkbox);
        });
       
        // Initialize weekly trends chart
        let weeklyChart = null;
       
        function updateWeeklyChart() {
            const selectedTeams = [];
            teamNames.forEach((team, idx) => {
                const checkbox = document.getElementById(`team_${idx}`);
                if (checkbox && checkbox.checked) {
                    selectedTeams.push(team);
                }
            });
           
            const datasets = selectedTeams.map((team, idx) => {
                const color = allColors[teamNames.indexOf(team) % allColors.length];
                return {
                    label: team,
                    data: weeklyTeamData[team],
                    borderColor: color,
                    backgroundColor: color.replace('1)', '0.1)'),
                    tension: 0,
                    borderWidth: 2
                };
            });
           
            // Add league average as a dashed line
            datasets.push({
                label: 'League Average',
                data: """ + str(league_avg_by_week) + """,
                borderColor: 'rgba(128, 128, 128, 0.8)',
                backgroundColor: 'rgba(128, 128, 128, 0)',
                borderDash: [10, 5],
                tension: 0,
                borderWidth: 3,
                pointRadius: 0
            });
           
            if (weeklyChart) {
                weeklyChart.destroy();
            }
           
            weeklyChart = new Chart(document.getElementById('weeklyTrendsChart'), {
                type: 'line',
                data: {
                    labels: Array.from({length: """ + str(league_data["current_week"]) + """}, (_, i) => 'Week ' + (i + 1)),
                    datasets: datasets
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: { display: true, position: 'top' }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: { display: true, text: 'Points Scored' }
                        }
                    }
                }
            });
        }
       
        // Initialize chart with first 6 teams selected
        updateWeeklyChart();
       
        // League Average Points Per Week Chart
        const weekLabels = Array.from({length: """ + str(len(league_avg_by_week)) + """}, (_, i) => `Week ${i + 1}`);
        new Chart(document.getElementById('leagueAvgChart'), {
            type: 'line',
            data: {
                labels: weekLabels,
                datasets: [{
                    label: 'League Average Points',
                    data: """ + str(league_avg_by_week) + """,
                    backgroundColor: 'rgba(118, 75, 162, 0.2)',
                    borderColor: 'rgba(118, 75, 162, 1)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.3,
                    pointRadius: 4,
                    pointBackgroundColor: 'rgba(118, 75, 162, 1)'
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { display: true },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return context.dataset.label + ': ' + context.parsed.y.toFixed(1) + ' pts';
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: { display: true, text: 'Average Points' }
                    },
                    x: {
                        title: { display: true, text: 'Week' }
                    }
                }
            }
        });
    </script>
   
    <script>
        // Table sorting functionality
        let sortDirection = {};
       
        function sortTable(columnIndex) {
            const table = document.getElementById('statsTable');
            const tbody = table.querySelector('tbody');
            const rows = Array.from(tbody.querySelectorAll('tr'));
            const headers = table.querySelectorAll('th');
           
            // Toggle sort direction
            if (sortDirection[columnIndex] === 'asc') {
                sortDirection[columnIndex] = 'desc';
            } else {
                sortDirection[columnIndex] = 'asc';
            }
           
            // Remove sort indicators from all headers
            headers.forEach(h => {
                h.classList.remove('sort-asc', 'sort-desc');
            });
           
            // Add sort indicator to current header
            headers[columnIndex].classList.add(sortDirection[columnIndex] === 'asc' ? 'sort-asc' : 'sort-desc');
           
            // Sort rows
            rows.sort((a, b) => {
                let aVal = a.cells[columnIndex].textContent.trim();
                let bVal = b.cells[columnIndex].textContent.trim();
               
                // Extract numeric values from cells
                let aNum = parseFloat(aVal.replace(/[^0-9.-]/g, ''));
                let bNum = parseFloat(bVal.replace(/[^0-9.-]/g, ''));
               
                // Compare
                let comparison = 0;
                if (!isNaN(aNum) && !isNaN(bNum)) {
                    comparison = aNum - bNum;
                } else {
                    comparison = aVal.localeCompare(bVal);
                }
               
                return sortDirection[columnIndex] === 'asc' ? comparison : -comparison;
            });
           
            // Reattach sorted rows and update rank column (only for non-Chopped leagues)
            rows.forEach((row, index) => {
                tbody.appendChild(row);
                // Update rank column only if it exists (Dynasty leagues have rank in first column)
                if (row.cells[0].textContent.match(/^\\d+$/)) {
                    row.cells[0].textContent = index + 1; // Update rank
                }
            });
        }
    </script>
</body>
</html>
"""
   
    # Write HTML file
    with open(safe_filename, 'w', encoding='utf-8') as f:
        f.write(html_content)
   
    print(f"  + Generated: {safe_filename}")

