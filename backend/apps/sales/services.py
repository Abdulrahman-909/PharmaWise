from collections import defaultdict

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.inventory.models import PurchaseReceiptLine, StockBatch

from .models import Sale, SaleAllocationCost, SaleBatchAllocation


def record_delivery_costs(allocations, changed_batches):
    # complete_sale already holds the stock batch locks.
    deliveries = list(
        PurchaseReceiptLine.objects.select_for_update(of=("self",))
        .filter(
            batch_id__in=changed_batches,
            receipt__posted_at__isnull=False,
            remaining_cost_units__gt=0,
        )
        .order_by("batch_id", "receipt__posted_at", "pk")
    )

    deliveries_by_batch = defaultdict(list)
    tracked_units = defaultdict(int)

    for delivery in deliveries:
        deliveries_by_batch[delivery.batch_id].append(delivery)
        tracked_units[delivery.batch_id] += delivery.remaining_cost_units

    # changed_batches contains balances after the deductions for this sale.
    starting_stock = {
        batch_id: batch.quantity_on_hand
        for batch_id, batch in changed_batches.items()
    }
    for allocation in allocations:
        starting_stock[allocation.batch_id] += allocation.quantity

    older_units = {}
    for batch_id, quantity in starting_stock.items():
        older_units[batch_id] = quantity - tracked_units[batch_id]
        if older_units[batch_id] < 0:
            raise ValidationError(
                f"Tracked delivery units exceed stock for {changed_batches[batch_id]}. "
                "Check the batch quantities before completing this sale."
            )

    cost_parts = []
    used_deliveries = {}

    for allocation in allocations:
        batch_id = allocation.batch_id
        remaining = allocation.quantity

        # Consume stock already on hand when delivery tracking began.
        take = min(remaining, older_units[batch_id])
        if take:
            cost_parts.append(
                SaleAllocationCost(allocation=allocation, quantity=take)
            )
            older_units[batch_id] -= take
            remaining -= take

        # Within this batch, consume tracked deliveries in posting order.
        for delivery in deliveries_by_batch[batch_id]:
            if remaining == 0:
                break

            take = min(remaining, delivery.remaining_cost_units)
            if take == 0:
                continue

            cost_parts.append(
                SaleAllocationCost(
                    allocation=allocation,
                    receipt_line=delivery,
                    quantity=take,
                    purchase_price_per_box=delivery.purchase_price_per_box,
                    units_per_box=delivery.units_per_box,
                )
            )
            delivery.remaining_cost_units -= take
            used_deliveries[delivery.pk] = delivery
            remaining -= take

        if remaining:
            raise ValidationError(
                "The delivery quantities do not cover this sale."
            )

    PurchaseReceiptLine.objects.bulk_update(
        used_deliveries.values(), ["remaining_cost_units"]
    )
    SaleAllocationCost.objects.bulk_create(cost_parts)


@transaction.atomic
def complete_sale(sale_id):
    sale = Sale.objects.select_for_update().get(pk=sale_id)

    if sale.completed_at is not None:
        raise ValidationError("This sale is already completed.")

    lines = list(sale.lines.select_related("medicine").order_by("pk"))
    if not lines:
        raise ValidationError("Add at least one medicine before completing the sale.")

    medicine_ids = {line.medicine_id for line in lines}

    # Acquire locks in a consistent order across concurrent checkouts.
    batches = list(
        StockBatch.objects.select_for_update()
        .filter(
            medicine_id__in=medicine_ids,
            quantity_on_hand__gt=0,
            expiry_date__gte=timezone.localdate(),
        )
        .order_by("pk")
    )

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
                SaleBatchAllocation(
                    sale_line=line,
                    batch=batch,
                    quantity=deducted,
                )
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
    allocations = SaleBatchAllocation.objects.bulk_create(allocations)
    record_delivery_costs(allocations, changed_batches)

    sale.completed_at = timezone.now()
    sale.save(update_fields=["completed_at"])