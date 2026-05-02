import io
import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from rest_framework import status
from rest_framework.test import APIClient

from .models import Category, Product, ProductImage, ProductVariant

User = get_user_model()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _uid():
    return uuid.uuid4().hex[:8]


def make_user(role="buyer", **kwargs):
    defaults = {
        "email": f"{role}_{_uid()}@test.com",
        "password": "TestPass1!",
        "role": role,
    }
    defaults.update(kwargs)
    return User.objects.create_user(**defaults)


def make_category(**kwargs):
    defaults = {
        "name": f"Category {_uid()}",
        "slug": f"cat-{_uid()}",
        "level": 1,
        "display_order": 0,
        "is_active": True,
    }
    defaults.update(kwargs)
    return Category.objects.create(**defaults)


def make_product(seller, category, **kwargs):
    defaults = {
        "title": f"Product {_uid()}",
        "price": Decimal("999.99"),
        "currency": "PKR",
        "stock": 100,
        "is_active": True,
    }
    defaults.update(kwargs)
    return Product.objects.create(seller=seller, category=category, **defaults)


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

class CategoryModelTests(TestCase):
    def test_str(self):
        cat = make_category(name="Electronics")
        self.assertEqual(str(cat), "Electronics")

    def test_unique_name_per_parent(self):
        from django.db import IntegrityError
        make_category(name="Shoes", slug="shoes-1")
        with self.assertRaises(IntegrityError):
            Category.objects.create(
                name="Shoes", slug="shoes-2", level=1, parent=None
            )

    def test_child_category(self):
        parent = make_category(name="Clothing", level=1)
        child = make_category(name="Shirts", slug="shirts", level=2, parent=parent)
        self.assertEqual(child.parent, parent)
        self.assertIn(child, parent.children.all())


class ProductModelTests(TestCase):
    def setUp(self):
        self.seller = make_user("seller")
        self.cat = make_category()

    def test_str(self):
        p = make_product(self.seller, self.cat, title="Blue Jeans")
        self.assertEqual(str(p), "Blue Jeans")

    def test_uuid_primary_key(self):
        p = make_product(self.seller, self.cat)
        self.assertIsInstance(p.pk, uuid.UUID)

    def test_is_on_sale_false_no_discount(self):
        p = make_product(self.seller, self.cat)
        self.assertFalse(p.is_on_sale)

    def test_is_on_sale_true_within_window(self):
        now = timezone.now()
        p = make_product(
            self.seller, self.cat,
            discount_pct=Decimal("20"),
            sale_start=now - timedelta(hours=1),
            sale_end=now + timedelta(hours=1),
        )
        self.assertTrue(p.is_on_sale)

    def test_is_on_sale_false_outside_window(self):
        now = timezone.now()
        p = make_product(
            self.seller, self.cat,
            discount_pct=Decimal("20"),
            sale_start=now - timedelta(days=2),
            sale_end=now - timedelta(days=1),
        )
        self.assertFalse(p.is_on_sale)

    def test_current_price_with_discount(self):
        now = timezone.now()
        p = make_product(
            self.seller, self.cat,
            price=Decimal("1000"),
            discount_pct=Decimal("10"),
            sale_start=now - timedelta(hours=1),
            sale_end=now + timedelta(hours=1),
        )
        self.assertEqual(p.current_price, Decimal("900.00"))

    def test_current_price_without_discount(self):
        p = make_product(self.seller, self.cat, price=Decimal("500"))
        self.assertEqual(p.current_price, Decimal("500"))

    def test_soft_delete_preserves_row(self):
        p = make_product(self.seller, self.cat)
        p.is_active = False
        p.save()
        self.assertTrue(Product.objects.filter(pk=p.pk).exists())

    def test_stock_non_negative(self):
        # PositiveIntegerField enforces >= 0 at DB level
        p = make_product(self.seller, self.cat, stock=0)
        self.assertEqual(p.stock, 0)


class ProductVariantTests(TestCase):
    def setUp(self):
        self.seller = make_user("seller")
        self.cat = make_category()
        self.product = make_product(self.seller, self.cat)

    def test_variant_str_is_sku(self):
        v = ProductVariant.objects.create(
            product=self.product, sku="SKU-001",
            attributes={"color": "red", "size": "M"}, stock=10
        )
        self.assertEqual(str(v), "SKU-001")

    def test_sku_unique(self):
        from django.db import IntegrityError
        ProductVariant.objects.create(product=self.product, sku="UNIQUE-SKU", stock=5)
        with self.assertRaises(IntegrityError):
            ProductVariant.objects.create(product=self.product, sku="UNIQUE-SKU", stock=3)


