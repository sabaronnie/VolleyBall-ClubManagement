from django.core.management.base import BaseCommand, CommandError

from apps.core.services.database_backup_service import DatabaseBackupError, DatabaseBackupService


class Command(BaseCommand):
    help = "Run backup if configured frequency window has elapsed."

    def handle(self, *args, **options):
        if not DatabaseBackupService.should_run_scheduled_backup():
            self.stdout.write("Skipped: backup frequency window has not elapsed.")
            return
        try:
            result = DatabaseBackupService.create_backup()
        except DatabaseBackupError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"Scheduled backup created: {result.path}"))
