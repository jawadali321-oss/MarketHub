import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.models import CustomUser, SellerProfile, EmailVerificationToken, PasswordResetToken
from django.utils import timezone
from datetime import timedelta
import secrets


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def buyer(db):
    return CustomUser.objects.create_user(
        email="buyer@test.com",
        password="TestPass1!",
        role="buyer",
        is_verified=True,
    )


@pytest.fixture
def seller(db):
    user = CustomUser.objects.create_user(
        email="seller@test.com",
        password="TestPass1!",
        role="seller",
        is_verified=True,
    )
    SellerProfile.objects.get_or_create(user=user, defaults={"store_name": "Test Store"})
    return user


@pytest.fixture
def auth_client(client, buyer):
    token = RefreshToken.for_user(buyer)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(token.access_token)}")
    return client


# ── Registration Tests ─────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestRegister:
    url = "/api/v1/auth/register/"

    def test_register_buyer_success(self, client):
        data = {
            "email": "newbuyer@test.com",
            "password": "TestPass1!",
            "password_confirm": "TestPass1!",
            "first_name": "New",
            "last_name": "Buyer",
            "role": "buyer",
        }
        response = client.post(self.url, data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["success"] is True
        assert CustomUser.objects.filter(email="newbuyer@test.com").exists()

    def test_register_seller_success(self, client):
        data = {
            "email": "newseller@test.com",
            "password": "TestPass1!",
            "password_confirm": "TestPass1!",
            "role": "seller",
            "store_name": "My Store",
        }
        response = client.post(self.url, data)
        assert response.status_code == status.HTTP_201_CREATED
        user = CustomUser.objects.get(email="newseller@test.com")
        assert user.role == "seller"

    def test_register_password_mismatch(self, client):
        data = {
            "email": "test@test.com",
            "password": "TestPass1!",
            "password_confirm": "WrongPass1!",
            "role": "buyer",
        }
        response = client.post(self.url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_weak_password(self, client):
        data = {
            "email": "test@test.com",
            "password": "simple",
            "password_confirm": "simple",
            "role": "buyer",
        }
        response = client.post(self.url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_duplicate_email(self, client, buyer):
        data = {
            "email": buyer.email,
            "password": "TestPass1!",
            "password_confirm": "TestPass1!",
            "role": "buyer",
        }
        response = client.post(self.url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ── Login Tests ────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestLogin:
    url = "/api/v1/auth/login/"

    def test_login_success(self, client, buyer):
        response = client.post(self.url, {"email": buyer.email, "password": "TestPass1!"})
        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data["data"]
        assert "refresh_token" in response.cookies

    def test_login_wrong_password(self, client, buyer):
        response = client.post(self.url, {"email": buyer.email, "password": "wrongpassword"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.data["success"] is False

    def test_login_inactive_user(self, client, buyer):
        buyer.is_active = False
        buyer.save()
        response = client.post(self.url, {"email": buyer.email, "password": "TestPass1!"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_nonexistent_user(self, client):
        response = client.post(self.url, {"email": "ghost@test.com", "password": "TestPass1!"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ── Profile Tests ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestProfile:
    url = "/api/v1/auth/me/"

    def test_get_profile_authenticated(self, auth_client, buyer):
        response = auth_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["email"] == buyer.email

    def test_get_profile_unauthenticated(self, client):
        response = client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_update_profile(self, auth_client):
        data = {"first_name": "Updated", "last_name": "Name"}
        response = auth_client.patch(self.url, data)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["first_name"] == "Updated"


# ── Email Verification Tests ───────────────────────────────────────────────────

@pytest.mark.django_db
class TestEmailVerification:
    def test_verify_valid_token(self, client, buyer):
        buyer.is_verified = False
        buyer.save()
        token_val = secrets.token_urlsafe(64)
        EmailVerificationToken.objects.create(
            user=buyer,
            token=token_val,
            expires_at=timezone.now() + timedelta(hours=24),
        )
        response = client.get(f"/api/v1/auth/verify-email/{token_val}/")
        assert response.status_code == status.HTTP_200_OK
        buyer.refresh_from_db()
        assert buyer.is_verified is True

    def test_verify_invalid_token(self, client):
        response = client.get("/api/v1/auth/verify-email/invalidtoken123/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_verify_expired_token(self, client, buyer):
        buyer.is_verified = False
        buyer.save()
        token_val = secrets.token_urlsafe(64)
        EmailVerificationToken.objects.create(
            user=buyer,
            token=token_val,
            expires_at=timezone.now() - timedelta(hours=1),  # expired
        )
        response = client.get(f"/api/v1/auth/verify-email/{token_val}/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ── Token Refresh Tests ────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestTokenRefresh:
    url = "/api/v1/auth/token/refresh/"

    def test_refresh_via_body(self, client, buyer):
        refresh = RefreshToken.for_user(buyer)
        response = client.post(self.url, {"refresh": str(refresh)})
        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data["data"]


# ── Logout Tests ───────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestLogout:
    url = "/api/v1/auth/logout/"

    def test_logout_success(self, auth_client, buyer):
        refresh = RefreshToken.for_user(buyer)
        response = auth_client.post(self.url, {"refresh": str(refresh)})
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_logout_unauthenticated(self, client):
        response = client.post(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ── 2FA Tests ─────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestTwoFA:
    def test_enable_2fa(self, auth_client):
        response = auth_client.post("/api/v1/auth/2fa/enable/")
        assert response.status_code == status.HTTP_200_OK
        assert "qr_code" in response.data["data"]
        assert "secret" in response.data["data"]

    def test_verify_2fa_invalid_code(self, auth_client, buyer):
        import pyotp
        buyer.totp_secret = pyotp.random_base32()
        buyer.save()
        response = auth_client.post("/api/v1/auth/2fa/verify/", {"totp_code": "000000"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_verify_2fa_valid_code(self, auth_client, buyer):
        import pyotp
        secret = pyotp.random_base32()
        buyer.totp_secret = secret
        buyer.save()
        totp = pyotp.TOTP(secret)
        valid_code = totp.now()
        response = auth_client.post("/api/v1/auth/2fa/verify/", {"totp_code": valid_code})
        assert response.status_code == status.HTTP_200_OK
        buyer.refresh_from_db()
        assert buyer.is_2fa_enabled is True


# ── Password Reset Tests ───────────────────────────────────────────────────────

@pytest.mark.django_db
class TestPasswordReset:
    def test_reset_request_existing_user(self, client, buyer):
        response = client.post("/api/v1/auth/password/reset/", {"email": buyer.email})
        assert response.status_code == status.HTTP_200_OK

    def test_reset_request_nonexistent_user(self, client):
        # Should still return 200 to prevent email enumeration
        response = client.post("/api/v1/auth/password/reset/", {"email": "ghost@test.com"})
        assert response.status_code == status.HTTP_200_OK

    def test_reset_confirm_valid_token(self, client, buyer):
        token_val = secrets.token_urlsafe(64)
        PasswordResetToken.objects.create(
            user=buyer,
            token=token_val,
            expires_at=timezone.now() + timedelta(hours=2),
        )
        response = client.post("/api/v1/auth/password/reset/confirm/", {
            "token": token_val,
            "new_password": "NewPass1!",
            "new_password_confirm": "NewPass1!",
        })
        assert response.status_code == status.HTTP_200_OK


# ── Health Check Test ──────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestHealthCheck:
    def test_health_endpoint(self, client):
        response = client.get("/api/health/")
        assert response.status_code in (200, 503)
        assert "db" in response.data["data"]
        assert "redis" in response.data["data"]
