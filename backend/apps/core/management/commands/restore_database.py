from django.core.management.base import BaseCommand, CommandError

from apps.core.services.database_backup_service import DatabaseBackupError, DatabaseBackupService


class Command(BaseCommand):
    help = "Restore the default database from a SQL backup file."

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True, help="Backup filename to restore.")
        parser.add_argument(
            "--yes-i-understand",
            action="store_true",
            help="Required safety confirmation for destructive restore.",
        )

    def handle(self, *args, **options):
        if not options["yes_i_understand"]:
            raise CommandError(
                "Restore aborted. Re-run with --yes-i-understand to confirm destructive restore."
            )
        try:
            result = DatabaseBackupService.restore_backup(options["file"])
        except DatabaseBackupError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"Database restored from: {result.path}"))
