from lib.log import log

from sync import fixtures as sync_fixtures
from sync import match_details as sync_match_details
from sync import reconcile_goals
from sync import standings as sync_standings


def main():

    log("##################################################")
    log("FOOTBALL_DATA SYNC RUN START")
    log("##################################################")

    try:
        sync_fixtures.main()
    except Exception as error:
        log(f"FATAL in sync_fixtures: {error}")

    try:
        sync_match_details.main()
    except Exception as error:
        log(f"FATAL in sync_match_details: {error}")

    try:
        reconcile_goals.main()
    except Exception as error:
        log(f"FATAL in reconcile_goals: {error}")

    try:
        sync_standings.main()
    except Exception as error:
        log(f"FATAL in sync_standings: {error}")

    log("##################################################")
    log("FOOTBALL_DATA SYNC RUN END")
    log("##################################################")


if __name__ == "__main__":
    main()
    
