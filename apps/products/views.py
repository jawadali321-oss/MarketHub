import csv
import io
from decimal import Decimal, InvalidOperation

from django.core.cache import cache
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db.models import F

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.pagination import CursorPagination
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from django_filters.rest_framework import DjangoFilterBackend

from .filters import ProductFilter
from .models import Category, Product, ProductImage
from .serializers import (
    CategorySerializer,
    CategoryWriteSerializer,
    ProductImageSerializer,
    ProductListSerializer,
    ProductSerializer,
)
from .tasks import process_product_image


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

class ProductCursorPagination(CursorPagination):
    page_size = 20
    ordering = "-created_at"
    cursor_query_param = "cursor"
    page_size_query_param = "page_size"
    max_page_size = 100


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------

class IsSellerOrReadOnly(permissions.BasePermission):
    """Write access requires role == 'seller'; reads are public."""

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return (
            request.user.is_authenticated
            and getattr(request.user, "role", None) == "seller"
        )

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.seller_id == request.user.pk


class IsAdminRole(permissions.BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and getattr(request.user, "role", None) == "admin"
        )


# ---------------------------------------------------------------------------
# Category ViewSet
# ---------------------------------------------------------------------------

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.filter(is_active=True)

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return CategoryWriteSerializer
        return CategorySerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAdminRole()]
        return [permissions.AllowAny()]

    def get_queryset(self):
        if self.action == "list":
            return (
                Category.objects.filter(is_active=True, parent__isnull=True)
                .prefetch_related(
                    "children__children__children"
                )
                .order_by("display_order", "name")
            )
        return Category.objects.filter(is_active=True)

    def list(self, request, *args, **kwargs):
        cache_key = "categories:tree"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)
        response = super().list(request, *args, **kwargs)
        cache.set(cache_key, response.data, timeout=3600)
        return response


# ---------------------------------------------------------------------------
# Product ViewSet
# ---------------------------------------------------------------------------

