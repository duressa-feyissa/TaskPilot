from core.application.schema import EmailData
from core.domain.entity import User


def generate_no_rescheduled_email(email_data: EmailData, user: User):
    """Generates the email message for a rescheduled meeting without a link."""
    return f"""
    Subject: Re: Meeting Reschedule - Please Suggest a New Time

    Dear {email_data.senderName or email_data.senderEmail},

    I attempted to schedule the meeting at the requested time, but encountered a scheduling conflict. 

    To find a time that works best for you, could you please reply to this email with a few alternative dates and times that are convenient? 

    I apologize for any inconvenience this may cause, and I look forward to finding a new time that suits your schedule.

    Sincerely,

    {user.name}
    """
