from django.core.management.base import BaseCommand, CommandError

from apps.core.services.database_backup_service import DatabaseBackupError, DatabaseBackupService


class Command(BaseCommand):
    help = "Create a full SQL backup (schema + data) for the default database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--filename",
            type=str,
            help="Optional backup filename, e.g. backup_2026-04-25_19-30.sql",
        )

    def handle(self, *args, **options):
        try:
            result = DatabaseBackupService.create_backup(filename=options.get("filename"))
        except DatabaseBackupError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(f"Backup created: {result.path}"))
