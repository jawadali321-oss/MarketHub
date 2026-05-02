import re
import pyotp
import qrcode
import io
import base64
from django.contrib.auth import authenticate
from django.utils import timezone
from datetime import timedelta
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from .models import CustomUser, SellerProfile, Address, EmailVerificationToken, PasswordResetToken


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(
        choices=CustomUser.ROLE_CHOICES,
        default=CustomUser.ROLE_BUYER
    )
    store_name = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = CustomUser
        fields = [
            "email", "password", "password_confirm",
            "first_name", "last_name", "role",
            "language_preference", "phone_number", "store_name",
        ]

    def validate_password(self, value):
        if not re.search(r"[A-Z]", value):
            raise serializers.ValidationError("Password must contain at least 1 uppercase letter.")
        if not re.search(r"\d", value):
            raise serializers.ValidationError("Password must contain at least 1 digit.")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", value):
            raise serializers.ValidationError("Password must contain at least 1 special character.")
        return value

    def validate(self, data):
        if data["password"] != data.pop("password_confirm"):
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        return data

    def create(self, validated_data):
        store_name = validated_data.pop("store_name", "")
        user = CustomUser.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
            role=validated_data.get("role", CustomUser.ROLE_BUYER),
            language_preference=validated_data.get("language_preference", "en"),
            phone_number=validated_data.get("phone_number", ""),
        )
        if user.role == CustomUser.ROLE_SELLER and store_name:
            SellerProfile.objects.create(user=user, store_name=store_name)
        return user


class LoginSerializer(TokenObtainPairSerializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    totp_code = serializers.CharField(write_only=True, required=False, allow_blank=True)

    username_field = "email"

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")
        totp_code = attrs.get("totp_code", "")

        user = authenticate(request=self.context.get("request"), username=email, password=password)
        if not user:
            raise serializers.ValidationError(
                {"detail": "Invalid email or password."},
                code="authentication_failed",
            )
        if not user.is_active:
            raise serializers.ValidationError({"detail": "This account has been deactivated."})

        # 2FA check
        if user.is_2fa_enabled:
            if not totp_code:
                raise serializers.ValidationError(
                    {"totp_code": "2FA code is required.", "requires_2fa": True}
                )
            totp = pyotp.TOTP(user.totp_secret)
            if not totp.verify(totp_code, valid_window=1):
                raise serializers.ValidationError({"totp_code": "Invalid 2FA code."})

        refresh = RefreshToken.for_user(user)
        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": UserProfileSerializer(user).data,
        }


class UserProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    seller_profile = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = [
            "id", "email", "first_name", "last_name", "full_name",
            "role", "is_verified", "is_2fa_enabled",
            "language_preference", "phone_number", "avatar",
            "notification_preferences", "date_joined", "seller_profile",
        ]
        read_only_fields = ["id", "email", "role", "is_verified", "date_joined"]

    def get_seller_profile(self, obj):
        if obj.role == CustomUser.ROLE_SELLER:
            try:
                profile = obj.seller_profile
                return {
                    "store_name": profile.store_name,
                    "kyc_status": profile.kyc_status,
                    "rating_avg": str(profile.rating_avg),
                    "reputation_score": str(profile.reputation_score),
                }
            except SellerProfile.DoesNotExist:
                return None
        return None


class ProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = [
            "first_name", "last_name", "phone_number",
            "avatar", "language_preference", "notification_preferences",
        ]


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = [
            "id", "label", "full_name", "phone",
            "street", "city", "state", "country",
            "postal_code", "is_default", "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class KYCUploadSerializer(serializers.Serializer):
    document_type = serializers.ChoiceField(
        choices=[("cnic", "CNIC"), ("passport", "Passport"), ("driving_license", "Driving License")]
    )
    document_front = serializers.FileField()
    document_back = serializers.FileField(required=False)


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)
    new_password_confirm = serializers.CharField(write_only=True)

    def validate_new_password(self, value):
        if not re.search(r"[A-Z]", value):
            raise serializers.ValidationError("Must contain at least 1 uppercase letter.")
        if not re.search(r"\d", value):
            raise serializers.ValidationError("Must contain at least 1 digit.")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", value):
            raise serializers.ValidationError("Must contain at least 1 special character.")
        return value

    def validate(self, data):
        if data["new_password"] != data["new_password_confirm"]:
            raise serializers.ValidationError({"new_password_confirm": "Passwords do not match."})
        return data


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)
    new_password_confirm = serializers.CharField(write_only=True)

    def validate(self, data):
        if data["new_password"] != data["new_password_confirm"]:
            raise serializers.ValidationError({"new_password_confirm": "Passwords do not match."})
        return data


class Enable2FASerializer(serializers.Serializer):
    """Returns TOTP secret and QR code image (base64 PNG)."""
    pass


class Verify2FASerializer(serializers.Serializer):
    totp_code = serializers.CharField(max_length=6, min_length=6)


class TokenRefreshResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
