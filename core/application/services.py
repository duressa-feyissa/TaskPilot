from typing import List, Optional

import requests
from fastapi import HTTPException
from google.auth.transport.requests import Request
from google.oauth2 import credentials
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from httplib2 import Credentials

from config import (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, PROJECT_ID,
                    TOKEN_URI, TOPIC_NAME)
from core.application.ports.inbound import IEmailServicePort, IUserServicePort
from core.application.ports.outbound import IUserRepositoryPort
from core.domain.entity import User


class UserService(IUserServicePort):
    def __init__(self, user_repository: IUserRepositoryPort):
        self.user_repository = user_repository

    async def create_user(self, user: User) -> User:
        user_exists = await self.user_repository.get_user_by_email(user.email)
        if user_exists:
            return await self.user_repository.update_user(user_exists.id, user)
        return await self.user_repository.add_user(user)

    async def get_user_by_email(self, email: str) -> User:
        user = await self.user_repository.get_user_by_email(email)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user


class EmailService(IEmailServicePort):
    def __init__(self, user_repository: IUserRepositoryPort):
        self.user_repository = user_repository

    async def watch_user(self, user: User) -> dict:
        """
        Start watching Gmail for a specific user.
        """
        creds = credentials.Credentials(
            token=user.access_token,
            refresh_token=user.refresh_token,
            token_uri=user.token_uri,
            client_id=GOOGLE_CLIENT_ID,
            client_secret=GOOGLE_CLIENT_SECRET
        )

        if not creds.valid:
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                user.access_token = creds.token
                await self.store_user_tokens(user)

        service = build("gmail", "v1", credentials=creds)

        request = {
            "labelIds": ["INBOX"],
            "topicName": f"projects/{PROJECT_ID}/topics/{TOPIC_NAME}"
        }
        response = service.users().watch(userId="me", body=request).execute()
        return response

    async def watch_gmail(self) -> None:
        users = await self.user_repository.get_users()

        # for user in users:
        #     await self.watch_user(user)

        print("------ Finished watching Gmail for all users ------")

    async def fetch_new_emails(self, user: User, history_id: str) -> List[dict]:
        creds = credentials.Credentials(
            token=user.access_token,
            refresh_token=user.refresh_token,
            token_uri=user.token_uri,
            client_id=GOOGLE_CLIENT_ID,
            client_secret=GOOGLE_CLIENT_SECRET
        )

        service = build("gmail", "v1", credentials=creds)

        try:
            response = service.users().history().list(
                userId="me", startHistoryId=history_id
            ).execute()
            print("New emails fetched")
            print("Response: ", response)
            return response.get("history", [])

        except Exception as e:
            print(f"Error fetching emails for {user.email}: {e}")
            return []

    async def store_user_tokens(self, user: User) -> None:
        await self.user_repository.update_user(user.id, user)

    async def get_user_credentials(self, email: str) -> Optional[User]:
        return await self.user_repository.get_user_by_email(email)