# ---------------------------------------------------------------------------
# API tests
# ---------------------------------------------------------------------------

class CategoryAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            email="admin@test.com", password="Admin1!", role="admin"
        )

    def test_list_categories_public(self):
        make_category()
        r = self.client.get("/api/v1/categories/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_create_category_requires_auth(self):
        r = self.client.post("/api/v1/categories/", {"name": "X", "slug": "x", "level": 1})
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_category_as_admin(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post("/api/v1/categories/", {
            "name": "Electronics", "slug": "electronics-test",
            "level": 1, "display_order": 1, "is_active": True,
        })
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data["name"], "Electronics")

    def test_nested_tree_returned(self):
        parent = make_category(name="Fashion", slug="fashion")
        make_category(name="Shirts", slug="shirts-sub", level=2, parent=parent)
        self.client.force_authenticate(self.admin)
        r = self.client.get("/api/v1/categories/")
        fashion = next((c for c in r.data if c["name"] == "Fashion"), None)
        self.assertIsNotNone(fashion)
        self.assertEqual(len(fashion["children"]), 1)


class ProductAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.seller = make_user("seller")
        self.buyer = make_user("buyer")
        self.cat = make_category()
        self.product = make_product(self.seller, self.cat)

    def test_list_public(self):
        r = self.client.get("/api/v1/products/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_create_requires_seller(self):
        self.client.force_authenticate(self.buyer)
        r = self.client.post("/api/v1/products/", {
            "title": "New", "price": "100",
            "category": self.cat.pk, "stock": 5, "currency": "PKR",
        })
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_as_seller(self):
        self.client.force_authenticate(self.seller)
        r = self.client.post("/api/v1/products/", {
            "title": "Cotton Shirt", "price": "599",
            "category": self.cat.pk, "stock": 50, "currency": "PKR",
        })
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data["title"], "Cotton Shirt")

    def test_soft_delete(self):
        self.client.force_authenticate(self.seller)
        r = self.client.delete(f"/api/v1/products/{self.product.pk}/")
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT)
        self.product.refresh_from_db()
        self.assertFalse(self.product.is_active)

    def test_partial_update_price(self):
        self.client.force_authenticate(self.seller)
        r = self.client.patch(
            f"/api/v1/products/{self.product.pk}/",
            {"price": "1299.00"},
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal("1299.00"))

    def test_other_seller_cannot_update(self):
        other = make_user("seller")
        self.client.force_authenticate(other)
        r = self.client.patch(
            f"/api/v1/products/{self.product.pk}/",
            {"price": "1"},
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_retrieve_increments_view_count(self):
        initial = self.product.view_count
        self.client.get(f"/api/v1/products/{self.product.pk}/")
        self.product.refresh_from_db()
        self.assertEqual(self.product.view_count, initial + 1)


class BulkUploadAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.seller = make_user("seller")
        self.cat = make_category()

    def _csv(self, rows):
        header = "title,price,category_id,stock,currency,description,compare_at_price\n"
        body = "\n".join(
            f"{r['title']},{r['price']},{r['category_id']},{r['stock']},{r.get('currency','PKR')},{r.get('description','')},{r.get('compare_at_price','')}"
            for r in rows
        )
        return io.BytesIO((header + body).encode())

    def test_bulk_upload_success(self):
        self.client.force_authenticate(self.seller)
        csv_file = self._csv([
            {"title": "Product A", "price": "100", "category_id": self.cat.pk, "stock": 10},
            {"title": "Product B", "price": "200", "category_id": self.cat.pk, "stock": 20},
        ])
        r = self.client.post(
            "/api/v1/products/bulk-upload/",
            {"file": csv_file},
            format="multipart",
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data["success_count"], 2)
        self.assertEqual(r.data["error_count"], 0)

    def test_bulk_upload_invalid_row(self):
        self.client.force_authenticate(self.seller)
        csv_file = self._csv([
            {"title": "Good", "price": "100", "category_id": self.cat.pk, "stock": 5},
            {"title": "Bad",  "price": "abc", "category_id": self.cat.pk, "stock": 5},
        ])
        r = self.client.post(
            "/api/v1/products/bulk-upload/",
            {"file": csv_file},
            format="multipart",
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data["success_count"], 1)
        self.assertEqual(r.data["error_count"], 1)

    def test_bulk_upload_requires_seller(self):
        buyer = make_user("buyer")
        self.client.force_authenticate(buyer)
        csv_file = self._csv([
            {"title": "X", "price": "50", "category_id": self.cat.pk, "stock": 1}
        ])
        r = self.client.post(
            "/api/v1/products/bulk-upload/",
            {"file": csv_file},
            format="multipart",
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
