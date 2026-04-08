import json
from datetime import date

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_POST

from .decorators import login_required
from .tokens import generate_auth_token


User = get_user_model()


def _parse_json_request(request):
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return None


def _parse_date_of_birth(value):
    if not value:
        return None

    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError({"date_of_birth": "Use YYYY-MM-DD format."}) from exc


@csrf_exempt
@require_POST
def register(request):
    payload = _parse_json_request(request)
    if payload is None:
        return JsonResponse({"errors": {"body": "Invalid JSON."}}, status=400)

    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    first_name = (payload.get("first_name") or "").strip()
    last_name = (payload.get("last_name") or "").strip()

    errors = {}

    if not email:
        errors["email"] = "Email is required."
    if not password:
        errors["password"] = "Password is required."
    if not first_name:
        errors["first_name"] = "First name is required."
    if not last_name:
        errors["last_name"] = "Last name is required."

    if errors:
        return JsonResponse({"errors": errors}, status=400)

    try:
        validate_password(password)
        date_of_birth = _parse_date_of_birth(payload.get("date_of_birth"))
    except ValidationError as exc:
        if hasattr(exc, "message_dict"):
            return JsonResponse({"errors": exc.message_dict}, status=400)
        messages = exc.messages if hasattr(exc, "messages") else [str(exc)]
        return JsonResponse({"errors": {"password": messages}}, status=400)

    try:
        user = User.objects.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            date_of_birth=date_of_birth,
        )
    except IntegrityError:
        return JsonResponse(
            {"errors": {"email": "An account with this email already exists."}},
            status=400,
        )

    return JsonResponse(
        {
            "message": "User registered successfully.",
            "user": {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "date_of_birth": (
                    user.date_of_birth.isoformat() if user.date_of_birth else None
                ),
            },
        },
        status=201,
    )


@csrf_exempt
@require_POST
def login(request):
    payload = _parse_json_request(request)
    if payload is None:
        return JsonResponse({"errors": {"body": "Invalid JSON."}}, status=400)

    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    errors = {}
    if not email:
        errors["email"] = "Email is required."
    if not password:
        errors["password"] = "Password is required."

    if errors:
        return JsonResponse({"errors": errors}, status=400)

    user = authenticate(request, email=email, password=password)
    if user is None:
        return JsonResponse(
            {"errors": {"credentials": "Invalid email or password."}},
            status=401,
        )

    token = generate_auth_token(user)
    return JsonResponse(
        {
            "message": "Authentication successful.",
            "token": token,
            "user": {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
            },
        }
    )


@login_required
@require_GET
def me(request):
    return JsonResponse(
        {
            "user": {
                "id": request.user.id,
                "email": request.user.email,
                "first_name": request.user.first_name,
                "last_name": request.user.last_name,
                "date_of_birth": (
                    request.user.date_of_birth.isoformat()
                    if request.user.date_of_birth
                    else None
                ),
            }
        }
    )
