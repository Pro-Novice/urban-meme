from django.urls import path,include
from . import views

app_name = 'seed_license'

urlpatterns = [
    # ══════════════════════════════════════════════════════════════════
    # Core Blockchain Interaction Endpoints
    # ══════════════════════════════════════════════════════════════════
    
    # Universal write endpoint for any state-changing contract function
    path('blockchain/write/', views.blockchain_write_view, name='blockchain-write'),
    
    # Universal read endpoint for any view/pure contract function
    path('blockchain/read/', views.blockchain_read_view, name='blockchain-read'),
    
    # ══════════════════════════════════════════════════════════════════
    # Transaction Management
    # ══════════════════════════════════════════════════════════════════
    
    # Get transaction status by hash
    path('blockchain/transactions/<str:tx_hash>/', views.transaction_status_view, name='transaction-status'),
    
    # ══════════════════════════════════════════════════════════════════
    # Contract Information & Utilities
    # ══════════════════════════════════════════════════════════════════
    
    # Get available methods (read/write) for a contract
    path('blockchain/contracts/<str:contract_name>/methods/', views.contract_methods_view, name='contract-methods'),
    
    # Get contract ABI
    path('blockchain/contracts/<str:contract_name>/abi/', views.contract_abi_view, name='contract-abi'),
    
    # Get contract address
    path('blockchain/contracts/<str:contract_name>/address/', views.contract_address_view, name='contract-address'),
    
    # Estimate gas for a method call
    path('blockchain/estimate-gas/', views.estimate_gas_view, name='estimate-gas'),

    path('evault/',include('seed_license.e_vault_apis.urls'))
]