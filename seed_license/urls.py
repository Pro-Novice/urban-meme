from django.urls import path
from .views import (
    LicenseCreateView, LicenseDetailView, LicenseStatusUpdateView,
    LicenseStatusView, LicenseHistoryView, LicenseCertificateDownloadView,
    LicenseListView
)

urlpatterns = [
    path('licenses/apply/', LicenseCreateView.as_view(), name="apply-license"),
    path('licenses/', LicenseListView.as_view(), name="list-licenses"),  
    path('licenses/<int:license_id>/', LicenseDetailView.as_view(), name="license-detail"),
    path('licenses/<int:license_id>/update-status/', LicenseStatusUpdateView.as_view(), name="update-license-status"),
    path('licenses/<int:license_id>/status/', LicenseStatusView.as_view(), name="license-status"),
    path('licenses/<int:license_id>/history/', LicenseHistoryView.as_view(), name="license-history"),
    path('licenses/<int:license_id>/certificate/', LicenseCertificateDownloadView.as_view(), name="license-certificate"),
#     path('blockchain/transactions/<str:tx_hash>/', TransactionStatusView.as_view(), name="transaction-status"),
#     path('blockchain/transactions/history/', TransactionHistoryView.as_view(), name="transaction-history"),
 ]
