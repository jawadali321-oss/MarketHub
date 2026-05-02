import io
import logging
import uuid

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from celery import shared_task
from django.conf import settings
from PIL import Image

logger = logging.getLogger(__name__)

WEBP_MAX_DIM = (800, 800)
WEBP_QUALITY = 85


# ---------------------------------------------------------------------------
# Image processing
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=3, default_retry_delay=15, name="products.process_product_image")
def process_product_image(self, image_id: int, file_data: bytes, original_name: str):
    """
    1. Open raw bytes with Pillow
    2. Resize to max 800×800 (aspect-preserving)
    3. Convert to WebP quality=85
    4. Upload to S3
    5. Update ProductImage.url + cdn_url
    """
    from .models import ProductImage  # local import avoids circular on app startup

    try:
        img = Image.open(io.BytesIO(file_data)).convert("RGB")
        img.thumbnail(WEBP_MAX_DIM, Image.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format="WEBP", quality=WEBP_QUALITY, method=6)
        buf.seek(0)

        key = f"products/images/{uuid.uuid4().hex}.webp"
        bucket = settings.AWS_STORAGE_BUCKET_NAME

        s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=getattr(settings, "AWS_S3_REGION_NAME", "us-east-1"),
        )
        s3.upload_fileobj(
            buf,
            bucket,
            key,
            ExtraArgs={"ContentType": "image/webp", "ACL": "public-read"},
        )

        region = getattr(settings, "AWS_S3_REGION_NAME", "us-east-1")
        s3_url = f"https://{bucket}.s3.{region}.amazonaws.com/{key}"
        cdn_url = f"{settings.CDN_BASE_URL.rstrip('/')}/{key}" if getattr(settings, "CDN_BASE_URL", None) else s3_url

        ProductImage.objects.filter(pk=image_id).update(url=s3_url, cdn_url=cdn_url)
        logger.info("process_product_image: image_id=%s uploaded → %s", image_id, cdn_url)

    except (BotoCoreError, ClientError) as exc:
        logger.error("process_product_image: S3 error for image_id=%s: %s", image_id, exc)
        raise self.retry(exc=exc)
    except Exception as exc:
        logger.error("process_product_image: unexpected error image_id=%s: %s", image_id, exc)
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Search vector refresh (run via Celery Beat, e.g. every 15 min)
# ---------------------------------------------------------------------------

@shared_task(name="products.refresh_search_vectors")
def refresh_search_vectors():
    """
    Re-compute tsvector for all active products.
    Called periodically so newly created products are indexed.
    """
    from django.contrib.postgres.search import SearchVector
    from .models import Product

    updated = Product.objects.filter(is_active=True).update(
        search_vector=(
            SearchVector("title", weight="A", config="english")
            + SearchVector("description", weight="B", config="english")
        )
    )
    logger.info("refresh_search_vectors: updated %d products", updated)
    return updated


# ---------------------------------------------------------------------------
# Low-stock notification task  FR-SELL-008
# ---------------------------------------------------------------------------

@shared_task(name="products.notify_low_stock")
def notify_low_stock(product_id: str):
    """
    Notify the seller when stock drops at or below low_stock_threshold.
    Logs the alert; in production wire to email/push notification service.
    """
    from .models import Product
    try:
        product = Product.objects.select_related("seller").get(pk=product_id)
    except Product.DoesNotExist:
        return

    logger.warning(
        "notify_low_stock: seller=%s product='%s' stock=%d threshold=%d",
        product.seller.email,
        product.title,
        product.stock,
        product.low_stock_threshold,
    )
    # TODO Session 6: wire to NotificationService.send_push / send_email
    return {
        "product_id": product_id,
        "seller_email": product.seller.email,
        "stock": product.stock,
        "threshold": product.low_stock_threshold,
    }
