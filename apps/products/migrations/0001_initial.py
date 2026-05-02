import uuid
import django.core.validators
import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ------------------------------------------------------------------
        # Category
        # ------------------------------------------------------------------
        migrations.CreateModel(
            name="Category",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="children",
                        to="products.category",
                    ),
                ),
                ("slug", models.SlugField(max_length=255, unique=True)),
                (
                    "level",
                    models.PositiveSmallIntegerField(
                        choices=[(1, "1"), (2, "2"), (3, "3"), (4, "4")],
                        default=1,
                    ),
                ),
                ("icon_url", models.URLField(blank=True)),
                ("display_order", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "verbose_name_plural": "categories",
                "ordering": ["display_order", "name"],
            },
        ),
        migrations.AddConstraint(
            model_name="category",
            constraint=models.UniqueConstraint(
                fields=("name", "parent"),
                name="unique_category_name_per_parent",
            ),
        ),
        # ------------------------------------------------------------------
        # Product
        # ------------------------------------------------------------------
        migrations.CreateModel(
            name="Product",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "seller",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="products",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "category",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="products",
                        to="products.category",
                    ),
                ),
                ("title", models.CharField(max_length=500)),
                ("description", models.TextField(blank=True)),
                (
                    "price",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=12,
                        validators=[django.core.validators.MinValueValidator(Decimal("0"))],
                    ),
                ),
                (
                    "currency",
                    models.CharField(
                        choices=[
                            ("PKR", "PKR"), ("USD", "USD"), ("EUR", "EUR"),
                            ("GBP", "GBP"), ("AED", "AED"), ("SAR", "SAR"), ("MYR", "MYR"),
                        ],
                        default="PKR",
                        max_length=3,
                    ),
                ),
                (
                    "compare_at_price",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=12,
                        null=True,
                        validators=[django.core.validators.MinValueValidator(Decimal("0"))],
                    ),
                ),
                (
                    "discount_pct",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=5,
                        null=True,
                        validators=[django.core.validators.MinValueValidator(Decimal("0"))],
                    ),
                ),
                ("sale_start", models.DateTimeField(blank=True, null=True)),
                ("sale_end", models.DateTimeField(blank=True, null=True)),
                ("stock", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("view_count", models.PositiveIntegerField(default=0)),
                ("search_vector", SearchVectorField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="product",
            index=GinIndex(fields=["search_vector"], name="product_search_vector_gin"),
        ),
        # Partial index: active products by category (raw SQL)
        migrations.RunSQL(
            sql="""
                CREATE INDEX product_category_active_idx
                ON products_product (category_id)
                WHERE is_active = TRUE;
            """,
            reverse_sql="DROP INDEX IF EXISTS product_category_active_idx;",
        ),
        # GIN index on variants.attributes JSONB (added after ProductVariant table)
        # ------------------------------------------------------------------
        # ProductImage
        # ------------------------------------------------------------------
        migrations.CreateModel(
            name="ProductImage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="images",
                        to="products.product",
                    ),
                ),
                ("url", models.URLField(blank=True)),
                ("cdn_url", models.URLField(blank=True)),
                ("is_primary", models.BooleanField(default=False)),
                ("display_order", models.PositiveIntegerField(default=0)),
            ],
            options={
                "ordering": ["display_order"],
            },
        ),
        # ------------------------------------------------------------------
        # ProductVariant
        # ------------------------------------------------------------------
        migrations.CreateModel(
            name="ProductVariant",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="variants",
                        to="products.product",
                    ),
                ),
                ("sku", models.CharField(max_length=100, unique=True)),
                ("attributes", models.JSONField(default=dict)),
                ("stock", models.PositiveIntegerField(default=0)),
                (
                    "price_override",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=12,
                        null=True,
                        validators=[django.core.validators.MinValueValidator(Decimal("0"))],
                    ),
                ),
            ],
        ),
        # GIN index on variants.attributes JSONB
        migrations.RunSQL(
            sql="""
                CREATE INDEX product_variant_attributes_gin
                ON products_productvariant USING gin (attributes jsonb_path_ops);
            """,
            reverse_sql="DROP INDEX IF EXISTS product_variant_attributes_gin;",
        ),
    ]
