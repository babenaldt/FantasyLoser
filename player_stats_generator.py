import statistics
import json

def generate_player_stats_report(league_data, all_player_data, output_dir="output"):
    """Generate an HTML report with advanced player statistics."""
    import os
    league_name = league_data["league_name"]
    league_id = league_data["league_id"]
    safe_filename = os.path.join(output_dir, f"player_stats_{league_id}.html")
   
    print(f"  Generating player stats report: {safe_filename}")
   
    # Prepare player stats sorted by total points
    player_stats = sorted(all_player_data, key=lambda x: x.get("total_points", 0), reverse=True)
   
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{league_name} - Player Stats</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            margin: 0;
            padding: 0;
            color: #2c3e50;
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
        .header {{
            text-align: center;
            color: white;
            margin-bottom: 30px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }}
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        .subtitle {{
            font-size: 1.2em;
            opacity: 0.95;
        }}
        .filters {{
            background: white;
            padding: 20px;
            border-radius: 15px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        .filter-group {{
            display: inline-block;
            margin: 10px 20px 10px 0;
        }}
        .filter-group label {{
            font-weight: bold;
            margin-right: 10px;
        }}
        .filter-group select, .filter-group input {{
            padding: 8px 12px;
            border: 2px solid #667eea;
            border-radius: 8px;
            font-size: 1em;
        }}
        .stats-container {{
            background: white;
            padding: 20px;
            border-radius: 15px;
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
            position: sticky;
            top: 0;
            cursor: pointer;
            user-select: none;
        }}
        th:hover {{
            background: linear-gradient(135deg, #764ba2 0%, #667eea 100%);
        }}
        td {{
            padding: 12px 10px;
            border-bottom: 1px solid #ecf0f1;
        }}
        tr:hover {{
            background-color: #f8f9fa;
        }}
        .position {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-weight: bold;
            font-size: 0.85em;
        }}
        .position.QB {{ background-color: #e74c3c; color: white; }}
        .position.RB {{ background-color: #3498db; color: white; }}
        .position.WR {{ background-color: #2ecc71; color: white; }}
        .position.TE {{ background-color: #f39c12; color: white; }}
        .position.K {{ background-color: #9b59b6; color: white; }}
        .position.DEF {{ background-color: #34495e; color: white; }}
        .consistency-high {{ color: #27ae60; font-weight: bold; }}
        .consistency-low {{ color: #e74c3c; font-weight: bold; }}
        .team-name {{
            font-size: 0.9em;
            color: #7f8c8d;
        }}
        .position-tabs {{
            background: white;
            padding: 0;
            border-radius: 15px 15px 0 0;
            box-shadow: 0 8px 32px rgba(0,0,0,0.1);
            margin-bottom: 0;
            display: flex;
            overflow-x: auto;
        }}
        .position-tab {{
            padding: 15px 30px;
            cursor: pointer;
            font-weight: 600;
            border: none;
            background: transparent;
            color: #7f8c8d;
            transition: all 0.3s;
            border-bottom: 3px solid transparent;
        }}
        .position-tab:hover {{
            background: #f8f9fa;
        }}
        .position-tab.active {{
            color: #667eea;
            border-bottom: 3px solid #667eea;
        }}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <nav class="nav-bar">
        <div class="nav-title">🏈 Fantasy Tool</div>
        <div class="nav-links">
            <a href="../index.html">Home</a>
            <a href="player_stats.html" class="active">Player Stats</a>
            <a href="defense_stats.html">Defense Stats</a>
            <a href="season_stats.html">Season Stats</a>
        </div>
    </nav>
    <div class="content-wrapper">
    <div class="header">
        <h1>{league_name}</h1>
        <div class="subtitle">Advanced Player Statistics - Week {league_data["current_week"]} | {league_data.get("season", "2025")}</div>
    </div>
   
    <div class="position-tabs">
        <button class="position-tab active" onclick="setPositionFilter('ALL')">All Positions</button>
        <button class="position-tab" onclick="setPositionFilter('QB')">Quarterbacks</button>
        <button class="position-tab" onclick="setPositionFilter('RB')">Running Backs</button>
        <button class="position-tab" onclick="setPositionFilter('WR')">Wide Receivers</button>
        <button class="position-tab" onclick="setPositionFilter('TE')">Tight Ends</button>
        <button class="position-tab" onclick="setPositionFilter('K')">Kickers</button>
        <button class="position-tab" onclick="setPositionFilter('DEF')">Defense</button>
    </div>
   
    <div class="filters">
        <input type="hidden" id="positionFilter" value="ALL">
        <div class="filter-group">
            <label for="minGames">Min Games:</label>
            <input type="number" id="minGames" value="5" min="1" max="18" onchange="filterTable()">
        </div>
        <div class="filter-group">
            <label for="searchPlayer">Search Player:</label>
            <input type="text" id="searchPlayer" placeholder="Player name..." onkeyup="filterTable()">
        </div>
        <div class="filter-group">
            <button onclick="toggleColumnSelector()" style="padding: 8px 16px; background: #667eea; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: 600;">⚙️ Customize Columns</button>
            <button onclick="openCompare()" style="padding: 8px 16px; background: #2ecc71; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: 600; margin-left: 10px;">⚖️ Compare Players</button>
        </div>
    </div>
    
    <div id="columnSelector" style="display: none; background: white; padding: 20px; border-radius: 15px; box-shadow: 0 8px 32px rgba(0,0,0,0.1); margin-bottom: 20px;">
        <h3 style="margin-bottom: 15px;">Select Columns to Display:</h3>
        <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px;">
            <label><input type="checkbox" class="col-toggle" data-col="0" checked> Rank</label>
            <label><input type="checkbox" class="col-toggle" data-col="1" checked> Player</label>
            <label><input type="checkbox" class="col-toggle" data-col="2" checked> Position</label>
            <label><input type="checkbox" class="col-toggle" data-col="3" checked> Team</label>
            <label><input type="checkbox" class="col-toggle" data-col="4" checked> Dynasty Owner</label>
            <label><input type="checkbox" class="col-toggle" data-col="5" checked> Chopped Owner</label>
            <label><input type="checkbox" class="col-toggle" data-col="6" checked> Games</label>
            <label><input type="checkbox" class="col-toggle" data-col="7" checked> Total Pts</label>
            <label><input type="checkbox" class="col-toggle" data-col="8" checked> Avg PPG</label>
            <label><input type="checkbox" class="col-toggle" data-col="9"> Pos Avg</label>
            <label><input type="checkbox" class="col-toggle" data-col="10" checked> vs Pos Avg</label>
            <label><input type="checkbox" class="col-toggle" data-col="11"> Std Dev</label>
            <label><input type="checkbox" class="col-toggle" data-col="12" checked> Consistency</label>
            <label><input type="checkbox" class="col-toggle" data-col="13"> Best Game</label>
            <label><input type="checkbox" class="col-toggle" data-col="14"> Worst Game</label>
            <label><input type="checkbox" class="col-toggle" data-col="15"> Median</label>
            <label><input type="checkbox" class="col-toggle" data-col="16"> % Above Avg</label>
            <label><input type="checkbox" class="col-toggle" data-col="17" checked> Trend</label>
            <label><input type="checkbox" class="col-toggle" data-col="18" checked> Age</label>
            <label><input type="checkbox" class="col-toggle" data-col="19" checked> Avg Targets</label>
            <label><input type="checkbox" class="col-toggle" data-col="20" checked> Avg Rec</label>
            <label><input type="checkbox" class="col-toggle" data-col="21" checked> Avg Rush</label>
            <label><input type="checkbox" class="col-toggle" data-col="22" checked> Avg Rush Yds</label>
            <label><input type="checkbox" class="col-toggle" data-col="23" checked> Avg Rec Yds</label>
            <label><input type="checkbox" class="col-toggle" data-col="24" checked> Snap %</label>
        </div>
        <button onclick="applyColumnSettings()" style="margin-top: 15px; padding: 8px 16px; background: #667eea; color: white; border: none; border-radius: 8px; cursor: pointer;">Apply</button>
    </div>
    
    <div id="compareModal" style="display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); z-index: 1000; overflow-y: auto;">
        <div style="background: white; max-width: 1200px; margin: 50px auto; padding: 30px; border-radius: 15px; position: relative;">
            <button onclick="closeCompare()" style="position: absolute; top: 10px; right: 10px; background: #e74c3c; color: white; border: none; padding: 5px 10px; border-radius: 5px; cursor: pointer; font-size: 20px;">✕</button>
            <h2 style="margin-bottom: 20px;">Compare Players</h2>
            <div style="margin-bottom: 20px;">
                <label>Player 1: <input type="text" id="comparePlayer1" list="playerList" placeholder="Search player..." style="padding: 8px; width: 300px;"></label>
                <label style="margin-left: 20px;">Player 2: <input type="text" id="comparePlayer2" list="playerList" placeholder="Search player..." style="padding: 8px; width: 300px;"></label>
                <button onclick="runComparison()" style="margin-left: 20px; padding: 8px 16px; background: #2ecc71; color: white; border: none; border-radius: 8px; cursor: pointer;">Compare</button>
            </div>
            <datalist id="playerList">
""" + "".join([f'<option value="{p["name"]}">' for p in player_stats]) + """
            </datalist>
            <div id="comparisonResult"></div>
        </div>
    </div>
   
    <div class="stats-container">
        <table id="playerTable">
            <thead>
                <tr>
                    <th onclick="sortTable(0)">Rank</th>
                    <th onclick="sortTable(1)">Player</th>
                    <th onclick="sortTable(2)">Pos</th>
                    <th onclick="sortTable(3)">Team</th>
                    <th onclick="sortTable(4)">Dynasty Owner</th>
                    <th onclick="sortTable(5)">Chopped Owner</th>
                    <th onclick="sortTable(6)" title="Total games with points scored">Games</th>
                    <th onclick="sortTable(7)" title="Total points scored this season">Total Pts</th>
                    <th onclick="sortTable(8)" title="Average points per game">Avg PPG</th>
                    <th onclick="sortTable(9)" title="Positional average PPG">Pos Avg</th>
                    <th onclick="sortTable(10)" title="Points above/below positional average">vs Pos Avg</th>
                    <th onclick="sortTable(11)" title="Standard deviation of weekly scores">Std Dev</th>
                    <th onclick="sortTable(12)" title="Consistency score: Mean/StdDev. Higher = more consistent">Consistency</th>
                    <th onclick="sortTable(13)" title="Best single game performance">Best Game</th>
                    <th onclick="sortTable(14)" title="Worst single game performance">Worst Game</th>
                    <th onclick="sortTable(15)" title="Median weekly score">Median</th>
                    <th onclick="sortTable(16)" title="Percentage of games scoring above their average">% Above Avg</th>
                    <th onclick="sortTable(17)" title="Recent trend: Last 4 weeks vs early season. Positive = heating up, Negative = cooling down">Trend</th>
                    <th onclick="sortTable(18)" title="Player age">Age</th>
                    <th onclick="sortTable(19)" title="Average targets per game (WR/TE/RB)">Avg Targets</th>
                    <th onclick="sortTable(20)" title="Average receptions per game">Avg Rec</th>
                    <th onclick="sortTable(21)" title="Average rushing attempts per game">Avg Rush</th>
                    <th onclick="sortTable(22)" title="Average rushing yards per game">Avg Rush Yds</th>
                    <th onclick="sortTable(23)" title="Average receiving yards per game">Avg Rec Yds</th>
                    <th onclick="sortTable(24)" title="Average offensive snap percentage">Snap %</th>
                </tr>
            </thead>
            <tbody>
"""
   
    # Add player rows
    for idx, player in enumerate(player_stats, 1):
        consistency_class = "consistency-high" if player["consistency"] > 5 else ("consistency-low" if player["consistency"] < 3 else "")
        vs_pos_class = "consistency-high" if player["vs_position_avg"] > 0 else ("consistency-low" if player["vs_position_avg"] < -2 else "")
        vs_pos_sign = "+" if player["vs_position_avg"] > 0 else ""
        
        # Get ownership info
        dynasty_owner = player.get('dynasty_owner', 'Free Agent')
        chopped_owner = player.get('chopped_owner', 'Free Agent')
        
        # Get NFL stats
        nfl_stats = player.get('nfl_stats', {})
        age = nfl_stats.get('age', '-')
        avg_targets = nfl_stats.get('avg_targets', '-')
        avg_receptions = nfl_stats.get('avg_receptions', '-')
        avg_rushes = nfl_stats.get('avg_rushes', '-')
        avg_rushing_yds = nfl_stats.get('avg_rushing_yds', '-')
        avg_receiving_yds = nfl_stats.get('avg_receiving_yds', '-')
        avg_snap_pct = nfl_stats.get('avg_snap_pct', '-')
        
        # Format snap percentage
        if avg_snap_pct != '-' and avg_snap_pct > 0:
            snap_display = f'{avg_snap_pct}%'
        else:
            snap_display = '-'
       
        # Format trend
        trend_val = player.get('trend_pct', 0)
        if trend_val > 5:
            trend_display = f'<span class="consistency-high">▲ {trend_val:.1f}%</span>'
        elif trend_val < -5:
            trend_display = f'<span class="consistency-low">▼ {trend_val:.1f}%</span>'
        else:
            trend_display = f'<span>— {trend_val:.1f}%</span>'
       
        # Create safe filename for player detail page in players subfolder
        safe_name = player['name'].replace(' ', '_').replace('.', '').replace("'", '')
        detail_link = f"players/player_{safe_name}.html"
        
        html_content += f"""                <tr data-position="{player['position']}" data-games="{player['games']}">
                    <td>{idx}</td>
                    <td><strong><a href="{detail_link}" style="color: #667eea; text-decoration: none;">{player['name']}</a></strong></td>
                    <td><span class="position {player['position']}">{player['position']}</span></td>
                    <td class="team-name">{player['team']}</td>
                    <td>{dynasty_owner}</td>
                    <td>{chopped_owner}</td>
                    <td>{player['games']}</td>
                    <td>{player['total_points']:.1f}</td>
                    <td>{player['avg_ppg']:.1f}</td>
                    <td class="team-name">{player['position_avg']:.1f}</td>
                    <td class="{vs_pos_class}">{vs_pos_sign}{player['vs_position_avg']:.1f}</td>
                    <td>{player['std_dev']:.1f}</td>
                    <td class="{consistency_class}">{player['consistency']:.2f}</td>
                    <td>{player['best_game']:.1f}</td>
                    <td>{player['worst_game']:.1f}</td>
                    <td>{player['median']:.1f}</td>
                    <td>{player['pct_above_avg']:.1f}%</td>
                    <td>{trend_display}</td>
                    <td>{age}</td>
                    <td>{avg_targets}</td>
                    <td>{avg_receptions}</td>
                    <td>{avg_rushes}</td>
                    <td>{avg_rushing_yds}</td>
                    <td>{avg_receiving_yds}</td>
                    <td>{snap_display}</td>
                </tr>
"""
   
    html_content += """            </tbody>
        </table>
    </div>
   
    <script>
        function sortTable(columnIndex) {
            const table = document.getElementById("playerTable");
            const tbody = table.querySelector("tbody");
            const rows = Array.from(tbody.querySelectorAll("tr"));
           
            // Determine sort direction
            const currentDir = table.dataset.sortDir || "desc";
            const newDir = currentDir === "desc" ? "asc" : "desc";
            table.dataset.sortDir = newDir;
           
            rows.sort((a, b) => {
                let aVal = a.cells[columnIndex].textContent.trim();
                let bVal = b.cells[columnIndex].textContent.trim();
               
                // Remove % sign and parse as number for percentage columns
                aVal = aVal.replace('%', '');
                bVal = bVal.replace('%', '');
               
                // Try to parse as numbers
                const aNum = parseFloat(aVal);
                const bNum = parseFloat(bVal);
               
                if (!isNaN(aNum) && !isNaN(bNum)) {
                    return newDir === "desc" ? bNum - aNum : aNum - bNum;
                } else {
                    return newDir === "desc" ?
                        bVal.localeCompare(aVal) :
                        aVal.localeCompare(bVal);
                }
            });
           
            // Re-append sorted rows
            rows.forEach(row => tbody.appendChild(row));
           
            // Update rank numbers
            const visibleRows = Array.from(tbody.querySelectorAll("tr")).filter(row =>
                row.style.display !== "none"
            );
            visibleRows.forEach((row, idx) => {
                row.cells[0].textContent = idx + 1;
            });
        }
       
        function setPositionFilter(position) {
            // Update hidden input
            document.getElementById("positionFilter").value = position;
           
            // Update tab styling
            document.querySelectorAll('.position-tab').forEach(tab => {
                tab.classList.remove('active');
            });
            event.target.classList.add('active');
           
            // Apply filter
            filterTable();
        }
       
        function filterTable() {
            const posFilter = document.getElementById("positionFilter").value;
            const minGames = parseInt(document.getElementById("minGames").value) || 0;
            const searchText = document.getElementById("searchPlayer").value.toLowerCase();
           
            const tbody = document.getElementById("playerTable").querySelector("tbody");
            const rows = tbody.querySelectorAll("tr");
           
            let visibleCount = 0;
            rows.forEach(row => {
                const position = row.dataset.position;
                const games = parseInt(row.dataset.games);
                const playerName = row.cells[1].textContent.toLowerCase();
               
                const posMatch = posFilter === "ALL" || position === posFilter;
                const gamesMatch = games >= minGames;
                const nameMatch = playerName.includes(searchText);
               
                if (posMatch && gamesMatch && nameMatch) {
                    row.style.display = "";
                    visibleCount++;
                    row.cells[0].textContent = visibleCount;
                } else {
                    row.style.display = "none";
                }
            });
        }
        
        // Column visibility functions
        function toggleColumnSelector() {
            const selector = document.getElementById('columnSelector');
            selector.style.display = selector.style.display === 'none' ? 'block' : 'none';
        }
        
        function applyColumnSettings() {
            const table = document.getElementById('playerTable');
            const checkboxes = document.querySelectorAll('.col-toggle');
            
            checkboxes.forEach(checkbox => {
                const colIndex = parseInt(checkbox.dataset.col);
                const visible = checkbox.checked;
                
                // Toggle header
                const headers = table.querySelectorAll('thead th');
                if (headers[colIndex]) {
                    headers[colIndex].style.display = visible ? '' : 'none';
                }
                
                // Toggle cells
                const rows = table.querySelectorAll('tbody tr');
                rows.forEach(row => {
                    if (row.cells[colIndex]) {
                        row.cells[colIndex].style.display = visible ? '' : 'none';
                    }
                });
            });
        }
        
        // Comparison functions
        const playerData = """ + json.dumps([{
            'name': p['name'],
            'position': p['position'],
            'team': p['team'],
            'games': p['games'],
            'total_points': round(p['total_points'], 1),
            'avg_ppg': round(p['avg_ppg'], 1),
            'consistency': round(p['consistency'], 2),
            'trend_pct': round(p.get('trend_pct', 0), 1),
            'nfl_stats': {
                'age': p.get('nfl_stats', {}).get('age'),
                'avg_targets': p.get('nfl_stats', {}).get('avg_targets'),
                'avg_receptions': p.get('nfl_stats', {}).get('avg_receptions'),
                'avg_rushes': p.get('nfl_stats', {}).get('avg_rushes'),
                'avg_rushing_yds': p.get('nfl_stats', {}).get('avg_rushing_yds'),
                'avg_receiving_yds': p.get('nfl_stats', {}).get('avg_receiving_yds'),
                'avg_snap_pct': p.get('nfl_stats', {}).get('avg_snap_pct')
            }
        } for p in player_stats]) + """;
        
        function openCompare() {
            document.getElementById('compareModal').style.display = 'block';
        }
        
        function closeCompare() {
            document.getElementById('compareModal').style.display = 'none';
        }
        
        function runComparison() {
            const p1Name = document.getElementById('comparePlayer1').value;
            const p2Name = document.getElementById('comparePlayer2').value;
            
            const player1 = playerData.find(p => p.name === p1Name);
            const player2 = playerData.find(p => p.name === p2Name);
            
            if (!player1 || !player2) {
                document.getElementById('comparisonResult').innerHTML = '<p style="color: red;">Please select two valid players</p>';
                return;
            }
            
            let html = '<table style="width: 100%; border-collapse: collapse;">';
            html += '<tr style="background: #667eea; color: white;"><th style="padding: 10px;">Stat</th><th style="padding: 10px;">' + player1.name + '</th><th style="padding: 10px;">' + player2.name + '</th><th style="padding: 10px;">Difference</th></tr>';
            
            const compareStats = [
                {label: 'Position', key: 'position', isNum: false},
                {label: 'Team', key: 'team', isNum: false},
                {label: 'Games Played', key: 'games', isNum: true},
                {label: 'Total Points', key: 'total_points', isNum: true},
                {label: 'Avg PPG', key: 'avg_ppg', isNum: true},
                {label: 'Consistency', key: 'consistency', isNum: true},
                {label: 'Trend %', key: 'trend_pct', isNum: true},
                {label: 'Age', key: 'nfl_stats.age', isNum: true},
                {label: 'Avg Targets', key: 'nfl_stats.avg_targets', isNum: true},
                {label: 'Avg Receptions', key: 'nfl_stats.avg_receptions', isNum: true},
                {label: 'Avg Rush Att', key: 'nfl_stats.avg_rushes', isNum: true},
                {label: 'Avg Rush Yds', key: 'nfl_stats.avg_rushing_yds', isNum: true},
                {label: 'Avg Rec Yds', key: 'nfl_stats.avg_receiving_yds', isNum: true},
                {label: 'Snap %', key: 'nfl_stats.avg_snap_pct', isNum: true}
            ];
            
            compareStats.forEach((stat, idx) => {
                const bg = idx % 2 === 0 ? '#f8f9fa' : 'white';
                const keys = stat.key.split('.');
                let val1 = player1;
                let val2 = player2;
                keys.forEach(k => {
                    val1 = val1?.[k];
                    val2 = val2?.[k];
                });
                
                let diff = '';
                if (stat.isNum && val1 != null && val2 != null) {
                    const d = val1 - val2;
                    const color = d > 0 ? 'green' : (d < 0 ? 'red' : 'gray');
                    diff = '<span style="color: ' + color + '; font-weight: bold;">' + (d > 0 ? '+' : '') + d.toFixed(1) + '</span>';
                }
                
                html += '<tr style="background: ' + bg + ';"><td style="padding: 10px; font-weight: bold;">' + stat.label + '</td><td style="padding: 10px;">' + (val1 || '-') + '</td><td style="padding: 10px;">' + (val2 || '-') + '</td><td style="padding: 10px;">' + diff + '</td></tr>';
            });
            
            html += '</table>';
            document.getElementById('comparisonResult').innerHTML = html;
        }
    </script>
    </div>
</body>
</html>
"""
   
    # Write to file
    with open(safe_filename, 'w', encoding='utf-8') as f:
        f.write(html_content)
   
    print(f"  + Generated: {safe_filename}")
