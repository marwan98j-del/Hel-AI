import os

from dotenv import load_dotenv
from supabase import create_client


load_dotenv(override=True)


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


def get_supabase_client():

    if not SUPABASE_URL:
        raise ValueError(
            "SUPABASE_URL was not found in .env"
        )

    if not SUPABASE_KEY:
        raise ValueError(
            "SUPABASE_KEY was not found in .env"
        )

    return create_client(
        SUPABASE_URL,
        SUPABASE_KEY
    )


def load_opportunities():

    client = get_supabase_client()

    result = (
        client
        .table("opportunities")
        .select("*")
        .eq("active", True)
        .execute()
    )

    opportunities = (
        result.data or []
    )

    return opportunities