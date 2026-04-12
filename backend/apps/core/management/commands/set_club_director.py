"""Assign or reactivate club director membership (and optional Django staff)."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.core.models import Club, ClubMembership


class Command(BaseCommand):
    help = (
        "Set a user as club director for a club (reactivates existing row if present). "
        "Use a numeric club id, e.g. --club-id=1 (not angle brackets; zsh treats <...> as redirection). "
        "List ids: python3 manage.py shell -c \"from apps.core.models import Club; "
        "[print(c.id, c.name) for c in Club.objects.order_by('id')]\""
    )

    def add_arguments(self, parser):
        parser.add_argument("email", type=str, help="User email (case-insensitive match)")
        parser.add_argument("--club-id", type=int, required=True, help="Club primary key")
        parser.add_argument(
            "--staff",
            action="store_true",
            help="Also set is_staff=True (Django admin access)",
        )

    def handle(self, *args, **options):
        email = str(options["email"]).strip()
        club_id = options["club_id"]
        User = get_user_model()
        user = User.objects.filter(email__iexact=email).first()
        if not user:
            raise CommandError(f"No user with email matching: {email!r}")

        club = Club.objects.filter(pk=club_id).first()
        if not club:
            raise CommandError(f"No club with id={club_id}")

        if options["staff"]:
            user.is_staff = True
            user.save(update_fields=["is_staff"])
            self.stdout.write(self.style.SUCCESS(f"Set is_staff=True for {user.email}"))

        ClubMembership.objects.assign_director(user=user, club=club)
        self.stdout.write(
            self.style.SUCCESS(
                f"Club director role active for {user.email} on club {club.id} ({club.name})"
            )
        )
