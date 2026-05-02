import pyotp
import qrcode
import io
import base64
import secrets
from datetime import timedelta

from django.utils import timezone
from django.contrib.auth import update_session_auth_hash
from django.conf import settings
from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView as BaseTokenRefreshView
from rest_framework_simplejwt.exceptions import TokenError
from drf_spectacular.utils import extend_schema, OpenApiResponse

from apps.core.responses import success_response, error_response, created_response, no_content_response
from .models import CustomUser, SellerProfile, Address, EmailVerificationToken, PasswordResetToken
from .serializers import (
    RegisterSerializer,
    LoginSerializer,
    UserProfileSerializer,
    ProfileUpdateSerializer,
    AddressSerializer,
    KYCUploadSerializer,
    PasswordChangeSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    Verify2FASerializer,
)
from .tasks import send_verification_email, send_password_reset_email


class RegisterView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["auth"],
        request=RegisterSerializer,
        summary="Register a new user account",
        description="Creates a buyer or seller account. Sends email verification link.",
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(serializer.errors)

        user = serializer.save()

        # Create email verification token (expires in 24h)
        token_value = secrets.token_urlsafe(64)
        EmailVerificationToken.objects.create(
            user=user,
            token=token_value,
            expires_at=timezone.now() + timedelta(hours=24),
        )

        # Queue email (async via Celery)
        send_verification_email.delay(str(user.id), token_value)

        return created_response(
            data={"email": user.email, "role": user.role},
            message="Registration successful. Please check your email to verify your account.",
        )


class LoginView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["auth"],
        request=LoginSerializer,
        summary="Login and obtain JWT tokens",
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            return error_response(serializer.errors, status_code=status.HTTP_401_UNAUTHORIZED)

        data = serializer.validated_data
        response = success_response(
            data={
                "access": data["access"],
                "user": data["user"],
            },
            message="Login successful.",
        )
        # Set refresh token in HttpOnly cookie
        response.set_cookie(
            key="refresh_token",
            value=data["refresh"],
            httponly=True,
            secure=not settings.DEBUG,
            samesite="Strict",
            max_age=7 * 24 * 60 * 60,  # 7 days
        )
        return response


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["auth"], summary="Logout and blacklist refresh token")
    def post(self, request):
        refresh_token = request.COOKIES.get("refresh_token") or request.data.get("refresh")
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except TokenError:
                pass  # Token already invalid, that's fine

        response = no_content_response()
        response.delete_cookie("refresh_token")
        return response


class TokenRefreshView(BaseTokenRefreshView):
    """Refresh access token using HttpOnly cookie or body."""

    def post(self, request, *args, **kwargs):
        from rest_framework_simplejwt.tokens import RefreshToken as RT
        from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
        token_str = request.data.get("refresh") or request.COOKIES.get("refresh_token")
        if not token_str:
            return error_response({"detail": "No refresh token provided."}, status_code=status.HTTP_401_UNAUTHORIZED)
        try:
            access = str(RT(token_str).access_token)
        except (TokenError, InvalidToken):
            return error_response({"detail": "Invalid or expired refresh token."}, status_code=status.HTTP_401_UNAUTHORIZED)
        return success_response(data={"access": access}, message="Token refreshed successfully.")


class EmailVerifyView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(tags=["auth"], summary="Verify email address via token")
    def get(self, request, token):
        try:
            verification = EmailVerificationToken.objects.select_related("user").get(token=token)
        except EmailVerificationToken.DoesNotExist:
            return error_response(
                {"token": "Invalid verification link."},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if not verification.is_valid():
            return error_response(
                {"token": "Verification link has expired. Please request a new one."},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        user = verification.user
        user.is_verified = True
        user.save(update_fields=["is_verified"])
        verification.is_used = True
        verification.save(update_fields=["is_used"])

        return success_response(message="Email verified successfully. You can now login.")


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(tags=["auth"], summary="Request password reset email")
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(serializer.errors)

        email = serializer.validated_data["email"]
        # Always return 200 to prevent email enumeration
        try:
            user = CustomUser.objects.get(email=email, is_active=True)
            token_value = secrets.token_urlsafe(64)
            PasswordResetToken.objects.create(
                user=user,
                token=token_value,
                expires_at=timezone.now() + timedelta(hours=2),
            )
            send_password_reset_email.delay(str(user.id), token_value)
        except CustomUser.DoesNotExist:
            pass  # Silent fail to prevent enumeration

        return success_response(
            message="If an account with that email exists, a password reset link has been sent."
        )


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(tags=["auth"], summary="Confirm password reset with token")
    def post(self, request):
        token_value = request.data.get("token")
        new_password = request.data.get("new_password")
        new_password_confirm = request.data.get("new_password_confirm")

        if not token_value or not new_password:
            return error_response({"detail": "Token and new_password are required."})

        if new_password != new_password_confirm:
            return error_response({"new_password_confirm": "Passwords do not match."})

        try:
            reset_token = PasswordResetToken.objects.select_related("user").get(token=token_value)
        except PasswordResetToken.DoesNotExist:
            return error_response({"token": "Invalid reset link."}, status_code=400)

        if not reset_token.is_valid():
            return error_response({"token": "Reset link has expired."}, status_code=400)

        user = reset_token.user
        user.set_password(new_password)
        user.save()
        reset_token.is_used = True
        reset_token.save(update_fields=["is_used"])

        # Blacklist all existing tokens for this user
        try:
            from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
            tokens = OutstandingToken.objects.filter(user=user)
            for t in tokens:
                BlacklistedToken.objects.get_or_create(token=t)
        except Exception:
            pass

        return success_response(message="Password reset successfully. Please login with your new password.")


class Enable2FAView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["auth"], summary="Enable TOTP 2FA — returns QR code")
    def post(self, request):
        user = request.user
        if user.is_2fa_enabled or user.totp_secret:
            return error_response({"detail": "2FA is already enabled."})

        # Generate TOTP secret
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=user.email,
            issuer_name="MarketHub"
        )

        # Generate QR code as base64 PNG
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        qr_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

        # Save secret (not yet enabled — user must verify first)
        user.totp_secret = secret
        user.save(update_fields=["totp_secret"])

        return success_response(
            data={
                "secret": secret,
                "qr_code": f"data:image/png;base64,{qr_base64}",
                "provisioning_uri": provisioning_uri,
            },
            message="Scan QR code in Google Authenticator, then verify with /auth/2fa/verify/",
        )


