from django.urls import path

from . import views

urlpatterns = [
    path("public/config/", views.public_config, name="public-config"),
    path("auth/csrf/", views.csrf_token, name="auth-csrf"),
    path("auth/login/", views.login_view, name="auth-login"),
    path("auth/me/", views.current_user, name="auth-me"),
    path("auth/logout/", views.logout_view, name="auth-logout"),
    path("shipments/", views.shipment_list, name="shipment-list"),
    path("shipments/<str:number>/", views.shipment_detail, name="shipment-detail"),
    path("shipments/<str:number>/events/", views.shipment_events, name="shipment-events"),
    path("package-prealerts/", views.package_prealert, name="package-prealert"),
]
