from decimal import Decimal

from django.core.exceptions import ValidationError as ModelValidationError
from django.db import transaction
from django.middleware.csrf import get_token
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from apps.accounts.permissions import SALES_CREATE, require
from rest_framework.response import Response

from apps.inventory.models import Medicine
from .models import CheckoutRecord, Customer, Payment, Sale, SaleLine
from .services import complete_sale


class CartItem(serializers.Serializer):
    agreed_price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False)
    medicine = serializers.IntegerField(min_value=1)
    package = serializers.ChoiceField(choices=SaleLine.Package.choices)
    quantity = serializers.IntegerField(min_value=1, max_value=2147483647)
    discount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    expected_price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    expected_units = serializers.IntegerField(min_value=1)


class Checkout(serializers.Serializer):
    key = serializers.UUIDField()
    lines = CartItem(many=True, allow_empty=False, max_length=100)
    customer = serializers.IntegerField(min_value=1, allow_null=True)
    paid = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)


def check_cashier(user):
    if not user.organization.is_active or user.organization.base_currency != "AFN":
        raise PermissionDenied("Checkout requires an active AFN pharmacy.")


@api_view(["GET"])
@permission_classes([require(SALES_CREATE)])
def checkout_options(request):
    check_cashier(request.user)
    customers = Customer.objects.for_organization(request.user.organization).values("id", "name", "phone", "is_business")
    return Response({"csrf": get_token(request), "customers": list(customers)})


@transaction.atomic
def submit_checkout(user, data, snapshot):
    record, created = CheckoutRecord.objects.get_or_create(
        key=data["key"], defaults={"cashier": user, "organization": user.organization, "request_data": snapshot}
    )
    if not created:
        if record.organization_id != user.organization_id or record.cashier_id != user.pk or record.request_data != snapshot:
            raise serializers.ValidationError("This checkout reference has already been used.")
        return record.receipt, 200

    customer = None
    if data["customer"] is not None:
        customer = Customer.objects.for_organization(user.organization).filter(pk=data["customer"]).first()
        if customer is None:
            raise serializers.ValidationError("Choose an existing customer.")

    medicine_ids = {item["medicine"] for item in data["lines"]}
    medicines = {
        med.pk: med for med in Medicine.objects.select_for_update()
        .filter(organization=user.organization, pk__in=medicine_ids, is_active=True).order_by("pk")
    }
    sale = Sale.objects.create(organization=user.organization, cashier=user, customer=customer)
    receipt_lines = []
    total = Decimal("0.00")
    for item in data["lines"]:
        medicine = medicines.get(item["medicine"])
        if medicine is None:
            raise serializers.ValidationError("An item in the cart is no longer available.")
        box = item["package"] == SaleLine.Package.BOX
        price = medicine.box_sale_price if box else medicine.unit_sale_price
        size = medicine.units_per_box if box else 1
        if price != item["expected_price"] or size != item["expected_units"]:
            raise serializers.ValidationError(f"{medicine.sku}: package changed. Refresh the catalog.")
        if "agreed_price" in item:
            if not box or customer is None or not customer.is_business:
                raise serializers.ValidationError("Choose a business customer for wholesale box pricing.")
            price = item["agreed_price"]
        line = SaleLine(
            sale=sale, medicine=medicine, quantity=item["quantity"], package=item["package"],
            discount=item["discount"], price_per_package=price, units_per_package=size,
        )
        if line.line_total < 0:
            raise serializers.ValidationError(f"{medicine.sku}: discount exceeds the line price.")
        line.save()
        total += line.line_total
        receipt_lines.append({
            "name": str(medicine), "sku": medicine.sku,
            "package": "box" if box else medicine.stock_unit or "unit",
            "quantity": line.quantity, "price": f"{price:.2f}",
            "discount": f"{line.discount:.2f}", "total": f"{line.line_total:.2f}",
        })

    paid = data["paid"]
    if paid > total:
        raise serializers.ValidationError("Payment exceeds the sale total.")
    if paid < total and customer is None:
        raise serializers.ValidationError("Choose a customer for an unpaid balance.")
    complete_sale(sale.pk)
    if paid:
        Payment.objects.create(sale=sale, amount=paid, received_by=user)
    sale.refresh_from_db(fields=["completed_at"])
    record.receipt = {
        "date": sale.completed_at.isoformat(), "shop": user.organization.name, "cashier": user.get_username(),
        "wholesale": any("agreed_price" in item for item in data["lines"]),
        "sale": sale.pk, "lines": receipt_lines, "total": f"{total:.2f}",
        "paid": f"{paid:.2f}", "balance": f"{total - paid:.2f}",
        "customer": str(customer) if customer else "Walk-in",
    }
    record.save(update_fields=["receipt"])
    return record.receipt, 201


@api_view(["POST"])
@permission_classes([require(SALES_CREATE)])
def checkout(request):
    check_cashier(request.user)
    form = Checkout(data=request.data)
    form.is_valid(raise_exception=True)
    try:
        receipt, status = submit_checkout(request.user, form.validated_data, form.data)
    except ModelValidationError as error:
        raise serializers.ValidationError(error.messages) from error
    return Response(receipt, status=status)
