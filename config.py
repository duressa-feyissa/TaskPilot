import os

GOOGLE_CLIENT_ID = "619052101442-8vmi6o6b8d8l917oiob624ihelmmm5p9.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "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"
GEMINI_API_KEY = "AIzaSyDE4FwC7-L3Adqjs1-GKl7-FiU3yAsIoRo"

REDIRECT_URI = ["http://localhost:8000/auth/callback",
                "https://taskpilot-lwrc.onrender.com/auth/callback"]
SCOPES = SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.settings.basic",
    "https://www.googleapis.com/auth/gmail.settings.sharing",
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/calendar'
]
PROJECT_ID = "astral-field-448905-v3"
AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
TOKEN_URI = "https://oauth2.googleapis.com/token"
AUTH_PROVIDER_X509_CERT_URL = "https://www.googleapis.com/oauth2/v1/certs"
TOPIC_NAME = "gmail-notifications"


