from inventory.models import Inventory

def inventory_items(request):
    if request.user.is_authenticated and request.user.userprofile.role in ['manager', 'admin']:
        return {'inventory_items': Inventory.objects.all()[:5]}
    return {'inventory_items': []}