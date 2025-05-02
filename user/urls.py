from django.urls import path
from .views import register_user, login_user, logout_user

urlpatterns = [
    path('auth/register/', register_user, name='register'),
    path('auth/login/', login_user, name='login'),
     path('auth/logout/', logout_user, name='logout'),

]