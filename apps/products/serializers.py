from rest_framework import serializers

from .models import Category, Product, ProductImage, ProductVariant


# ---------------------------------------------------------------------------
# Category
# ---------------------------------------------------------------------------

class CategorySerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = [
            "id", "name", "parent", "slug", "level",
            "icon_url", "display_order", "is_active", "children",
        ]

    def get_children(self, obj):
        qs = obj.children.filter(is_active=True).order_by("display_order", "name")
        return CategorySerializer(qs, many=True).data


class CategoryWriteSerializer(serializers.ModelSerializer):
    parent = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), required=False, allow_null=True)
    class Meta:
        model = Category
        fields = [
            "id", "name", "parent", "slug", "level",
            "icon_url", "display_order", "is_active",
        ]

    def validate(self, attrs):
        parent = attrs.get("parent")
        level = attrs.get("level", 1)
        if parent and level != parent.level + 1:
            raise serializers.ValidationError(
                {"level": f"Level must be parent.level + 1 (expected {parent.level + 1})."}
            )
        if level > 4:
            raise serializers.ValidationError({"level": "Maximum category depth is 4."})
        return attrs


# ---------------------------------------------------------------------------
# Product images / variants
# ---------------------------------------------------------------------------

class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ["id", "url", "cdn_url", "is_primary", "display_order"]
        read_only_fields = ["url", "cdn_url"]


class ProductVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariant
        fields = ["id", "sku", "attributes", "stock", "price_override"]


# ---------------------------------------------------------------------------
# Product – detail
# ---------------------------------------------------------------------------

class ProductSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, read_only=True)
    variants = ProductVariantSerializer(many=True, read_only=True)
    is_on_sale = serializers.BooleanField(read_only=True)
    current_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    seller_id = serializers.UUIDField(source="seller.id", read_only=True)

    class Meta:
        model = Product
        fields = [
            "id", "seller_id", "category", "title", "description",
            "price", "currency", "compare_at_price", "discount_pct",
            "sale_start", "sale_end", "stock", "low_stock_threshold",
            "is_active", "view_count",
            "brand", "weight_kg", "length_cm", "width_cm", "height_cm",
            "is_on_sale", "current_price",
            "images", "variants",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "seller_id", "view_count", "is_on_sale",
            "current_price", "created_at", "updated_at",
        ]

    def validate_stock(self, value):
        if value < 0:
            raise serializers.ValidationError("Stock must be non-negative.")
        return value


# ---------------------------------------------------------------------------
# Product – lightweight list
# ---------------------------------------------------------------------------

class ProductListSerializer(serializers.ModelSerializer):
    primary_image = serializers.SerializerMethodField()
    is_on_sale = serializers.BooleanField(read_only=True)
    current_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )

    class Meta:
        model = Product
        fields = [
            "id", "title", "price", "currency", "current_price",
            "is_on_sale", "discount_pct", "stock", "low_stock_threshold",
            "brand", "primary_image", "category", "created_at",
        ]

    def get_primary_image(self, obj):
        img = obj.images.filter(is_primary=True).first() or obj.images.first()
        if img:
            return img.cdn_url or img.url
        return None


# ---------------------------------------------------------------------------
# Bulk upload
# ---------------------------------------------------------------------------

class BulkUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
