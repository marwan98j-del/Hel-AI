import os

from dotenv import load_dotenv
from supabase import create_client


# =========================================================
# CONFIGURATION
# =========================================================

load_dotenv(override=True)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


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

def create_supabase_client():
    return create_client(
        SUPABASE_URL,
        SUPABASE_KEY
    )


# =========================================================
# SIGN UP
# =========================================================

def sign_up_user(
    email,
    password,
    full_name=""
):
    client = create_supabase_client()

    try:
        response = client.auth.sign_up(
            {
                "email": email,
                "password": password,
                "options": {
                    "data": {
                        "full_name": full_name
                    }
                }
            }
        )

        user = response.user
        session = response.session

        if session:
            message = "Account created successfully."
        else:
            message = (
                "Account created. "
                "Please check your email for confirmation."
            )

        return {
            "success": True,
            "message": message,
            "user_id": str(user.id) if user else None,
            "email": user.email if user else email,
            "session": session
        }

    except Exception as error:
        return {
            "success": False,
            "message": str(error),
            "user_id": None,
            "email": None,
            "session": None
        }


# =========================================================
# SIGN IN
# =========================================================

def sign_in_user(
    email,
    password
):
    client = create_supabase_client()

    try:
        response = client.auth.sign_in_with_password(
            {
                "email": email,
                "password": password
            }
        )

        user = response.user
        session = response.session

        if not user or not session:
            return {
                "success": False,
                "message": "Login failed.",
                "user": None,
                "access_token": None,
                "refresh_token": None
            }

        return {
            "success": True,
            "message": "Signed in successfully.",
            "user": {
                "id": str(user.id),
                "email": user.email
            },
            "access_token": session.access_token,
            "refresh_token": session.refresh_token
        }

    except Exception as error:
        return {
            "success": False,
            "message": str(error),
            "user": None,
            "access_token": None,
            "refresh_token": None
        }


# =========================================================
# AUTHENTICATED CLIENT
# =========================================================

def create_authenticated_client(
    access_token,
    refresh_token
):
    client = create_supabase_client()

    client.auth.set_session(
        access_token,
        refresh_token
    )

    return client


# =========================================================
# GET CURRENT USER
# =========================================================

def get_current_user(
    access_token,
    refresh_token
):
    try:
        client = create_authenticated_client(
            access_token,
            refresh_token
        )

        response = client.auth.get_user()
        user = response.user

        if not user:
            return {
                "success": False,
                "message": "No authenticated user found.",
                "user": None
            }

        return {
            "success": True,
            "message": "Authenticated user found.",
            "user": {
                "id": str(user.id),
                "email": user.email
            }
        }

    except Exception as error:
        return {
            "success": False,
            "message": str(error),
            "user": None
        }


# =========================================================
# GET PROFILE
# =========================================================

def get_profile(
    access_token,
    refresh_token
):
    try:
        client = create_authenticated_client(
            access_token,
            refresh_token
        )

        user_response = client.auth.get_user()
        user = user_response.user

        if not user:
            return {
                "success": False,
                "message": "No authenticated user found.",
                "profile": None
            }

        response = (
            client
            .table("profiles")
            .select("*")
            .eq("id", str(user.id))
            .single()
            .execute()
        )

        return {
            "success": True,
            "message": "Profile loaded successfully.",
            "profile": response.data
        }

    except Exception as error:
        return {
            "success": False,
            "message": str(error),
            "profile": None
        }


# =========================================================
# UPDATE PROFILE
# =========================================================

def update_profile(
    access_token,
    refresh_token,
    profile_data
):
    try:
        client = create_authenticated_client(
            access_token,
            refresh_token
        )

        user_response = client.auth.get_user()
        user = user_response.user

        if not user:
            return {
                "success": False,
                "message": "No authenticated user found.",
                "profile": None
            }

        allowed_fields = {
            "full_name",
            "date_of_birth",
            "nationality",
            "country_of_residence",
            "city",
            "education",
            "field_of_study",
            "grade",
            "work_experience_years",
            "languages",
            "skills",
            "interests",
            "opportunity_types",
            "has_passport",
            "has_ielts",
            "has_portfolio",
            "has_cv",
            "preferred_language",
            "email_notifications",
            "profile_complete"
        }

        clean_data = {
            key: value
            for key, value in profile_data.items()
            if key in allowed_fields
        }

        response = (
            client
            .table("profiles")
            .update(clean_data)
            .eq("id", str(user.id))
            .execute()
        )

        profile = None

        if response.data:
            profile = response.data[0]

        return {
            "success": True,
            "message": "Profile updated successfully.",
            "profile": profile
        }

    except Exception as error:
        return {
            "success": False,
            "message": str(error),
            "profile": None
        }


# =========================================================
# SIGN OUT
# =========================================================

def sign_out_user(
    access_token,
    refresh_token
):
    try:
        client = create_authenticated_client(
            access_token,
            refresh_token
        )

        client.auth.sign_out()

        return {
            "success": True,
            "message": "Signed out successfully."
        }

    except Exception as error:
        return {
            "success": False,
            "message": str(error)
        }