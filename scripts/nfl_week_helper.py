"""Helper functions to determine current NFL week and completed weeks.

NFL 2026 Season: Wed Sept 9 – Sun Jan 10
Each week's last game is Monday Night Football.
A week is considered COMPLETE on Tuesday 6 AM ET (after MNF wraps up).

Timeline:
  Tue Sept  8 06:00 ET  →  week1_boundary  (before this = preseason)
  Tue Sept 15 06:00 ET  →  Week 1 complete
  Tue Sept 22 06:00 ET  →  Week 2 complete
  ...and so on for 18 weeks.
"""

from datetime import datetime, timedelta

# Tuesday 6 AM ET before Week 1 games start (first game is Wed Sept 9)
WEEK1_BOUNDARY = datetime(2026, 9, 8, 6, 0, 0)


def get_current_nfl_week(season_year=2026):
    """
    Determine the current NFL week based on the date.
    Returns the week whose games are currently being played or about to start.

    Returns:
        int: Current week number (1-18). Returns 1 if preseason.
    """
    now = datetime.now()

    if now < WEEK1_BOUNDARY:
        return 1

    days_since = (now - WEEK1_BOUNDARY).days
    current_week = (days_since // 7) + 1

    return min(max(current_week, 1), 18)


def get_last_completed_nfl_week(season_year=2026):
    """
    Return the number of the last fully completed NFL week.
    A week is complete once Tuesday 6 AM ET arrives (after MNF).

    Returns:
        int: 0 if no week has completed yet, otherwise 1-18.
    """
    now = datetime.now()

    if now < WEEK1_BOUNDARY:
        return 0

    days_since = (now - WEEK1_BOUNDARY).days
    completed = days_since // 7  # Week 1 completes at day 7 (next Tuesday)

    return min(max(completed, 0), 18)


if __name__ == "__main__":
    week = get_current_nfl_week()
    completed = get_last_completed_nfl_week()
    print(f"Current NFL Week: {week}")
    print(f"Last Completed Week: {completed}")
