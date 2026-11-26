from django.test import TestCase

from apps.core.testing import make_org, make_user

from .models import AuditLog
from .services import record_audit


class AuditLogTest(TestCase):
    def test_entries_cannot_be_edited_or_deleted(self):
        org = make_org()
        user = make_user(org)
        entry = record_audit("test.action", user=user, details={"x": 1})
        self.assertEqual(entry.organization_id, org.pk)
        with self.assertRaises(ValueError):
            entry.save()
        with self.assertRaises(ValueError):
            entry.delete()
        self.assertEqual(AuditLog.objects.count(), 1)
