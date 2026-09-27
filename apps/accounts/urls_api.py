from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    u = request.user
    return Response(
        {"id": u.id, "username": u.username, "email": u.email, "role": u.role, "is_hr": u.is_hr}
    )


urlpatterns = [
    path("me/", me, name="api-me"),
]
