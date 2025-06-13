import io
import json
from django.urls import reverse
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from seed_license.blockchain_api.authentication import RajSSOUser


class PDFHashingAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.valid_pdf = io.BytesIO(b"%PDF-1.4\n%HashTest\n")
        self.valid_pdf.name = "sample.pdf"
        self.valid_pdf.content_type = 'application/pdf'

        self.valid_pdf_2 = io.BytesIO(b"%PDF-1.4\n%HashDifferent\n")
        self.valid_pdf_2.name = "different.pdf"
        self.valid_pdf_2.content_type = 'application/pdf'

        self.fake_user = RajSSOUser(
            ssoid="user123",
            roles=["AnyRole"],
            user_type="Employee",
            profile={"displayName": "Test User"}
        )

        self.client.force_authenticate(user=self.fake_user)

    def test_upload_document_success(self):
        self.valid_pdf.seek(0)
        response = self.client.post(
            reverse("document-upload"),
            {"document": self.valid_pdf},
            format="multipart"
        )
        response_data = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("sha256_hash", response_data["data"])

    def test_upload_document_missing_file(self):
        response = self.client.post(reverse("document-upload"), {}, format="multipart")
        response_data = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Missing document", response_data["error"])

    def test_upload_document_invalid_type(self):
        non_pdf = io.BytesIO(b"Not a PDF")
        non_pdf.name = "file.txt"
        non_pdf.content_type = 'text/plain'
        response = self.client.post(reverse("document-upload"), {"document": non_pdf}, format="multipart")
        response_data = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Invalid file type", response_data["error"])

    def test_compare_pdfs_equal(self):
        pdf1 = io.BytesIO(b"%PDF-1.4\n%HashTest\n")
        pdf1.name = "copy1.pdf"
        pdf1.content_type = 'application/pdf'

        pdf2 = io.BytesIO(b"%PDF-1.4\n%HashTest\n") 
        pdf2.name = "copy2.pdf"
        pdf2.content_type = 'application/pdf'

        response = self.client.post(
            reverse("compare-pdfs"),
            {"document1": pdf1, "document2": pdf2},
            format="multipart"
        )
        response_data = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response_data["data"]["are_equal"])

    def test_compare_pdfs_not_equal(self):
        self.valid_pdf.seek(0)
        self.valid_pdf_2.seek(0)
        response = self.client.post(
            reverse("compare-pdfs"),
            {"document1": self.valid_pdf, "document2": self.valid_pdf_2},
            format="multipart"
        )
        response_data = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response_data["data"]["are_equal"])

    def test_compare_pdfs_missing_file(self):
        self.valid_pdf.seek(0)
        response = self.client.post(reverse("compare-pdfs"), {"document1": self.valid_pdf}, format="multipart")
        response_data = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Both 'document1' and 'document2' must be provided", response_data["error"])

    def test_compare_invalid_file_type(self):
        non_pdf = io.BytesIO(b"Invalid")
        non_pdf.name = "bad.txt"
        non_pdf.content_type = 'text/plain'

        self.valid_pdf.seek(0)
        response = self.client.post(
            reverse("compare-pdfs"),
            {"document1": self.valid_pdf, "document2": non_pdf},
            format="multipart"
        )
        response_data = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Invalid file type", response_data["error"])
