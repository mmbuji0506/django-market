from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from users.decorators import role_required
from .models import Sale, CartItem, CartAbandonment, UserActivity
from products.models import Product
from inventory.models import Inventory
from .forms import SaleForm, DateRangeForm, ActivityFilterForm
from django.db.models import Sum, Count, F
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.db.models.functions import TruncDay
from django.core.cache import cache
from django.http import HttpResponse
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from django.utils import timezone
from datetime import timedelta
import csv
import io

@login_required
@role_required('cashier')
def process_sale(request):
    if request.method == 'POST':
        form = SaleForm(request.POST)
        if form.is_valid():
            product = form.cleaned_data['barcode']
            quantity = form.cleaned_data['quantity']
            cart_item = CartItem.objects.create(user=request.user, product=product, quantity=quantity)
            UserActivity.objects.create(
                user=request.user,
                action='add',
                details=f"Added {quantity} x {product.name}"
            )
            messages.success(request, f"Added {quantity} {product.name}(s) to cart!")
            return redirect('process_sale')
    else:
        form = SaleForm()
    cart_items = CartItem.objects.filter(user=request.user)
    total = sum(item.product.price * item.quantity for item in cart_items)
    return render(request, 'sales/process_sale.html', {'form': form, 'cart_items': cart_items, 'total': total})

@login_required
@role_required('cashier')
def remove_cart_item(request, item_id):
    cart_item = CartItem.objects.filter(id=item_id, user=request.user).first()
    if cart_item:
        UserActivity.objects.create(
            user=request.user,
            action='remove',
            details=f"Removed {cart_item.quantity} x {cart_item.product.name}"
        )
        CartAbandonment.objects.create(
            user=request.user,
            product=cart_item.product,
            quantity=cart_item.quantity,
            added_at=cart_item.added_at
        )
        cart_item.delete()
        messages.success(request, f"Removed {cart_item.product.name} from cart!")
    else:
        messages.error(request, "Item not found in your cart.")
    return redirect('process_sale')

@login_required
@role_required('cashier')
def edit_cart_item(request, item_id):
    cart_item = CartItem.objects.filter(id=item_id, user=request.user).first()
    if not cart_item:
        messages.error(request, "Item not found in your cart.")
        return redirect('process_sale')

    if request.method == 'POST':
        quantity = request.POST.get('quantity', '').strip()
        try:
            quantity = int(quantity)
            old_quantity = cart_item.quantity
            if quantity <= 0:
                UserActivity.objects.create(
                    user=request.user,
                    action='remove',
                    details=f"Removed {old_quantity} x {cart_item.product.name} (set to 0)"
                )
                CartAbandonment.objects.create(
                    user=request.user,
                    product=cart_item.product,
                    quantity=old_quantity,
                    added_at=cart_item.added_at
                )
                cart_item.delete()
                messages.success(request, f"Removed {cart_item.product.name} from cart!")
            else:
                cart_item.quantity = quantity
                cart_item.save()
                UserActivity.objects.create(
                    user=request.user,
                    action='edit',
                    details=f"Changed {cart_item.product.name} from {old_quantity} to {quantity}"
                )
                messages.success(request, f"Updated {cart_item.product.name} to {quantity}!")
        except ValueError:
            messages.error(request, "Invalid quantity.")
        return redirect('process_sale')

    return render(request, 'sales/edit_cart_item.html', {'cart_item': cart_item})

@login_required
@role_required('cashier')
def clear_cart(request):
    cart_items = CartItem.objects.filter(user=request.user)
    if cart_items:
        for item in cart_items:
            CartAbandonment.objects.create(
                user=request.user,
                product=item.product,
                quantity=item.quantity,
                added_at=item.added_at
            )
        UserActivity.objects.create(
            user=request.user,
            action='clear',
            details=f"Cleared cart with {cart_items.count()} items"
        )
        cart_items.delete()
        messages.success(request, "Cart cleared!")
    else:
        messages.info(request, "Cart was already empty.")
    return redirect('process_sale')

