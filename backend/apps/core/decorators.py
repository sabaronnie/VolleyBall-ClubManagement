import json
from functools import wraps

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.http import JsonResponse
from jwt import ExpiredSignatureError, InvalidTokenError

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
    except ExpiredSignatureError:
        return JsonResponse(
            {"errors": {"token": "Token has expired."}},
            status=401,
        )
    except InvalidTokenError:
        return JsonResponse(
            {"errors": {"token": "Invalid token."}},
            status=401,
        )

    try:
        user = User.objects.get(pk=payload["user_id"])
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


def _client_ip(request):
    forwarded_for = request.headers.get("X-Forwarded-For", "").strip()
    if forwarded_for:
        return forwarded_for.split(",")[0].strip() or "unknown"
    return (request.META.get("REMOTE_ADDR") or "").strip() or "unknown"


def _login_email_from_request(request):
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return ""
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("email") or "").strip().lower()


def _rate_limit_key(scope: str, identifier: str):
    return f"auth:login:rl:{scope}:{identifier}"


def _read_rate_limiter_count(key: str) -> int:
    value = cache.get(key, 0)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _increment_rate_limiter(key: str, window_seconds: int) -> None:
    if not cache.add(key, 1, timeout=window_seconds):
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, 1, timeout=window_seconds)


def login_rate_limited(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        max_attempts = int(getattr(settings, "LOGIN_RATE_LIMIT_MAX_ATTEMPTS", 5))
        window_seconds = int(getattr(settings, "LOGIN_RATE_LIMIT_WINDOW_SECONDS", 15 * 60))

        ip = _client_ip(request)
        email = _login_email_from_request(request)
        ip_key = _rate_limit_key("ip", ip)
        email_key = _rate_limit_key("email", email) if email else None

        if _read_rate_limiter_count(ip_key) >= max_attempts or (
            email_key and _read_rate_limiter_count(email_key) >= max_attempts
        ):
            return JsonResponse(
                {"errors": {"auth": "Too many login attempts. Please try again later."}},
                status=429,
            )

        response = view_func(request, *args, **kwargs)

        # Only count failed credential attempts toward lockout.
        if response.status_code == 401:
            _increment_rate_limiter(ip_key, window_seconds)
            if email_key:
                _increment_rate_limiter(email_key, window_seconds)
        elif response.status_code < 400:
            cache.delete(ip_key)
            if email_key:
                cache.delete(email_key)

        return response

    return _wrapped_view
