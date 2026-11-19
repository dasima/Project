from django.contrib import admin
from django.urls import include, path

from logistics.views import development_frontend, healthz, readyz

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("logistics.urls")),
    path("healthz", healthz),
    path("healthz/", healthz),
    path("readyz", readyz),
    path("readyz/", readyz),
    path("", development_frontend),
    path("<str:asset>", development_frontend),
]
