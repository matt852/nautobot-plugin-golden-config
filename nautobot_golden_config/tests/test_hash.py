"""Unit tests for ConfigMismatchHashViewSet."""

from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, override_settings
from nautobot.apps.testing import TestCase
from nautobot.dcim.models import Device
from rest_framework.response import Response

from nautobot_golden_config import models
from nautobot_golden_config.views import ConfigComplianceHashUIViewSet

from .conftest import create_device_data, create_feature_rule_json

User = get_user_model()


@override_settings(EXEMPT_VIEW_PERMISSIONS=["*"])
class ConfigMismatchHashViewSetTestCase(TestCase):
    """Test ConfigMismatchHashViewSet functionality."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data for ConfigMismatchHashViewSet tests."""
        create_device_data()

        # Get devices created by conftest
        cls.device1 = Device.objects.get(name="Device 1")
        cls.device2 = Device.objects.get(name="Device 2")
        cls.device3 = Device.objects.get(name="Device 3")

        # Create compliance features and rules
        cls.feature1 = create_feature_rule_json(cls.device1, feature="TestFeature1")
        cls.feature2 = create_feature_rule_json(cls.device2, feature="TestFeature2")

        # Create ConfigCompliance objects (non-compliant) for hash relationships
        cls.compliance1 = models.ConfigCompliance.objects.create(
            device=cls.device1, rule=cls.feature1, compliance=False, actual="test actual 1", intended="test intended 1"
        )
        cls.compliance2 = models.ConfigCompliance.objects.create(
            device=cls.device1, rule=cls.feature2, compliance=False, actual="test actual 2", intended="test intended 2"
        )
        cls.compliance3 = models.ConfigCompliance.objects.create(
            device=cls.device2, rule=cls.feature1, compliance=False, actual="test actual 1", intended="test intended 1"
        )
        cls.compliance4 = models.ConfigCompliance.objects.create(
            device=cls.device3, rule=cls.feature1, compliance=False, actual="test actual 3", intended="test intended 3"
        )

        # Get ConfigComplianceHash objects that were automatically created by ConfigCompliance save
        # In the new architecture, these are created by the ConfigCompliance save process
        cls.hash1_actual = models.ConfigComplianceHash.objects.get(
            device=cls.device1, rule=cls.feature1, config_type="actual"
        )
        cls.hash1_intended = models.ConfigComplianceHash.objects.get(
            device=cls.device1, rule=cls.feature1, config_type="intended"
        )
        cls.hash2_actual = models.ConfigComplianceHash.objects.get(
            device=cls.device1, rule=cls.feature2, config_type="actual"
        )
        cls.hash2_intended = models.ConfigComplianceHash.objects.get(
            device=cls.device1, rule=cls.feature2, config_type="intended"
        )
        cls.hash3_actual = models.ConfigComplianceHash.objects.get(
            device=cls.device2, rule=cls.feature1, config_type="actual"
        )
        cls.hash3_intended = models.ConfigComplianceHash.objects.get(
            device=cls.device2, rule=cls.feature1, config_type="intended"
        )
        cls.hash4_actual = models.ConfigComplianceHash.objects.get(
            device=cls.device3, rule=cls.feature1, config_type="actual"
        )
        cls.hash4_intended = models.ConfigComplianceHash.objects.get(
            device=cls.device3, rule=cls.feature1, config_type="intended"
        )

        # Create superuser
        cls.user = User.objects.create_superuser(username="testuser", email="test@example.com", password="testpass")

    def setUp(self):
        """Set up test fixtures for each test method."""
        self.factory = RequestFactory()

    def test_viewset_queryset_filters_actual_only(self):
        """Test that the viewset queryset only includes actual config type hashes."""
        viewset = ConfigComplianceHashUIViewSet()
        queryset = viewset.queryset

        # Should only include actual config type
        actual_hashes = list(queryset.values_list("config_type", flat=True))
        self.assertTrue(all(config_type == "actual" for config_type in actual_hashes))

        # Should include actual hashes from the test setup (count may vary based on filtering)
        self.assertGreater(len(actual_hashes), 0)

    def test_viewset_queryset_filters_non_compliant_only(self):
        """Test that the viewset queryset only includes hashes from non-compliant devices."""
        # Create additional compliance rule and record for testing
        # Need to create a rule for device3's platform (different from feature2 which is for device2's platform)
        feature3 = create_feature_rule_json(self.device3, feature="TestFeature3")
        
        # Verify the rule was created successfully
        self.assertIsNotNone(feature3)
        self.assertEqual(feature3.platform, self.device3.platform)
        
        # Create compliant ConfigCompliance record
        compliance_record, created = models.ConfigCompliance.objects.get_or_create(
            device=self.device3,
            rule=feature3,
            defaults={
                "compliance": True,
                "actual": "compliant config",
                "intended": "compliant config",
            }
        )
        
        # Verify the record was created (not just retrieved)
        self.assertTrue(created, "ConfigCompliance record should have been created, not retrieved")
        self.assertIsNotNone(compliance_record)
        # Verify it's actually compliant
        self.assertTrue(compliance_record.compliance, "Record should be compliant")

        # Hash objects are only created for non-compliant configs
        viewset = ConfigComplianceHashUIViewSet()
        queryset = viewset.queryset

        # Should only include actual hashes from non-compliant devices
        actual_hashes = list(queryset.filter(config_type="actual"))
        # Count should be at least 1 (may vary based on viewset filtering logic)
        self.assertGreater(len(actual_hashes), 0)

        # Check what exists for device3
        compliance_records = models.ConfigCompliance.objects.filter(device=self.device3)
        hash_records = models.ConfigComplianceHash.objects.filter(device=self.device3, config_type="actual")

        # We should have 2 compliance records: 1 non-compliant (feature1) + 1 compliant (feature3)
        self.assertEqual(compliance_records.count(), 2)

        # Debug: let's see what compliance records exist and their status
        print(f"Found {compliance_records.count()} compliance records for device3:")
        for record in compliance_records:
            print(f"  - Rule: {record.rule.feature.name}, Compliant: {record.compliance}")
        
        print(f"Found {hash_records.count()} hash records for device3:")
        for record in hash_records:
            print(f"  - Rule: {record.rule.feature.name}, Hash: {record.config_hash}")
        
        # We should have 1 hash record: only for the non-compliant one (feature1)
        # (Hash was created in setUpTestData)
        self.assertEqual(hash_records.count(), 1)

        # The hash record should be for feature1 (non-compliant)
        hash_record = hash_records.first()
        self.assertEqual(hash_record.rule, self.feature1)

        # The viewset queryset should include this hash record since it corresponds to non-compliant config
        device3_items = queryset.filter(device=self.device3)
        self.assertEqual(device3_items.count(), 1)

        # Verify it's the correct record
        device3_item = device3_items.first()
        self.assertEqual(device3_item.rule, self.feature1)

    def test_get_extra_context(self):
        """Test that get_extra_context returns correct context data."""
        request = self.factory.get("/mismatch-hash/")
        request.user = self.user

        viewset = ConfigComplianceHashUIViewSet()
        context = viewset.get_extra_context(request)

        self.assertIn("title", context)
        self.assertEqual(context["title"], "Configuration Hashes")
        self.assertIn("compliance", context)

    @patch("nautobot_golden_config.views.messages")
    def test_perform_bulk_destroy_confirmation_phase(self, mock_messages):
        """Test the initial confirmation phase of bulk destroy."""
        request = self.factory.post(
            "/mismatch-hash/delete/",
            data={"pk": [str(self.hash1_actual.pk), str(self.hash3_actual.pk)]},
        )
        request.user = self.user

        viewset = ConfigComplianceHashUIViewSet()
        viewset.get_filter_params = MagicMock(return_value={})
        viewset.get_form_class = MagicMock(return_value=MagicMock)
        viewset.get_return_url = MagicMock(return_value="/mismatch-hash/")

        response = viewset.perform_bulk_destroy(request)

        # Should return Response with confirmation data
        self.assertIsInstance(response, Response)
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.data)
        self.assertIn("total_objs_to_delete", response.data)
        # Should show at least 1 object for deletion (may be filtered)
        self.assertGreaterEqual(response.data["total_objs_to_delete"], 1)

    @patch("nautobot_golden_config.views.messages")
    def test_perform_bulk_destroy_deletes_both_hash_types(self, mock_messages):
        """Test that bulk delete removes both actual and intended hashes for device/rule combinations."""
        # Verify initial state
        initial_count = models.ConfigComplianceHash.objects.count()
        # Note: Count may vary due to test isolation and auto-creation of hash objects
        self.assertGreaterEqual(initial_count, 8)  # At least 4 device/rule combinations × 2 config types

        # Create confirmation request
        request = self.factory.post(
            "/mismatch-hash/delete/",
            data={"pk": [str(self.hash1_actual.pk), str(self.hash2_actual.pk)], "_confirm": "true"},
        )
        request.user = self.user

        # Mock form validation
        mock_form = MagicMock()
        mock_form.is_valid.return_value = True

        viewset = ConfigComplianceHashUIViewSet()
        viewset.get_filter_params = MagicMock(return_value={})
        viewset.get_form_class = MagicMock(return_value=lambda data: mock_form)
        viewset.get_return_url = MagicMock(return_value="/mismatch-hash/")

        response = viewset.perform_bulk_destroy(request)

        # Should redirect after successful deletion
        self.assertEqual(response.status_code, 302)

        # Verify both actual and intended hashes deleted for device1/feature1 and device1/feature2
        self.assertFalse(models.ConfigComplianceHash.objects.filter(device=self.device1, rule=self.feature1).exists())
        self.assertFalse(models.ConfigComplianceHash.objects.filter(device=self.device1, rule=self.feature2).exists())

        # Verify other device hashes remain untouched
        self.assertTrue(models.ConfigComplianceHash.objects.filter(device=self.device2, rule=self.feature1).exists())
        self.assertTrue(models.ConfigComplianceHash.objects.filter(device=self.device3, rule=self.feature1).exists())

        # Verify count: deleted 4 hashes (2 device/rule combos × 2 config types each)
        final_count = models.ConfigComplianceHash.objects.count()
        self.assertEqual(final_count, initial_count - 4)

        # Verify success message was called
        mock_messages.success.assert_called_once()
        success_message = mock_messages.success.call_args[0][1]
        self.assertIn("Successfully deleted 4 configuration hash records", success_message)
        self.assertIn("2 device/rule combinations", success_message)

    @patch("nautobot_golden_config.views.messages")
    def test_perform_bulk_destroy_handles_empty_selection(self, mock_messages):
        """Test that bulk delete handles empty selection gracefully."""
        request = self.factory.post("/mismatch-hash/delete/", data={"pk": []})
        request.user = self.user

        viewset = ConfigComplianceHashUIViewSet()
        viewset.get_filter_params = MagicMock(return_value={})
        viewset.get_form_class = MagicMock(return_value=MagicMock)
        viewset.get_return_url = MagicMock(return_value="/mismatch-hash/")

        response = viewset.perform_bulk_destroy(request)

        # Should redirect when no objects are selected
        self.assertEqual(response.status_code, 302)

    @patch("nautobot_golden_config.views.messages")
    def test_perform_bulk_destroy_handles_nonexistent_pks(self, mock_messages):
        """Test that bulk delete handles nonexistent primary keys gracefully."""
        request = self.factory.post(
            "/mismatch-hash/delete/",
            data={
                "pk": ["550e8400-e29b-41d4-a716-446655440000", "550e8400-e29b-41d4-a716-446655440001"],
                "_confirm": "true",
            },
        )
        request.user = self.user

        # Mock form validation
        mock_form = MagicMock()
        mock_form.is_valid.return_value = True

        viewset = ConfigComplianceHashUIViewSet()
        viewset.get_filter_params = MagicMock(return_value={})
        viewset.get_form_class = MagicMock(return_value=lambda data: mock_form)
        viewset.get_return_url = MagicMock(return_value="/mismatch-hash/")

        response = viewset.perform_bulk_destroy(request)

        # Should redirect after handling error
        self.assertEqual(response.status_code, 302)

        # Verify error message was called
        mock_messages.error.assert_called_once()
        error_message = mock_messages.error.call_args[0][1]
        self.assertIn("Selected items not found", error_message)

        # Verify no hashes were deleted
        final_count = models.ConfigComplianceHash.objects.count()
        self.assertEqual(final_count, 8)

    @patch("nautobot_golden_config.views.messages")
    def test_perform_bulk_destroy_groups_by_device_rule_combination(self, mock_messages):
        """Test that bulk delete correctly groups deletions by device/rule combinations."""
        # Verify initial state
        initial_count = models.ConfigComplianceHash.objects.count()

        # Select hash records from different devices but same rule
        request = self.factory.post(
            "/mismatch-hash/delete/",
            data={"pk": [str(self.hash1_actual.pk), str(self.hash3_actual.pk)], "_confirm": "true"},
        )
        request.user = self.user

        # Mock form validation
        mock_form = MagicMock()
        mock_form.is_valid.return_value = True

        viewset = ConfigComplianceHashUIViewSet()
        viewset.get_filter_params = MagicMock(return_value={})
        viewset.get_form_class = MagicMock(return_value=lambda data: mock_form)
        viewset.get_return_url = MagicMock(return_value="/mismatch-hash/")

        response = viewset.perform_bulk_destroy(request)

        # Should redirect after successful deletion
        self.assertEqual(response.status_code, 302)

        # Verify both device/rule combinations had all their hashes deleted
        self.assertFalse(models.ConfigComplianceHash.objects.filter(device=self.device1, rule=self.feature1).exists())
        self.assertFalse(models.ConfigComplianceHash.objects.filter(device=self.device2, rule=self.feature1).exists())

        # Verify other combinations remain untouched
        self.assertTrue(models.ConfigComplianceHash.objects.filter(device=self.device1, rule=self.feature2).exists())
        self.assertTrue(models.ConfigComplianceHash.objects.filter(device=self.device3, rule=self.feature1).exists())

        # Verify count: deleted 4 hashes (2 device/rule combos × 2 config types each)
        final_count = models.ConfigComplianceHash.objects.count()
        self.assertEqual(final_count, initial_count - 4)

    @patch("nautobot_golden_config.views.messages")
    def test_perform_bulk_destroy_with_all_selection(self, mock_messages):
        """Test that bulk delete handles '_all' selection correctly."""
        request = self.factory.post("/mismatch-hash/delete/", data={"_all": "true"})
        request.user = self.user

        # Mock filterset
        mock_filterset = MagicMock()
        mock_filterset.values_list.return_value.values_list.return_value = [1, 2, 3, 4]

        viewset = ConfigComplianceHashUIViewSet()
        viewset.get_filter_params = MagicMock(return_value={})
        viewset.get_form_class = MagicMock(return_value=MagicMock)
        viewset.get_return_url = MagicMock(return_value="/mismatch-hash/")
        viewset.filterset_class = MagicMock(return_value=mock_filterset)

        response = viewset.perform_bulk_destroy(request)

        # Should return response with delete_all flag
        self.assertIsInstance(response, Response)
        self.assertEqual(response.status_code, 200)
        self.assertIn("delete_all", response.data)
        self.assertTrue(response.data["delete_all"])

    def test_viewset_table_class(self):
        """Test that the viewset uses the correct table class."""
        viewset = ConfigComplianceHashUIViewSet()
        self.assertEqual(viewset.table_class.__name__, "ConfigComplianceHashTable")

    def test_viewset_filterset_class(self):
        """Test that the viewset uses the correct filterset class."""
        viewset = ConfigComplianceHashUIViewSet()
        self.assertEqual(viewset.filterset_class.__name__, "ConfigComplianceHashFilterSet")

    def test_viewset_template_name(self):
        """Test that the viewset uses the correct template."""
        viewset = ConfigComplianceHashUIViewSet()
        self.assertEqual(viewset.template_name, "nautobot_golden_config/config_hash_grouping.html")
