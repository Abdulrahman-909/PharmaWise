from decimal import Decimal

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.accounts.permissions import CUSTOMERS_MANAGE, PURCHASING_MANAGE, SALES_CREATE, require
from apps.inventory.models import Medicine, PurchaseReceipt, PurchaseReceiptLine, StockBatch, Supplier
from .checkout import check_cashier
from .history import completed, with_balances
from .models import Customer, Payment


class Repayment(serializers.Serializer):
    key = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))


@api_view(["POST"])
@permission_classes([require(SALES_CREATE)])
@transaction.atomic
def repay(request, pk):
    check_cashier(request.user)
    form = Repayment(data=request.data)
    form.is_valid(raise_exception=True)
    data = form.validated_data
    sale = get_object_or_404(completed(request.user).select_for_update(), pk=pk, customer__isnull=False)
    existing = Payment.objects.filter(repayment_key=data["key"]).first()
    if existing:
        if (existing.sale_id, existing.received_by_id, existing.amount) != (sale.pk, request.user.pk, data["amount"]):
            raise serializers.ValidationError("Payment reference already used.")
        payment = existing
    else:
        balance = with_balances(completed(request.user)).get(pk=pk).outstanding
        if data["amount"] > balance:
            raise serializers.ValidationError(f"Outstanding balance is {balance:.2f} AFN.")
        payment = Payment.objects.create(sale=sale, received_by=request.user, amount=data["amount"],
                                         repayment_key=data["key"], balance_after=balance-data["amount"])
    return Response({"id": payment.pk, "sale": pk, "name": str(sale.customer), "date": payment.received_at,
                     "shop": request.user.organization.name, "amount": f"{payment.amount:.2f}",
                     "balance": f"{payment.balance_after:.2f}"})


class Business(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=30)


@api_view(["POST"])
@permission_classes([require(CUSTOMERS_MANAGE)])
def business(request):
    form = Business(data=request.data)
    form.is_valid(raise_exception=True)
    account, _ = Customer.objects.get_or_create(organization=request.user.organization, is_business=True, **form.validated_data)
    return Response({"id": account.pk, "name": account.name, "phone": account.phone, "is_business": True})


class DeliveryItem(serializers.Serializer):
    medicine = serializers.IntegerField(min_value=1)
    batch = serializers.CharField(max_length=80)
    expiry = serializers.DateField()
    boxes = serializers.IntegerField(min_value=1, max_value=2147483647)
    units = serializers.IntegerField(min_value=1, max_value=2147483647)
    price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)


class Delivery(serializers.Serializer):
    supplier = serializers.IntegerField(min_value=1)
    invoice = serializers.CharField(max_length=80)
    date = serializers.DateField()
    lines = DeliveryItem(many=True, allow_empty=False, max_length=100)


@api_view(["GET", "POST"])
@permission_classes([require(PURCHASING_MANAGE)])
@transaction.atomic
def deliveries(request):
    org = request.user.organization
    suppliers = Supplier.objects.for_organization(org).filter(is_active=True)
    if request.method == "GET":
        return Response(list(suppliers.values("id", "name")))
    form = Delivery(data=request.data)
    form.is_valid(raise_exception=True)
    data = form.validated_data
    supplier = get_object_or_404(suppliers.select_for_update(), pk=data["supplier"])
    if PurchaseReceipt.objects.filter(supplier=supplier, invoice_number=data["invoice"]).exists():
        raise serializers.ValidationError("This supplier invoice already exists.")
    receipt = PurchaseReceipt.objects.create(organization=org, supplier=supplier, invoice_number=data["invoice"], received_on=data["date"])
    ids = {item["medicine"] for item in data["lines"]}
    medicines = {m.pk: m for m in Medicine.objects.for_organization(org).select_for_update().filter(pk__in=ids).order_by("pk")}
    if len(medicines) != len(ids):
        raise serializers.ValidationError("Choose a medicine from this pharmacy.")
    units_received = 0
    for item in data["lines"]:
        batch, _ = StockBatch.objects.select_for_update().get_or_create(
            organization=org, medicine=medicines[item["medicine"]], batch_number=item["batch"], defaults={"expiry_date": item["expiry"]})
        if batch.expiry_date != item["expiry"]:
            raise serializers.ValidationError("Expiry differs from the saved batch.")
        quantity = item["boxes"] * item["units"]
        if quantity + batch.quantity_on_hand > 2147483647:
            raise serializers.ValidationError("Batch quantity is too large.")
        PurchaseReceiptLine.objects.create(receipt=receipt, batch=batch, boxes_received=item["boxes"], units_per_box=item["units"],
                                           purchase_price_per_box=item["price"], remaining_cost_units=quantity)
        batch.quantity_on_hand += quantity
        batch.save(update_fields=["quantity_on_hand"])
        units_received += quantity
    receipt.posted_at = timezone.now()
    receipt.save(update_fields=["posted_at"])
    return Response({"invoice": receipt.invoice_number, "units": units_received}, status=201)
