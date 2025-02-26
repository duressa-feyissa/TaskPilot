import base64
import json
import os

import requests
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow

from config import (AUTH_PROVIDER_X509_CERT_URL, AUTH_URI, GOOGLE_CLIENT_ID,
                    GOOGLE_CLIENT_SECRET, PROJECT_ID, REDIRECT_URI, SCOPES,
                    TOKEN_URI)
from core.application.ports.inbound import IEmailServicePort, IUserServicePort
from core.domain.entity import User
from dependencies import get_email_service, get_user_service

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
router = APIRouter()


flow = Flow.from_client_config(
    {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uris": [REDIRECT_URI[0]],
            "auth_uri": AUTH_URI,
            "token_uri": TOKEN_URI,
        }
    },
    scopes=SCOPES,
    redirect_uri=REDIRECT_URI[0]
)


@router.get("/auth/login")
async def login():
    """
    Redirects the user to the Google OAuth2 authorization URL.
    """
    auth_url, _ = flow.authorization_url(prompt="consent")
    return RedirectResponse(auth_url)


@router.get("/auth/callback")
async def callback(request: Request, auth_service: IUserServicePort = Depends(get_user_service), email_service: IEmailServicePort = Depends(get_email_service)):
    """
    Handles the OAuth2 callback after the user authorizes the app.
    """
    flow.fetch_token(authorization_response=str(request.url))
    credentials = flow.credentials

    access_token = credentials.token
    refresh_token = credentials.refresh_token
    token_uri = credentials.token_uri
    id_token = credentials.id_token

    headers = {"Authorization": f"Bearer {access_token}"}
    user_info_response = requests.get(
        "https://www.googleapis.com/oauth2/v3/userinfo", headers=headers)

    if user_info_response.status_code == 200:
        user_info = user_info_response.json()
        user = User(
            email=user_info.get("email"),
            access_token=access_token,
            refresh_token=refresh_token,
            token_uri=token_uri,
            id_token=id_token,
            name=user_info.get("name"),
            given_name=user_info.get("given_name"),
            family_name=user_info.get("family_name"),
            picture=user_info.get("picture"),
        )
        await auth_service.create_user(user)

        return {"message": "User Logged in successfully"}
    return {"error": "Error getting user info"}


@router.post("/email-notification")
async def email_notification(request: Request, email_service: IEmailServicePort = Depends(get_email_service)):
    try:
        body = await request.json()
        data = json.loads(base64.b64decode(body["message"]["data"]))

        history_id = data.get("historyId")
        user_email = data.get("emailAddress")

        print(f"New email for {user_email}, History ID: {history_id}")

        user = await email_service.get_user_credentials(user_email)
        await email_service.fetch_new_emails(user, history_id)

        return {"message": "Notification received"}
    except Exception as e:
        print(f"Error: {e}")
        return {"error": str(e)}
