from django.contrib import admin
from django.urls import path, include
from .views import home, permission_denied
from rest_framework.routers import DefaultRouter
from products.views import CategoryViewSet, ProductViewSet, product_list, get_product_by_barcode
from inventory.views import inventory_list, update_inventory
from sales.views import process_sale, dashboard, get_total_sales, clear_cart,product_autocomplete,notifications,export_activity_pdf,export_abandonment_csv,export_abandonment_pdf,export_activity_csv, finalize_sale, remove_cart_item, edit_cart_item,print_receipt,export_sales_pdf,export_sales_csv, activity_log
from users.views import user_list, user_edit
from django.conf.urls import handler403
from django.contrib.auth.views import LogoutView

router = DefaultRouter()
router.register(r'categories', CategoryViewSet)
router.register(r'products', ProductViewSet)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('api/product-by-barcode/', get_product_by_barcode, name='get_product_by_barcode'),
    path('api/total-sales/', get_total_sales, name='get_total_sales'),
    path('products/', product_list, name='product_list'),
    path('', home, name='home'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('accounts/logout/', LogoutView.as_view(next_page='/accounts/login/'), name='logout'),
    path('inventory/', inventory_list, name='inventory_list'),
    path('inventory/update/<int:inventory_id>/', update_inventory, name='update_inventory'),
    path('sales/', process_sale, name='process_sale'),
    path('sales/clear/', clear_cart, name='clear_cart'),
    path('sales/finalize/', finalize_sale, name='finalize_sale'),
    path('sales/remove/<int:item_id>/', remove_cart_item, name='remove_cart_item'),
    path('sales/edit/<int:item_id>/', edit_cart_item, name='edit_cart_item'),
    path('dashboard/', dashboard, name='dashboard'),
    path('users/', user_list, name='user_list'),
    path('users/edit/<int:user_id>/', user_edit, name='user_edit'),
    path('sales/receipt/<str:sale_ids>/', print_receipt, name='print_receipt'),
    path('dashboard/export/csv/', export_sales_csv, name='export_sales_csv'),
    path('dashboard/export/pdf/', export_sales_pdf, name='export_sales_pdf'),
    path('dashboard/activity/', activity_log, name='activity_log'),
    path('dashboard/export/abandonment/csv/', export_abandonment_csv, name='export_abandonment_csv'),
    path('dashboard/export/abandonment/pdf/', export_abandonment_pdf, name='export_abandonment_pdf'),
    path('dashboard/export/activity/csv/', export_activity_csv, name='export_activity_csv'),
    path('dashboard/export/activity/pdf/', export_activity_pdf, name='export_activity_pdf'),
    path('dashboard/notifications/', notifications, name='notifications'),
    path('api/product-autocomplete/', product_autocomplete, name='product_autocomplete'),
]

handler403 = 'supermarket_management.views.permission_denied'