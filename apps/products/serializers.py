from rest_framework import serializers
from .models import Product


class ProductSearchSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    store_quantity = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = Product
        fields = ["id", "title", "description", "price", "category_name", "created_at", "store_quantity"]
