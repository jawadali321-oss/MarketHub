import time
from django.http import JsonResponse
from django.db import connection
from django.core.cache import cache


def health_check(request):
    status = {"db": "ok", "redis": "ok", "s3": "ok"}
    http_status = 200
    start = time.time()

    # Check DB
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception as e:
        status["db"] = f"error: {str(e)}"
        http_status = 503

    # Check Redis
    try:
        cache.set("health_check", "ok", timeout=10)
        val = cache.get("health_check")
        if val != "ok":
            raise ValueError("Cache read/write mismatch")
    except Exception as e:
        status["redis"] = f"error: {str(e)}"
        http_status = 503

    # Check S3 (only if configured)
    from django.conf import settings
    if settings.USE_S3:
        try:
            import boto3
            s3 = boto3.client(
                "s3",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME,
            )
            s3.head_bucket(Bucket=settings.AWS_STORAGE_BUCKET_NAME)
        except Exception as e:
            status["s3"] = f"error: {str(e)}"
            http_status = 503
    else:
        status["s3"] = "not configured (local storage)"

    status["response_time_ms"] = round((time.time() - start) * 1000, 2)
    status["status"] = "healthy" if http_status == 200 else "degraded"

    return JsonResponse({"success": http_status == 200, "data": status}, status=http_status)
