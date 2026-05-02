import uuid
from decimal import Decimal

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class Category(models.Model):
    LEVEL_CHOICES = [(1, "1"), (2, "2"), (3, "3"), (4, "4")]

    name = models.CharField(max_length=255)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="children",
    )
    slug = models.SlugField(max_length=255, unique=True)
    level = models.PositiveSmallIntegerField(default=1, choices=LEVEL_CHOICES)
    icon_url = models.URLField(blank=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "categories"
        unique_together = [("name", "parent")]
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name


class Product(models.Model):
    CURRENCY_CHOICES = [
        ("PKR", "PKR"),
        ("USD", "USD"),
        ("EUR", "EUR"),
        ("GBP", "GBP"),
        ("AED", "AED"),
        ("SAR", "SAR"),
        ("MYR", "MYR"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="products",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
    )
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default="PKR")
    compare_at_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    discount_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    sale_start = models.DateTimeField(null=True, blank=True)
    sale_end = models.DateTimeField(null=True, blank=True)
    stock = models.PositiveIntegerField(default=0)  # CHECK >= 0 via PositiveIntegerField
    low_stock_threshold = models.PositiveIntegerField(default=5)  # FR-SELL-008
    is_active = models.BooleanField(default=True)  # soft-delete
    view_count = models.PositiveIntegerField(default=0)

    # FR-SELL-004: Shipping dimensions/weight for freight calculation
    brand = models.CharField(max_length=255, blank=True)  # FR-BUY-002
    weight_kg = models.DecimalField(
        max_digits=8, decimal_places=3, null=True, blank=True,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Weight in kilograms"
    )
    length_cm = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Length in centimetres"
    )
    width_cm = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Width in centimetres"
    )
    height_cm = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Height in centimetres"
    )
    search_vector = SearchVectorField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            GinIndex(fields=["search_vector"], name="product_search_vector_gin"),
        ]

    def __str__(self):
        return self.title

    @property
    def is_on_sale(self) -> bool:
        if not self.discount_pct:
            return False
        if self.sale_start and self.sale_end:
            now = timezone.now()
            return self.sale_start <= now <= self.sale_end
        return True  # discount set, no date window → always on sale

    @property
    def current_price(self) -> Decimal:
        if self.is_on_sale and self.discount_pct:
            discount = self.price * (self.discount_pct / Decimal("100"))
            return round(self.price - discount, 2)
        return self.price


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="images"
    )
    url = models.URLField(blank=True)
    cdn_url = models.URLField(blank=True)
    is_primary = models.BooleanField(default=False)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["display_order"]

    def __str__(self):
        return f"Image {self.pk} → Product {self.product_id}"


class ProductVariant(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="variants"
    )
    sku = models.CharField(max_length=100, unique=True)
    attributes = models.JSONField(default=dict)  # {"color": "red", "size": "M"}
    stock = models.PositiveIntegerField(default=0)  # CHECK >= 0 via PositiveIntegerField
    price_override = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )

    def __str__(self):
        return self.sku
