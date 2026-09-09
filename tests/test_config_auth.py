"""Unit coverage recovered for configuration, connections, and authentication.

All data in this module is synthetic.  Database interactions are mocked so the
tests exercise application boundaries without requiring either PostgreSQL
database.
"""

from __future__ import annotations

import os
from datetime import datetime
from unittest import TestCase
from unittest.mock import MagicMock, Mock, call, patch
from uuid import uuid4

from app import create_app
from db import get_app_db, get_clinical_db
from repositories.drafts import release_locks_for_user
from repositories.users import AuthUser, get_user_by_id, get_user_by_username
from services.auth import authenticate_user
from services.passwords import hash_password, verify_password
from services.signature_profile import SIGNATURE_PROFILE_SESSION_KEY


def extract_csrf(html: str) -> str:
    marker = 'name="csrf_token" value="'
    start = html.index(marker) + len(marker)
    return html[start : html.index('"', start)]


class AppConfigTests(TestCase):
    def test_development_uses_explicit_database_urls_and_cookie_policy(self) -> None:
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "development",
                "APP_DATABASE_URL": "postgresql://synthetic-app-db",
                "CLINICAL_DATABASE_URL": "postgresql://synthetic-clinical-db",
                "SECRET_KEY": "synthetic-test-secret",
                "SESSION_COOKIE_SECURE": "true",
            },
            clear=True,
        ):
            app = create_app()

        self.assertEqual(app.config["APP_DATABASE_URL"], "postgresql://synthetic-app-db")
        self.assertEqual(
            app.config["CLINICAL_DATABASE_URL"], "postgresql://synthetic-clinical-db"
        )
        self.assertTrue(app.config["SESSION_COOKIE_SECURE"])
        self.assertTrue(app.config["SESSION_COOKIE_HTTPONLY"])
        self.assertEqual(app.config["SESSION_COOKIE_SAMESITE"], "Lax")

    def test_testing_requires_no_database_configuration(self) -> None:
        with patch.dict(os.environ, {"APP_ENV": "testing"}, clear=True):
            app = create_app("testing")

        self.assertTrue(app.config["TESTING"])
        self.assertIsNone(app.config["APP_DATABASE_URL"])
        self.assertIsNone(app.config["CLINICAL_DATABASE_URL"])
        self.assertFalse(app.config["SESSION_COOKIE_SECURE"])
        self.assertTrue(app.config["SESSION_COOKIE_HTTPONLY"])
        self.assertEqual(app.config["SESSION_COOKIE_SAMESITE"], "Lax")


class DatabaseConnectionTests(TestCase):
    def test_app_and_clinical_connections_are_request_scoped_and_closed(self) -> None:
        app_connection = Mock(name="app_connection")
        clinical_connection = Mock(name="clinical_connection")
        app = create_app("testing")
        app.config.update(
            APP_DATABASE_URL="postgresql://synthetic-app-db",
            CLINICAL_DATABASE_URL="postgresql://synthetic-clinical-db",
        )

        with patch(
            "db.psycopg.connect", side_effect=[app_connection, clinical_connection]
        ) as connect:
            with app.test_request_context("/"):
                self.assertIs(get_app_db(), get_app_db())
                self.assertIs(get_clinical_db(), get_clinical_db())
                self.assertIsNot(get_app_db(), get_clinical_db())
                self.assertEqual(
                    connect.call_args_list,
                    [
                        call("postgresql://synthetic-app-db", autocommit=True),
                        call(
                            "postgresql://synthetic-clinical-db",
                            autocommit=False,
                            options="-c default_transaction_read_only=on",
                        ),
                    ],
                )

        app_connection.close.assert_called_once_with()
        clinical_connection.close.assert_called_once_with()


