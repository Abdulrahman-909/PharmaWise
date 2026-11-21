from django.contrib import admin

from .models import Medicine, StockBatch


@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
    list_display = ("sku", "generic_name", "brand_name", "strength", "dosage_form", "is_active")
    search_fields = ("sku", "generic_name", "brand_name")
    list_filter = ("is_active", "dosage_form")
@admin.register(StockBatch)
class StockBatchAdmin(admin.ModelAdmin):
    list_display = ("batch_number", "medicine", "expiry_date", "quantity_on_hand")
    search_fields = ("batch_number", "medicine__sku", "medicine__generic_name")
    ordering = ("expiry_date", "batch_number")