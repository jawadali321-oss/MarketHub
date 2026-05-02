from django.contrib.postgres.search import SearchVector
from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
import logging

logger = logging.getLogger(__name__)

from .models import Category, Product


@receiver(post_save, sender=Product)
def on_product_save(sender, instance, created, **kwargs):
    """Invalidate cache, refresh search_vector, and fire low-stock alert."""
    cache.delete(f"product:{instance.pk}")
    cache.delete("products:list")
    # Update search_vector in-place (avoids triggering signal again via update_fields)
    Product.objects.filter(pk=instance.pk).update(
        search_vector=(
            SearchVector("title", weight="A", config="english")
            + SearchVector("description", weight="B", config="english")
        )
    )
    # FR-SELL-008: low-stock alert
    if (
        not created
        and instance.stock <= instance.low_stock_threshold
        and instance.stock >= 0
        and instance.is_active
    ):
        logger.warning(
            "LOW STOCK ALERT: product_id=%s title='%s' stock=%d threshold=%d seller_id=%s",
            instance.pk,
            instance.title,
            instance.stock,
            instance.low_stock_threshold,
            instance.seller_id,
        )
        # Trigger async notification task
        from .tasks import notify_low_stock
        notify_low_stock.delay(str(instance.pk))


@receiver(post_save, sender=Category)
def on_category_save(sender, instance, **kwargs):
    cache.delete("categories:tree")


@receiver(post_delete, sender=Category)
def on_category_delete(sender, instance, **kwargs):
    cache.delete("categories:tree")
