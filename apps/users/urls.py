from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenVerifyView

from .views import ChangePasswordView, MeView, RegisterView

urlpatterns = [
    # Registration
    path("register/", RegisterView.as_view(), name="auth-register"),
    # JWT
    path("token/", TokenObtainPairView.as_view(), name="token-obtain-pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("token/verify/", TokenVerifyView.as_view(), name="token-verify"),
    # Profile
    path("me/", MeView.as_view(), name="auth-me"),
    path("me/change-password/", ChangePasswordView.as_view(), name="auth-change-password"),
]
