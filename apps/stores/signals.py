from django.db.models.signals import post_save, post_delete
from apps.products.signals import bump_search_cache_version
from .models import Inventory

post_save.connect(bump_search_cache_version, sender=Inventory)
post_delete.connect(bump_search_cache_version, sender=Inventory)
