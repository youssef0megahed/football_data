from lib.config import validate_environment
from lib.log import log
from lib.supabase_client import supabase_request, select


# ============================================================
# RECONCILE ONE MATCH
# ============================================================

def reconcile_match(match):

    match_id = match["id"]
    home_team_id = match["home_team_id"]
    away_team_id = match["away_team_id"]
    home_score = match["home_score"]
    away_score = match["away_score"]

    if home_score is None or away_score is None:
        return 0

    goals = select(
        "match_events",
        {
            "select": "id,team_id,minute,extra_time",
            "match_id": f"eq.{match_id}",
            "event_type": "eq.goal",
            "order": "minute.asc",
        },
    )

    home_goals = [g for g in goals if g["team_id"] == home_team_id]
    away_goals = [g for g in goals if g["team_id"] == away_team_id]

    to_invalidate = []

    # لو عدد الأهداف المسجلة أكتر من النتيجة الرسمية، الزيادة
    # دي أهداف اتلغت لاحقًا (VAR/تسلل) وESPN سابها في القايمة.
    # بنشيل الأقدم زمنيًا أولًا (الأقرب لحظيًا للمراجعة الفعلية).

    if len(home_goals) > home_score:

        excess = len(home_goals) - home_score
        to_invalidate.extend(home_goals[:excess])

    if len(away_goals) > away_score:

        excess = len(away_goals) - away_score
        to_invalidate.extend(away_goals[:excess])

    for goal in to_invalidate:

        supabase_request(
            "PATCH",
            "match_events",
            params={"id": f"eq.{goal['id']}"},
            json_body={"event_type": "ignored_disallowed_goal"},
            extra_headers={"Prefer": "return=minimal"},
        )

        log(
            f"  match={match_id}: invalidated goal event "
            f"id={goal['id']} (minute={goal.get('minute')}) "
            f"— exceeded official score"
        )

    return len(to_invalidate)


# ============================================================
# MAIN
# ============================================================

def main():

    validate_environment()

    log("==================================================")
    log("RECONCILE GOALS START")
    log("==================================================")

    matches = select(
        "matches",
        {
            "select": (
                "id,home_team_id,away_team_id,home_score,away_score"
            ),
            "status": "eq.FINISHED",
        },
    )

    log(f"Checking {len(matches)} finished matches")

    total_fixed = 0

    for match in matches:

        try:
            fixed = reconcile_match(match)
            total_fixed += fixed
        except Exception as error:
            log(f"ERROR match={match['id']}: {error}")
            continue

    log("==================================================")
    log(f"Total phantom goal events fixed: {total_fixed}")
    log("RECONCILE GOALS END")
    log("==================================================")


if __name__ == "__main__":
    main()
  
