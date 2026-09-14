from rest_framework.generics import ListAPIView
from .models import Inventory
from .serializers import InventoryListSerializer


class StoreInventoryListView(ListAPIView):
    """
    GET /stores/<store_id>/inventory/
    Sorted alphabetically by product title. select_related avoids N+1 queries.
    """
    serializer_class = InventoryListSerializer

    def get_queryset(self):
        store_id = self.kwargs["store_id"]
        return (
            Inventory.objects.filter(store_id=store_id)
            .select_related("product", "product__category")
            .order_by("product__title")
        )