@login_required
@role_required('cashier')
def finalize_sale(request):
    cart_items = CartItem.objects.filter(user=request.user)
    if not cart_items:
        messages.error(request, "Cart is empty!")
        return redirect('process_sale')

    try:
        sales = []
        for item in cart_items:
            sale = Sale(user=request.user, product=item.product, quantity=item.quantity)
            sale.save()
            sales.append(sale)
        UserActivity.objects.create(
            user=request.user,
            action='finalize',
            details=f"Finalized sale with {cart_items.count()} items"
        )
        cart_items.delete()
        messages.success(request, "Sale completed successfully!")
        return redirect('print_receipt', sale_ids=','.join(str(sale.id) for sale in sales))
    except ValueError as e:
        messages.error(request, str(e))
        return redirect('process_sale')
    
@login_required
@role_required('cashier')
def print_receipt(request, sale_ids):
    sale_ids = [int(id) for id in sale_ids.split(',')]
    sales = Sale.objects.filter(id__in=sale_ids, user=request.user)
    total = sum(sale.total_price for sale in sales)
    return render(request, 'sales/receipt.html', {'sales': sales, 'total': total})

@login_required
@role_required('manager', 'admin')
def dashboard(request):
    form = DateRangeForm(request.GET or None)
    sales_queryset = Sale.objects.all()
    abandonment_queryset = CartAbandonment.objects.all()

    cache_key = 'dashboard_data'
    if form.is_valid():
        start_date = form.cleaned_data['start_date']
        end_date = form.cleaned_data['end_date']
        cache_key += f'_{start_date}_{end_date}' if start_date and end_date else ''
        if start_date:
            sales_queryset = sales_queryset.filter(sale_date__gte=start_date)
            abandonment_queryset = abandonment_queryset.filter(abandoned_at__gte=start_date)
        if end_date:
            sales_queryset = sales_queryset.filter(sale_date__lte=end_date)
            abandonment_queryset = abandonment_queryset.filter(abandoned_at__lte=end_date)

    cached_data = cache.get(cache_key)
    if cached_data:
        total_sales, top_products, sales_over_time, abandonment_over_time = cached_data
    else:
        total_sales = sales_queryset.aggregate(total=Sum('total_price'))['total'] or 0
        top_products = sales_queryset.values('product__name').annotate(
            total_quantity=Sum('quantity')
        ).order_by('-total_quantity')[:5]
        sales_over_time = sales_queryset.annotate(
            day=TruncDay('sale_date')
        ).values('day').annotate(
            daily_total=Sum('total_price')
        ).order_by('day')
        abandonment_over_time = abandonment_queryset.annotate(
            day=TruncDay('abandoned_at')
        ).values('day').annotate(
            total_abandoned=Sum('quantity')
        ).order_by('day')
        cache.set(cache_key, (total_sales, top_products, sales_over_time, abandonment_over_time), 60 * 5)

    low_stock = Inventory.objects.filter(quantity__lte=F('low_stock_threshold'))
    abandonment = abandonment_queryset.order_by('-abandoned_at')[:5]
    activity = UserActivity.objects.order_by('-timestamp')[:5]

    context = {
        'form': form,
        'total_sales': total_sales,
        'top_products': top_products,
        'low_stock': low_stock,
        'sales_over_time': sales_over_time,
        'abandonment': abandonment,
        'activity': activity,
        'abandonment_over_time': abandonment_over_time,
    }
    return render(request, 'sales/dashboard.html', context)


@login_required
@role_required('manager', 'admin')
def activity_log(request):
    form = ActivityFilterForm(request.GET or None)
    activity_queryset = UserActivity.objects.order_by('-timestamp')

    if form.is_valid():
        user = form.cleaned_data['user']
        start_date = form.cleaned_data['start_date']
        end_date = form.cleaned_data['end_date']
        if user:
            activity_queryset = activity_queryset.filter(user=user)
        if start_date:
            activity_queryset = activity_queryset.filter(timestamp__gte=start_date)
        if end_date:
            activity_queryset = activity_queryset.filter(timestamp__lte=end_date)

    context = {
        'form': form,
        'activity': activity_queryset,
    }
    return render(request, 'sales/activity_log.html', context)

