import base64
import html
import json
import os
from datetime import datetime, timedelta, timezone
from typing import List

import jwt
import requests
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from google_auth_oauthlib.flow import Flow

from config import (ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM, AUTH_URI,
                    GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, REDIRECT_URI,
                    SCOPES, SECRET_KEY, TOKEN_URI)
from core.application.ports.inbound import IEmailServicePort, IUserServicePort
from core.application.schema import EmailHistoryRequest
from core.domain.entity import Email, Profile, Token, User, UserInfo
from dependencies import get_email_service, get_user_service

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
router = APIRouter()


def create_access_token(user: User, expires_delta: timedelta = None):
    to_encode = {"sub": user.email}
    expire = datetime.now(timezone.utc) + \
        (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {
            "sub": payload.get("sub")
        }
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def create_access_token(user: User, expires_delta: timedelta = None):
    to_encode = {"sub": user.email}
    expire = datetime.now(timezone.utc) + \
        (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {
            "sub": payload.get("sub"),
        }
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_token_from_header(request: Request):
    authorization_header = request.headers.get("Authorization")
    if not authorization_header:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Authorization header missing")

    try:
        scheme, token = authorization_header.split()
        if scheme.lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization scheme")
        return token
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid authorization header format")


def get_current_user(request: Request):
    token = get_token_from_header(request)
    try:
        payload = verify_access_token(token)

        user = UserInfo(email=payload["sub"])

        return user
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        )


flow = Flow.from_client_config(
    {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uris": [REDIRECT_URI[0], REDIRECT_URI[1]],
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


@router.get("/auth/callback", response_model=Token)
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
        await email_service.watch_user(user)
        access_token = create_access_token(user)
        chrome_extension_url = "chrome-extension://nnklciemhdhkoeieljphgcffbcfbikmm/callback.html"
        url = f"{chrome_extension_url}?token={access_token}"
        redirect_url = f"http://127.0.0.1:8000/redirect?token={access_token}"
        return RedirectResponse(url=redirect_url)
    return {"error": "Error getting user info"}


@router.get("/redirect", response_class=HTMLResponse)
async def redirect_page(token: str = Query(None, description="JWT token for authentication")):
    if not token:
        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Error</title>
            </head>
            <body>
                <h1>Error: Missing token</h1>
            </body>
            </html>
            """,
            status_code=400
        )

    safe_token = html.escape(token)

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Processing...</title>
        <script>
            window.onload = function() {{
                const token = "{safe_token}";

                // Send the token to the Chrome extension using window.postMessage
                window.postMessage({{ type: "FROM_PAGE", token: token }}, "*");

                document.body.innerHTML = "<h1>Token sent successfully!</h1>";
            }};
        </script>
    </head>
    <body>
        <h1>Processing...</h1>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@router.post("/email-notification")
async def email_notification(request: Request,  auth_service: IUserServicePort = Depends(get_user_service), email_service: IEmailServicePort = Depends(get_email_service)):
    try:
        body = await request.json()
        data = json.loads(base64.b64decode(body["message"]["data"]))

        history_id = data.get("historyId")
        user_email = data.get("emailAddress")

        print(f"New email for {user_email}, History ID: {history_id}")

        user = await email_service.get_user_credentials(user_email)
        data = []
        if not user.history_id:
            data = await email_service.process_emails(user, user.history_id)
        else:
            data = await email_service.process_emails(user, history_id)

        if len(data) > 0:
            user.history_id = history_id
            await auth_service.update_user(user)

        return {"message": "Notification received"}
    except Exception as e:
        print(f"Error: {e}")
        return {"error": str(e)}


@router.post("/test")
async def email_notification(request: EmailHistoryRequest, email_service: IEmailServicePort = Depends(get_email_service)):
    try:

        user = await email_service.get_user_credentials(request.email)
        if not user:
            raise
        return await email_service.process_emails(user, request.history_id)
    except Exception as e:
        print(f"Error: {e}")
        return {"error": str(e)}


@router.get("/emails", response_model=List[Email])
async def read_users_email(current_user: UserInfo = Depends(get_current_user), email_service: IEmailServicePort = Depends(get_email_service)):
    return await email_service.get_emails(current_user.email, 0, 10)


@router.get("/me", response_model=Profile)
async def read_users_email(current_user: UserInfo = Depends(get_current_user), auth_service: IUserServicePort = Depends(get_user_service)):
    result = await auth_service.get_user_by_email(current_user.email)
    return Profile(
        id=result.id,
        email=result.email,
        name=result.name,
        given_name=result.given_name,
        family_name=result.family_name,
        picture=result.picture
    )
