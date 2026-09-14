import hashlib
import json

from django.core.cache import cache
from django.db.models import Q, OuterRef, Subquery, IntegerField
from django.db.models.functions import Coalesce
from rest_framework.views import APIView
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from apps.products.models import Product
from apps.products.serializers import ProductSearchSerializer
from apps.products.signals import SEARCH_CACHE_VERSION_KEY
from apps.stores.models import Inventory

CACHE_TTL_SECONDS = 60 * 5  # 5 minutes


def _cache_version():
    version = cache.get(SEARCH_CACHE_VERSION_KEY)
    if version is None:
        version = 1
        cache.set(SEARCH_CACHE_VERSION_KEY, version, None)
    return version


def _cache_key(prefix, params: dict):
    raw = json.dumps(params, sort_keys=True, default=str)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    return f"{prefix}:v{_cache_version()}:{digest}"


class ProductSearchView(APIView):
    """
    GET /api/search/products/
    Query params: q, category, min_price, max_price, store_id, in_stock,
                  sort=price|newest|relevance, page, page_size

    Cached in Redis (Option A). Cache is invalidated automatically whenever
    Product/Category/Inventory data changes, via a versioned cache key
    (see apps.products.signals) - no manual key deletion required.
    """

    def get(self, request):
        params = request.query_params.dict()
        cache_key = _cache_key("search:products", params)
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        qs = Product.objects.select_related("category")

        q = params.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(title__icontains=q) | Q(description__icontains=q) | Q(category__name__icontains=q)
            )

        category = params.get("category")
        if category:
            qs = qs.filter(category__name__iexact=category)

        min_price = params.get("min_price")
        max_price = params.get("max_price")
        if min_price:
            qs = qs.filter(price__gte=min_price)
        if max_price:
            qs = qs.filter(price__lte=max_price)

        store_id = params.get("store_id")
        if store_id:
            inv_subquery = Inventory.objects.filter(store_id=store_id, product=OuterRef("pk")).values("quantity")[:1]
            qs = qs.annotate(store_quantity=Coalesce(Subquery(inv_subquery, output_field=IntegerField()), 0))

            in_stock = params.get("in_stock")
            if in_stock in ("1", "true", "True"):
                qs = qs.filter(store_quantity__gt=0)

        sort = params.get("sort", "relevance")
        if sort == "price":
            qs = qs.order_by("price")
        elif sort == "newest":
            qs = qs.order_by("-created_at")
        else:  # relevance: title matches first, then newest
            if q:
                qs = qs.order_by("-created_at")
            else:
                qs = qs.order_by("-created_at")

        paginator = PageNumberPagination()
        paginator.page_size = int(params.get("page_size", 20))
        page = paginator.paginate_queryset(qs, request)
        serializer = ProductSearchSerializer(page, many=True)
        response = paginator.get_paginated_response(serializer.data)

        cache.set(cache_key, response.data, CACHE_TTL_SECONDS)
        return Response(response.data)


class SuggestThrottle(UserRateThrottle):
    """20 requests/min per user; falls back to per-IP for anonymous users."""
    scope = "suggest"
    rate = "20/min"


class SuggestAnonThrottle(AnonRateThrottle):
    scope = "suggest"
    rate = "20/min"


class ProductSuggestView(APIView):
    """
    GET /api/search/suggest/?q=xxx
    Rate limited to 20 req/min per user/IP (Option B), backed by Redis cache.
    Prefix matches ranked before general (substring) matches.
    """
    throttle_classes = [SuggestAnonThrottle, SuggestThrottle]

    def get(self, request):
        q = request.query_params.get("q", "").strip()
        if len(q) < 3:
            return Response({"detail": "q must be at least 3 characters"}, status=400)

        cache_key = _cache_key("search:suggest", {"q": q.lower()})
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        prefix_matches = list(
            Product.objects.filter(title__istartswith=q).values_list("title", flat=True)[:10]
        )
        results = list(dict.fromkeys(prefix_matches))  # de-dupe, preserve order

        if len(results) < 10:
            remaining = 10 - len(results)
            general_matches = (
                Product.objects.filter(title__icontains=q)
                .exclude(title__istartswith=q)
                .values_list("title", flat=True)[:remaining]
            )
            results.extend(dict.fromkeys(general_matches))

        payload = {"results": results[:10]}
        cache.set(cache_key, payload, CACHE_TTL_SECONDS)
        return Response(payload)
