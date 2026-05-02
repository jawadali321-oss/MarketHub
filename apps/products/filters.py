import django_filters
from django.utils import timezone

from .models import Product


class ProductFilter(django_filters.FilterSet):
    min_price = django_filters.NumberFilter(field_name="price", lookup_expr="gte")
    max_price = django_filters.NumberFilter(field_name="price", lookup_expr="lte")
    category = django_filters.NumberFilter(field_name="category__id")
    currency = django_filters.CharFilter(field_name="currency", lookup_expr="iexact")
    seller = django_filters.UUIDFilter(field_name="seller__id")
    in_stock = django_filters.BooleanFilter(method="filter_in_stock")
    on_sale = django_filters.BooleanFilter(method="filter_on_sale")
    search = django_filters.CharFilter(method="filter_search")

    # FR-BUY-002: missing filters now added
    brand = django_filters.CharFilter(field_name="brand", lookup_expr="icontains")
    has_shipping_info = django_filters.BooleanFilter(method="filter_has_shipping_info")
    min_rating = django_filters.NumberFilter(method="filter_min_rating")

    class Meta:
        model = Product
        fields = ["category", "currency", "seller", "brand"]

    def filter_in_stock(self, queryset, name, value):
        return queryset.filter(stock__gt=0) if value else queryset.filter(stock=0)

    def filter_on_sale(self, queryset, name, value):
        if not value:
            return queryset
        now = timezone.now()
        return queryset.filter(
            discount_pct__isnull=False,
            sale_start__lte=now,
            sale_end__gte=now,
        )

    def filter_search(self, queryset, name, value):
        """Basic icontains fallback when search_vector is not populated yet."""
        return queryset.filter(title__icontains=value)

    def filter_has_shipping_info(self, queryset, name, value):
        """Filter products that have shipping dimensions/weight set (FR-SELL-004)."""
        if value:
            return queryset.filter(weight_kg__isnull=False)
        return queryset.filter(weight_kg__isnull=True)

    def filter_min_rating(self, queryset, name, value):
        """Filter sellers by minimum avg rating via seller profile (FR-BUY-002)."""
        return queryset.filter(seller__seller_profile__rating_avg__gte=value)

