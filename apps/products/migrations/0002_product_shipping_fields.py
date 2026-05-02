from django.db import migrations, models
import django.core.validators
from decimal import Decimal


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="brand",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="product",
            name="low_stock_threshold",
            field=models.PositiveIntegerField(default=5),
        ),
        migrations.AddField(
            model_name="product",
            name="weight_kg",
            field=models.DecimalField(
                blank=True, decimal_places=3, help_text="Weight in kilograms",
                max_digits=8, null=True,
                validators=[django.core.validators.MinValueValidator(Decimal("0"))],
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="length_cm",
            field=models.DecimalField(
                blank=True, decimal_places=2, help_text="Length in centimetres",
                max_digits=8, null=True,
                validators=[django.core.validators.MinValueValidator(Decimal("0"))],
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="width_cm",
            field=models.DecimalField(
                blank=True, decimal_places=2, help_text="Width in centimetres",
                max_digits=8, null=True,
                validators=[django.core.validators.MinValueValidator(Decimal("0"))],
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="height_cm",
            field=models.DecimalField(
                blank=True, decimal_places=2, help_text="Height in centimetres",
                max_digits=8, null=True,
                validators=[django.core.validators.MinValueValidator(Decimal("0"))],
            ),
        ),
    ]
