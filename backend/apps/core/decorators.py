from functools import wraps

from django.contrib.auth import get_user_model
from django.core.signing import BadSignature, SignatureExpired
from django.http import JsonResponse

from .tokens import verify_auth_token


User = get_user_model()


def _authenticate_request(request):
    authorization_header = request.headers.get("Authorization", "").strip()

    if not authorization_header:
        return JsonResponse(
            {"errors": {"authorization": "Authorization header is required."}},
            status=401,
        )

    scheme, _, token = authorization_header.partition(" ")
    if scheme != "Bearer" or not token:
        return JsonResponse(
            {
                "errors": {
                    "authorization": "Authorization header must use Bearer <token>."
                }
            },
            status=401,
        )

    try:
        payload = verify_auth_token(token)
    except SignatureExpired:
        return JsonResponse(
            {"errors": {"token": "Token has expired."}},
            status=401,
        )
    except BadSignature:
        return JsonResponse(
            {"errors": {"token": "Invalid token."}},
            status=401,
        )

    try:
        user = User.objects.get(pk=payload["user_id"], email=payload["email"])
    except User.DoesNotExist:
        return JsonResponse(
            {"errors": {"token": "User for token was not found."}},
            status=401,
        )

    if not user.is_active:
        return JsonResponse(
            {"errors": {"account": "User account is inactive."}},
            status=401,
        )

    request.user = user
    request.auth = payload
    return None


def login_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        auth_error = _authenticate_request(request)
        if auth_error is not None:
            return auth_error

        return view_func(request, *args, **kwargs)

    return _wrapped_view


def admin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        auth_error = _authenticate_request(request)
        if auth_error is not None:
            return auth_error

        if not request.user.is_staff:
            return JsonResponse(
                {"errors": {"authorization": "Admin access is required."}},
                status=403,
            )

        return view_func(request, *args, **kwargs)

    return _wrapped_view
