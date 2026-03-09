from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView


class IsOwner(BasePermission):
    """Allow access only to the owner of the object."""

    def has_object_permission(self, request: Request, view: APIView, obj) -> bool:
        return bool(request.user and obj.owner == request.user)
