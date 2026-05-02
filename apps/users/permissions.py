from rest_framework.permissions import BasePermission


class IsBuyer(BasePermission):
    """Allow access only to users with buyer role."""
    message = "Only buyers can perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role == "buyer"
        )


class IsSeller(BasePermission):
    """Allow access only to users with seller role."""
    message = "Only sellers can perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role == "seller"
        )


class IsAdmin(BasePermission):
    """Allow access only to admin users."""
    message = "Only admins can perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role == "admin"
        )


class IsOwner(BasePermission):
    """Allow access only to the owner of the object."""
    message = "You do not have permission to access this resource."

    def has_object_permission(self, request, view, obj):
        if hasattr(obj, "user"):
            return obj.user == request.user
        if hasattr(obj, "buyer"):
            return obj.buyer == request.user
        if hasattr(obj, "seller"):
            return obj.seller == request.user
        return obj == request.user


class IsSellerOrAdmin(BasePermission):
    """Allow access to sellers and admins."""

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role in ("seller", "admin")
        )


class IsVerifiedSeller(BasePermission):
    """Allow access only to KYC-approved sellers."""
    message = "Your seller account must be KYC approved to perform this action."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated and request.user.role == "seller"):
            return False
        try:
            return request.user.seller_profile.is_kyc_approved
        except Exception:
            return False
