import base64
import datetime
import uuid
from typing import Any, Dict, List, Optional

import dateparser
import googleapiclient
from fastapi import HTTPException
from google import genai
from google.auth.transport.requests import Request
from google.genai import types
from google.oauth2 import credentials
from googleapiclient.discovery import build

from config import (GEMINI_API_KEY, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET,
                    PROJECT_ID, TOPIC_NAME)
from core.application.helper import generate_no_rescheduled_email
from core.application.ports.inbound import IEmailServicePort, IUserServicePort
from core.application.ports.outbound import IUserRepositoryPort
from core.application.schema import EmailData, EmailPriority
from core.domain.entity import Email, User


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

    async def update_user(self, user: User) -> User:
        return await self.user_repository.update_user(user)


class EmailService(IEmailServicePort):
    def __init__(self, user_repository: IUserRepositoryPort):
        self.user_repository = user_repository
        self.client = genai.Client(
            api_key=GEMINI_API_KEY)
        self.MODEL_ID = "gemini-2.0-flash"

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

    async def get_emails(self, receiver_email: str, skip: int, limit: int) -> List[Email]:
        return await self.user_repository.get_emails(receiver_email, skip, limit)

    async def get_latest_email_by_date(self, receiver_email: str) -> Optional[Email]:
        return await self.user_repository.get_latest_email_by_date(receiver_email)

    async def watch_gmail(self) -> None:
        users = await self.user_repository.get_users()

        for user in users:
            await self.watch_user(user)

        print("------ Finished watching Gmail for all users ------")

    async def fetch_latest_unread_email(self, user: User) -> Optional[EmailData]:
        creds = credentials.Credentials(
            token=user.access_token,
            refresh_token=user.refresh_token,
            token_uri=user.token_uri,
            client_id=GOOGLE_CLIENT_ID,
            client_secret=GOOGLE_CLIENT_SECRET
        )
        try:
            service = build('gmail', 'v1', credentials=creds)

            # Fetch unread messages (max 5)
            messages_response = service.users().messages().list(
                userId='me', q='is:unread', maxResults=5
            ).execute()

            messages = messages_response.get('messages', [])
            # Sort messages by internal date (newest first)
            sorted_messages = sorted(messages, key=lambda msg: msg.get(
                'internalDate', 0), reverse=True)

            for message_data in sorted_messages:
                message_id = message_data['id']
                message = service.users().messages().get(
                    userId='me', id=message_id, format='full'
                ).execute()

                if 'UNREAD' in message.get('labelIds', []):
                    headers = {header["name"]: header["value"]
                               for header in message["payload"]["headers"]}

                    sender = headers.get("From", "")
                    sender_name = None
                    sender_email = ""

                    if "<" in sender and ">" in sender:
                        sender_name = sender.split("<")[0].strip()
                        sender_email = sender.split(
                            "<")[1].split(">")[0].strip()
                    else:
                        sender_email = sender.strip()

                    priority = headers.get("Priority", "").lower()
                    priority_enum = (
                        EmailPriority.HIGH if priority == "high" else
                        EmailPriority.MEDIUM if priority == "medium" else
                        EmailPriority.LOW
                    )

                    email_data = EmailData(
                        id=message["id"],
                        threadId=message["threadId"],
                        senderName=sender_name,
                        senderEmail=sender_email,
                        priority=priority_enum
                    )

                    # Extract email body
                    payload = message["payload"]
                    body_data = ""

                    if "parts" in payload:
                        for part in payload["parts"]:
                            if part["mimeType"] == "text/plain":
                                body_data = part["body"].get("data", "")
                                break
                            elif part["mimeType"] == "text/html" and not body_data:
                                body_data = part["body"].get("data", "")

                    elif "body" in payload and "data" in payload["body"]:
                        body_data = payload["body"]["data"]

                    if body_data:
                        try:
                            body_data = base64.urlsafe_b64decode(
                                body_data).decode("utf-8").strip()
                            email_data.body = body_data
                        except Exception as body_decode_error:
                            print(
                                f"Error decoding body for message {message_id}: {body_decode_error}")

                    # Mark message as read
                    service.users().messages().modify(
                        userId='me', id=message_id, body={'removeLabelIds': ['UNREAD']}
                    ).execute()

                    return email_data

            return None

        except Exception as e:
            print(f"Error fetching emails: {e}")
            return None

    async def store_user_tokens(self, user: User) -> None:
        await self.user_repository.update_user(user.id, user)

    async def get_user_credentials(self, email: str) -> Optional[User]:
        return await self.user_repository.get_user_by_email(email)

    async def process_emails(self, user: User, history_id: str, current_history_id: str):
        """
        Processes new emails, handling various scenarios with AI-driven decisions.

        This function retrieves new emails, iterates through them, and calls the
        process_single_email function for each email to determine the appropriate action.
        """
        new_email = await self.fetch_latest_unread_email(user)
        if new_email:
            await self.process_single_email(user, new_email, current_history_id)
            return [new_email]
        return []

    async def process_single_email(self, user: 'User', email_data: 'EmailData', history_id: str):
        """Processes a single email using AI, generates notification title, summary, urgency, and executes actions."""

        generate_reply_func = types.FunctionDeclaration(
            name="generate_reply",
            description="Generates a professional and concise reply to an email.",
            parameters={
                "type": "OBJECT",
                "properties": {
                    "title": {"type": "string", "description": "A short title summarizing the received email."},
                    "summary": {"type": "string", "description": "A brief summary of the received email's content."},
                    "priority": {"type": "string", "enum": ["High", "Medium", "Low"], "description": "The priority level of the email."},
                    "reply_body": {"type": "string", "description": "The generated reply text."},
                },
            },
        )

        schedule_meeting_func = types.FunctionDeclaration(
            name="schedule_meeting",
            description="Schedules a meeting with the given details.",
            parameters={
                "type": "OBJECT",
                "properties": {
                    "title": {"type": "string", "description": "A short title summarizing the received email."},
                    "summary": {"type": "string", "description": "A brief summary of the received email's content."},
                    "priority": {"type": "string", "enum": ["High", "Medium", "Low"], "description": "The priority level of the email."},
                    "date": {"type": "string", "description": "The meeting date (YYYY-MM-DD)."},
                    "time": {"type": "string", "description": "The meeting time (HH:MM)."},
                    "duration_minutes": {"type": "integer", "description": "Duration of the meeting in minutes."},
                    "attendees": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of attendee email addresses.",
                    },
                },
            },
        )

        no_action_required_func = types.FunctionDeclaration(
            name="no_action_required",
            description="Indicates that no action is required for the email.",
            parameters={
                "type": "OBJECT",
                "properties": {
                    "title": {"type": "string", "description": "A short title summarizing the received email."},
                    "summary": {"type": "string", "description": "A brief summary of the received email's content."},
                    "priority": {"type": "string", "enum": ["High", "Medium", "Low"], "description": "The priority level of the email."},
                    "confirmation": {"type": "boolean", "description": "A flag to confirm that no action is required."},
                },
            },
        )

        today_date = datetime.date.today()

        prompt = f"""
        Analyze the following email and determine the appropriate action. Use the provided functions to execute the action.

        ### **Email Content:**  
        {email_data.body}

        Today is {today_date.strftime("%A")}, {today_date.strftime("%Y-%m-%d")}.

        ---

        ### **Instructions:**
        #### **1. Extract Key Information**
        - **Title**: Generate a short, descriptive title summarizing the email's topic.  
        - **Summary**: Provide a concise explanation of the email's key message in a few sentences.  
        - **Priority Level**:
            - **High**: Urgent matters that require immediate action (e.g., critical deadlines, emergency meetings).
            - **Medium**: Important but not urgent (e.g., scheduling discussions, follow-ups).
            - **Low**: Informational emails, notifications, or general updates.

        #### **2. Determine the Appropriate Action**
        - **`generate_reply`** → For responses, clarifications, or communication. The reply body should be clear, professional, and polite, either addressing the main points of the original email, requesting clarification, scheduling a meeting, or confirming no action is required.
        - **`schedule_meeting`** → When the email requests a meeting:
            - Extract the **date** (YYYY-MM-DD) and **time** (HH:MM) if provided.
            - If no time is mentioned, propose a reasonable time (e.g., 14:00).
            - If no date is mentioned, schedule the next available working day.
            - **Duration**: If the email does not specify the meeting duration, use a default value (e.g., 30 minutes).
            - Validate that the date is in the **future** (after {today_date.strftime('%Y-%m-%d')}).
        - **`no_action_required`** → For simple acknowledgments, notifications, or spam.

        #### **3. Generate the Response Message**
        - If scheduling a meeting, provide the **meeting link dynamically** in the reply.
        - Ensure the response is **professional and polite**.
        - If details are missing, request clarification.

        """

        story_tools = types.Tool(
            function_declarations=[generate_reply_func,
                                   schedule_meeting_func, no_action_required_func]
        )

        try:
            response = self.client.models.generate_content(
                model=self.MODEL_ID,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[story_tools],
                    temperature=0
                ),
            )

            if response.candidates and response.candidates[0].content.parts:
                content_part = response.candidates[0].content.parts[0]
                print(content_part)
                function_call = getattr(
                    content_part, "function_call", None)
                if function_call:
                    function_name = function_call.name
                    function_args = function_call.args

                    if function_name == "generate_reply":
                        title = function_args.get("title")
                        reply_body = function_args.get("reply_body")
                        if reply_body and title:
                            self.send_email(
                                email_data.senderEmail, "Re: " + title, reply_body, email_data.threadId, user)
                            await self.user_repository.set_email_history(Email(
                                user_id=user.id,
                                sender_email=email_data.senderEmail,
                                sender_name=email_data.senderName,
                                receiver_email=user.email,
                                history_id=history_id,
                                date=datetime.datetime.now().date(),
                                title=function_args.get("title"),
                                summary=function_args.get("summary"),
                                priority=function_args.get("priority"),
                                read=False
                            ))
                        else:
                            self._handle_processing_error(
                                user, email_data, "Reply title or body missing.")

                    elif function_name == "schedule_meeting":
                        await self._handle_schedule_meeting(
                            user, email_data, function_args)
                        await self.user_repository.set_email_history(Email(
                            user_id=user.id,
                            sender_email=email_data.senderEmail,
                            sender_name=email_data.senderName,
                            receiver_email=user.email,
                            history_id=history_id,
                            date=datetime.datetime.now().date(),
                            title=function_args.get("title"),
                            summary=function_args.get("summary"),
                            priority=function_args.get("priority"),
                            read=False
                        ))
                    elif function_name == "no_action_required":
                        await self.user_repository.set_email_history(Email(
                            user_id=user.id,
                            sender_email=email_data.senderEmail,
                            sender_name=email_data.senderName,
                            receiver_email=user.email,
                            history_id=history_id,
                            date=datetime.datetime.now().date(),
                            title=function_args.get("title"),
                            summary=function_args.get("summary"),
                            priority=function_args.get("priority"),
                            read=False
                        ))
                    else:
                        self._handle_processing_error(
                            user, email_data, f"Unknown function: {function_name}")

                else:
                    self._handle_processing_error(
                        user, email_data, "No function response or incomplete response found.")

            else:
                self._handle_processing_error(
                    user, email_data, "No response candidates found.")

        except Exception as e:
            self._handle_processing_error(user, email_data, f"Exception: {e}")

    async def _handle_schedule_meeting(self, user: 'User', email_data: 'EmailData', function_args: Dict[str, Any]):
        try:

            if "date" in function_args and "time" in function_args and "duration_minutes" in function_args and "attendees" in function_args:
                await self.schedule_meeting_from_details(user, email_data, function_args)
            else:
                self._handle_processing_error(
                    user, email_data, "Meeting details incomplete.")
        except Exception as e:
            self._handle_processing_error(
                user, email_data, f"Error handling meeting: {e}")

    async def schedule_meeting_from_details(self, user: 'User', email_data: 'EmailData', meeting_details: Dict[str, Any]):
        """
        Schedules a meeting based on provided details.
        """
        try:
            meeting_date = meeting_details["date"]
            meeting_time = meeting_details["time"]
            duration_minutes = meeting_details["duration_minutes"]
            attendees = meeting_details["attendees"]

            parsed_datetime = dateparser.parse(
                f"{meeting_date} {meeting_time}")

            if parsed_datetime:
                start_time = parsed_datetime.isoformat()
                end_time = (
                    parsed_datetime + datetime.timedelta(minutes=duration_minutes)).isoformat()

            event = {
                'summary': 'Meeting with ' + ", ".join(attendees),
                'location': 'Virtual Meeting',
                'start': {'dateTime': start_time, 'timeZone': 'Africa/Addis_Ababa'},
                'end': {'dateTime': end_time, 'timeZone': 'Africa/Addis_Ababa'},
                'attendees': [
                    {'email': email_data.senderEmail,
                        'responseStatus': 'needsAction'},

                ],
                'conferenceData': {
                    'createRequest': {
                        'requestId': 'meeting-' + str(uuid.uuid4()),
                        'conferenceSolutionKey': {'type': 'hangoutsMeet'}
                    }
                },
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'email', 'minutes': 10},
                        {'method': 'popup', 'minutes': 5}
                    ]
                }
            }

            service = self.create_calendar_service(user)
            event = service.events().insert(calendarId='primary', body=event,
                                            conferenceDataVersion=1).execute()
            meeting_link = event.get(
                'hangoutLink', 'No meeting link available')
            self.generate_reply_after_event(
                user, email_data, meeting_link, meeting_date, meeting_time, duration_minutes)

        except googleapiclient.errors.HttpError as e:
            if e.resp.status == 409:
                reply = generate_no_rescheduled_email(email_data, user)
                self.send_email(
                    email_data.senderEmail, "Re: Meeting Rescheduled", reply, email_data.threadId, user)
            else:
                self._handle_processing_error(
                    user, email_data, f"I encountered an error while scheduling the meeting: {e}. Please try again later.")
        except Exception as e:
            self._handle_processing_error(
                user, email_data, f"I encountered an error while scheduling the meeting: {e}. Please try again later.")

    def _handle_processing_error(self, user: 'User', email_data: 'EmailData', error_message: str):
        print(f"Error processing email {email_data.id}: {error_message}")

    def create_calendar_service(self, user: 'User') -> Any:
        """
        Creates a Google Calendar service using the user's credentials.

        This function initializes a Calendar API service object using the user's
        access token and refresh token.
        """
        creds = credentials.Credentials(
            token=user.access_token,
            refresh_token=user.refresh_token,
            token_uri=user.token_uri,
            client_id=GOOGLE_CLIENT_ID,
            client_secret=GOOGLE_CLIENT_SECRET
        )
        return build('calendar', 'v3', credentials=creds)

    def send_email(self, to: str, subject: str, body: str, thread_id: str, user: User):
        """
        Sends an email reply.

        This function constructs an email message with a subject and body, 
        encodes it, and sends it using the Gmail API.

        It handles potential errors during email sending.
        """
        try:
            creds = credentials.Credentials(
                token=user.access_token,
                refresh_token=user.refresh_token,
                token_uri=user.token_uri,
                client_id=GOOGLE_CLIENT_ID,
                client_secret=GOOGLE_CLIENT_SECRET
            )
            gmail = build('gmail', 'v1', credentials=creds)
            message_body = f"To: {to}\r\nSubject: {subject}\r\n\r\n{body}"
            message = (gmail.users().messages().send(
                userId='me',
                body={'raw': base64.urlsafe_b64encode(message_body.encode(
                    'utf-8')).decode('utf-8'), 'threadId': thread_id}
            ).execute())
            print(f'sent message to {to} Message Id: {message["id"]}')
        except Exception as error:
            print(f'An error occurred while sending email: {error}')

    def generate_reply_after_event(self, user: User, email_data: EmailData, meeting_link: str, meeting_date: str, meeting_time: str, meeting_duration: int):
        """Generates a reply message after a calendar event is created."""

        generate_reply_func = types.FunctionDeclaration(
            name="generate_reply",
            description="Generates a reply message with meeting details after event creation.",
            parameters={
                "type": "OBJECT",
                "properties": {
                    "reply_title": {"type": "string", "description": "A short title for the reply message."},
                    "reply_body": {"type": "string", "description": "The reply message body, including meeting details and link."},
                },
            },
        )

        story_tools = types.Tool(
            function_declarations=[generate_reply_func]
        )

        prompt = f"""
        Generate a reply message to the user after a meeting has been scheduled.

        **Meeting Link:** {meeting_link}
        **Start Time:** {meeting_date} {meeting_time}
        **End Time:** {meeting_date} {meeting_time} + {meeting_duration} minutes
        **Received Email Content:** {email_data.body}
        **Received Email Sender:** {email_data.senderEmail}
        **Received Email Owner:** {email_data.senderName}
        
  
            ### **Instructions:**
            #### **1. Compose a Reply Message**
            - **Reply Title:** Create a concise title for the reply, confirming the meeting schedule and reflecting the content of the received message.
            - **Reply Body:** Write a polite and informative message.
            - Acknowledge the user's original message and address any points they raised.
            - Include the meeting link, start time, and end time in the reply body.
            - Confirm that the meeting has been successfully scheduled.
            - Tailor the response to the context and tone of the received message.

            #### **2. Ensure Accuracy**
            - The reply should accurately reflect the meeting details and the content of the received message.
            - Always generate a function call.
            - If there are any issues or missing details, include a message addressing them.
        """
        try:
            response = self.client.models.generate_content(
                model=self.MODEL_ID,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[story_tools],
                    temperature=0
                ),
            )

            if response.candidates and response.candidates[0].content.parts:
                content_part = response.candidates[0].content.parts[0]

                function_call = getattr(
                    content_part, "function_call", None)
                if function_call:
                    function_name = function_call.name
                    function_args = function_call.args

                    if function_name == "generate_reply":
                        reply_title = function_args.get("reply_title")
                        reply_body = function_args.get("reply_body")
                        if reply_title and reply_body:
                            self.send_email(
                                email_data.senderEmail, reply_title, reply_body, email_data.threadId, user)
                        else:
                            self._handle_processing_error(
                                user, email_data, "Reply title or body missing.")
                    else:
                        self._handle_processing_error(
                            user, email_data, f"Unknown function: {function_name}")
                else:
                    self._handle_processing_error(
                        user, email_data, "No function response or incomplete response found.")
            else:
                self._handle_processing_error(
                    user, email_data, "No response candidates found.")
        except Exception as e:
            self._handle_processing_error(
                user, email_data, f"Exception: {e}")
