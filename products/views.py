from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from rest_framework import viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from users.decorators import role_required
from .models import Product, Category
from .serializers import CategorySerializer, ProductSerializer
from inventory.models import Inventory

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer

@login_required
@role_required('cashier')
def product_list(request):
    products = Product.objects.all()
    return render(request, 'products/product_list.html', {'products': products})

@api_view(['GET'])
def get_product_by_barcode(request):
    ip = request.META.get('REMOTE_ADDR')
    cache_key = f"rate_limit_barcode_{ip}"
    request_count = cache.get(cache_key, 0)
    if request_count >= 10:
        return Response({'error': 'Too many requests'}, status=status.HTTP_429_TOO_MANY_REQUESTS)
    cache.set(cache_key, request_count + 1, 60)

    barcode = request.GET.get('barcode')
    try:
        product = Product.objects.get(barcode=barcode)
        inventory = Inventory.objects.get(product=product)
        data = {
            'name': product.name,
            'price': str(product.price),
            'stock': inventory.quantity,
        }
        return Response(data, status=status.HTTP_200_OK)
    except (Product.DoesNotExist, Inventory.DoesNotExist):
        return Response({'error': 'Product or inventory not found'}, status=status.HTTP_404_NOT_FOUND)