from django.urls import path, include
from .views import public_verify_license_view, public_verify_qr_view

urlpatterns = [
    path('verify/<int:license_id>/', public_verify_license_view, name='public-verify-license'),
    path('verify/qr/', public_verify_qr_view, name='public-verify-qr'),
]