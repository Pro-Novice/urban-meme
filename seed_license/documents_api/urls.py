from django.urls import path
from .views import upload_document_view, compare_pdf_hashes

urlpatterns = [
    path("upload/", upload_document_view, name='document-upload'),
    path("compare/", compare_pdf_hashes, name="compare-pdfs"),
]