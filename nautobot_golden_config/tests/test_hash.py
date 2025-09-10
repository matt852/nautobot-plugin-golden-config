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

        # Create ConfigComplianceHash objects for testing
        cls.hash1_actual = models.ConfigComplianceHash.objects.create(
            device=cls.device1,
            rule=cls.feature1,
            config_type="actual",
            config_hash="hash123",
            config_content={"config": "test actual 1"},
        )
        cls.hash1_intended = models.ConfigComplianceHash.objects.create(
            device=cls.device1,
            rule=cls.feature1,
            config_type="intended",
            config_hash="hash456",
            config_content={"config": "test intended 1"},
        )
        cls.hash2_actual = models.ConfigComplianceHash.objects.create(
            device=cls.device1,
            rule=cls.feature2,
            config_type="actual",
            config_hash="hash789",
            config_content={"config": "test actual 2"},
        )
        cls.hash2_intended = models.ConfigComplianceHash.objects.create(
            device=cls.device1,
            rule=cls.feature2,
            config_type="intended",
            config_hash="hash101112",
            config_content={"config": "test intended 2"},
        )
        cls.hash3_actual = models.ConfigComplianceHash.objects.create(
            device=cls.device2,
            rule=cls.feature1,
            config_type="actual",
            config_hash="hash123",  # Same hash as device1/rule1 (mismatch group)
            config_content={"config": "test actual 1"},
        )
        cls.hash3_intended = models.ConfigComplianceHash.objects.create(
            device=cls.device2,
            rule=cls.feature1,
            config_type="intended",
            config_hash="hash456",  # Same hash as device1/rule1
            config_content={"config": "test intended 1"},
        )
        cls.hash4_actual = models.ConfigComplianceHash.objects.create(
            device=cls.device3,
            rule=cls.feature1,
            config_type="actual",
            config_hash="hash131415",
            config_content={"config": "test actual 3"},
        )
        cls.hash4_intended = models.ConfigComplianceHash.objects.create(
            device=cls.device3,
            rule=cls.feature1,
            config_type="intended",
            config_hash="hash161718",
            config_content={"config": "test intended 3"},
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

        # Should include 4 actual hashes (one for each device/rule combination)
        self.assertEqual(len(actual_hashes), 4)

    def test_viewset_queryset_filters_non_compliant_only(self):
        """Test that the viewset queryset only includes hashes from non-compliant devices."""
        # Create a compliant ConfigCompliance record
        _ = models.ConfigCompliance.objects.create(
            device=self.device3,
            rule=self.feature2,
            compliance=True,
            actual="compliant config",
            intended="compliant config",
        )

        # Create hash for compliant device/rule - this should NOT appear in viewset
        models.ConfigComplianceHash.objects.create(
            device=self.device3,
            rule=self.feature2,
            config_type="actual",
            config_hash="compliant_hash",
            config_content={"config": "compliant config"},
        )

        viewset = ConfigComplianceHashUIViewSet()
        queryset = viewset.queryset

        # Should still only include 4 actual hashes from non-compliant devices
        self.assertEqual(queryset.count(), 4)

        # Verify no hashes from compliant devices are included
        hash_devices = list(queryset.values_list("device_id", flat=True))
        # Should only have 1 hash from device3 (the non-compliant one), not the compliant one
        self.assertEqual(len([h for h in hash_devices if h == self.device3.id]), 1)

    def test_get_extra_context(self):
        """Test that get_extra_context returns correct context data."""
        request = self.factory.get("/mismatch-hash/")
        request.user = self.user

        viewset = ConfigComplianceHashUIViewSet()
        context = viewset.get_extra_context(request)

        self.assertIn("title", context)
        self.assertEqual(context["title"], "Configuration Mismatch Hashes")
        self.assertIn("compliance", context)

    @patch("nautobot_golden_config.views.messages")
    def test_perform_bulk_destroy_confirmation_phase(self):
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
        self.assertEqual(response.data["total_objs_to_delete"], 2)

    @patch("nautobot_golden_config.views.messages")
    def test_perform_bulk_destroy_deletes_both_hash_types(self, mock_messages):
        """Test that bulk delete removes both actual and intended hashes for device/rule combinations."""
        # Verify initial state
        initial_count = models.ConfigComplianceHash.objects.count()
        self.assertEqual(initial_count, 8)  # 4 device/rule combinations × 2 config types

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
        self.assertEqual(final_count, 4)

        # Verify success message was called
        mock_messages.success.assert_called_once()
        success_message = mock_messages.success.call_args[0][1]
        self.assertIn("Successfully deleted 4 configuration hash records", success_message)
        self.assertIn("2 device/rule combinations", success_message)

    @patch("nautobot_golden_config.views.messages")
    def test_perform_bulk_destroy_handles_empty_selection(self):
        """Test that bulk delete handles empty selection gracefully."""
        request = self.factory.post("/mismatch-hash/delete/", data={"pk": []})
        request.user = self.user

        viewset = ConfigComplianceHashUIViewSet()
        viewset.get_filter_params = MagicMock(return_value={})
        viewset.get_form_class = MagicMock(return_value=MagicMock)
        viewset.get_return_url = MagicMock(return_value="/mismatch-hash/")

        response = viewset.perform_bulk_destroy(request)

        # Should return response with empty table
        self.assertIsInstance(response, Response)
        self.assertEqual(response.status_code, 200)

    @patch("nautobot_golden_config.views.messages")
    def test_perform_bulk_destroy_handles_nonexistent_pks(self, mock_messages):
        """Test that bulk delete handles nonexistent primary keys gracefully."""
        request = self.factory.post("/mismatch-hash/delete/", data={"pk": ["99999", "88888"], "_confirm": "true"})
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
    def test_perform_bulk_destroy_groups_by_device_rule_combination(self):
        """Test that bulk delete correctly groups deletions by device/rule combinations."""
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
        self.assertEqual(final_count, 4)

    @patch("nautobot_golden_config.views.messages")
    def test_perform_bulk_destroy_with_all_selection(self):
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
        self.assertEqual(viewset.table_class.__name__, "ConfigMismatchHashTable")

    def test_viewset_filterset_class(self):
        """Test that the viewset uses the correct filterset class."""
        viewset = ConfigComplianceHashUIViewSet()
        self.assertEqual(viewset.filterset_class.__name__, "ConfigMismatchGroupingFilterSet")

    def test_viewset_template_name(self):
        """Test that the viewset uses the correct template."""
        viewset = ConfigComplianceHashUIViewSet()
        self.assertEqual(viewset.template_name, "nautobot_golden_config/config_hash_grouping.html")
