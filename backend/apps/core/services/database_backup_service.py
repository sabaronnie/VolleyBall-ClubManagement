from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings


BACKUP_FILENAME_REGEX = re.compile(r"^backup_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}\.sql$")


class DatabaseBackupError(Exception):
    pass


@dataclass(frozen=True)
class BackupResult:
    filename: str
    path: str


class DatabaseBackupService:
    @staticmethod
    def backup_dir() -> Path:
        path = Path(getattr(settings, "DB_BACKUP_DIR", "backups"))
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def generate_backup_filename(now: datetime | None = None) -> str:
        dt = now or datetime.now()
        return dt.strftime("backup_%Y-%m-%d_%H-%M.sql")

    @staticmethod
    def _db_config():
        cfg = settings.DATABASES["default"]
        return {
            "name": cfg.get("NAME", ""),
            "user": cfg.get("USER", ""),
            "password": cfg.get("PASSWORD", ""),
            "host": cfg.get("HOST", "127.0.0.1"),
            "port": str(cfg.get("PORT", "3306")),
        }

    @staticmethod
    def create_backup(filename: str | None = None) -> BackupResult:
        db = DatabaseBackupService._db_config()
        if not db["name"]:
            raise DatabaseBackupError("Database name is missing from settings.")

        backup_filename = filename or DatabaseBackupService.generate_backup_filename()
        if not BACKUP_FILENAME_REGEX.match(backup_filename):
            raise DatabaseBackupError("Backup filename format is invalid.")

        backup_path = DatabaseBackupService.backup_dir() / backup_filename
        env = os.environ.copy()
        if db["password"]:
            env["MYSQL_PWD"] = db["password"]

        cmd = [
            getattr(settings, "MYSQLDUMP_BIN", "mysqldump"),
            "--single-transaction",
            "--routines",
            "--triggers",
            "--events",
            "--add-drop-table",
            "--databases",
            db["name"],
            "-h",
            db["host"] or "127.0.0.1",
            "-P",
            db["port"] or "3306",
            "-u",
            db["user"],
        ]
        with backup_path.open("w", encoding="utf-8") as sql_out:
            try:
                subprocess.run(
                    cmd,
                    check=True,
                    stdout=sql_out,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=env,
                )
            except FileNotFoundError as exc:
                raise DatabaseBackupError(
                    "mysqldump command was not found. Configure MYSQLDUMP_BIN."
                ) from exc
            except subprocess.CalledProcessError as exc:
                raise DatabaseBackupError(
                    f"Database backup failed: {exc.stderr.strip() or 'unknown error'}"
                ) from exc
        return BackupResult(filename=backup_filename, path=str(backup_path))

    @staticmethod
    def restore_backup(filename: str) -> BackupResult:
        if not BACKUP_FILENAME_REGEX.match(filename):
            raise DatabaseBackupError("Backup filename format is invalid.")

        backup_path = DatabaseBackupService.backup_dir() / filename
        if not backup_path.exists():
            raise DatabaseBackupError("Backup file not found.")

        db = DatabaseBackupService._db_config()
        env = os.environ.copy()
        if db["password"]:
            env["MYSQL_PWD"] = db["password"]

        cmd = [
            getattr(settings, "MYSQL_BIN", "mysql"),
            db["name"],
            "-h",
            db["host"] or "127.0.0.1",
            "-P",
            db["port"] or "3306",
            "-u",
            db["user"],
        ]
        try:
            with backup_path.open("r", encoding="utf-8") as sql_in:
                subprocess.run(
                    cmd,
                    check=True,
                    stdin=sql_in,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=env,
                )
        except FileNotFoundError as exc:
            raise DatabaseBackupError("mysql command was not found. Configure MYSQL_BIN.") from exc
        except subprocess.CalledProcessError as exc:
            raise DatabaseBackupError(
                f"Database restore failed: {exc.stderr.strip() or 'unknown error'}"
            ) from exc

        return BackupResult(filename=filename, path=str(backup_path))

    @staticmethod
    def list_backups() -> list[str]:
        folder = DatabaseBackupService.backup_dir()
        files = [
            path.name for path in folder.glob("backup_*.sql") if BACKUP_FILENAME_REGEX.match(path.name)
        ]
        files.sort(reverse=True)
        return files

    @staticmethod
    def should_run_scheduled_backup(now: datetime | None = None) -> bool:
        current = now or datetime.now()
        backups = DatabaseBackupService.list_backups()
        if not backups:
            return True
        latest = backups[0]
        latest_path = DatabaseBackupService.backup_dir() / latest
        modified_at = datetime.fromtimestamp(latest_path.stat().st_mtime)
        frequency_hours = int(getattr(settings, "DB_BACKUP_FREQUENCY_HOURS", 24))
        return current - modified_at >= timedelta(hours=frequency_hours)
