from collections import defaultdict

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.inventory.models import StockBatch
from .models import Sale, SaleBatchAllocation


@transaction.atomic
def complete_sale(sale_id):
    sale = Sale.objects.select_for_update().get(pk=sale_id)

    if sale.completed_at is not None:
        raise ValidationError("This sale is already completed.")

    lines = list(sale.lines.select_related("medicine").order_by("pk"))
    if not lines:
        raise ValidationError("Add at least one medicine before completing the sale.")

    medicine_ids = {line.medicine_id for line in lines}

    # Lock batches in a consistent order when cashiers sell at the same time.
    batches = list(
        StockBatch.objects.select_for_update()
        .filter(
            medicine_id__in=medicine_ids,
            quantity_on_hand__gt=0,
            expiry_date__gte=timezone.localdate(),
        )
        .order_by("pk")
    )

    # Use the earliest expiry first. Break ties by batch number, then ID.
    batches_by_medicine = defaultdict(list)
    for batch in sorted(batches, key=lambda b: (b.expiry_date, b.batch_number, b.pk)):
        batches_by_medicine[batch.medicine_id].append(batch)

    allocations = []
    changed_batches = {}

    for line in lines:
        if not line.medicine.is_active:
            raise ValidationError(f"{line.medicine.sku} is inactive.")

        remaining = line.stock_units
        if remaining is None or remaining <= 0:
            raise ValidationError(f"Check the quantity on sale line #{line.pk}.")

        for batch in batches_by_medicine[line.medicine_id]:
            deducted = min(remaining, batch.quantity_on_hand)
            if deducted == 0:
                continue

            batch.quantity_on_hand -= deducted
            changed_batches[batch.pk] = batch
            allocations.append(
                SaleBatchAllocation(sale_line=line, batch=batch, quantity=deducted)
            )
            remaining -= deducted

            if remaining == 0:
                break

        if remaining:
            raise ValidationError(
                f"Insufficient unexpired stock for {line.medicine.sku}. "
                f"Short by {remaining} stock units."
            )

    StockBatch.objects.bulk_update(changed_batches.values(), ["quantity_on_hand"])
    SaleBatchAllocation.objects.bulk_create(allocations)
    sale.completed_at = timezone.now()
    sale.save(update_fields=["completed_at"])