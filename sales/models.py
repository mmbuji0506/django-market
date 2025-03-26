from django.db import models
from django.contrib.auth.models import User
from products.models import Product
from inventory.models import Inventory

class Sale(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    sale_date = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.total_price = self.product.price * self.quantity
        inventory = Inventory.objects.get(product=self.product)
        if inventory.quantity >= self.quantity:
            inventory.quantity -= self.quantity
            inventory.save()
        else:
            raise ValueError("Not enough stock available.")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Sale {self.id} - {self.product.name}"

class CartItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.quantity} x {self.product.name} (Cart)"

class CartAbandonment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    added_at = models.DateTimeField()
    abandoned_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Abandoned: {self.quantity} x {self.product.name} by {self.user.username}"

class UserActivity(models.Model):
    ACTION_CHOICES = (
        ('add', 'Add to Cart'),
        ('edit', 'Edit Cart Item'),
        ('remove', 'Remove from Cart'),
        ('finalize', 'Finalize Sale'),
        ('clear', 'Clear Cart'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.TextField(blank=True)  # E.g., "Added 2 x Product X"

    def __str__(self):
        return f"{self.user.username} - {self.get_action_display()} at {self.timestamp}"