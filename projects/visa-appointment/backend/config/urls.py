from django.contrib import admin
from django.urls import path
from django.views.generic import RedirectView

from apps.api import views as api
from apps.demo_provider import views as demo

admin.site.site_header = "留学签证预约系统"
admin.site.site_title = "Visa Appointment"
admin.site.index_title = "运营工作台"

urlpatterns = [
    path("", RedirectView.as_view(url="/admin/", permanent=False)),
    path("admin/", admin.site.urls),
    path("healthz/", api.health),
    path("api/<slug:resource>/", api.collection),
    path("demo-provider/availability/", demo.availability),
    path("demo-provider/bookings/", demo.submit),
    path("demo-provider/bookings/<uuid:operation_id>/", demo.reconcile),
]
