from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from users.decorators import role_required
from .models import Inventory
from .forms import InventoryUpdateForm

@login_required
@role_required('manager', 'admin')
def inventory_list(request):
    inventory_items = Inventory.objects.all()
    return render(request, 'inventory/inventory_list.html', {'inventory_items': inventory_items})

@login_required
@role_required('manager', 'admin')
def update_inventory(request, inventory_id):
    inventory = get_object_or_404(Inventory, id=inventory_id)
    if request.method == 'POST':
        form = InventoryUpdateForm(request.POST, instance=inventory)
        if form.is_valid():
            barcode_product = form.cleaned_data['barcode']
            if barcode_product and barcode_product != inventory.product:
                return render(request, 'inventory/update_inventory.html', {
                    'form': form,
                    'inventory': inventory,
                    'error': "Barcode does not match this product."
                })
            form.save()
            return redirect('inventory_list')
    else:
        form = InventoryUpdateForm(instance=inventory)
    return render(request, 'inventory/update_inventory.html', {'form': form, 'inventory': inventory})