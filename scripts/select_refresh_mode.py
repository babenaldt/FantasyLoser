"""Select the data refresh mode for the deployment workflow."""

import argparse


LIVE_SCHEDULES = {
    '17,47 20-23 * * 4',
    '17,47 13-23 * * 0',
    '17,47 20-23 * * 1',
}


def select_refresh_mode(event_name, schedule='', full_refresh=False):
    if event_name == 'workflow_dispatch' and full_refresh:
        return 'all'
    if event_name == 'schedule' and schedule in LIVE_SCHEDULES:
        return 'gameday'
    return 'quick'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--event-name', required=True)
    parser.add_argument('--schedule', default='')
    parser.add_argument('--full-refresh', default='false')
    args = parser.parse_args()
    full_refresh = str(args.full_refresh).lower() in {'1', 'true', 'yes', 'on'}
    print(select_refresh_mode(args.event_name, args.schedule, full_refresh))


if __name__ == '__main__':
    main()
