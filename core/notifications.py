"""
Email notifications. Kept separate from services.py since this is
delivery/infrastructure concern, not NLP business logic.
"""

import logging
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse

logger = logging.getLogger(__name__)


def send_analysis_complete_email(session, request=None):
    """
    Sends a simple notification email when an analysis finishes.
    Silently no-ops if the user has disabled notifications or has no email.
    Never raises — a failed email should never break the analysis flow.
    """
    try:
        profile = getattr(session.user, 'profile', None)
        if profile and not profile.email_notifications:
            return
        if not session.user.email:
            return

        results_path = reverse('core:results', kwargs={'pk': session.pk})
        results_url = request.build_absolute_uri(results_path) if request else results_path

        subject = f'Your resume analysis for {session.job_title} is ready'
        message = (
            f"Hi {session.user.username},\n\n"
            f"Your resume analysis for \"{session.job_title}\" at "
            f"{session.company_name} is complete.\n\n"
            f"Match score: {session.match_score:.1f}%\n"
            f"Weighted score: {session.weighted_score:.1f}%\n\n"
            f"View full results here:\n{results_url}\n\n"
            f"— ResumeMatch"
        )

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[session.user.email],
            fail_silently=True,
        )
    except Exception as exc:
        # Never let email failures break the user-facing flow
        logger.warning("Failed to send analysis-complete email: %s", exc)