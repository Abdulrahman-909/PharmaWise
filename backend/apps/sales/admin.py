from decimal import Decimal

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.forms.models import BaseInlineFormSet

from .models import (
    Customer,
    Payment,
    PaymentCorrection,
    Sale,
    SaleLine,
    SaleReturn,
    SaleReturnLine,
)
from .services import complete_sale, post_sale_return


def recorded_payments_total(sale):
    received = sale.payments.aggregate(
        total=Sum("amount", default=Decimal("0.00"))
    )["total"]

    corrections = PaymentCorrection.objects.filter(
        payment__sale=sale
    ).aggregate(
        total=Sum("amount", default=Decimal("0.00"))
    )["total"]

    return received - corrections


class SaleLineForm(forms.ModelForm):
    class Meta:
        model = SaleLine
        fields = ("medicine", "package", "quantity", "discount")

    def clean(self):
        data = super().clean()
        medicine = data.get("medicine")
        package = data.get("package")
        quantity = data.get("quantity")
        discount = data.get("discount")

        if medicine is None or not package:
            return data

        line = self.instance
        package_changed = (
            "medicine" in self.changed_data or "package" in self.changed_data
        )

        # Keep the saved price when only quantity or discount changes.
        if line.pk is None or package_changed:
            if package == SaleLine.Package.BOX:
                price = medicine.box_sale_price
                units = medicine.units_per_box
            else:
                price = medicine.unit_sale_price
                units = 1

            if price is None:
                self.add_error(
                    "package",
                    "Set a selling price for this package in Medicines.",
                )
                return data

            if not units:
                self.add_error(
                    "package",
                    "Set the number of stock units per box in Medicines.",
                )
                return data

            line.price_per_package = price
            line.units_per_package = units

        if quantity is not None and discount is not None:
            if discount > quantity * line.price_per_package:
                self.add_error(
                    "discount",
                    "The discount exceeds the price of this line.",
                )

        return data


class SaleLineInline(admin.StackedInline):
    model = SaleLine
    form = SaleLineForm
    extra = 0
    fields = (
        "medicine",
        "package",
        "quantity",
        "discount",
        "price_per_package",
        "stock_units",
        "line_total",
    )
    readonly_fields = ("price_per_package", "stock_units", "line_total")


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "phone")
    search_fields = ("name", "phone")
    readonly_fields = ("outstanding_balance_afn",)

    @admin.display(description="Outstanding balance across completed sales (AFN)")
    def outstanding_balance_afn(self, obj):
        if obj is None or obj.pk is None:
            return "0.00"

        sales = obj.sales.filter(
            completed_at__isnull=False
        ).prefetch_related("lines", "payments__corrections")

        balance = Decimal("0.00")
        for sale in sales:
            balance += sale.total_due
            for payment in sale.payments.all():
                balance -= payment.amount
                for correction in payment.corrections.all():
                    balance += correction.amount

        return f"{balance:.2f}"


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "customer",
        "cashier",
        "status",
        "created_at",
        "completed_at",
    )
    autocomplete_fields = ("customer",)
    readonly_fields = (
        "cashier",
        "status",
        "total_due_afn",
        "paid_afn",
        "balance_afn",
        "created_at",
        "completed_at",
    )
    inlines = [SaleLineInline]
    actions = ["complete_selected_sale"]

    @admin.display(description="Total due (AFN)")
    def total_due_afn(self, obj):
        if obj is None or obj.pk is None:
            return "0.00"
        return f"{obj.total_due:.2f}"

    @admin.display(description="Payments recorded (AFN)")
    def paid_afn(self, obj):
        if obj is None or obj.pk is None:
            return "0.00"
        return f"{recorded_payments_total(obj):.2f}"

    @admin.display(description="Outstanding balance (AFN)")
    def balance_afn(self, obj):
        if obj is None or obj.completed_at is None:
            return "—"
        balance = obj.total_due - recorded_payments_total(obj)
        return f"{balance:.2f}"

    def save_model(self, request, obj, form, change):
        if not change:
            obj.cashier = request.user
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        match = request.resolver_match

        if request.method == "POST" and match and match.url_name in {
            "sales_sale_change",
            "sales_sale_delete",
        }:
            return queryset.select_for_update()

        return queryset

    def has_change_permission(self, request, obj=None):
        if obj is not None and obj.completed_at is not None:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.completed_at is not None:
            return False
        return super().has_delete_permission(request, obj)

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    @admin.action(description="Complete selected sale", permissions=["change"])
    def complete_selected_sale(self, request, queryset):
        sale_ids = list(queryset.values_list("pk", flat=True)[:2])

        if len(sale_ids) != 1:
            self.message_user(
                request,
                "Select one sale at a time.",
                messages.WARNING,
            )
            return

        sale_id = sale_ids[0]

        try:
            complete_sale(sale_id)
        except ValidationError as error:
            self.message_user(request, " ".join(error.messages), messages.WARNING)
        except Sale.DoesNotExist:
            self.message_user(request, "This sale no longer exists.", messages.WARNING)
        else:
            self.message_user(
                request,
                f"Sale #{sale_id} completed. Stock updated.",
                messages.SUCCESS,
            )


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ("sale", "amount")

    def clean(self):
        data = super().clean()
        sale = data.get("sale")
        amount = data.get("amount")

        if sale is None or amount is None:
            return data

        # Payments and corrections on a sale share this lock.
        sale = Sale.objects.select_for_update().get(pk=sale.pk)

        if sale.completed_at is None:
            self.add_error("sale", "Complete this sale before recording a payment.")
            return data

        balance = sale.total_due - recorded_payments_total(sale)

        if amount > balance:
            self.add_error(
                "amount",
                f"The outstanding balance is {balance:.2f} AFN. "
                "Enter an amount within that balance.",
            )
        elif amount < balance and sale.customer_id is None:
            self.add_error(
                "amount",
                "A partial payment requires a sale linked to a customer.",
            )

        return data


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    form = PaymentForm
    fields = ("sale", "amount", "received_by", "received_at")
    readonly_fields = ("received_by", "received_at")
    list_display = ("sale", "amount", "received_by", "received_at")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "sale":
            kwargs["queryset"] = Sale.objects.filter(completed_at__isnull=False)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @transaction.atomic
    def add_view(self, request, form_url="", extra_context=None):
        return super().add_view(request, form_url, extra_context)

    def save_model(self, request, obj, form, change):
        obj.received_by = request.user
        super().save_model(request, obj, form, change)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class PaymentCorrectionForm(forms.ModelForm):
    class Meta:
        model = PaymentCorrection
        fields = ("payment", "amount", "reason")

    def clean(self):
        data = super().clean()
        payment = data.get("payment")
        amount = data.get("amount")

        if payment is None or amount is None:
            return data

        Sale.objects.select_for_update().get(pk=payment.sale_id)

        already_corrected = payment.corrections.aggregate(
            total=Sum("amount", default=Decimal("0.00"))
        )["total"]
        remaining = payment.amount - already_corrected

        if amount > remaining:
            self.add_error(
                "amount",
                f"Only {remaining:.2f} AFN of this payment remains available "
                "for correction.",
            )

        return data


