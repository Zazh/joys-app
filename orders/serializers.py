from rest_framework import serializers


class CartItemSerializer(serializers.Serializer):
    size_id = serializers.IntegerField()
    qty = serializers.IntegerField()
    name = serializers.CharField()
    size_name = serializers.CharField()
    sku = serializers.CharField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    old_price = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2)
    image_url = serializers.CharField()
    product_url = serializers.CharField()
    payment_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    payment_subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)


class CartAddSerializer(serializers.Serializer):
    size_id = serializers.IntegerField()
    qty = serializers.IntegerField(default=1, min_value=1)


class CartUpdateSerializer(serializers.Serializer):
    size_id = serializers.IntegerField()
    qty = serializers.IntegerField(min_value=0)


class CartRemoveSerializer(serializers.Serializer):
    size_id = serializers.IntegerField()


class FavoriteItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.CharField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    old_price = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    image_url = serializers.CharField()
    product_url = serializers.CharField()
    first_size_id = serializers.IntegerField(allow_null=True)
    payment_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)


class FavoriteToggleSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()


class OrderItemSerializer(serializers.Serializer):
    product_name = serializers.CharField()
    size_name = serializers.CharField()
    quantity = serializers.IntegerField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2)


class OrderSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    number = serializers.CharField()
    status = serializers.CharField()
    status_display = serializers.SerializerMethodField()
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    display_amount = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    display_currency_code = serializers.CharField()
    currency_symbol = serializers.SerializerMethodField()
    city = serializers.CharField()
    address = serializers.CharField()
    customer_name = serializers.CharField()
    created_at = serializers.DateTimeField()
    items = OrderItemSerializer(many=True, source='items.all')

    def get_status_display(self, obj):
        return obj.get_status_display()

    def get_currency_symbol(self, obj):
        return obj.region.currency_symbol if obj.region else '₸'


class CheckoutSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    phone = serializers.CharField(max_length=30)
    email = serializers.EmailField(required=False, allow_blank=True)
    city = serializers.CharField(max_length=200)
    address = serializers.CharField(max_length=500)
