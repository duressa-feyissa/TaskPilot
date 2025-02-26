import base64
from typing import Any, Dict, List, Optional

import requests
from fastapi import HTTPException
from google.auth.transport.requests import Request
from google.oauth2 import credentials
from googleapiclient.discovery import build

from config import (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, PROJECT_ID,
                    TOKEN_URI, TOPIC_NAME)
from core.application.ports.inbound import IEmailServicePort, IUserServicePort
from core.application.ports.outbound import IUserRepositoryPort
from core.application.schema import EmailData
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
        try:
            service = build('gmail', 'v1', credentials=creds)
            history_response = service.users().history().list(
                userId='me', startHistoryId=history_id
            ).execute()

            history_records = history_response.get('history', [])

            message_ids = []
            if history_records:
                for record in history_records:
                    if 'messagesAdded' in record:
                        for message_added in record['messagesAdded']:
                            message_ids.append(message_added['message']['id'])

            messages_json: List[EmailData] = []
            for message_id in message_ids:
                message = service.users().messages().get(
                    userId='me', id=message_id, format='full'
                ).execute()

                headers = {header["name"]: header["value"]
                           for header in message["payload"]["headers"]}

                email_data = EmailData(
                    id=message["id"],
                    threadId=message["threadId"],
                    labelIds=message.get("labelIds", []),
                    snippet=message.get("snippet", ""),
                    headers=headers,
                )

                payload = message["payload"]
                body_data = ""

                if "parts" in payload:
                    for part in payload["parts"]:
                        if part["mimeType"] == "text/plain":
                            body_data = part["body"].get("data", "")
                            break
                        elif part["mimeType"] == "text/html":
                            body_data = part["body"].get("data", "")
                            if not body_data and "parts" in part:
                                for inner_part in part["parts"]:
                                    if inner_part["mimeType"] == "text/html":
                                        body_data = inner_part["body"].get(
                                            "data", "")
                                        break
                            if body_data:
                                break
                elif "body" in payload and "data" in payload["body"]:
                    body_data = payload["body"]["data"]

                if body_data:
                    try:
                        body_data = base64.urlsafe_b64decode(
                            body_data).decode("utf-8")
                    except Exception as body_decode_error:
                        print(
                            f"Error decoding body for message {message_id}: {body_decode_error}")
                        body_data = f"Decoding Error: {body_decode_error}"

                email_data.body = body_data
                messages_json.append(email_data)
            print(f"Messages: {messages_json}")
            return messages_json

        except Exception as e:
            print(f'An error occurred: {e}')
            return []

    async def store_user_tokens(self, user: User) -> None:
        await self.user_repository.update_user(user.id, user)

    async def get_user_credentials(self, email: str) -> Optional[User]:
        return await self.user_repository.get_user_by_email(email)
