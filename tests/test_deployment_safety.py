"""Static and unit coverage for deployment safety boundaries."""

from __future__ import annotations

import os
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from migrations.__main__ import MIGRATION_OPT_IN_ENV, main, migration_database_url


class DockerContextSafetyTests(TestCase):
    def test_dockerignore_excludes_secrets_and_local_artifacts(self) -> None:
        ignored = {
            line.strip()
            for line in Path(".dockerignore").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        }

        self.assertTrue(
            {
                ".env",
                ".env.*",
                ".git",
                ".venv/",
                "venv/",
                "__pycache__/",
                "*.pyc",
                ".pytest_cache/",
                ".mypy_cache/",
                ".ruff_cache/",
                "tests/",
                "/tmp",
            }.issubset(ignored)
        )

    def test_container_starts_gunicorn_without_running_migrations(self) -> None:
        dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
        self.assertIn('CMD ["gunicorn"', dockerfile)
        self.assertNotIn("python -m migrations", dockerfile)


class MigrationRunnerSafetyTests(TestCase):
    def test_migrations_require_explicit_opt_in_before_a_connection(self) -> None:
        with patch.dict(
            os.environ,
            {"APP_ENV": "testing", "APP_DATABASE_URL": "postgresql://localhost/app_test"},
            clear=True,
        ):
            with self.assertRaisesRegex(RuntimeError, MIGRATION_OPT_IN_ENV):
                migration_database_url()

    def test_explicit_opt_in_continues_only_with_the_app_database_url(self) -> None:
        app_database_url = "postgresql://localhost/app_test"
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "testing",
                "APP_DATABASE_URL": app_database_url,
                "CLINICAL_DATABASE_URL": "postgresql://localhost/clinical",
                MIGRATION_OPT_IN_ENV: "1",
            },
            clear=True,
        ):
            with patch("migrations.__main__.apply_pending_migrations") as apply:
                main()

        apply.assert_called_once_with(app_database_url)
