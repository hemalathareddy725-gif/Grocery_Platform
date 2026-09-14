from rest_framework import serializers
from .models import Order, OrderItem


class OrderItemInputSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity_requested = serializers.IntegerField(min_value=1)


class OrderCreateSerializer(serializers.Serializer):
    store_id = serializers.IntegerField()
    items = OrderItemInputSerializer(many=True)


class OrderItemOutputSerializer(serializers.ModelSerializer):
    product_title = serializers.CharField(source="product.title")

    class Meta:
        model = OrderItem
        fields = ["product_id", "product_title", "quantity_requested"]


class OrderDetailSerializer(serializers.ModelSerializer):
    items = OrderItemOutputSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ["id", "store_id", "status", "created_at", "items"]


class OrderListSerializer(serializers.ModelSerializer):
    """Uses an annotated `item_count` to avoid N+1 (see view)."""
    item_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Order
        fields = ["id", "status", "created_at", "item_count"]