class ProductViewSet(viewsets.ModelViewSet):
    permission_classes = [IsSellerOrReadOnly]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = ProductFilter
    ordering_fields = ["price", "created_at", "view_count", "title"]
    ordering = ["-created_at"]
    pagination_class = ProductCursorPagination

    def get_serializer_class(self):
        if self.action == "list":
            return ProductListSerializer
        return ProductSerializer

    def get_queryset(self):
        qs = (
            Product.objects.filter(is_active=True)
            .select_related("category", "seller")
            .prefetch_related("images", "variants")
        )
        # Sellers see their own products regardless of active state
        if (
            self.request.user.is_authenticated
            and getattr(self.request.user, "role", None) == "seller"
        ):
            qs = (
                Product.objects.filter(seller=self.request.user)
                .select_related("category", "seller")
                .prefetch_related("images", "variants")
            )
        return qs

    def perform_create(self, serializer):
        serializer.save(seller=self.request.user)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        Product.objects.filter(pk=instance.pk).update(view_count=F("view_count") + 1)
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def perform_destroy(self, instance):
        """Soft delete: set is_active=False instead of removing row."""
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])
        cache.delete_many([f"product:{instance.pk}", "products:list"])

    # ------------------------------------------------------------------
    # POST /api/v1/products/{id}/clone/   FR-SELL-007
    # ------------------------------------------------------------------
    @action(
        detail=True,
        methods=["post"],
        url_path="clone",
        permission_classes=[permissions.IsAuthenticated],
    )
    def clone(self, request, pk=None):
        """Duplicate a product listing and return the new product."""
        original = self.get_object()
        if original.seller_id != request.user.pk:
            return Response({"detail": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)

        # Clone the product
        original.pk = None
        original.id = None
        original.title = f"{original.title} (Copy)"
        original.is_active = False  # clones start inactive until seller edits
        original.view_count = 0
        original.search_vector = None
        original.save()

        serializer = self.get_serializer(original)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    # ------------------------------------------------------------------
    # GET /api/v1/products/search/?q=<term>
    # ------------------------------------------------------------------
    @action(detail=False, methods=["get"], url_path="search")
    def search(self, request):
        q = request.query_params.get("q", "").strip()
        if not q:
            return Response(
                {"detail": "q parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        query = SearchQuery(q, config="english")
        qs = (
            Product.objects.filter(is_active=True, search_vector=query)
            .annotate(rank=SearchRank(F("search_vector"), query))
            .order_by("-rank")
            .select_related("category")
            .prefetch_related("images")
        )
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = ProductListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        return Response(ProductListSerializer(qs, many=True).data)

    # ------------------------------------------------------------------
    # POST /api/v1/products/{id}/images/
    # ------------------------------------------------------------------
    @action(
        detail=True,
        methods=["post"],
        url_path="images",
        permission_classes=[permissions.IsAuthenticated],
        parser_classes=[MultiPartParser, FormParser],
    )
    def upload_image(self, request, pk=None):
        product = self.get_object()
        if product.seller_id != request.user.pk:
            return Response({"detail": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)

        if product.images.count() >= 10:
            return Response(
                {"detail": "Maximum 10 images per product."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        image_file = request.FILES.get("image")
        if not image_file:
            return Response(
                {"detail": "image field is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if image_file.size > 5 * 1024 * 1024:
            return Response(
                {"detail": "Image must not exceed 5 MB."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        is_primary = product.images.count() == 0
        image_obj = ProductImage.objects.create(
            product=product,
            url="",
            is_primary=is_primary,
            display_order=product.images.count(),
        )
        file_bytes = image_file.read()
        process_product_image.delay(image_obj.pk, file_bytes, image_file.name)

        return Response(
            {"id": image_obj.pk, "status": "processing"},
            status=status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------------------
# Bulk CSV Upload
# ---------------------------------------------------------------------------

class BulkUploadView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    REQUIRED_COLS = {"title", "price", "category_id", "stock", "currency"}

    def post(self, request):
        if getattr(request.user, "role", None) != "seller":
            return Response(
                {"detail": "Seller role required."},
                status=status.HTTP_403_FORBIDDEN,
            )

        file = request.FILES.get("file")
        if not file:
            return Response(
                {"detail": "CSV file required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            raw = file.read().decode("utf-8-sig")
        except UnicodeDecodeError:
            return Response(
                {"detail": "File must be UTF-8 encoded."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reader = csv.DictReader(io.StringIO(raw))
        actual_cols = set(reader.fieldnames or [])
        missing = self.REQUIRED_COLS - actual_cols
        if missing:
            return Response(
                {"detail": f"Missing columns: {sorted(missing)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        success_count = 0
        error_count = 0
        errors = []
        products_to_create = []

        for row_num, row in enumerate(reader, start=2):
            row_errors = []

            # Validate category
            category = None
            try:
                category = Category.objects.get(
                    pk=int(row["category_id"]), is_active=True
                )
            except (Category.DoesNotExist, ValueError, TypeError):
                row_errors.append(f"category_id '{row['category_id']}' not found or inactive")

            # Validate price
            price = None
            try:
                price = Decimal(str(row["price"]).strip())
                if price < 0:
                    raise ValueError
            except (InvalidOperation, ValueError):
                row_errors.append(f"price '{row['price']}' is invalid")

            # Validate stock
            stock = None
            try:
                stock = int(row["stock"])
                if stock < 0:
                    raise ValueError
            except (ValueError, TypeError):
                row_errors.append(f"stock '{row['stock']}' is invalid")

            if row_errors:
                error_count += 1
                errors.append({"row": row_num, "errors": row_errors})
                continue

            products_to_create.append(
                Product(
                    seller=request.user,
                    category=category,
                    title=str(row["title"])[:500],
                    description=str(row.get("description", "")),
                    price=price,
                    currency=str(row.get("currency", "PKR"))[:3].upper(),
                    stock=stock,
                    compare_at_price=(Decimal(str(row["compare_at_price"])) if row.get("compare_at_price") and str(row["compare_at_price"]).replace(".","",1).isdigit() else None),
                )
            )
            success_count += 1

        if products_to_create:
            Product.objects.bulk_create(products_to_create)

        return Response(
            {
                "success_count": success_count,
                "error_count": error_count,
                "errors": errors,
            },
            status=status.HTTP_201_CREATED,
        )
