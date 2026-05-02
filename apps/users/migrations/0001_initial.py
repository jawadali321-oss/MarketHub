import uuid
import django.utils.timezone
import encrypted_model_fields.fields
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.CreateModel(
            name="CustomUser",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("password", models.CharField(max_length=128, verbose_name="password")),
                ("last_login", models.DateTimeField(blank=True, null=True, verbose_name="last login")),
                ("is_superuser", models.BooleanField(default=False)),
                ("email", models.EmailField(max_length=254, unique=True, verbose_name="email address")),
                ("first_name", models.CharField(blank=True, max_length=150, verbose_name="first name")),
                ("last_name", models.CharField(blank=True, max_length=150, verbose_name="last name")),
                ("role", models.CharField(
                    choices=[("buyer", "Buyer"), ("seller", "Seller"), ("admin", "Admin")],
                    default="buyer", max_length=10
                )),
                ("is_verified", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("is_staff", models.BooleanField(default=False)),
                ("language_preference", models.CharField(
                    choices=[
                        ("en", "English"), ("ur", "Urdu"), ("ar", "Arabic"),
                        ("fr", "French"), ("de", "German"), ("zh", "Chinese (Simplified)"),
                        ("ms", "Malay"), ("tr", "Turkish"), ("es", "Spanish"), ("hi", "Hindi"),
                    ],
                    default="en", max_length=5
                )),
                ("avatar", models.ImageField(blank=True, null=True, upload_to="avatars/")),
                ("phone_number", models.CharField(blank=True, max_length=20)),
                ("totp_secret", models.CharField(blank=True, max_length=64)),
                ("is_2fa_enabled", models.BooleanField(default=False)),
                ("is_anonymised", models.BooleanField(default=False)),
                ("anonymised_at", models.DateTimeField(blank=True, null=True)),
                ("deletion_requested_at", models.DateTimeField(blank=True, null=True)),
                ("notification_preferences", models.JSONField(blank=True, default=dict)),
                ("date_joined", models.DateTimeField(default=django.utils.timezone.now)),
                ("groups", models.ManyToManyField(blank=True, related_name="customuser_set", to="auth.group")),
                ("user_permissions", models.ManyToManyField(blank=True, related_name="customuser_permissions_set", to="auth.permission")),
            ],
            options={"db_table": "users", "verbose_name": "user", "verbose_name_plural": "users"},
        ),
        migrations.AddIndex(
            model_name="customuser",
            index=models.Index(fields=["email"], name="users_email_idx"),
        ),
        migrations.AddIndex(
            model_name="customuser",
            index=models.Index(fields=["role", "is_active"], name="users_role_active_idx"),
        ),
        migrations.CreateModel(
            name="SellerProfile",
            fields=[
                ("user", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    primary_key=True, related_name="seller_profile",
                    serialize=False, to=settings.AUTH_USER_MODEL
                )),
                ("store_name", models.CharField(max_length=255)),
                ("store_description", models.TextField(blank=True)),
                ("store_logo", models.ImageField(blank=True, null=True, upload_to="store_logos/")),
                ("kyc_status", models.CharField(
                    choices=[
                        ("pending", "Pending"), ("under_review", "Under Review"),
                        ("approved", "Approved"), ("rejected", "Rejected"),
                    ],
                    default="pending", max_length=20
                )),
                ("kyc_document_url", models.URLField(blank=True)),
                ("kyc_submitted_at", models.DateTimeField(blank=True, null=True)),
                ("kyc_reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("kyc_rejection_reason", models.TextField(blank=True)),
                ("bank_info_encrypted", encrypted_model_fields.fields.EncryptedTextField(blank=True, default="")),
                ("rating_avg", models.DecimalField(decimal_places=2, default=0.0, max_digits=3)),
                ("reputation_score", models.DecimalField(decimal_places=2, default=0.0, max_digits=5)),
                ("total_sales", models.PositiveIntegerField(default=0)),
                ("total_revenue", models.DecimalField(decimal_places=2, default=0.0, max_digits=12)),
                ("payout_method", models.CharField(
                    choices=[("bank", "Bank Transfer"), ("paypal", "PayPal")],
                    default="bank", max_length=20
                )),
                ("paypal_email", models.EmailField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "seller_profiles"},
        ),
        migrations.CreateModel(
            name="Address",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="addresses", to=settings.AUTH_USER_MODEL
                )),
                ("label", models.CharField(
                    choices=[("home", "Home"), ("work", "Work"), ("other", "Other")],
                    default="home", max_length=10
                )),
                ("full_name", models.CharField(max_length=255)),
                ("phone", models.CharField(blank=True, max_length=20)),
                ("street", models.CharField(max_length=500)),
                ("city", models.CharField(max_length=100)),
                ("state", models.CharField(max_length=100)),
                ("country", models.CharField(max_length=100)),
                ("postal_code", models.CharField(max_length=20)),
                ("is_default", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "addresses", "verbose_name_plural": "addresses", "ordering": ["-is_default", "-created_at"]},
        ),
        migrations.CreateModel(
            name="EmailVerificationToken",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="verification_tokens", to=settings.AUTH_USER_MODEL
                )),
                ("token", models.CharField(max_length=255, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField()),
                ("is_used", models.BooleanField(default=False)),
            ],
            options={"db_table": "email_verification_tokens"},
        ),
        migrations.CreateModel(
            name="PasswordResetToken",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="password_reset_tokens", to=settings.AUTH_USER_MODEL
                )),
                ("token", models.CharField(max_length=255, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField()),
                ("is_used", models.BooleanField(default=False)),
            ],
            options={"db_table": "password_reset_tokens"},
        ),
    ]
