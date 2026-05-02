from django.urls import path
from .views import (
    RegisterView,
    LoginView,
    LogoutView,
    TokenRefreshView,
    EmailVerifyView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    Enable2FAView,
    Verify2FAView,
    MeView,
    PasswordChangeView,
    KYCUploadView,
    AccountDeleteView,
    AddressListCreateView,
    AddressDetailView,
)

urlpatterns = [
    # Registration & Login
    path("register/", RegisterView.as_view(), name="auth-register"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("token/refresh/", TokenRefreshView.as_view(), name="auth-token-refresh"),

    # Email verification
    path("verify-email/<str:token>/", EmailVerifyView.as_view(), name="auth-verify-email"),

    # Password reset
    path("password/reset/", PasswordResetRequestView.as_view(), name="auth-password-reset"),
    path("password/reset/confirm/", PasswordResetConfirmView.as_view(), name="auth-password-reset-confirm"),
    path("password/change/", PasswordChangeView.as_view(), name="auth-password-change"),

    # 2FA
    path("2fa/enable/", Enable2FAView.as_view(), name="auth-2fa-enable"),
    path("2fa/verify/", Verify2FAView.as_view(), name="auth-2fa-verify"),

    # Profile
    path("me/", MeView.as_view(), name="auth-me"),

    # Addresses
    path("addresses/", AddressListCreateView.as_view(), name="auth-addresses"),
    path("addresses/<uuid:pk>/", AddressDetailView.as_view(), name="auth-address-detail"),

    # KYC
    path("kyc/upload/", KYCUploadView.as_view(), name="auth-kyc-upload"),

    # Account deletion (GDPR)
    path("account/delete/", AccountDeleteView.as_view(), name="auth-account-delete"),
]
