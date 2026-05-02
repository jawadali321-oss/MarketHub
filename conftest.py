import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def buyer_user(db):
    from apps.users.models import CustomUser
    user = CustomUser.objects.create_user(
        email="buyer@test.com",
        password="TestPass1!",
        first_name="Test",
        last_name="Buyer",
        role="buyer",
        is_verified=True,
    )
    return user


@pytest.fixture
def seller_user(db):
    from apps.users.models import CustomUser, SellerProfile
    user = CustomUser.objects.create_user(
        email="seller@test.com",
        password="TestPass1!",
        first_name="Test",
        last_name="Seller",
        role="seller",
        is_verified=True,
    )
    SellerProfile.objects.get_or_create(user=user, defaults={"store_name": "Test Store"})
    return user


@pytest.fixture
def admin_user(db):
    from apps.users.models import CustomUser
    return CustomUser.objects.create_superuser(
        email="admin@test.com",
        password="TestPass1!",
    )


@pytest.fixture
def auth_client(api_client, buyer_user):
    """API client authenticated as buyer."""
    refresh = RefreshToken.for_user(buyer_user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    return api_client


@pytest.fixture
def seller_client(api_client, seller_user):
    """API client authenticated as seller."""
    refresh = RefreshToken.for_user(seller_user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    return api_client


@pytest.fixture
def admin_client(api_client, admin_user):
    """API client authenticated as admin."""
    refresh = RefreshToken.for_user(admin_user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    return api_client
