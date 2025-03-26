from rest_framework import serializers
from .models import Inventory

class InventorySerializer(serializers.ModelSerializer):
    product = ProductSerializer()
    class Meta:
        model = Inventory
        fields = '__all__'