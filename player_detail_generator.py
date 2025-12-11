import os
import json

def generate_player_detail_page(player_name, player_data, weekly_performances, output_dir="output"):
    """Generate a detailed player page with week-by-week stats."""
    
    # Create players subfolder
    players_dir = os.path.join(output_dir, "players")
    if not os.path.exists(players_dir):
        os.makedirs(players_dir)
    
    # Create safe filename from player name
    safe_name = player_name.replace(' ', '_').replace('.', '').replace("'", '')
    filename = os.path.join(players_dir, f"player_{safe_name}.html")
    
    # Get player info
    position = player_data.get('position', 'UNKNOWN')
    team = player_data.get('team', 'FA')
    total_points = player_data.get('total_points', 0)
    avg_ppg = player_data.get('avg_ppg', 0)
    games = player_data.get('games', 0)
    dynasty_owner = player_data.get('dynasty_owner', 'Free Agent')
    chopped_owner = player_data.get('chopped_owner', 'Free Agent')
    
    # NFL stats
    nfl_stats = player_data.get('nfl_stats', {})
    age = nfl_stats.get('age', '-')
    
    # Weekly performance data - handle both dict (week->points) and list formats
    weeks_data = []
    if isinstance(weekly_performances, dict):
        # Dict format: {week_num: points}
        for week_num in sorted(weekly_performances.keys()):
            weeks_data.append({'week': week_num, 'points': weekly_performances[week_num]})
    elif weekly_performances:
        # Legacy list format (fallback)
        for i, pts in enumerate(weekly_performances, 1):
            weeks_data.append({'week': i, 'points': pts})
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{player_name} - Player Stats</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            margin: 0;
            padding: 0;
        }}
        .nav-bar {{
            background-color: rgba(255, 255, 255, 0.95);
            padding: 15px 30px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 15px;
        }}
        .nav-bar .nav-title {{
            font-size: 24px;
            font-weight: bold;
            color: #667eea;
            margin: 0;
        }}
        .nav-links {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }}
        .nav-links a {{
            text-decoration: none;
            color: #667eea;
            padding: 8px 16px;
            border-radius: 5px;
            transition: all 0.3s;
            font-weight: 500;
        }}
        .nav-links a:hover {{
            background-color: #667eea;
            color: white;
        }}
        .nav-links a.active {{
            background-color: #667eea;
            color: white;
        }}
        .content-wrapper {{
            padding: 20px;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        .back-link {{
            display: inline-block;
            color: white;
            text-decoration: none;
            margin-bottom: 20px;
            font-size: 1.1em;
            padding: 10px 20px;
            background: rgba(255,255,255,0.2);
            border-radius: 8px;
            transition: background 0.3s;
        }}
        .back-link:hover {{
            background: rgba(255,255,255,0.3);
        }}
        .player-header {{
            background: white;
            border-radius: 15px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.1);
        }}
        .player-name {{
            font-size: 2.5em;
            color: #667eea;
            margin-bottom: 10px;
        }}
        .player-meta {{
            display: flex;
            gap: 30px;
            flex-wrap: wrap;
            margin-top: 20px;
        }}
        .meta-item {{
            display: flex;
            flex-direction: column;
        }}
        .meta-label {{
            font-size: 0.9em;
            color: #666;
            margin-bottom: 5px;
        }}
        .meta-value {{
            font-size: 1.3em;
            font-weight: 600;
            color: #333;
        }}
        .position {{
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            color: white;
            font-weight: 600;
            font-size: 1.1em;
        }}
        .position.QB {{ background: #e74c3c; }}
        .position.RB {{ background: #3498db; }}
        .position.WR {{ background: #2ecc71; }}
        .position.TE {{ background: #f39c12; }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .stat-card {{
            background: white;
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.1);
        }}
        .stat-card h3 {{
            color: #667eea;
            margin-bottom: 20px;
            font-size: 1.3em;
        }}
        .chart-container {{
            background: white;
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 30px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.1);
        }}
        .weekly-table {{
            background: white;
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.1);
            overflow-x: auto;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }}
        th {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px 10px;
            text-align: left;
            font-weight: 600;
        }}
        td {{
            padding: 12px 10px;
            border-bottom: 1px solid #ecf0f1;
        }}
        tr:hover {{
            background-color: #f8f9fa;
        }}
        .best-week {{
            background-color: #d4edda !important;
            font-weight: 600;
        }}
        .worst-week {{
            background-color: #f8d7da !important;
        }}
    </style>
</head>
<body>
    <nav class="nav-bar">
        <div class="nav-title">🏈 Fantasy Tool</div>
        <div class="nav-links">
            <a href="../index.html">Home</a>
            <a href="../player_stats.html" class="active">Player Stats</a>
            <a href="../defense_stats.html">Defense Stats</a>
            <a href="../season_stats_dynasty.html">Dynasty Stats</a>
            <a href="../season_stats_chopped.html">Chopped Stats</a>
        </div>
    </nav>
    <div class="content-wrapper">
    <div class="container">
        <a href="../player_stats.html" class="back-link">← Back to All Players</a>
        
        <div class="player-header">
            <h1 class="player-name">{player_name}</h1>
            <span class="position {position}">{position}</span>
            
            <div class="player-meta">
                <div class="meta-item">
                    <span class="meta-label">Team</span>
                    <span class="meta-value">{team}</span>
                </div>
                <div class="meta-item">
                    <span class="meta-label">Age</span>
                    <span class="meta-value">{age}</span>
                </div>
                <div class="meta-item">
                    <span class="meta-label">Dynasty Owner</span>
                    <span class="meta-value">{dynasty_owner}</span>
                </div>
                <div class="meta-item">
                    <span class="meta-label">Chopped Owner</span>
                    <span class="meta-value">{chopped_owner}</span>
                </div>
            </div>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <h3>Season Totals</h3>
                <div class="meta-item">
                    <span class="meta-label">Games Played</span>
                    <span class="meta-value">{games}</span>
                </div>
                <div class="meta-item" style="margin-top: 15px;">
                    <span class="meta-label">Total Points</span>
                    <span class="meta-value">{total_points:.1f}</span>
                </div>
                <div class="meta-item" style="margin-top: 15px;">
                    <span class="meta-label">Average PPG</span>
                    <span class="meta-value">{avg_ppg:.1f}</span>
                </div>
            </div>
            
            <div class="stat-card">
                <h3>Performance</h3>
                <div class="meta-item">
                    <span class="meta-label">Best Game</span>
                    <span class="meta-value">{player_data.get('best_game', 0):.1f} pts</span>
                </div>
                <div class="meta-item" style="margin-top: 15px;">
                    <span class="meta-label">Worst Game</span>
                    <span class="meta-value">{player_data.get('worst_game', 0):.1f} pts</span>
                </div>
                <div class="meta-item" style="margin-top: 15px;">
                    <span class="meta-label">Consistency</span>
                    <span class="meta-value">{player_data.get('consistency', 0):.2f}</span>
                </div>
            </div>
            
            <div class="stat-card">
                <h3>Advanced Stats</h3>
                <div class="meta-item">
                    <span class="meta-label">Avg Targets</span>
                    <span class="meta-value">{nfl_stats.get('avg_targets', '-')}</span>
                </div>
                <div class="meta-item" style="margin-top: 15px;">
                    <span class="meta-label">Avg Rush Attempts</span>
                    <span class="meta-value">{nfl_stats.get('avg_rushes', '-')}</span>
                </div>
                <div class="meta-item" style="margin-top: 15px;">
                    <span class="meta-label">Snap %</span>
                    <span class="meta-value">{nfl_stats.get('avg_snap_pct', '-')}{'%' if nfl_stats.get('avg_snap_pct', '-') != '-' else ''}</span>
                </div>
            </div>
        </div>
        
        <div class="chart-container">
            <h3 style="color: #667eea; margin-bottom: 20px;">Weekly Performance Chart</h3>
            <canvas id="weeklyChart"></canvas>
        </div>
        
        <div class="weekly-table">
            <h3 style="color: #667eea; margin-bottom: 20px;">Week-by-Week Stats</h3>
            <table>
                <thead>
                    <tr>
                        <th>Week</th>
                        <th>Fantasy Points</th>
                        <th>vs Average</th>
                        <th>Rank</th>
                    </tr>
                </thead>
                <tbody>
"""
    
    # Find best and worst weeks
    if weeks_data:
        best_week = max(weeks_data, key=lambda x: x['points'])
        worst_week = min(weeks_data, key=lambda x: x['points'])
        
        for week_data in weeks_data:
            week = week_data['week']
            points = week_data['points']
            vs_avg = points - avg_ppg
            vs_avg_sign = '+' if vs_avg >= 0 else ''
            
            row_class = ''
            if week_data == best_week:
                row_class = 'best-week'
            elif week_data == worst_week:
                row_class = 'worst-week'
            
            rank = '🏆' if row_class == 'best-week' else ('💔' if row_class == 'worst-week' else '')
            
            html_content += f"""
                    <tr class="{row_class}">
                        <td><strong>Week {week}</strong></td>
                        <td><strong>{points:.1f}</strong></td>
                        <td>{vs_avg_sign}{vs_avg:.1f}</td>
                        <td>{rank}</td>
                    </tr>
"""
    
    # Prepare chart data
    weeks_list = [w['week'] for w in weeks_data]
    points_list = [w['points'] for w in weeks_data]
    avg_line = [avg_ppg] * len(weeks_data)
    
    html_content += f"""
                </tbody>
            </table>
        </div>
    </div>
    
    <script>
        const ctx = document.getElementById('weeklyChart').getContext('2d');
        const chart = new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: {json.dumps(weeks_list)},
                datasets: [{{
                    label: 'Fantasy Points',
                    data: {json.dumps(points_list)},
                    borderColor: '#667eea',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    borderWidth: 3,
                    tension: 0.4,
                    fill: true,
                    pointRadius: 5,
                    pointHoverRadius: 7
                }},
                {{
                    label: 'Season Average',
                    data: {json.dumps(avg_line)},
                    borderColor: '#e74c3c',
                    borderWidth: 2,
                    borderDash: [5, 5],
                    fill: false,
                    pointRadius: 0
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: true,
                aspectRatio: 2.5,
                plugins: {{
                    legend: {{
                        display: true,
                        position: 'top'
                    }},
                    tooltip: {{
                        mode: 'index',
                        intersect: false
                    }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        title: {{
                            display: true,
                            text: 'Fantasy Points'
                        }}
                    }},
                    x: {{
                        title: {{
                            display: true,
                            text: 'Week'
                        }}
                    }}
                }}
            }}
        }});
    </script>
    </div>
    </div>
</body>
</html>
"""
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    return filename
