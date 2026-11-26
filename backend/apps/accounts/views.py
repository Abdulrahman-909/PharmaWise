from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import serializers, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import client_ip, record_audit

from .permissions import permissions_for_role
from .throttling import clear_failures, is_locked, register_failure


class CsrfAlwaysSessionAuthentication(SessionAuthentication):
    """Enforce CSRF even when nobody is signed in yet (protects the login form)."""

    def authenticate(self, request):
        self.enforce_csrf(request)
        return None


def user_payload(user):
    organization = user.organization
    return {
        "id": user.pk,
        "username": user.get_username(),
        "full_name": user.get_full_name(),
        "role": user.role,
        "role_label": user.get_role_display(),
        "is_superuser": user.is_superuser,
        "permissions": permissions_for_role(user.role),
        "organization": None if organization is None else {
            "id": organization.pk,
            "name": organization.name,
            "base_currency": organization.base_currency,
            "default_language": organization.default_language,
            "timezone": organization.timezone,
        },
    }


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=256, trim_whitespace=False)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    """Call once on page load so the browser receives the CSRF cookie."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"csrfToken": get_token(request)})


class LoginView(APIView):
    authentication_classes = [CsrfAlwaysSessionAuthentication]
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        username = serializer.validated_data["username"]
        password = serializer.validated_data["password"]
        ip = client_ip(request)

        if is_locked(username, ip):
            record_audit("login.locked", request=request, username=username)
            return Response(
                {"detail": "Too many failed attempts. Try again in 15 minutes."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        user = authenticate(request, username=username, password=password)

        # One message for every failure so attackers cannot learn which
        # usernames exist.
        if user is None or user.organization_id is None and not user.is_superuser:
            register_failure(username, ip)
            record_audit("login.failed", request=request, username=username)
            return Response(
                {"detail": "Incorrect username or password."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if user.organization is not None and not user.organization.is_active:
            record_audit("login.blocked_inactive_org", request=request, user=user)
            return Response(
                {"detail": "This organization is inactive. Contact your administrator."},
                status=status.HTTP_403_FORBIDDEN,
            )

        clear_failures(username, ip)
        login(request, user)
        record_audit("login.success", request=request, user=user)
        return Response(user_payload(user))


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        record_audit("logout", request=request)
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(user_payload(request.user))
