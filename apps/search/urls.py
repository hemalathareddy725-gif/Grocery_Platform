from django.urls import path
from .views import ProductSearchView, ProductSuggestView

urlpatterns = [
    path("products/", ProductSearchView.as_view(), name="product-search"),
    path("suggest/", ProductSuggestView.as_view(), name="product-suggest"),
]
