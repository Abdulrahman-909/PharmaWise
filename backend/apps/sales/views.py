from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.accounts.permissions import REPORTS_VIEW, require

from .models import Payment, PaymentCorrection, Sale


class DailyReportQuery(serializers.Serializer):
    date = serializers.DateField(required=False, input_formats=["%Y-%m-%d"])


@api_view(["GET"])
@permission_classes([require(REPORTS_VIEW)])
def daily_sales_report(request):
    query = DailyReportQuery(data=request.query_params)
    query.is_valid(raise_exception=True)
    report_date = query.validated_data.get("date", timezone.localdate())

    organization = request.user.organization

    completed_sales = Sale.objects.for_organization(organization).filter(
        completed_at__date=report_date
    ).prefetch_related("lines__batch_allocations__cost_parts")

    sales_total = Decimal("0.00")
    known_purchase_cost = Decimal("0.00")
    units_with_unknown_cost = 0

    for sale in completed_sales:
        for line in sale.lines.all():
            sales_total += line.line_total

            # Older sale lines may have no cost records at all.
            unknown_units = line.stock_units

            for allocation in line.batch_allocations.all():
                for part in allocation.cost_parts.all():
                    cost = part.cost_afn
                    if cost is not None:
                        known_purchase_cost += cost
                        unknown_units -= part.quantity

            units_with_unknown_cost += unknown_units

    payments_received = Payment.objects.for_organization(organization).filter(
        received_at__date=report_date
    ).aggregate(total=Sum("amount", default=Decimal("0.00")))["total"]

    payment_corrections = PaymentCorrection.objects.for_organization(organization).filter(
        corrected_at__date=report_date
    ).aggregate(total=Sum("amount", default=Decimal("0.00")))["total"]

    gross_profit = None
    if units_with_unknown_cost == 0:
        gross_profit = f"{sales_total - known_purchase_cost:.2f}"

    return Response({
        "date": report_date.isoformat(),
        "currency": "AFN",
        "completed_sales": len(completed_sales),
        "sales_after_discounts": f"{sales_total:.2f}",
        "known_purchase_cost": f"{known_purchase_cost:.2f}",
        "units_with_unknown_cost": units_with_unknown_cost,
        "gross_profit": gross_profit,
        "payments_received": f"{payments_received:.2f}",
        "payment_corrections": f"{payment_corrections:.2f}",
        "net_payments": f"{payments_received - payment_corrections:.2f}",
    })