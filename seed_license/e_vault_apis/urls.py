# urls.py
from django.urls import path

from seed_license.e_vault_apis.views import add_document_to_evault, update_document_in_evault, \
    fetch_document_from_evault

urlpatterns = [
    path('add-document', add_document_to_evault, name='add_document_to_evault'),
    path('update-document',update_document_in_evault, name='update_document_in_evault'),
    path('fetch-document',fetch_document_from_evault, name='fetch_document_from_evault'),
]