class UserRepositoryTests(TestCase):
    def test_user_lookups_load_role_and_optional_signature_profile(self) -> None:
        connection = MagicMock(name="app_connection")
        cursor = connection.cursor.return_value.__enter__.return_value
        created_at = datetime(2026, 1, 1, 9, 30)
        cursor.fetchone.side_effect = [
            (
                7,
                "synthetic-user",
                "Nombre sintético",
                "hash",
                True,
                "MEDICO",
                created_at,
                "Dra. Firma sintética",
                "Neumología",
                "RM 12345",
                "Instituto sintético",
            ),
            (
                8,
                "without-profile",
                "Perfil ausente",
                "hash",
                True,
                "AUXILIAR",
                created_at,
                None,
                None,
                None,
                None,
            ),
        ]

        with patch("repositories.users.get_app_db", return_value=connection):
            profiled = get_user_by_username(" synthetic-user ")
            without_profile = get_user_by_id("8")

        first_query, first_params = cursor.execute.call_args_list[0].args
        second_query, second_params = cursor.execute.call_args_list[1].args
        self.assertIn("LEFT JOIN ergo_app.user_signature_profiles", first_query)
        self.assertIn("WHERE u.username = %s", first_query)
        self.assertEqual(first_params, ("synthetic-user",))
        self.assertIn("LEFT JOIN ergo_app.user_signature_profiles", second_query)
        self.assertIn("WHERE u.id = %s", second_query)
        self.assertEqual(second_params, (8,))

        self.assertEqual(profiled.role, "MEDICO")
        self.assertEqual(profiled.created_at, created_at)
        self.assertEqual(profiled.signature_name, "Dra. Firma sintética")
        self.assertEqual(profiled.profession_specialty, "Neumología")
        self.assertEqual(profiled.professional_registration, "RM 12345")
        self.assertEqual(profiled.institutional_line, "Instituto sintético")
        self.assertEqual(without_profile.role, "AUXILIAR")
        self.assertIsNone(without_profile.signature_name)
        self.assertIsNone(without_profile.profession_specialty)
        self.assertIsNone(without_profile.professional_registration)
        self.assertIsNone(without_profile.institutional_line)

    def test_invalid_user_identifiers_do_not_query_the_database(self) -> None:
        with patch("repositories.users.get_app_db") as get_connection:
            self.assertIsNone(get_user_by_username("  "))
            self.assertIsNone(get_user_by_id("not-an-id"))

        get_connection.assert_not_called()


class TechnicalLockCleanupTests(TestCase):
    def test_logout_cleanup_only_deletes_legacy_technical_locks(self) -> None:
        connection = MagicMock(name="app_connection")
        cursor = connection.cursor.return_value.__enter__.return_value

        with patch("repositories.drafts.get_app_db", return_value=connection):
            release_locks_for_user(17)

        query, parameters = cursor.execute.call_args.args
        self.assertIn("DELETE FROM ergo_app.draft_locks", query)
        self.assertEqual(parameters, (17,))
        self.assertNotIn("report_drafts", query)
        self.assertNotIn("medical_owner", query)
        connection.commit.assert_called_once_with()


class PasswordAndAuthenticationTests(TestCase):
    def test_password_hashing_uses_argon2id_and_verifies_credentials(self) -> None:
        password_hash = hash_password("synthetic-password")

        self.assertTrue(password_hash.startswith("$argon2id$"))
        self.assertTrue(verify_password(password_hash, "synthetic-password"))
        self.assertFalse(verify_password(password_hash, "incorrect-password"))

    def test_authentication_accepts_only_active_users_with_valid_passwords(self) -> None:
        active_user = AuthUser(
            id=5,
            username="active-user",
            full_name="Usuario activo",
            password_hash="stored-hash",
            active=True,
            role="MEDICO",
        )
        inactive_user = AuthUser(
            id=6,
            username="inactive-user",
            full_name="Usuario inactivo",
            password_hash="stored-hash",
            active=False,
            role="MEDICO",
        )

        with patch(
            "services.auth.get_user_by_username", side_effect=[active_user, inactive_user]
        ) as get_user, patch("services.auth.verify_password", return_value=True) as verify:
            self.assertIs(authenticate_user(" active-user ", "secret"), active_user)
            self.assertIsNone(authenticate_user("inactive-user", "secret"))
            self.assertIsNone(authenticate_user("", "secret"))
            self.assertIsNone(authenticate_user("active-user", ""))

        self.assertEqual(get_user.call_args_list, [call("active-user"), call("inactive-user")])
        verify.assert_called_once_with("stored-hash", "secret")


