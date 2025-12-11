import statistics
import json

def generate_defense_stats_report(defense_data, output_dir="output"):
    """Generate an HTML report with comprehensive defensive statistics."""
    import os
    
    safe_filename = os.path.join(output_dir, "defense_stats.html")
    print(f"  Generating defense stats report: {safe_filename}")
    
    # Sort defenses by total fantasy points allowed
    sorted_defenses = sorted(defense_data, key=lambda x: x.get('total_points_allowed', 0))
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NFL Defense Statistics - 2025</title>
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
        .position-tabs {{
            background: white;
            padding: 15px;
            border-radius: 15px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.1);
            margin-bottom: 20px;
            text-align: center;
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
        .rank {{
            font-weight: bold;
            color: #667eea;
        }}
        .rank-1 {{ color: #f39c12; }}
        .rank-2 {{ color: #95a5a6; }}
        .rank-3 {{ color: #cd7f32; }}
        .team-name {{
            font-weight: 600;
            font-size: 1.1em;
        }}
        .good {{ color: #27ae60; font-weight: bold; }}
        .bad {{ color: #e74c3c; font-weight: bold; }}
        .chart-container {{
            background: white;
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        .chart-container h3 {{
            color: #667eea;
            margin-bottom: 20px;
        }}
    </style>
</head>
<body>
    <nav class="nav-bar">
        <div class="nav-title">🏈 Fantasy Tool</div>
        <div class="nav-links">
            <a href="index.html">Home</a>
            <a href="player_stats.html">Player Stats</a>
            <a href="defense_stats.html" class="active">Defense Stats</a>
            <a href="season_stats_dynasty.html">Dynasty Stats</a>
            <a href="season_stats_chopped.html">Chopped Stats</a>
        </div>
    </nav>
    <div class="content-wrapper">
    <div class="header">
        <h1>NFL Defense Statistics</h1>
        <div class="subtitle">2025 Season - Fantasy Points Allowed Analysis</div>
    </div>
    
    <div class="position-tabs">
        <button class="position-tab active" onclick="setPositionFilter('ALL')">All Defenses</button>
        <button class="position-tab" onclick="setPositionFilter('QB')">vs QB</button>
        <button class="position-tab" onclick="setPositionFilter('RB')">vs RB</button>
        <button class="position-tab" onclick="setPositionFilter('WR')">vs WR</button>
        <button class="position-tab" onclick="setPositionFilter('TE')">vs TE</button>
    </div>
    
    <div class="filters">
        <input type="hidden" id="positionFilter" value="ALL">
        <div class="filter-group">
            <label for="searchTeam">Search Team:</label>
            <input type="text" id="searchTeam" placeholder="Team name..." onkeyup="filterTable()">
        </div>
        <div class="filter-group">
            <label for="sortBy">Sort By:</label>
            <select id="sortBy" onchange="sortTable(this.value)">
                <option value="total">Total Points Allowed</option>
                <option value="qb">QB Points Allowed</option>
                <option value="rb">RB Points Allowed</option>
                <option value="wr">WR Points Allowed</option>
                <option value="te">TE Points Allowed</option>
                <option value="rush_yds">Rush Yards Allowed</option>
                <option value="rec_yds">Receiving Yards Allowed</option>
            </select>
        </div>
    </div>
    
    <div class="chart-container">
        <h3>Fantasy Points Allowed by Position</h3>
        <canvas id="positionChart"></canvas>
    </div>
    
    <div class="stats-container">
        <h2 style="margin-bottom: 20px; color: #667eea;">Defense Rankings</h2>
        <table id="defenseTable">
            <thead>
                <tr>
                    <th onclick="sortTableByColumn(0)">Rank</th>
                    <th onclick="sortTableByColumn(1)">Team</th>
                    <th onclick="sortTableByColumn(2)" title="Total fantasy points allowed">Total Pts</th>
                    <th onclick="sortTableByColumn(3)" title="Average fantasy points allowed per game">Avg PPG</th>
                    <th onclick="sortTableByColumn(4)" title="Fantasy points allowed to QBs">QB Pts</th>
                    <th onclick="sortTableByColumn(5)" title="Fantasy points allowed to RBs">RB Pts</th>
                    <th onclick="sortTableByColumn(6)" title="Fantasy points allowed to WRs">WR Pts</th>
                    <th onclick="sortTableByColumn(7)" title="Fantasy points allowed to TEs">TE Pts</th>
                    <th onclick="sortTableByColumn(8)" title="Total rushing yards allowed">Rush Yds</th>
                    <th onclick="sortTableByColumn(9)" title="Average rushing yards per game">Rush Yds/G</th>
                    <th onclick="sortTableByColumn(10)" title="Rushing TDs allowed">Rush TDs</th>
                    <th onclick="sortTableByColumn(11)" title="Total receiving yards allowed">Rec Yds</th>
                    <th onclick="sortTableByColumn(12)" title="Average receiving yards per game">Rec Yds/G</th>
                    <th onclick="sortTableByColumn(13)" title="Receiving TDs allowed">Rec TDs</th>
                    <th onclick="sortTableByColumn(14)" title="Passing TDs allowed">Pass TDs</th>
                </tr>
            </thead>
            <tbody>
"""
    
    # Add defense rows
    for idx, defense in enumerate(sorted_defenses, 1):
        team = defense.get('team', 'UNK')
        total_pts = defense.get('total_points_allowed', 0)
        games = defense.get('games', 1)
        avg_ppg = total_pts / games if games > 0 else 0
        
        qb_pts = defense.get('qb_points_allowed', 0)
        rb_pts = defense.get('rb_points_allowed', 0)
        wr_pts = defense.get('wr_points_allowed', 0)
        te_pts = defense.get('te_points_allowed', 0)
        
        rush_yds = defense.get('rushing_yards_allowed', 0)
        rush_yds_pg = rush_yds / games if games > 0 else 0
        rush_tds = defense.get('rushing_tds_allowed', 0)
        
        rec_yds = defense.get('receiving_yards_allowed', 0)
        rec_yds_pg = rec_yds / games if games > 0 else 0
        rec_tds = defense.get('receiving_tds_allowed', 0)
        pass_tds = defense.get('passing_tds_allowed', 0)
        
        rank_class = f"rank-{idx}" if idx <= 3 else "rank"
        
        html_content += f"""                <tr data-team="{team}" data-qb="{qb_pts}" data-rb="{rb_pts}" data-wr="{wr_pts}" data-te="{te_pts}">
                    <td class="{rank_class}">{idx}</td>
                    <td class="team-name">{team}</td>
                    <td>{total_pts:.1f}</td>
                    <td>{avg_ppg:.1f}</td>
                    <td>{qb_pts:.1f}</td>
                    <td>{rb_pts:.1f}</td>
                    <td>{wr_pts:.1f}</td>
                    <td>{te_pts:.1f}</td>
                    <td>{rush_yds:.0f}</td>
                    <td>{rush_yds_pg:.1f}</td>
                    <td>{rush_tds}</td>
                    <td>{rec_yds:.0f}</td>
                    <td>{rec_yds_pg:.1f}</td>
                    <td>{rec_tds}</td>
                    <td>{pass_tds}</td>
                </tr>
"""
    
    # Prepare data for chart
    team_names = [d['team'] for d in sorted_defenses]
    qb_points = [d.get('qb_points_allowed', 0) for d in sorted_defenses]
    rb_points = [d.get('rb_points_allowed', 0) for d in sorted_defenses]
    wr_points = [d.get('wr_points_allowed', 0) for d in sorted_defenses]
    te_points = [d.get('te_points_allowed', 0) for d in sorted_defenses]
    
    html_content += f"""            </tbody>
        </table>
    </div>
    
    <script>
        const allDefenseData = {json.dumps([{
            'team': d['team'],
            'total': d.get('total_points_allowed', 0),
            'qb': d.get('qb_points_allowed', 0),
            'rb': d.get('rb_points_allowed', 0),
            'wr': d.get('wr_points_allowed', 0),
            'te': d.get('te_points_allowed', 0),
            'rush_yds': d.get('rushing_yards_allowed', 0),
            'rec_yds': d.get('receiving_yards_allowed', 0),
            'games': d.get('games', 1)
        } for d in sorted_defenses])};
        
        // Position Chart
        const ctx = document.getElementById('positionChart').getContext('2d');
        const chart = new Chart(ctx, {{
            type: 'bar',
            data: {{
                labels: {json.dumps(team_names)},
                datasets: [
                    {{
                        label: 'QB Points',
                        data: {json.dumps(qb_points)},
                        backgroundColor: 'rgba(231, 76, 60, 0.7)',
                        borderColor: 'rgba(231, 76, 60, 1)',
                        borderWidth: 1
                    }},
                    {{
                        label: 'RB Points',
                        data: {json.dumps(rb_points)},
                        backgroundColor: 'rgba(52, 152, 219, 0.7)',
                        borderColor: 'rgba(52, 152, 219, 1)',
                        borderWidth: 1
                    }},
                    {{
                        label: 'WR Points',
                        data: {json.dumps(wr_points)},
                        backgroundColor: 'rgba(46, 204, 113, 0.7)',
                        borderColor: 'rgba(46, 204, 113, 1)',
                        borderWidth: 1
                    }},
                    {{
                        label: 'TE Points',
                        data: {json.dumps(te_points)},
                        backgroundColor: 'rgba(243, 156, 18, 0.7)',
                        borderColor: 'rgba(243, 156, 18, 1)',
                        borderWidth: 1
                    }}
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: true,
                aspectRatio: 2,
                scales: {{
                    x: {{
                        stacked: true,
                        title: {{
                            display: true,
                            text: 'Team'
                        }}
                    }},
                    y: {{
                        stacked: true,
                        beginAtZero: true,
                        title: {{
                            display: true,
                            text: 'Fantasy Points Allowed'
                        }}
                    }}
                }},
                plugins: {{
                    legend: {{
                        display: true,
                        position: 'top'
                    }},
                    tooltip: {{
                        mode: 'index',
                        intersect: false
                    }}
                }}
            }}
        }});
        
        function setPositionFilter(position) {{
            document.getElementById("positionFilter").value = position;
            
            // Update tab styling
            document.querySelectorAll('.position-tab').forEach(tab => {{
                tab.classList.remove('active');
            }});
            event.target.classList.add('active');
            
            filterTable();
        }}
        
        function filterTable() {{
            const searchText = document.getElementById("searchTeam").value.toLowerCase();
            const posFilter = document.getElementById("positionFilter").value;
            
            const tbody = document.getElementById("defenseTable").querySelector("tbody");
            const rows = tbody.querySelectorAll("tr");
            
            rows.forEach(row => {{
                const team = row.dataset.team.toLowerCase();
                const matchesSearch = team.includes(searchText);
                
                row.style.display = matchesSearch ? "" : "none";
            }});
            
            // Update rankings for visible rows
            updateRankings();
        }}
        
        function updateRankings() {{
            const tbody = document.getElementById("defenseTable").querySelector("tbody");
            const visibleRows = Array.from(tbody.querySelectorAll("tr")).filter(row =>
                row.style.display !== "none"
            );
            visibleRows.forEach((row, idx) => {{
                const rankCell = row.cells[0];
                rankCell.textContent = idx + 1;
                rankCell.className = idx < 3 ? `rank-${{idx + 1}}` : 'rank';
            }});
        }}
        
        function sortTableByColumn(columnIndex) {{
            const table = document.getElementById("defenseTable");
            const tbody = table.querySelector("tbody");
            const rows = Array.from(tbody.querySelectorAll("tr"));
            
            const currentDir = table.dataset.sortDir || "asc";
            const newDir = currentDir === "desc" ? "asc" : "desc";
            table.dataset.sortDir = newDir;
            
            rows.sort((a, b) => {{
                let aVal = a.cells[columnIndex].textContent.trim();
                let bVal = b.cells[columnIndex].textContent.trim();
                
                const aNum = parseFloat(aVal);
                const bNum = parseFloat(bVal);
                
                if (!isNaN(aNum) && !isNaN(bNum)) {{
                    return newDir === "desc" ? bNum - aNum : aNum - bNum;
                }} else {{
                    return newDir === "desc" ?
                        bVal.localeCompare(aVal) :
                        aVal.localeCompare(bVal);
                }}
            }});
            
            rows.forEach(row => tbody.appendChild(row));
            updateRankings();
        }}
        
        function sortTable(sortBy) {{
            const tbody = document.getElementById("defenseTable").querySelector("tbody");
            const rows = Array.from(tbody.querySelectorAll("tr"));
            
            rows.sort((a, b) => {{
                const aTeam = a.dataset.team;
                const bTeam = b.dataset.team;
                const aData = allDefenseData.find(d => d.team === aTeam);
                const bData = allDefenseData.find(d => d.team === bTeam);
                
                let aVal = 0, bVal = 0;
                
                switch(sortBy) {{
                    case 'total': aVal = aData.total; bVal = bData.total; break;
                    case 'qb': aVal = aData.qb; bVal = bData.qb; break;
                    case 'rb': aVal = aData.rb; bVal = bData.rb; break;
                    case 'wr': aVal = aData.wr; bVal = bData.wr; break;
                    case 'te': aVal = aData.te; bVal = bData.te; break;
                    case 'rush_yds': aVal = aData.rush_yds; bVal = bData.rush_yds; break;
                    case 'rec_yds': aVal = aData.rec_yds; bVal = bData.rec_yds; break;
                }}
                
                return aVal - bVal;  // Always ascending (best defenses = fewest points allowed)
            }});
            
            rows.forEach(row => tbody.appendChild(row));
            updateRankings();
        }}
    </script>
    </div>
</body>
</html>
"""
    
    with open(safe_filename, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"  + Generated: {safe_filename}")
    return safe_filename
