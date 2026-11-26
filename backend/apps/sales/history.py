from decimal import Decimal

from django.db.models import DecimalField, F, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from apps.accounts.permissions import CUSTOMERS_VIEW, SALES_VIEW, require
from .models import CheckoutRecord, Customer, Payment, PaymentCorrection, Sale, SaleLine


def completed(user):
    return Sale.objects.for_organization(user.organization).filter(completed_at__isnull=False)


def with_balances(sales):
    money = DecimalField(max_digits=24, decimal_places=2)

    def amount(model, key, expression):
        grouped = (model.objects.filter(**{key: OuterRef("pk")}).order_by()
                   .values(key).annotate(value=Sum(expression, output_field=money)).values("value"))
        return Coalesce(Subquery(grouped, output_field=money), Value(Decimal("0")), output_field=money)

    return sales.annotate(
        billed=amount(SaleLine, "sale_id", F("price_per_package") * F("quantity") - F("discount")),
        received=amount(Payment, "sale_id", "amount"),
        corrected=amount(PaymentCorrection, "payment__sale_id", "amount"),
    ).annotate(outstanding=F("billed") - F("received") + F("corrected"))


def sale_row(sale):
    return {"id": sale.pk, "date": sale.completed_at, "customer": str(sale.customer or "Walk-in"),
            "total": f"{sale.billed:.2f}", "balance": f"{sale.outstanding:.2f}"}


@api_view(["GET"])
@permission_classes([require(SALES_VIEW)])
def receipts(request):
    sales = completed(request.user)
    term = request.query_params.get("q", "").strip()
    if term:
        match = Q(customer__name__icontains=term) | Q(customer__phone__icontains=term)
        number = term.removeprefix("#")
        if number.isascii() and number.isdigit() and len(number) <= 18:
            match |= Q(pk=int(number))
        sales = sales.filter(match)
    pages = PageNumberPagination()
    pages.page_size = 25
    batch = pages.paginate_queryset(with_balances(sales.select_related("customer")).order_by("-completed_at", "-pk"), request)
    return pages.get_paginated_response([sale_row(s) for s in batch])


@api_view(["GET"])
@permission_classes([require(SALES_VIEW)])
def receipt(request, pk):
    sale = get_object_or_404(with_balances(completed(request.user)).select_related("customer", "cashier"), pk=pk)
    saved = CheckoutRecord.objects.filter(organization=request.user.organization, receipt__sale=pk).values_list("receipt", flat=True).first()
    if saved is None:
        saved = {"sale": pk, "customer": str(sale.customer or "Walk-in"), "lines": [
            {"name": str(line.medicine), "quantity": line.quantity,
             "package": "box" if line.package == "box" else line.medicine.stock_unit or "unit",
             "price": f"{line.price_per_package:.2f}", "discount": f"{line.discount:.2f}", "total": f"{line.line_total:.2f}"}
            for line in sale.lines.select_related("medicine").order_by("pk")
        ], "total": f"{sale.billed:.2f}", "paid": f"{sale.received - sale.corrected:.2f}",
                 "balance": f"{sale.outstanding:.2f}", "current": True}
    return Response({"shop": request.user.organization.name, "date": sale.completed_at,
                     "cashier": sale.cashier.get_username(), **saved})


@api_view(["GET"])
@permission_classes([require(CUSTOMERS_VIEW), require(SALES_VIEW)])
def debtors(request):
    sales = completed(request.user).filter(customer__isnull=False)
    rows = (with_balances(sales).filter(outstanding__gt=0).order_by("customer__name", "customer_id")
            .values("customer_id", "customer__name", "customer__phone", "outstanding"))
    accounts = {}
    for row in rows.iterator():
        account = accounts.setdefault(row["customer_id"], {"id": row["customer_id"], "name": row["customer__name"],
                                      "phone": row["customer__phone"], "balance": Decimal("0"), "open_receipts": 0})
        account["balance"] += row["outstanding"]
        account["open_receipts"] += 1
    return Response([{**a, "balance": f"{a['balance']:.2f}"} for a in accounts.values()])


@api_view(["GET"])
@permission_classes([require(CUSTOMERS_VIEW), require(SALES_VIEW)])
def statement(request, pk):
    customer = get_object_or_404(Customer.objects.for_organization(request.user.organization), pk=pk)
    sales = with_balances(completed(request.user).filter(customer=customer)).prefetch_related("payments__corrections")
    events = []
    def entry(date, sale, label, change):
        events.append({"date": date, "sale": sale.pk, "label": label, "change": f"{change:.2f}"})
    balance = Decimal("0.00")
    invoices = []
    for sale in sales.order_by("completed_at", "pk"):
        if sale.outstanding > 0:
            invoices.append({"sale": sale.pk, "balance": f"{sale.outstanding:.2f}"})
        balance += sale.outstanding
        entry(sale.completed_at, sale, "Sale", sale.billed)
        for payment in sale.payments.all():
            entry(payment.received_at, sale, "Payment", -payment.amount)
            for correction in payment.corrections.all():
                entry(correction.corrected_at, sale, "Payment correction", correction.amount)
    running = Decimal("0.00")
    events.sort(key=lambda event: event["date"])
    for event in events:
        running += Decimal(event["change"])
        event["balance"] = f"{running:.2f}"
    return Response({"name": customer.name, "phone": customer.phone, "balance": f"{balance:.2f}", "events": events[::-1], "invoices": invoices})
