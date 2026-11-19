from functools import wraps
from secrets import compare_digest

from django.conf import settings
from django.http import JsonResponse


def valid_bearer(request, expected):
    supplied = request.headers.get("Authorization", "")
    return bool(expected) and compare_digest(
        supplied.encode("utf-8"), f"Bearer {expected}".encode("utf-8")
    )


def staff_or_token(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if valid_bearer(request, settings.API_TOKEN):
            response = view(request, *args, **kwargs)
        elif request.user.is_authenticated:
            if request.user.is_active and request.user.is_staff:
                response = view(request, *args, **kwargs)
            else:
                response = JsonResponse({"error": "staff_access_required"}, status=403)
        else:
            response = JsonResponse({"error": "authentication_required"}, status=401)
            response["WWW-Authenticate"] = "Bearer"
        response["Cache-Control"] = "no-store"
        return response

    return wrapped
