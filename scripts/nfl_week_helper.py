"""Helper function to determine current NFL week."""

from datetime import datetime, timedelta

def get_current_nfl_week(season_year=2026):
    """
    Determine the current NFL week based on the date.
    Week resets after Monday Night Football (Tuesday 3 AM ET).
    
    Args:
        season_year: NFL season year (default 2026)
    
    Returns:
        int: Current week number (1-18)
    """
    # NFL 2026 Season Start: Wednesday, September 9, 2026
    # Each week runs Tuesday 3 AM ET to following Tuesday 3 AM ET (after MNF)
    
    # Week 1 starts Tuesday Sept 8, 2026 at 3 AM ET
    week1_start = datetime(2026, 9, 8, 3, 0, 0)
    
    # Get current time
    now = datetime.now()
    
    # If before season start, return week 1
    if now < week1_start:
        return 1
    
    # Calculate days since week 1 start
    days_since_start = (now - week1_start).days
    
    # Each week is 7 days
    current_week = (days_since_start // 7) + 1
    
    # Cap at week 18
    if current_week > 18:
        return 18
    
    return current_week


if __name__ == "__main__":
    week = get_current_nfl_week()
    print(f"Current NFL Week: {week}")