@login_required
@role_required('manager', 'admin')
def export_sales_csv(request):
    form = DateRangeForm(request.GET or None)
    sales_queryset = Sale.objects.all()
    if form.is_valid():
        start_date = form.cleaned_data['start_date']
        end_date = form.cleaned_data['end_date']
        if start_date:
            sales_queryset = sales_queryset.filter(sale_date__gte=start_date)
        if end_date:
            sales_queryset = sales_queryset.filter(sale_date__lte=end_date)

    total_sales = sales_queryset.aggregate(total=Sum('total_price'))['total'] or 0
    top_products = sales_queryset.values('product__name').annotate(total_quantity=Sum('quantity')).order_by('-total_quantity')[:5]
    sales_over_time = sales_queryset.annotate(day=TruncDay('sale_date')).values('day').annotate(daily_total=Sum('total_price')).order_by('day')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="sales_report.csv"'
    writer = csv.writer(response)
    writer.writerow(['Sales Report'])
    writer.writerow(['Total Sales', f"${total_sales:.2f}"])
    writer.writerow([])
    writer.writerow(['Top 5 Products'])
    writer.writerow(['Product', 'Quantity Sold'])
    for product in top_products:
        writer.writerow([product['product__name'], product['total_quantity']])
    writer.writerow([])
    writer.writerow(['Sales Over Time'])
    writer.writerow(['Date', 'Daily Total'])
    for sale in sales_over_time:
        writer.writerow([sale['day'].strftime('%Y-%m-%d'), f"${sale['daily_total']:.2f}"])
    return response

@login_required
@role_required('manager', 'admin')
def export_sales_pdf(request):
    form = DateRangeForm(request.GET or None)
    sales_queryset = Sale.objects.all()
    if form.is_valid():
        start_date = form.cleaned_data['start_date']
        end_date = form.cleaned_data['end_date']
        if start_date:
            sales_queryset = sales_queryset.filter(sale_date__gte=start_date)
        if end_date:
            sales_queryset = sales_queryset.filter(sale_date__lte=end_date)

    total_sales = sales_queryset.aggregate(total=Sum('total_price'))['total'] or 0
    top_products = sales_queryset.values('product__name').annotate(total_quantity=Sum('quantity')).order_by('-total_quantity')[:5]
    sales_over_time = sales_queryset.annotate(day=TruncDay('sale_date')).values('day').annotate(daily_total=Sum('total_price')).order_by('day')

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="sales_report.pdf"'
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.drawString(100, 750, "Sales Report")
    p.drawString(100, 730, f"Total Sales: ${total_sales:.2f}")
    p.drawString(100, 700, "Top 5 Products")
    y = 680
    for product in top_products:
        p.drawString(100, y, f"{product['product__name']}: {product['total_quantity']} sold")
        y -= 20
    p.drawString(100, y - 20, "Sales Over Time")
    y -= 40
    for sale in sales_over_time:
        p.drawString(100, y, f"{sale['day'].strftime('%Y-%m-%d')}: ${sale['daily_total']:.2f}")
        y -= 20
    p.showPage()
    p.save()
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)
    return response


@login_required
@role_required('manager', 'admin')
def export_abandonment_csv(request):
    form = DateRangeForm(request.GET or None)
    abandonment_queryset = CartAbandonment.objects.all()
    if form.is_valid():
        start_date = form.cleaned_data['start_date']
        end_date = form.cleaned_data['end_date']
        if start_date:
            abandonment_queryset = abandonment_queryset.filter(abandoned_at__gte=start_date)
        if end_date:
            abandonment_queryset = abandonment_queryset.filter(abandoned_at__lte=end_date)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="abandonment_report.csv"'
    writer = csv.writer(response)
    writer.writerow(['Cart Abandonment Report'])
    writer.writerow(['User', 'Product', 'Quantity', 'Added At', 'Abandoned At'])
    for item in abandonment_queryset:
        writer.writerow([
            item.user.username,
            item.product.name,
            item.quantity,
            item.added_at.strftime('%Y-%m-%d %H:%M'),
            item.abandoned_at.strftime('%Y-%m-%d %H:%M')
        ])
    return response

