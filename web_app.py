
from flask import Flask, request, jsonify, render_template_string
import os
import json
import requests
import time

from core.settings import MODEL

app = Flask(__name__)

# --------------------------------------------------
# SETTINGS
# --------------------------------------------------

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = "gemini-3.5-flash-lite"

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_PUBLISHABLE_KEY = os.environ.get(
    "SUPABASE_PUBLISHABLE_KEY", ""
).strip()

AI_NAME = "A.M."
CREATOR_NAME = "Aabel Mathew"

SYSTEM_PROMPT = f"""
You are {AI_NAME}, the AI assistant inside Future AI.

Your name is A.M.
Your creator is Aabel Mathew.
You were created by Aabel Mathew.

Never claim that your name is Zapp.
Never claim that Alibaba Cloud created you.
Never claim that Google created you.
Do not contradict your identity.

Be friendly, clear, and helpful.
Give simple explanations when appropriate.
Do not claim to have performed actions you have not performed.
"""

_GEMINI_CLIENT = None


# --------------------------------------------------
# SUPABASE AUTHENTICATION
# --------------------------------------------------

def get_authenticated_user():
    """Verify the signed-in user's access token with Supabase."""

    if not SUPABASE_URL or not SUPABASE_PUBLISHABLE_KEY:
        return None, (
            "Authentication is not configured on the server.",
            503
        )

    auth_header = request.headers.get("Authorization", "")

    if not auth_header.startswith("Bearer "):
        return None, ("Please sign in to continue.", 401)

    token = auth_header.split(" ", 1)[1].strip()

    if not token:
        return None, ("Please sign in to continue.", 401)

    try:
        response = requests.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={
                "apikey": SUPABASE_PUBLISHABLE_KEY,
                "Authorization": f"Bearer {token}"
            },
            timeout=10
        )
    except requests.RequestException:
        app.logger.exception("Could not verify Supabase session")
        return None, (
            "Could not verify your session. Please try again.",
            503
        )

    if response.status_code != 200:
        return None, (
            "Your session has expired. Please sign in again.",
            401
        )

    try:
        user = response.json()
    except ValueError:
        return None, (
            "Could not verify your session. Please sign in again.",
