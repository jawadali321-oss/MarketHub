from django.contrib import admin

from .models import Category, Product, ProductImage, ProductVariant


# ---------------------------------------------------------------------------
# Category
# ---------------------------------------------------------------------------

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "parent", "level", "slug", "display_order", "is_active"]
    list_filter = ["level", "is_active"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    ordering = ["display_order", "name"]
    list_editable = ["display_order", "is_active"]


# ---------------------------------------------------------------------------
# Product
# ---------------------------------------------------------------------------

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0
    readonly_fields = ["url", "cdn_url"]
    fields = ["url", "cdn_url", "is_primary", "display_order"]


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1
    fields = ["sku", "attributes", "stock", "price_override"]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        "title", "seller", "category", "price", "currency",
        "stock", "is_active", "view_count", "created_at",
    ]
    list_filter = ["is_active", "currency", "category__name"]
    search_fields = ["title", "description", "seller__email"]
    readonly_fields = ["id", "view_count", "search_vector", "created_at", "updated_at"]
    date_hierarchy = "created_at"
    inlines = [ProductImageInline, ProductVariantInline]
    fieldsets = (
        ("Core", {"fields": ("id", "seller", "category", "title", "description")}),
        ("Pricing", {"fields": ("price", "currency", "compare_at_price", "discount_pct", "sale_start", "sale_end")}),
        ("Inventory", {"fields": ("stock", "is_active", "view_count")}),
        ("Meta", {"fields": ("search_vector", "created_at", "updated_at")}),
    )
