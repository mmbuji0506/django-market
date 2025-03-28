# Generated by Django 5.1.7 on 2025-03-26 13:16

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0001_initial'),
        ('products', '0002_remove_product_created_at_product_expiration_date_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='inventory',
            name='last_updated',
        ),
        migrations.AlterField(
            model_name='inventory',
            name='product',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='products.product'),
        ),
    ]
