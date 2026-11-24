from django.db.models import Min, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from datetime import timedelta

from .models import Medicine, StockBatch


@api_view(["GET"])
@permission_classes([IsAdminUser])
def medicine_list(request):
    today = timezone.localdate()

    medicines = Medicine.objects.annotate(
        stock_on_hand=Sum("batches__quantity_on_hand", default=0),
        expired_units=Sum(
            "batches__quantity_on_hand",
            filter=Q(batches__expiry_date__lt=today),
            default=0,
        ),
        earliest_expiry=Min(
            "batches__expiry_date",
            filter=Q(batches__quantity_on_hand__gt=0),
        ),
    ).values(
        "id",
        "sku",
        "generic_name",
        "brand_name",
        "strength",
        "dosage_form",
        "stock_unit",
        "units_per_box",
        "unit_sale_price",
        "box_sale_price",
        "is_active",
        "stock_on_hand",
        "expired_units",
        "reorder_level",
        "earliest_expiry",
    )

    return Response(list(medicines))


@api_view(["GET"])
@permission_classes([IsAdminUser])
def medicine_batches(request, medicine_id):
    medicine = get_object_or_404(Medicine, pk=medicine_id)

    batches = medicine.batches.order_by("expiry_date", "batch_number").values(
        "id",
        "batch_number",
        "expiry_date",
        "quantity_on_hand",
    )

    return Response({
        "sku": medicine.sku,
        "generic_name": medicine.generic_name,
        "batches": list(batches),
    })
@api_view(["GET"])
@permission_classes([IsAdminUser])
def expiring_batches(request):
    today = timezone.localdate()
    cutoff = today + timedelta(days=30)

    batches = (
        StockBatch.objects
        .filter(
            quantity_on_hand__gt=0,
            expiry_date__range=(today, cutoff),
        )
        .order_by("expiry_date", "medicine__sku", "batch_number")
        .values(
            "medicine__sku",
            "medicine__generic_name",
            "medicine__stock_unit",
            "batch_number",
            "expiry_date",
            "quantity_on_hand",
        )
    )

    return Response(list(batches))