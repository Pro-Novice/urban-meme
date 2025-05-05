from django.urls import path
from .views import register_user, login_user, logout_user, get_user_profile, update_user_profile, reset_password_with_otp, request_password_reset, refresh_token_view

urlpatterns = [
    path('auth/register/', register_user, name='register'), # POST
    path('auth/login/', login_user, name='login'),           # POST
    path('auth/logout/', logout_user, name='logout'),         # POST
    path('auth/refresh/', refresh_token_view, name='refresh_token'), # POST
    path('auth/profile/', get_user_profile, name='get_profile') , # GET
    path('auth/profile/', update_user_profile, name='update_profile'), # PUT
    path('auth/password/request-reset/', request_password_reset, name='request_reset'),    # POST
    path('auth/password/reset/', reset_password_with_otp, name='reset_password'),   # POST

]