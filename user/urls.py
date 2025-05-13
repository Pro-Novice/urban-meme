from django.urls import path
from .views import  RegisterUserView, LoginUserView, RefreshTokenView, LogoutUserView, UserProfileView, UpdateUserProfileView, reset_password_with_otp, request_password_reset

urlpatterns = [
    path('register/', RegisterUserView.as_view()),
    path('login/', LoginUserView.as_view()),
    path('refresh-token/', RefreshTokenView.as_view()),
    path('logout/', LogoutUserView.as_view()),
    path('profile/', UserProfileView.as_view()),
    path('profile/update/', UpdateUserProfileView.as_view()),
    path('auth/password/request-reset/', request_password_reset, name='request_reset'),    # POST
    path('auth/password/reset/', reset_password_with_otp, name='reset_password'),   # POST

]