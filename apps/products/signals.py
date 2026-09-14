"""
Bumps a cache 'version' key whenever product/category data changes so that
all cached search results are invalidated cheaply (no need to enumerate keys).
"""
from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Product, Category

SEARCH_CACHE_VERSION_KEY = "search:cache:version"


def bump_search_cache_version(**kwargs):
    try:
        cache.incr(SEARCH_CACHE_VERSION_KEY)
    except ValueError:
        cache.set(SEARCH_CACHE_VERSION_KEY, 1, None)


post_save.connect(bump_search_cache_version, sender=Product)
post_delete.connect(bump_search_cache_version, sender=Product)
post_save.connect(bump_search_cache_version, sender=Category)
post_delete.connect(bump_search_cache_version, sender=Category)
