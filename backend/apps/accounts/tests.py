from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.core.testing import make_org, make_user

from .permissions import ROLE_PERMISSIONS, require, role_has_permission


class LoginApiTest(TestCase):
    def setUp(self):
        cache.clear()
        self.org = make_org()
        self.user = make_user(self.org, role="cashier", username="sara")
        self.client = APIClient(enforce_csrf_checks=True)

    def csrf(self):
        token = self.client.get("/api/auth/csrf/").json()["csrfToken"]
        return {"HTTP_X_CSRFTOKEN": token}

    def login(self, password="StrongPass!234", username="sara"):
        return self.client.post(
            "/api/auth/login/",
            {"username": username, "password": password},
            format="json",
            **self.csrf(),
        )

    def test_successful_login_returns_role_permissions_and_organization(self):
        response = self.login()
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["role"], "cashier")
        self.assertEqual(data["organization"]["name"], "Test Pharmacy")
        self.assertIn("sales.create", data["permissions"])
        self.assertNotIn("reports.view", data["permissions"])

    def test_me_requires_login_and_returns_the_user(self):
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 403)
        self.login()
        me = self.client.get("/api/auth/me/")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["username"], "sara")

    def test_login_without_csrf_token_is_rejected(self):
        response = self.client.post(
            "/api/auth/login/",
            {"username": "sara", "password": "StrongPass!234"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_wrong_password_gives_a_generic_message_and_is_audited(self):
        response = self.login(password="wrong")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Incorrect username or password.")
        unknown = self.login(username="nobody", password="wrong")
        self.assertEqual(unknown.json(), response.json())
        self.assertTrue(AuditLog.objects.filter(action="login.failed").exists())

    @override_settings(LOGIN_MAX_ATTEMPTS=3)
    def test_account_locks_after_too_many_failures(self):
        for _ in range(3):
            self.assertEqual(self.login(password="wrong").status_code, 400)
        # Even the correct password is refused while locked.
        locked = self.login()
        self.assertEqual(locked.status_code, 429)
        self.assertTrue(AuditLog.objects.filter(action="login.locked").exists())

    def test_logout_ends_the_session(self):
        self.login()
        headers = self.csrf()
        self.assertEqual(self.client.post("/api/auth/logout/", **headers).status_code, 204)
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 403)
        self.assertTrue(AuditLog.objects.filter(action="logout").exists())

    def test_successful_login_is_audited_with_the_organization(self):
        self.login()
        entry = AuditLog.objects.get(action="login.success")
        self.assertEqual(entry.organization_id, self.org.pk)
        self.assertEqual(entry.username, "sara")

    def test_user_without_organization_cannot_sign_in_through_the_api(self):
        orphan = get_user_model().objects.create_user("orphan", password="StrongPass!234")
        self.assertIsNone(orphan.organization)
        self.assertEqual(self.login(username="orphan").status_code, 400)

    def test_inactive_organization_is_blocked(self):
        self.org.is_active = False
        self.org.save()
        self.assertEqual(self.login().status_code, 403)

    def test_passwords_are_hashed_with_argon2(self):
        self.assertTrue(self.user.password.startswith("argon2"))


class RolePermissionTest(TestCase):
    def setUp(self):
        self.org = make_org()

    def api(self, role):
        client = APIClient()
        client.force_authenticate(make_user(self.org, role=role))
        return client

    def test_cashier_can_view_stock_but_not_reports(self):
        client = self.api("cashier")
        self.assertEqual(client.get("/api/medicines/").status_code, 200)
        self.assertEqual(client.get("/api/reports/daily-sales/").status_code, 403)

    def test_auditor_can_read_reports(self):
        self.assertEqual(self.api("auditor").get("/api/reports/daily-sales/").status_code, 200)

    def test_delivery_role_cannot_see_stock(self):
        self.assertEqual(self.api("delivery").get("/api/medicines/").status_code, 403)

    def test_anonymous_users_are_rejected(self):
        self.assertIn(APIClient().get("/api/medicines/").status_code, (401, 403))

    def test_user_without_an_organization_is_rejected(self):
        user = get_user_model().objects.create_user("lonely", password="x", role="admin")
        client = APIClient()
        client.force_authenticate(user)
        self.assertEqual(client.get("/api/medicines/").status_code, 403)

    def test_auditor_is_read_only_everywhere(self):
        for code in ROLE_PERMISSIONS["auditor"]:
            self.assertTrue(code.endswith(".view"), code)
        self.assertFalse(role_has_permission("auditor", "sales.create"))

    def test_unknown_permission_codes_are_refused_at_startup(self):
        with self.assertRaises(ValueError):
            require("inventory.typo")
