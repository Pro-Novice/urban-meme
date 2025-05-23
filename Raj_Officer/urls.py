"""URL configuration for Rajasthan Kisan Officer operations."""

from django.urls import path
from Raj_Officer import views

urlpatterns = [
    # Admin URLS (officer)
    path('admin/register-officer', views.register_raj_kisan_officer,
         name='add_raj_kisan_officer'),
    path('admin/officers/update', views.update_raj_kisan_officer,
         name='update_raj_kisan_officer'),
    path('admin/officers', views.get_raj_kisan_officer_detail,
         name='get_raj_kisan_officer_details'),
    path('admin/officers/', views.list_all_raj_kisan_officers,
         name='get_all_raj_kisan_officer'),
    path('admin/officers/delete', views.delete_raj_kisan_officer,name='delete_raj_kisan_officer'),

    #Department URLs (Seed License)
    path("department/licenses", views.department_licenses_view, name="list_licenses_views"),
    # Department License URLs
    path('department/licenses/', views.department_license_detail_view, name='license-detail'),
    path('department/licenses/<int:id>/status/', views.department_license_status_view, name='update-license-status'),
    path('department/licenses/<int:id>/verify-documents/', views.verify_license_documents, name='verify-documents'),
    path('department/licenses/<int:id>/field-inspection/', views.record_field_inspection, name='record-inspection'),
    path('department/licenses/<int:id>/revoke/',views.revoke_license, name='revoke-license'),

    # Inspection URLs
    path('inspections/check-in/', views.inspection_check_in, name='inspection-check-in'),
    path('inspections/upload-photo/', views.upload_inspection_photo, name='upload-inspection-photo'),
    path('inspections/complete/', views.complete_inspection, name='complete-inspection'),

    #Analytics API
    path('analytics/licenses/by-status', views.license_counts_by_status),
    path('analytics/licenses/by-type', views.license_counts_by_type),
    path('reports/licenses/monthly', views.monthly_license_stats),
    path('reports/licenses/by-district', views.licenses_by_district),
    path('reports/officers/performance', views.officer_performance_metrics),

]
