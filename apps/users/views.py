from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.template.loader import render_to_string
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import PasswordResetToken
from .serializers import (
    ChangePasswordSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    UserSerializer,
)

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self) -> User:
        return self.request.user  # type: ignore[return-value]


class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=ChangePasswordSerializer, responses={200: None})
    def post(self, request: Request) -> Response:
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        if not user.check_password(serializer.validated_data["old_password"]):
            raise ValidationError({"old_password": ["Mot de passe actuel incorrect."]})

        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])
        return Response({"message": "Mot de passe modifié avec succès."})


_RESET_GENERIC_MESSAGE = (
    "Si un compte existe avec cet email, vous recevrez un lien de réinitialisation."
)


class PasswordResetRequestView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        request=PasswordResetRequestSerializer,
        responses={200: None},
    )
    def post(self, request: Request) -> Response:
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"message": _RESET_GENERIC_MESSAGE})

        token = PasswordResetToken.objects.create(user=user)
        reset_link = f"{settings.FRONTEND_URL}/auth/reset-password?token={token.token}"

        html_body = render_to_string(
            "users/emails/password_reset.html",
            {"reset_link": reset_link},
        )

        send_mail(
            subject="Réinitialisation de votre mot de passe",
            message=reset_link,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            html_message=html_body,
        )

        return Response({"message": _RESET_GENERIC_MESSAGE})


class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        request=PasswordResetConfirmSerializer,
        responses={200: None},
    )
    def post(self, request: Request) -> Response:
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token_value = serializer.validated_data["token"]
        new_password = serializer.validated_data["new_password"]

        try:
            token = PasswordResetToken.objects.select_related("user").get(
                token=token_value
            )
        except PasswordResetToken.DoesNotExist:
            raise ValidationError(
                ["Ce lien de réinitialisation est invalide ou a expiré."]
            ) from None

        if not token.is_valid():
            raise ValidationError(
                ["Ce lien de réinitialisation est invalide ou a expiré."]
            )

        user = token.user
        user.set_password(new_password)
        user.save(update_fields=["password"])

        token.is_used = True
        token.save(update_fields=["is_used", "updated_at"])

        return Response({"message": "Mot de passe réinitialisé avec succès."})
