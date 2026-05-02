import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CustomUser, SellerProfile

logger = logging.getLogger(__name__)

@receiver(post_save, sender=CustomUser)
def create_seller_profile(sender, instance, created, **kwargs):
    """Signal disabled — SellerProfile is created by RegisterSerializer.create() instead."""
    pass