class AuthRouteTests(TestCase):
    def setUp(self) -> None:
        self.user = AuthUser(
            id=1,
            username="synthetic-doctor",
            full_name="Médica sintética",
            password_hash="stored-hash",
            active=True,
            role="MEDICO",
            signature_name="Dra. Firma sintética",
            profession_specialty="Medicina interna",
            professional_registration="RM 9876",
            institutional_line="Instituto sintético",
        )
        self.user_loader = patch("app.get_user_by_id", return_value=self.user)
        self.user_loader.start()
        self.addCleanup(self.user_loader.stop)
        self.app = create_app("testing")
        self.client = self.app.test_client()

    def test_home_clinical_and_workflow_routes_require_login(self) -> None:
        protected_requests = [
            ("get", "/"),
            ("get", "/studies/preview"),
            ("post", "/studies/select"),
            ("post", "/studies/drafts/save"),
            ("post", "/studies/drafts/take"),
            ("post", "/studies/drafts/release"),
            ("post", "/studies/drafts/sign"),
            ("post", "/studies/versions/create"),
            ("post", "/studies/versions/report.pdf"),
        ]

        for method, path in protected_requests:
            with self.subTest(method=method, path=path):
                response = getattr(self.client, method)(path)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/login", response.headers["Location"])

    def test_login_rejects_invalid_credentials(self) -> None:
        login_page = self.client.get("/login")
        csrf_token = extract_csrf(login_page.get_data(as_text=True))

        with patch("routes.auth.authenticate_user", return_value=None):
            response = self.client.post(
                "/login",
                data={
                    "username": "synthetic-doctor",
                    "password": "incorrect-password",
                    "csrf_token": csrf_token,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Credenciales incorrectas.", response.get_data(as_text=True))
        with self.client.session_transaction() as session:
            self.assertNotIn("_user_id", session)

    def test_login_creates_session_and_logout_only_cleans_technical_locks(self) -> None:
        login_page = self.client.get("/login")
        csrf_token = extract_csrf(login_page.get_data(as_text=True))

        with patch("routes.auth.authenticate_user", return_value=self.user):
            response = self.client.post(
                "/login",
                data={
                    "username": "synthetic-doctor",
                    "password": "synthetic-password",
                    "csrf_token": csrf_token,
                },
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/")
        with self.client.session_transaction() as session:
            self.assertEqual(session["_user_id"], "1")
            self.assertEqual(
                session[SIGNATURE_PROFILE_SESSION_KEY],
                {
                    "name": "Dra. Firma sintética",
                    "profession_specialty": "Medicina interna",
                    "professional_registration": "RM 9876",
                    "institutional_line": "Instituto sintético",
                },
            )

        home_response = self.client.get("/")
        logout_csrf = extract_csrf(home_response.get_data(as_text=True))
        with patch("routes.auth.release_locks_for_user") as release_locks:
            logout_response = self.client.post(
                "/logout", data={"csrf_token": logout_csrf}, follow_redirects=False
            )

        self.assertEqual(logout_response.status_code, 302)
        self.assertIn("/login", logout_response.headers["Location"])
        release_locks.assert_called_once_with(1)
        with self.client.session_transaction() as session:
            self.assertNotIn("_user_id", session)
            self.assertNotIn(SIGNATURE_PROFILE_SESSION_KEY, session)

    def test_create_version_redirects_html_forms_and_keeps_json_for_api_clients(self) -> None:
        source_version_id = uuid4()
        new_draft_id = uuid4()
        created_draft = Mock(id=new_draft_id, revision=2, state="EN_FIRMA")
        with self.client.session_transaction() as session:
            session["_user_id"] = str(self.user.id)
            session["_fresh"] = True
            session["_csrf_token"] = "synthetic-csrf"

        with patch("routes.studies.create_new_report_version", return_value=created_draft):
            html_response = self.client.post(
                "/studies/versions/create",
                data={
                    "csrf_token": "synthetic-csrf",
                    "version_id": str(source_version_id),
                    "response_format": "html",
                },
                follow_redirects=False,
            )
            api_response = self.client.post(
                "/studies/versions/create",
                data={"csrf_token": "synthetic-csrf", "version_id": str(source_version_id)},
                headers={"Accept": "application/json"},
            )

        self.assertEqual(html_response.status_code, 302)
        self.assertEqual(html_response.headers["Location"], f"/studies/drafts/{new_draft_id}")
        self.assertEqual(api_response.status_code, 200)
        self.assertEqual(
            api_response.get_json(),
            {"draft_id": str(new_draft_id), "revision": 2, "state": "EN_FIRMA", "created": True},
        )
