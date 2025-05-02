"""URL configuration for Rajasthan Kisan Officer operations."""

from django.urls import path
from Raj_Officer import views

urlpatterns = [
    path('admin/officers/register', views.register_raj_kisan_officer,
         name='add_raj_kisan_officer'),
    path('admin/officers/update', views.update_raj_kisan_officer,
         name='update_raj_kisan_officer'),
    path('admin/officers', views.get_raj_kisan_officer_detail,
         name='get_raj_kisan_officer_details'),
    path('admin/officers/', views.list_all_raj_kisan_officers,
         name='get_all_raj_kisan_officer'),
    path('admin/officers/delete', views.delete_raj_kisan_officer,name='delete_raj_kisan_officer'),
]
