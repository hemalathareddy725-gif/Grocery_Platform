from django.db import transaction
from django.db.models import Count, F
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework import status

from apps.stores.models import Store, Inventory
from apps.products.models import Product
from .models import Order, OrderItem
from .serializers import OrderCreateSerializer, OrderDetailSerializer, OrderListSerializer
from .tasks import send_order_confirmation


class OrderCreateView(APIView):
    """
    POST /orders/
    Body: {"store_id": 1, "items": [{"product_id": 1, "quantity_requested": 2}, ...]}

    All-or-nothing stock check + deduction wrapped in transaction.atomic().
    """

    def post(self, request):
        input_serializer = OrderCreateSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        data = input_serializer.validated_data

        store = get_object_or_404(Store, pk=data["store_id"])

        with transaction.atomic():
            order = Order.objects.create(store=store, status=Order.PENDING)

            product_ids = [item["product_id"] for item in data["items"]]
            # select_for_update to prevent race conditions on concurrent orders
            inventory_qs = (
                Inventory.objects.select_for_update()
                .filter(store=store, product_id__in=product_ids)
            )
            inventory_by_product = {inv.product_id: inv for inv in inventory_qs}

            items_to_create = []
            sufficient_stock = True

            for item in data["items"]:
                pid = item["product_id"]
                qty = item["quantity_requested"]
                inv = inventory_by_product.get(pid)
                if inv is None or inv.quantity < qty:
                    sufficient_stock = False
                items_to_create.append(OrderItem(order=order, product_id=pid, quantity_requested=qty))

            OrderItem.objects.bulk_create(items_to_create)

            if sufficient_stock:
                for item in data["items"]:
                    inv = inventory_by_product[item["product_id"]]
                    inv.quantity = F("quantity") - item["quantity_requested"]
                    inv.save(update_fields=["quantity"])
                order.status = Order.CONFIRMED
            else:
                order.status = Order.REJECTED
            order.save(update_fields=["status"])

        if order.status == Order.CONFIRMED:
            send_order_confirmation.delay(order.id)

        order.refresh_from_db()
        serializer = OrderDetailSerializer(order)
        http_status = status.HTTP_201_CREATED if order.status == Order.CONFIRMED else status.HTTP_200_OK
        return Response(serializer.data, status=http_status)


class StoreOrderListView(ListAPIView):
    """
    GET /stores/<store_id>/orders/
    Newest first, with item counts annotated to avoid N+1 queries.
    """
    serializer_class = OrderListSerializer

    def get_queryset(self):
        store_id = self.kwargs["store_id"]
        return (
            Order.objects.filter(store_id=store_id)
            .annotate(item_count=Count("items"))
            .order_by("-created_at")
        )
