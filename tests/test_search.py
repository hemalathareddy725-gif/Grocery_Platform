from decimal import Decimal
from django.test import TestCase

from apps.products.models import Category, Product


class ProductSearchTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Toys")
        Product.objects.create(title="Red Toy Car", price=Decimal("15.00"), category=self.category)
        Product.objects.create(title="Blue Toy Truck", price=Decimal("25.00"), category=self.category)

    def test_search_by_keyword(self):
        response = self.client.get("/api/search/products/?q=Toy")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 2)

    def test_suggest_requires_min_3_chars(self):
        response = self.client.get("/api/search/suggest/?q=to")
        self.assertEqual(response.status_code, 400)

    def test_suggest_prefix_ranked_first(self):
        Product.objects.create(title="Toyota Model", price=Decimal("100.00"), category=self.category)
        response = self.client.get("/api/search/suggest/?q=Toy")
        self.assertEqual(response.status_code, 200)
        results = response.json()["results"]
        self.assertTrue(results[0].lower().startswith("toy"))
