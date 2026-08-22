from lib.log import log

import sync_fixtures
import sync_match_details
import sync_standings


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
        sync_standings.main()
    except Exception as error:
        log(f"FATAL in sync_standings: {error}")

    log("##################################################")
    log("FOOTBALL_DATA SYNC RUN END")
    log("##################################################")


if __name__ == "__main__":
    main()