class Verify2FAView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["auth"], summary="Verify TOTP code to activate 2FA")
    def post(self, request):
        serializer = Verify2FASerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(serializer.errors)

        user = request.user
        if not user.totp_secret:
            return error_response({"detail": "2FA not initialised. Call /auth/2fa/enable/ first."})

        totp = pyotp.TOTP(user.totp_secret)
        if not totp.verify(serializer.validated_data["totp_code"], valid_window=1):
            return error_response({"totp_code": "Invalid code. Please try again."})

        user.is_2fa_enabled = True
        user.save(update_fields=["is_2fa_enabled"])

        return success_response(message="2FA enabled successfully.")


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["auth"], summary="Get current user profile")
    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return success_response(data=serializer.data)

    @extend_schema(tags=["auth"], request=ProfileUpdateSerializer, summary="Update current user profile")
    def patch(self, request):
        serializer = ProfileUpdateSerializer(request.user, data=request.data, partial=True)
        if not serializer.is_valid():
            return error_response(serializer.errors)
        serializer.save()
        return success_response(
            data=UserProfileSerializer(request.user).data,
            message="Profile updated successfully.",
        )


class PasswordChangeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["auth"], request=PasswordChangeSerializer, summary="Change password")
    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(serializer.errors)

        user = request.user
        if not user.check_password(serializer.validated_data["current_password"]):
            return error_response({"current_password": "Incorrect current password."})

        user.set_password(serializer.validated_data["new_password"])
        user.save()
        return success_response(message="Password changed. Please login again.")


class KYCUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        tags=["auth"],
        request=KYCUploadSerializer,
        summary="Upload KYC documents (sellers only)",
    )
    def post(self, request):
        if request.user.role != CustomUser.ROLE_SELLER:
            return error_response(
                {"detail": "Only seller accounts can submit KYC."},
                status_code=status.HTTP_403_FORBIDDEN,
            )

        serializer = KYCUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(serializer.errors)

        try:
            profile = request.user.seller_profile
        except SellerProfile.DoesNotExist:
            return error_response({"detail": "Seller profile not found."})

        # Upload to S3 (or local in dev)
        document_front = serializer.validated_data["document_front"]
        document_type = serializer.validated_data["document_type"]

        from django.core.files.storage import default_storage
        filename = f"kyc/{request.user.id}/{document_type}_front.{document_front.name.split('.')[-1]}"
        path = default_storage.save(filename, document_front)
        kyc_url = default_storage.url(path)

        profile.kyc_document_url = kyc_url
        profile.kyc_status = SellerProfile.KYC_UNDER_REVIEW
        profile.kyc_submitted_at = timezone.now()
        profile.save(update_fields=["kyc_document_url", "kyc_status", "kyc_submitted_at"])

        return success_response(
            data={"kyc_status": profile.kyc_status},
            message="KYC documents uploaded successfully. Review in progress.",
        )


class AccountDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["auth"], summary="Request account deletion (GDPR Art. 17)")
    def delete(self, request):
        user = request.user
        user.deletion_requested_at = timezone.now()
        user.is_active = False
        user.save(update_fields=["deletion_requested_at", "is_active"])

        # Schedule GDPR anonymisation task (30 days)
        from .tasks import anonymise_user_data
        anonymise_user_data.apply_async(
            args=[str(user.id)],
            countdown=30 * 24 * 60 * 60,  # 30 days
        )

        return success_response(
            message="Account deletion requested. Your data will be anonymised within 30 days."
        )


class AddressListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AddressSerializer

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return success_response(data=serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return error_response(serializer.errors)
        self.perform_create(serializer)
        return created_response(data=serializer.data, message="Address added successfully.")


class AddressDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AddressSerializer

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        return success_response(data=self.get_serializer(instance).data)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        if not serializer.is_valid():
            return error_response(serializer.errors)
        serializer.save()
        return success_response(data=serializer.data, message="Address updated.")

    def destroy(self, request, *args, **kwargs):
        self.get_object().delete()
        return no_content_response()
