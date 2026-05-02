import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from encrypted_model_fields.fields import EncryptedTextField

from .managers import CustomUserManager


class CustomUser(AbstractBaseUser, PermissionsMixin):
    ROLE_BUYER = "buyer"
    ROLE_SELLER = "seller"
    ROLE_ADMIN = "admin"
    ROLE_CHOICES = [
        (ROLE_BUYER, "Buyer"),
        (ROLE_SELLER, "Seller"),
        (ROLE_ADMIN, "Admin"),
    ]

    LANG_EN = "en"
    LANG_UR = "ur"
    LANG_AR = "ar"
    LANGUAGE_CHOICES = [
        (LANG_EN, "English"),
        (LANG_UR, "Urdu"),
        (LANG_AR, "Arabic"),
        ("fr", "French"),
        ("de", "German"),
        ("zh", "Chinese (Simplified)"),
        ("ms", "Malay"),
        ("tr", "Turkish"),
        ("es", "Spanish"),
        ("hi", "Hindi"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(_("email address"), unique=True)
    first_name = models.CharField(_("first name"), max_length=150, blank=True)
    last_name = models.CharField(_("last name"), max_length=150, blank=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=ROLE_BUYER)
    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    language_preference = models.CharField(
        max_length=5, choices=LANGUAGE_CHOICES, default=LANG_EN
    )
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True)

    # 2FA
    totp_secret = EncryptedTextField(max_length=64, blank=True)
    is_2fa_enabled = models.BooleanField(default=False)

    # GDPR / Account deletion
    is_anonymised = models.BooleanField(default=False)
    anonymised_at = models.DateTimeField(null=True, blank=True)
    deletion_requested_at = models.DateTimeField(null=True, blank=True)

    # Notification preferences (JSONField)
    notification_preferences = models.JSONField(
        default=dict,
        blank=True,
        help_text="e.g. {'email': True, 'push': True, 'sms': False}",
    )

    date_joined = models.DateTimeField(default=timezone.now)
    last_login = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        db_table = "users"
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["role", "is_active"]),
        ]

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email

    def get_default_notification_preferences(self):
        return {"email": True, "push": True, "sms": False}

    def save(self, *args, **kwargs):
        if not self.notification_preferences:
            self.notification_preferences = self.get_default_notification_preferences()
        super().save(*args, **kwargs)


class SellerProfile(models.Model):
    KYC_PENDING = "pending"
    KYC_UNDER_REVIEW = "under_review"
    KYC_APPROVED = "approved"
    KYC_REJECTED = "rejected"
    KYC_STATUS_CHOICES = [
        (KYC_PENDING, "Pending"),
        (KYC_UNDER_REVIEW, "Under Review"),
        (KYC_APPROVED, "Approved"),
        (KYC_REJECTED, "Rejected"),
    ]

    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="seller_profile",
        primary_key=True,
    )
    store_name = models.CharField(max_length=255)
    store_description = models.TextField(blank=True)
    store_logo = models.ImageField(upload_to="store_logos/", blank=True, null=True)
    kyc_status = models.CharField(
        max_length=20, choices=KYC_STATUS_CHOICES, default=KYC_PENDING
    )
    kyc_document_url = models.URLField(blank=True)  # S3 signed URL stored separately
    kyc_submitted_at = models.DateTimeField(null=True, blank=True)
    kyc_reviewed_at = models.DateTimeField(null=True, blank=True)
    kyc_rejection_reason = models.TextField(blank=True)

    # Encrypted bank info
    bank_info_encrypted = EncryptedTextField(blank=True, default="")

    # Metrics
    rating_avg = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    reputation_score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    total_sales = models.PositiveIntegerField(default=0)
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    # Payout settings
    payout_method = models.CharField(
        max_length=20,
        choices=[("bank", "Bank Transfer"), ("paypal", "PayPal")],
        default="bank",
    )
    paypal_email = models.EmailField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "seller_profiles"

    def __str__(self):
        return f"{self.store_name} ({self.user.email})"

    @property
    def is_kyc_approved(self):
        return self.kyc_status == self.KYC_APPROVED


class Address(models.Model):
    LABEL_HOME = "home"
    LABEL_WORK = "work"
    LABEL_OTHER = "other"
    LABEL_CHOICES = [
        (LABEL_HOME, "Home"),
        (LABEL_WORK, "Work"),
        (LABEL_OTHER, "Other"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="addresses"
    )
    label = models.CharField(max_length=10, choices=LABEL_CHOICES, default=LABEL_HOME)
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, blank=True)
    street = models.CharField(max_length=500)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "addresses"
        verbose_name_plural = "addresses"
        ordering = ["-is_default", "-created_at"]

    def __str__(self):
        return f"{self.label}: {self.street}, {self.city}"

    def save(self, *args, **kwargs):
        # If this address is being set as default, unset all others for this user
        if self.is_default:
            Address.objects.filter(user=self.user, is_default=True).exclude(
                pk=self.pk
            ).update(is_default=False)
        super().save(*args, **kwargs)


class EmailVerificationToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="verification_tokens"
    )
    token = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        db_table = "email_verification_tokens"

    def is_valid(self):
        return not self.is_used and self.expires_at > timezone.now()


class PasswordResetToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="password_reset_tokens"
    )
    token = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        db_table = "password_reset_tokens"

    def is_valid(self):
        return not self.is_used and self.expires_at > timezone.now()
