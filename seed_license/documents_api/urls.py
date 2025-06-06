from django.urls import path
from .views import upload_document_view, get_document_view, verify_document_view

urlpatterns = [
    path("upload/", upload_document_view, name='document-upload'),
    path("<int:id>/", get_document_view, name='document-view'),
    path("verify/", verify_document_view, name='document-verify'),
]
