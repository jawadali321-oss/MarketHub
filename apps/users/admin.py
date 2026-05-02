from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import CustomUser, SellerProfile, Address, EmailVerificationToken, PasswordResetToken


@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin):
    list_display = ["email", "full_name", "role", "is_verified", "is_active", "date_joined"]
    list_filter = ["role", "is_verified", "is_active", "is_2fa_enabled"]
    search_fields = ["email", "first_name", "last_name"]
    ordering = ["-date_joined"]
    readonly_fields = ["id", "date_joined", "last_login", "is_anonymised", "anonymised_at"]

    fieldsets = (
        (None, {"fields": ("id", "email", "password")}),
        (_("Personal info"), {"fields": ("first_name", "last_name", "phone_number", "avatar")}),
        (_("Roles & Status"), {"fields": ("role", "is_verified", "is_active", "is_staff", "is_superuser")}),
        (_("2FA"), {"fields": ("is_2fa_enabled", "totp_secret")}),
        (_("Preferences"), {"fields": ("language_preference", "notification_preferences")}),
        (_("GDPR"), {"fields": ("is_anonymised", "anonymised_at", "deletion_requested_at")}),
        (_("Dates"), {"fields": ("date_joined", "last_login")}),
        (_("Permissions"), {"fields": ("groups", "user_permissions")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "password1", "password2", "role", "first_name", "last_name"),
        }),
    )


@admin.register(SellerProfile)
class SellerProfileAdmin(admin.ModelAdmin):
    list_display = ["store_name", "user", "kyc_status", "rating_avg", "reputation_score"]
    list_filter = ["kyc_status"]
    search_fields = ["store_name", "user__email"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ["user", "label", "city", "country", "is_default"]
    list_filter = ["label", "country", "is_default"]
    search_fields = ["user__email", "city", "country"]


@admin.register(EmailVerificationToken)
class EmailVerificationTokenAdmin(admin.ModelAdmin):
    list_display = ["user", "created_at", "expires_at", "is_used"]
    list_filter = ["is_used"]
    readonly_fields = ["token", "created_at"]


@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ["user", "created_at", "expires_at", "is_used"]
    list_filter = ["is_used"]
    readonly_fields = ["token", "created_at"]
