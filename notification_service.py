from collector_client import collector_supabase
from helai_config import HELAI_MATCH_THRESHOLD
from opportunity_rules import effective_status, normalize_status


# =========================================================
# CONFIGURATION
# =========================================================

MINIMUM_MATCH_SCORE = HELAI_MATCH_THRESHOLD


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
        .execute()
    )

    matches = response.data or []

    return [
        match
        for match in matches
        if not match.get("notified", False)
    ]


# =========================================================
# LOAD USER PROFILE
# =========================================================

def load_profile(user_id):

    response = (
        collector_supabase
        .table("profiles")
        # "*" so notify_telegram is read once the Telegram migration exists
        # and nothing breaks before it does.
        .select("*")
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
# LOAD CANDIDATE OPPORTUNITIES (one query for the whole run)
# =========================================================

def load_opportunities_by_id(opportunity_ids):

    if not opportunity_ids:
        return {}

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
        .in_("id", list(opportunity_ids))
        .execute()
    )

    return {
        opportunity["id"]: opportunity
        for opportunity in (response.data or [])
    }


# =========================================================
# OPEN CHECK
# =========================================================

def not_open_reason(opportunity):
    """None while open; otherwise a reason that says why."""

    status = effective_status(opportunity)

    if status == "Open":
        return None

    deadline = opportunity.get("deadline")

    if (
        status == "Closed"
        and deadline
        and normalize_status(opportunity.get("status")) == "Open"
    ):
        return f"Opportunity is closed (deadline {deadline} passed)."

    return f"Opportunity is not open (status: {status})."


def split_expired(candidates):
    """(matches whose opportunity is still open, [(match, reason)] for closed ones).

    Matching stops re-scoring an opportunity once it closes, so its older
    eligible matches stay unnotified; they are reported apart instead of
    being counted as strong new matches. A missing opportunity stays in the
    first list so create_notification reports it as before.
    """

    opportunities = load_opportunities_by_id(
        {match["opportunity_id"] for match in candidates}
    )

    current = []
    expired = []

    for match in candidates:

        opportunity = opportunities.get(match["opportunity_id"])
        reason = not_open_reason(opportunity) if opportunity else None

        if reason:
            expired.append((match, reason))
        else:
            current.append(match)

    return current, expired


# =========================================================
# CHECK EXISTING NOTIFICATION
# =========================================================

def notification_exists(match_id, channel="email"):

    response = (
        collector_supabase
        .table("notifications")
        .select("id,status")
        .eq("match_id", match_id)
        .eq("channel", channel)
        .limit(1)
        .execute()
    )

    return bool(response.data)


# =========================================================
# CHANNELS
# Email keeps its original rules; Telegram needs the opt-in
# flag and a linked chat.
# =========================================================

def telegram_connected(user_id):

    response = (
        collector_supabase
        .table("telegram_connections")
        .select("user_id")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )

    return bool(response.data)


def enabled_channels(profile):

    channels = []

    if (
        profile.get("email_notifications", True)
        and profile.get("email")
    ):
        channels.append("email")

    if (
        profile.get("notify_telegram", False)
        and telegram_connected(profile["id"])
    ):
        channels.append("telegram")

    return channels


def skipped_reason(profile):
    """The original email-only reasons, kept for users without Telegram."""

    if not profile.get(
        "email_notifications",
        True
    ):
        return "Email notifications disabled."

    if not profile.get("email"):
        return "User has no email address."

    return "No notification channel enabled."


# =========================================================
# CREATE PENDING NOTIFICATION
# =========================================================

def create_notification(match_record):
    """Queue one row per enabled channel; (match_id, channel) is unique."""

    match_id = match_record["id"]

    profile = load_profile(
        match_record["user_id"]
    )

    if not profile:
        return {
            "created": False,
            "reason": "User profile not found."
        }

    profile.setdefault("id", match_record["user_id"])

    channels = enabled_channels(profile)

    if not channels:
        return {
            "created": False,
            "reason": skipped_reason(profile)
        }

    channels = [
        channel
        for channel in channels
        if not notification_exists(match_id, channel)
    ]

    if not channels:
        return {
            "created": False,
            "reason": "Notification already exists."
        }

    opportunity = load_opportunity(
        match_record["opportunity_id"]
    )

    if not opportunity:
        return {
            "created": False,
            "reason": "Opportunity not found."
        }

    reason = not_open_reason(opportunity)

    if reason:
        return {
            "created": False,
            "reason": reason
        }

    notifications = []

    for channel in channels:

        notification_record = {
            "match_id": match_id,
            "user_id": match_record["user_id"],
            "opportunity_id": (
                match_record["opportunity_id"]
            ),
            "channel": channel,
            "status": "pending",
            "attempts": 0
        }

        response = (
            collector_supabase
            .table("notifications")
            .insert(notification_record)
            .execute()
        )

        notifications.append(
            response.data[0]
            if response.data
            else None
        )

    return {
        "created": True,
        "channels": channels,
        "notification": notifications[0],
        "notifications": notifications,
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

    candidates, expired = split_expired(
        load_notification_candidates()
    )

    print(
        "Strong unnotified matches:",
        len(candidates)
    )

    if expired:

        print(
            "Not counted, opportunity closed:",
            len(expired)
        )

        for _match_record, reason in expired:
            print("  -", reason)

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

            print(
                "Channels:",
                ", ".join(result["channels"])
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

    return {
        "strong_new_matches": len(candidates),
        "expired": len(expired),
        "queued": created_count,
        "skipped": skipped_count,
    }


# =========================================================
# START
# =========================================================

if __name__ == "__main__":
    build_notification_queue()
