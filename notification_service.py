from collector_client import collector_supabase


# =========================================================
# CONFIGURATION
# =========================================================

MINIMUM_MATCH_SCORE = 70


# =========================================================
# LOAD STRONG UNNOTIFIED MATCHES
# =========================================================

def load_notification_candidates():

    response = (
        collector_supabase
        .table("matches")
        .select("*")
        .eq("eligible", True)
        .gte(
            "match_score",
            MINIMUM_MATCH_SCORE
        )
        .eq("notified", False)
        .execute()
    )

    return response.data or []


# =========================================================
# LOAD USER PROFILE
# =========================================================

def load_profile(user_id):

    response = (
        collector_supabase
        .table("profiles")
        .select(
            "id,"
            "email,"
            "full_name,"
            "email_notifications,"
            "profile_complete,"
            "preferred_language"
        )
        .eq("id", user_id)
        .limit(1)
        .execute()
    )

    if not response.data:
        return None

    return response.data[0]


# =========================================================
# LOAD OPPORTUNITY
# =========================================================

def load_opportunity(opportunity_id):

    response = (
        collector_supabase
        .table("opportunities")
        .select(
            "id,"
            "title,"
            "organization,"
            "type,"
            "location,"
            "deadline,"
            "status,"
            "source_url"
        )
        .eq("id", opportunity_id)
        .limit(1)
        .execute()
    )

    if not response.data:
        return None

    return response.data[0]


# =========================================================
# CHECK EXISTING NOTIFICATION
# =========================================================

def notification_exists(match_id):

    response = (
        collector_supabase
        .table("notifications")
        .select("id,status")
        .eq("match_id", match_id)
        .eq("channel", "email")
        .limit(1)
        .execute()
    )

    return bool(response.data)


# =========================================================
# CREATE PENDING NOTIFICATION
# =========================================================

def create_notification(match_record):

    match_id = match_record["id"]

    if notification_exists(match_id):
        return {
            "created": False,
            "reason": "Notification already exists."
        }

    profile = load_profile(
        match_record["user_id"]
    )

    if not profile:
        return {
            "created": False,
            "reason": "User profile not found."
        }

    if not profile.get(
        "email_notifications",
        True
    ):
        return {
            "created": False,
            "reason": "Email notifications disabled."
        }

    if not profile.get("email"):
        return {
            "created": False,
            "reason": "User has no email address."
        }

    opportunity = load_opportunity(
        match_record["opportunity_id"]
    )

    if not opportunity:
        return {
            "created": False,
            "reason": "Opportunity not found."
        }

    if opportunity.get("status") != "Open":
        return {
            "created": False,
            "reason": "Opportunity is not open."
        }

    notification_record = {
        "match_id": match_id,
        "user_id": match_record["user_id"],
        "opportunity_id": (
            match_record["opportunity_id"]
        ),
        "channel": "email",
        "status": "pending",
        "attempts": 0
    }

    response = (
        collector_supabase
        .table("notifications")
        .insert(notification_record)
        .execute()
    )

    return {
        "created": True,
        "notification": (
            response.data[0]
            if response.data
            else None
        ),
        "profile": profile,
        "opportunity": opportunity,
        "match": match_record
    }


# =========================================================
# BUILD NOTIFICATION QUEUE
# =========================================================

def build_notification_queue():

    print()
    print("====================================")
    print("      HelAI Notification Queue")
    print("====================================")
    print()

    candidates = (
        load_notification_candidates()
    )

    print(
        "Strong unnotified matches:",
        len(candidates)
    )

    print()

    created_count = 0
    skipped_count = 0

    for match_record in candidates:

        result = create_notification(
            match_record
        )

        if result["created"]:

            created_count += 1

            profile = result["profile"]
            opportunity = result[
                "opportunity"
            ]

            print(
                "QUEUED:",
                opportunity["title"]
            )

            print(
                "User:",
                profile["email"]
            )

            print(
                "Match:",
                f"{match_record['match_score']}%"
            )

            print()

        else:

            skipped_count += 1

            print(
                "SKIPPED:",
                result["reason"]
            )

            print()

    print("====================================")
    print(
        "Notifications queued:",
        created_count
    )
    print(
        "Skipped:",
        skipped_count
    )
    print("====================================")
    print()

    return created_count


# =========================================================
# START
# =========================================================

if __name__ == "__main__":
    build_notification_queue()