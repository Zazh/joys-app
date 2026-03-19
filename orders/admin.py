from django.contrib import admin

from .models import Order, OrderItem, EmailLog


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('size', 'product_name', 'size_name', 'quantity', 'price', 'subtotal_display')
    fields = ('product_name', 'size_name', 'quantity', 'price', 'subtotal_display')

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description='Итого')
    def subtotal_display(self, obj):
        return obj.subtotal


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('number', 'status', 'customer_name', 'region', 'total_amount', 'created_at', 'expires_at')
    list_filter = ('status', 'region')
    search_fields = ('number', 'customer_name', 'customer_phone', 'customer_email')
    list_select_related = ('region',)
    readonly_fields = ('number', 'created_at', 'paid_at')
    inlines = [OrderItemInline]
    list_per_page = 50
    fieldsets = (
        (None, {
            'fields': ('number', 'status', 'region'),
        }),
        ('Покупатель', {
            'fields': ('customer_name', 'customer_phone', 'customer_email'),
        }),
        ('Доставка', {
            'fields': ('city', 'address'),
        }),
        ('Оплата', {
            'fields': ('payment_id', 'payment_url', 'total_amount'),
        }),
        ('Даты', {
            'fields': ('expires_at', 'created_at', 'paid_at'),
        }),
    )


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ('template_slug', 'to_email', 'status', 'attempts', 'created_at', 'sent_at')
    list_filter = ('status', 'template_slug')
    search_fields = ('to_email', 'subject')
    readonly_fields = (
        'to_email', 'template_slug', 'subject', 'body',
        'status', 'attempts', 'next_retry_at', 'error',
        'created_at', 'sent_at',
    )
    list_per_page = 50

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return True
