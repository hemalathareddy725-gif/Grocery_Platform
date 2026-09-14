from decimal import Decimal
from django.test import TestCase
from django.urls import reverse

from apps.products.models import Category, Product
from apps.stores.models import Store, Inventory
from apps.orders.models import Order


class OrderCreationTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Electronics")
        self.store = Store.objects.create(name="Test Store", location="City")
        self.product_a = Product.objects.create(title="Widget A", price=Decimal("10.00"), category=self.category)
        self.product_b = Product.objects.create(title="Widget B", price=Decimal("20.00"), category=self.category)
        Inventory.objects.create(store=self.store, product=self.product_a, quantity=5)
        Inventory.objects.create(store=self.store, product=self.product_b, quantity=2)

    def test_order_confirmed_when_stock_sufficient(self):
        payload = {
            "store_id": self.store.id,
            "items": [{"product_id": self.product_a.id, "quantity_requested": 3}],
        }
        response = self.client.post("/orders/", data=payload, content_type="application/json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], Order.CONFIRMED)
        self.product_a_inv = Inventory.objects.get(store=self.store, product=self.product_a)
        self.assertEqual(self.product_a_inv.quantity, 2)

    def test_order_rejected_when_stock_insufficient_and_no_deduction(self):
        payload = {
            "store_id": self.store.id,
            "items": [
                {"product_id": self.product_a.id, "quantity_requested": 3},
                {"product_id": self.product_b.id, "quantity_requested": 10},  # insufficient
            ],
        }
        response = self.client.post("/orders/", data=payload, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], Order.REJECTED)
        # No stock deducted for either item
        self.assertEqual(Inventory.objects.get(store=self.store, product=self.product_a).quantity, 5)
        self.assertEqual(Inventory.objects.get(store=self.store, product=self.product_b).quantity, 2)

    def test_order_listing_sorted_newest_first(self):
        self.client.post("/orders/", data={
            "store_id": self.store.id,
            "items": [{"product_id": self.product_a.id, "quantity_requested": 1}],
        }, content_type="application/json")
        self.client.post("/orders/", data={
            "store_id": self.store.id,
            "items": [{"product_id": self.product_a.id, "quantity_requested": 1}],
        }, content_type="application/json")

        response = self.client.get(f"/stores/{self.store.id}/orders/")
        self.assertEqual(response.status_code, 200)
        results = response.json()["results"]
        self.assertEqual(len(results), 2)
        self.assertGreaterEqual(results[0]["id"], results[1]["id"])
        self.assertEqual(results[0]["item_count"], 1)


class InventoryListingTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Books")
        self.store = Store.objects.create(name="Book Store", location="Town")
        self.p1 = Product.objects.create(title="Zebra Book", price=Decimal("5.00"), category=self.category)
        self.p2 = Product.objects.create(title="Apple Book", price=Decimal("7.00"), category=self.category)
        Inventory.objects.create(store=self.store, product=self.p1, quantity=1)
        Inventory.objects.create(store=self.store, product=self.p2, quantity=2)

    def test_inventory_sorted_alphabetically(self):
        response = self.client.get(f"/stores/{self.store.id}/inventory/")
        self.assertEqual(response.status_code, 200)
        titles = [item["product_title"] for item in response.json()["results"]]
        self.assertEqual(titles, sorted(titles))
