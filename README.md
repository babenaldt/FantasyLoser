# Fantasy Football Analysis Tool

A comprehensive fantasy football analysis tool that generates detailed player statistics, season reports, and ownership tracking for Sleeper dynasty and redraft leagues.

## Features

- **2025 Season Data**: Automatically loads current NFL season stats using nflreadpy
- **Player Statistics**: Comprehensive stats including PPR scoring, advanced metrics, and trend analysis
- **Ownership Tracking**: Shows which players are owned in your dynasty and chopped leagues
- **Interactive Reports**: Beautiful HTML reports with sortable tables, charts, and player comparisons
- **Advanced Metrics**:
  - Average points per game (PPG)
  - Consistency scores
  - Position comparisons
  - Trend analysis (heating up/cooling down)
  - Snap count percentages
  - Target/reception/rushing averages
  - Age and biographical data

## Installation

1. Clone the repository:
```bash
git clone https://github.com/babenaldt/FantasyLoser.git
cd FantasyLoser
```

2. Create and activate a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install requests certifi nflreadpy pandas numpy
```

## Configuration

Edit `sleeperadvisor.py` and update the following:

```python
MY_LEAGUES = ["your_league_id_1", "your_league_id_2"]
MY_USERNAME = "your_sleeper_username"
```

To find your league ID, go to your Sleeper league and check the URL:
`https://sleeper.com/leagues/YOUR_LEAGUE_ID`

## Usage

### Generate Player Statistics Report

```bash
python sleeperadvisor.py --player-stats
```

This generates an HTML report at `output/player_stats_<league_id>.html` with:
- All NFL players with 2025 season stats
- Rosterable positions only (QB, RB, WR, TE)
- Dynasty and Chopped league ownership
- Advanced stats and metrics
- Interactive sorting and filtering
- Player comparison tool

### Generate Season Reports

```bash
python sleeperadvisor.py
```

This generates season statistics reports for all your leagues with:
- League standings
- Weekly performance
- Award winners (highest scorer, most consistent, etc.)
- Matchup analysis

## Output Files

All reports are saved to the `output/` directory:
- `player_stats_<league_id>.html` - Comprehensive player statistics
- `season_stats_<league_id>.html` - League season summary
- `league_data/` - Cached API responses for faster subsequent runs

## Features in Detail

### Player Statistics Report

- **Customizable Columns**: Toggle which stats to display
- **Position Filtering**: Filter by QB, RB, WR, TE
- **Ownership View**: See which players are available as free agents
- **Sorting**: Click any column header to sort
- **Player Comparison**: Compare two players side-by-side

### Scoring System

Standard PPR scoring:
- Passing: 0.04 points per yard, 4 pts per TD
- Rushing/Receiving: 0.1 points per yard, 6 pts per TD
- Receptions: 1 point (PPR)
- 2-point conversions: 2 points
- Interceptions: -1 point
- Fumbles lost: -2 points

## Data Sources

- **Sleeper API**: League data, rosters, matchups
- **nflverse/nflreadpy**: NFL player stats, snap counts, roster data

## Requirements

- Python 3.8+
- requests
- certifi
- nflreadpy
- pandas
- numpy

## License

MIT License

## Acknowledgments

- [Sleeper API](https://docs.sleeper.com/) for fantasy league data
- [nflverse](https://github.com/nflverse) for NFL statistics
- [nflreadpy](https://github.com/nflverse/nflreadpy) for Python data access

## Contributing

Feel free to open issues or submit pull requests for improvements!