@login_required
@role_required('manager', 'admin')
def export_abandonment_pdf(request):
    form = DateRangeForm(request.GET or None)
    abandonment_queryset = CartAbandonment.objects.all()
    if form.is_valid():
        start_date = form.cleaned_data['start_date']
        end_date = form.cleaned_data['end_date']
        if start_date:
            abandonment_queryset = abandonment_queryset.filter(abandoned_at__gte=start_date)
        if end_date:
            abandonment_queryset = abandonment_queryset.filter(abandoned_at__lte=end_date)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="abandonment_report.pdf"'
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.drawString(100, 750, "Cart Abandonment Report")
    y = 730
    for item in abandonment_queryset:
        p.drawString(100, y, f"{item.user.username} - {item.product.name}: {item.quantity} (Added: {item.added_at.strftime('%Y-%m-%d %H:%M')}, Abandoned: {item.abandoned_at.strftime('%Y-%m-%d %H:%M')})")
        y -= 20
        if y < 50:  # New page if needed
            p.showPage()
            y = 750
    p.showPage()
    p.save()
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)
    return response

@login_required
@role_required('manager', 'admin')
def export_activity_csv(request):
    form = ActivityFilterForm(request.GET or None)
    activity_queryset = UserActivity.objects.order_by('-timestamp')
    if form.is_valid():
        user = form.cleaned_data['user']
        start_date = form.cleaned_data['start_date']
        end_date = form.cleaned_data['end_date']
        if user:
            activity_queryset = activity_queryset.filter(user=user)
        if start_date:
            activity_queryset = activity_queryset.filter(timestamp__gte=start_date)
        if end_date:
            activity_queryset = activity_queryset.filter(timestamp__lte=end_date)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="activity_report.csv"'
    writer = csv.writer(response)
    writer.writerow(['User Activity Report'])
    writer.writerow(['User', 'Action', 'Details', 'Timestamp'])
    for action in activity_queryset:
        writer.writerow([
            action.user.username,
            action.get_action_display(),
            action.details,
            action.timestamp.strftime('%Y-%m-%d %H:%M')
        ])
    return response


@login_required
@role_required('manager', 'admin')
def export_activity_pdf(request):
    form = ActivityFilterForm(request.GET or None)
    activity_queryset = UserActivity.objects.order_by('-timestamp')
    if form.is_valid():
        user = form.cleaned_data['user']
        start_date = form.cleaned_data['start_date']
        end_date = form.cleaned_data['end_date']
        if user:
            activity_queryset = activity_queryset.filter(user=user)
        if start_date:
            activity_queryset = activity_queryset.filter(timestamp__gte=start_date)
        if end_date:
            activity_queryset = activity_queryset.filter(timestamp__lte=end_date)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="activity_report.pdf"'
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.drawString(100, 750, "User Activity Report")
    y = 730
    for action in activity_queryset:
        p.drawString(100, y, f"{action.user.username} - {action.get_action_display()}: {action.details} ({action.timestamp.strftime('%Y-%m-%d %H:%M')})")
        y -= 20
        if y < 50:  # New page if needed
            p.showPage()
            y = 750
    p.showPage()
    p.save()
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)
    return response

@login_required
@role_required('manager', 'admin')
def notifications(request):
    # Sales notifications (e.g., recent high-value sales)
    recent_sales = Sale.objects.filter(sale_date__gte=timezone.now() - timedelta(hours=24)).order_by('-total_price')[:5]
    
    # Near-expiration notifications (within 7 days)
    near_expiration = Product.objects.filter(
        expiration_date__lte=timezone.now().date() + timedelta(days=7),
        expiration_date__gte=timezone.now().date()
    )
    
    # Near-end-of-stock notifications
    near_end_of_stock = Inventory.objects.filter(quantity__lte=F('low_stock_threshold'))

    context = {
        'recent_sales': recent_sales,
        'near_expiration': near_expiration,
        'near_end_of_stock': near_end_of_stock,
    }
    return render(request, 'sales/notifications.html', context)

@api_view(['GET'])
def get_total_sales(request):
    ip = request.META.get('REMOTE_ADDR')
    cache_key = f"rate_limit_total_sales_{ip}"
    request_count = cache.get(cache_key, 0)
    if request_count >= 20:
        return Response({'error': 'Too many requests'}, status=status.HTTP_429_TOO_MANY_REQUESTS)
    cache.set(cache_key, request_count + 1, 60)

    total_sales = cache.get('total_sales')
    if total_sales is None:
        total_sales = Sale.objects.aggregate(total=Sum('total_price'))['total'] or 0
        cache.set('total_sales', total_sales, 60 * 5)
    return Response({'total_sales': total_sales}, status=status.HTTP_200_OK)