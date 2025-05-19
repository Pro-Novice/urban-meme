from django.urls import path, include
from .views import (
    license_create_view, license_detail_view, license_status_update_view,
    license_status_view, license_history_view, license_certificate_download_view,
    license_list_view, transaction_status_view, transaction_history_view
)

urlpatterns = [
    path('licenses/apply/', license_create_view, name='license-create'),
    path('licenses/', license_list_view, name='license-list'),
    path('licenses/<int:license_id>/', license_detail_view, name='license-detail'),
    path('licenses/<int:license_id>/update-status/', license_status_update_view, name='license-status-update'),
    path('licenses/<int:license_id>/status/', license_status_view, name='license-status'),
    path('licenses/<int:license_id>/history/', license_history_view, name='license-history'),
    path('licenses/<int:license_id>/certificate/', license_certificate_download_view, name='license-certificate'),
     path('blockchain/transactions/history/', transaction_history_view, name='transaction-history'),
    path('blockchain/transactions/<str:tx_hash>/', transaction_status_view, name='transaction-status'),
   
    # Blockchain Smart Contract APIs
    path('blockchain/contract/', include('seed_license.blockchain_api.urls')),
]