@admin.register(PaymentCorrection)
class PaymentCorrectionAdmin(admin.ModelAdmin):
    form = PaymentCorrectionForm
    fields = ("payment", "amount", "reason", "corrected_by", "corrected_at")
    readonly_fields = ("corrected_by", "corrected_at")
    list_display = ("payment", "amount", "reason", "corrected_by", "corrected_at")

    @transaction.atomic
    def add_view(self, request, form_url="", extra_context=None):
        return super().add_view(request, form_url, extra_context)

    def save_model(self, request, obj, form, change):
        obj.corrected_by = request.user
        super().save_model(request, obj, form, change)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class SaleReturnLineFormSet(BaseInlineFormSet):
    def add_fields(self, form, index):
        super().add_fields(form, index)

        if "sale_line" in form.fields:
            form.fields["sale_line"].queryset = SaleLine.objects.filter(
                sale_id=self.instance.sale_id
            ).order_by("pk")


class SaleReturnLineInline(admin.TabularInline):
    model = SaleReturnLine
    formset = SaleReturnLineFormSet
    fields = ("sale_line", "quantity")
    extra = 0

    def has_add_permission(self, request, obj):
        if obj is not None and obj.posted_at is not None:
            return False
        return super().has_add_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        if obj is not None and obj.posted_at is not None:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.posted_at is not None:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(SaleReturn)
class SaleReturnAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "sale",
        "status",
        "created_by",
        "created_at",
        "posted_at",
    )
    fields = (
        "sale",
        "reason",
        "status",
        "created_by",
        "created_at",
        "posted_at",
    )
    readonly_fields = ("status", "created_by", "created_at", "posted_at")
    inlines = [SaleReturnLineInline]
    actions = ["post_selected_return"]

    def get_inlines(self, request, obj=None):
        # The original sale must be selected before adding return lines.
        if obj is None:
            return []
        return super().get_inlines(request, obj)

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        if obj is not None:
            return (*fields, "sale")
        return fields

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        match = request.resolver_match

        # Draft edits and posting acquire the same return row lock.
        if request.method == "POST" and match and match.url_name in {
            "sales_salereturn_change",
            "sales_salereturn_delete",
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

    @admin.action(description="Post selected return", permissions=["change"])
    def post_selected_return(self, request, queryset):
        return_ids = list(queryset.values_list("pk", flat=True)[:2])

        if len(return_ids) != 1:
            self.message_user(
                request,
                "Select one return at a time.",
                messages.WARNING,
            )
            return

        return_id = return_ids[0]

        try:
            post_sale_return(return_id)
        except ValidationError as error:
            self.message_user(request, " ".join(error.messages), messages.WARNING)
        except SaleReturn.DoesNotExist:
            self.message_user(request, "This return no longer exists.", messages.WARNING)
        else:
            self.message_user(
                request,
                f"Return #{return_id} posted.",
                messages.SUCCESS,
            )