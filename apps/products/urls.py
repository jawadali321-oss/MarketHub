from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import BulkUploadView, CategoryViewSet, ProductViewSet

router = DefaultRouter()
router.register(r"categories", CategoryViewSet, basename="category")
router.register(r"products", ProductViewSet, basename="product")

urlpatterns = [
    # Bulk upload BEFORE router to avoid conflict with products/<pk>/ matcher
    path("products/bulk-upload/", BulkUploadView.as_view(), name="product-bulk-upload"),
    path("", include(router.urls)),
]
