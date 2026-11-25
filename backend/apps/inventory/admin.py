from django.contrib import admin, messages
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import Medicine, PurchaseReceipt, PurchaseReceiptLine, StockBatch, Supplier


@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
    list_display = (
        "sku",
        "generic_name",
        "brand_name",
        "strength",
        "dosage_form",
        "is_active",
    )
    search_fields = ("sku", "generic_name", "brand_name")
    list_filter = ("is_active", "dosage_form")


@admin.register(StockBatch)
class StockBatchAdmin(admin.ModelAdmin):
    list_display = ("batch_number", "medicine", "expiry_date", "quantity_on_hand")
    search_fields = ("batch_number", "medicine__sku", "medicine__generic_name")
    ordering = ("expiry_date", "batch_number")


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "is_active")
    search_fields = ("name", "phone")
    list_filter = ("is_active",)


class PurchaseReceiptLineInline(admin.TabularInline):
    model = PurchaseReceiptLine
    extra = 0
    fields = (
        "batch",
        "boxes_received",
        "units_per_box",
        "purchase_price_per_box",
        "units_received",
        "line_cost_afn",
        "unit_cost_afn",
    )
    readonly_fields = ("units_received", "line_cost_afn", "unit_cost_afn")

    @admin.display(description="Line cost (AFN)", empty_value="—")
    def line_cost_afn(self, obj):
        cost = obj.line_cost
        return None if cost is None else f"{cost:.2f}"

    @admin.display(description="Cost per stock unit (AFN)", empty_value="—")
    def unit_cost_afn(self, obj):
        if obj.purchase_price_per_box is None or not obj.units_per_box:
            return None

        unit_cost = obj.purchase_price_per_box / obj.units_per_box
        return f"{unit_cost:.2f}"


@admin.register(PurchaseReceipt)
class PurchaseReceiptAdmin(admin.ModelAdmin):
    list_display = ("invoice_number", "supplier", "received_on", "posted_at")
    search_fields = ("invoice_number", "supplier__name")
    list_filter = ("received_on",)
    inlines = [PurchaseReceiptLineInline]
    actions = ["post_receipt"]

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        match = request.resolver_match

        if request.method == "POST" and match and match.url_name in {
            "inventory_purchasereceipt_change",
            "inventory_purchasereceipt_delete",
        }:
            return queryset.select_for_update()

        return queryset

    def has_change_permission(self, request, obj=None):
        if obj is not None and obj.posted_at is not None:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.posted_at is not None:
            return False
        return super().has_delete_permission(request, obj)

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    @admin.action(description="Post selected receipt", permissions=["change"])
    def post_receipt(self, request, queryset):
        receipt_ids = list(queryset.values_list("pk", flat=True)[:2])
        if len(receipt_ids) != 1:
            self.message_user(request, "Select one receipt at a time.", messages.WARNING)
            return

        with transaction.atomic():
            receipt = (
                PurchaseReceipt.objects.select_for_update()
                .filter(pk=receipt_ids[0])
                .first()
            )

            if receipt is None:
                self.message_user(request, "Receipt no longer exists.", messages.WARNING)
                return

            if receipt.posted_at is not None:
                self.message_user(request, "Receipt is already posted.", messages.WARNING)
                return

            lines = list(receipt.lines.order_by("batch_id", "pk"))
            if not lines:
                self.message_user(
                    request,
                    "Add a delivery line before posting.",
                    messages.WARNING,
                )
                return

            for line in lines:
                units = line.units_received
                StockBatch.objects.filter(pk=line.batch_id).update(
                    quantity_on_hand=F("quantity_on_hand") + units
                )
                line.remaining_cost_units = units

            PurchaseReceiptLine.objects.bulk_update(lines, ["remaining_cost_units"])

            receipt.posted_at = timezone.now()
            receipt.save(update_fields=["posted_at"])

        self.message_user(
            request,
            f"Receipt {receipt.invoice_number} posted. Stock updated.",
            messages.SUCCESS,
        )