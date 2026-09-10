import os

from dotenv import load_dotenv
from supabase import create_client, Client


# =========================================================
# LOAD ENVIRONMENT VARIABLES
# =========================================================

load_dotenv(override=True)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")


# =========================================================
# VALIDATE CONFIGURATION
# =========================================================

if not SUPABASE_URL:
    raise ValueError(
        "SUPABASE_URL was not found in the .env file."
    )

if not SUPABASE_SECRET_KEY:
    raise ValueError(
        "SUPABASE_SECRET_KEY was not found in the .env file."
    )

if not SUPABASE_SECRET_KEY.startswith("sb_secret_"):
    raise ValueError(
        "SUPABASE_SECRET_KEY does not look like a valid "
        "Supabase secret key."
    )


# =========================================================
# TRUSTED COLLECTOR CLIENT
# =========================================================

collector_supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SECRET_KEY
)


# =========================================================
# CONNECTION TEST
# =========================================================

def test_collector_connection():

    try:
        response = (
            collector_supabase
            .table("opportunities")
            .select("id")
            .limit(1)
            .execute()
        )

        return {
            "success": True,
            "message": "HelAI trusted collector connected successfully.",
            "data": response.data
        }

    except Exception as error:
        return {
            "success": False,
            "message": str(error),
            "data": None
        }