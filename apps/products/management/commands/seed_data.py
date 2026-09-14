import random
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from faker import Faker

from apps.products.models import Category, Product
from apps.stores.models import Store, Inventory

fake = Faker()

CATEGORY_NAMES = [
    "Electronics", "Groceries", "Apparel", "Home & Kitchen", "Books",
    "Sports & Outdoors", "Toys", "Beauty", "Automotive", "Office Supplies",
    "Pet Supplies", "Health",
]


class Command(BaseCommand):
    help = "Seeds the database with categories, products, stores, and inventory."

    def add_arguments(self, parser):
        parser.add_argument("--products", type=int, default=1200)
        parser.add_argument("--stores", type=int, default=25)
        parser.add_argument("--inventory-per-store", type=int, default=350)

    @transaction.atomic
    def handle(self, *args, **options):
        n_products = options["products"]
        n_stores = options["stores"]
        n_inventory = options["inventory_per_store"]

        self.stdout.write("Seeding categories...")
        categories = [Category.objects.get_or_create(name=name)[0] for name in CATEGORY_NAMES]

        self.stdout.write(f"Seeding {n_products} products...")
        products = []
        for _ in range(n_products):
            products.append(Product(
                title=fake.unique.catch_phrase(),
                description=fake.text(max_nb_chars=200),
                price=Decimal(random.randrange(500, 50000)) / 100,
                category=random.choice(categories),
            ))
        Product.objects.bulk_create(products, batch_size=500)
        all_products = list(Product.objects.all())

        self.stdout.write(f"Seeding {n_stores} stores...")
        stores = []
        for _ in range(n_stores):
            stores.append(Store(name=f"{fake.company()} Store", location=fake.city()))
        Store.objects.bulk_create(stores)
        all_stores = list(Store.objects.all())

        self.stdout.write("Seeding inventory...")
        inventory_objs = []
        for store in all_stores:
            picked_products = random.sample(all_products, min(n_inventory, len(all_products)))
            for product in picked_products:
                inventory_objs.append(Inventory(
                    store=store,
                    product=product,
                    quantity=random.randint(0, 200),
                ))
        Inventory.objects.bulk_create(inventory_objs, batch_size=1000, ignore_conflicts=True)

        self.stdout.write(self.style.SUCCESS(
            f"Done: {len(categories)} categories, {len(all_products)} products, "
            f"{len(all_stores)} stores, {len(inventory_objs)} inventory rows."
        ))
