from collections import defaultdict

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.inventory.models import PurchaseReceiptLine, StockBatch

from .models import Sale, SaleAllocationCost, SaleBatchAllocation, SaleReturn


def record_delivery_costs(allocations, changed_batches):
    # complete_sale holds the stock batch locks while costs are recorded.
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

    # Recover each batch's balance immediately before this sale.
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

        # Opening stock was already on hand when delivery tracking began.
        take = min(remaining, older_units[batch_id])
        if take:
            cost_parts.append(
                SaleAllocationCost(allocation=allocation, quantity=take)
            )
            older_units[batch_id] -= take
            remaining -= take

        # Consume this batch's tracked deliveries in posting order.
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
            raise ValidationError("The delivery quantities do not cover this sale.")

    PurchaseReceiptLine.objects.bulk_update(
        used_deliveries.values(),
        ["remaining_cost_units"],
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

    for line in lines:
        if line.medicine.organization_id != sale.organization_id:
            raise ValidationError(
                f"{line.medicine.sku} belongs to a different organization."
            )

    medicine_ids = {line.medicine_id for line in lines}

    # Concurrent checkouts acquire batch locks in the same order.
    batches = list(
        StockBatch.objects.select_for_update()
        .filter(
            organization_id=sale.organization_id,
            medicine_id__in=medicine_ids,
            quantity_on_hand__gt=0,
            expiry_date__gte=timezone.localdate(),
        )
        .order_by("pk")
    )

    # Sell from the earliest-expiring batch first.
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


@transaction.atomic
def post_sale_return(return_id):
    sale_return = SaleReturn.objects.select_for_update().get(pk=return_id)

    if sale_return.posted_at is not None:
        raise ValidationError("This return is already posted.")

    # All returns for the same sale share this lock. The next cashier checks
    # the available quantity after the previous cashier's return has committed.
    sale = Sale.objects.select_for_update().get(pk=sale_return.sale_id)
    if sale.completed_at is None:
        raise ValidationError("Only completed sales can have a posted return.")

    lines = list(
        sale_return.lines.select_related("sale_line", "sale_return").order_by("pk")
    )
    if not lines:
        raise ValidationError("Add at least one return line before posting.")

    for line in lines:
        line.full_clean()

    sale_return.posted_at = timezone.now()
    sale_return.save(update_fields=["posted_at"])