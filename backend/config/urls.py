"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from apps.sales.views import daily_sales_report
from django.http import JsonResponse
from apps.inventory.views import expiring_batches, medicine_batches, medicine_list


def health_check(request):
    return JsonResponse({"status": "ok", "app": "PharmaWise"})
urlpatterns = [
    path('admin/', admin.site.urls),
    path("api/health/", health_check),
    path("api/medicines/", medicine_list, name="medicine-list"),
    path(
        "api/medicines/<int:medicine_id>/batches/",
        medicine_batches,
        name="medicine-batches",
    ),
    path("api/reports/expiring-batches/", expiring_batches, name="expiring-batches"),
    path(
        "api/reports/daily-sales/",
        daily_sales_report,
        name="daily-sales-report",
    ),
]
