from django import forms
from .models import Inventory
from products.models import Product

class InventoryUpdateForm(forms.ModelForm):
    barcode = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Scan barcode to verify'})
    )

    class Meta:
        model = Inventory
        fields = ['quantity', 'low_stock_threshold']
        widgets = {
            'quantity': forms.NumberInput(attrs={'min': 0, 'class': 'form-control'}),
            'low_stock_threshold': forms.NumberInput(attrs={'min': 1, 'class': 'form-control'}),
        }

    def clean_barcode(self):
        barcode = self.cleaned_data.get('barcode')
        if barcode:
            try:
                product = Product.objects.get(barcode=barcode)
                return product
            except Product.DoesNotExist:
                raise forms.ValidationError("Invalid barcode.")
        return None