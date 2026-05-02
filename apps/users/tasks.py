import logging
from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_verification_email(self, user_id: str, token: str):
    """Send email verification link to newly registered user."""
    from .models import CustomUser
    try:
        user = CustomUser.objects.get(id=user_id)
        verification_url = f"{settings.FRONTEND_URL}/verify-email/{token}"
        subject = "Verify your MarketHub email address"
        message = f"""
Hi {user.first_name or user.email},

Please verify your email address by clicking the link below:

{verification_url}

This link expires in 24 hours.

If you did not create a MarketHub account, please ignore this email.

— The MarketHub Team
        """.strip()

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        logger.info(f"Verification email sent to {user.email}")

    except CustomUser.DoesNotExist:
        logger.error(f"User {user_id} not found for verification email")
    except Exception as exc:
        logger.error(f"Failed to send verification email to {user_id}: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_password_reset_email(self, user_id: str, token: str):
    """Send password reset link."""
    from .models import CustomUser
    try:
        user = CustomUser.objects.get(id=user_id)
        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"
        subject = "Reset your MarketHub password"
        message = f"""
Hi {user.first_name or user.email},

You requested a password reset. Click below to set a new password:

{reset_url}

This link expires in 2 hours. If you didn't request this, please ignore this email.

— The MarketHub Team
        """.strip()

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        logger.info(f"Password reset email sent to {user.email}")

    except CustomUser.DoesNotExist:
        logger.error(f"User {user_id} not found for password reset")
    except Exception as exc:
        logger.error(f"Failed to send password reset email: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True)
def anonymise_user_data(self, user_id: str):
    """
    GDPR Art. 17 — anonymise all PII 30 days after deletion request.
    Called 30 days after AccountDeleteView is triggered.
    """
    from .models import CustomUser, Address
    try:
        user = CustomUser.objects.get(id=user_id)

        if not user.deletion_requested_at:
            logger.warning(f"Anonymisation called for user {user_id} without deletion request")
            return

        # Anonymise PII
        user.email = f"deleted_{user_id}@anonymised.markethub.com"
        user.first_name = "Deleted"
        user.last_name = "User"
        user.phone_number = ""
        user.avatar = None
        user.totp_secret = ""
        user.is_2fa_enabled = False
        user.is_anonymised = True
        user.anonymised_at = timezone.now()
        user.is_active = False
        user.save()

        # Remove addresses
        Address.objects.filter(user=user).delete()

        # Anonymise seller profile bank info
        try:
            profile = user.seller_profile
            profile.bank_info_encrypted = ""
            profile.save(update_fields=["bank_info_encrypted"])
        except Exception:
            pass

        logger.info(f"User {user_id} successfully anonymised (GDPR)")

    except CustomUser.DoesNotExist:
        logger.error(f"User {user_id} not found for anonymisation")
    except Exception as exc:
        logger.error(f"Anonymisation failed for {user_id}: {exc}")
        raise self.retry(exc=exc)
