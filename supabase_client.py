import os

from dotenv import load_dotenv
from supabase import create_client, Client


# =========================================================
# LOAD ENVIRONMENT VARIABLES
# =========================================================

load_dotenv(override=True)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


# =========================================================
# VALIDATE CONFIGURATION
# =========================================================

if not SUPABASE_URL:
    raise ValueError(
        "SUPABASE_URL was not found in the .env file."
    )

if not SUPABASE_KEY:
    raise ValueError(
        "SUPABASE_KEY was not found in the .env file."
    )


# =========================================================
# CREATE SUPABASE CLIENT
# =========================================================

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


# =========================================================
# CONNECTION TEST
# =========================================================

def test_supabase_connection():

    try:

        response = (
            supabase
            .table("profiles")
            .select("id")
            .limit(1)
            .execute()
        )

        return {
            "success": True,
            "message": "HelAI connected to Supabase successfully.",
            "data": response.data
        }

    except Exception as error:

        return {
            "success": False,
            "message": str(error),
            "data": None
        }