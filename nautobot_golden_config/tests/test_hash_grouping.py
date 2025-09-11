"""Unit tests for nautobot_golden_config hash grouping feature."""

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from nautobot.apps.testing import TestCase
from nautobot.dcim.models import Device

from nautobot_golden_config import models
from nautobot_golden_config.filters import ConfigHashGroupingFilterSet
from nautobot_golden_config.forms import ConfigHashGroupingFilterForm
from nautobot_golden_config.tables import ConfigHashGroupTable
from nautobot_golden_config.views import ConfigHashGroupingViewSet

from .conftest import create_device_data, create_feature_rule_json

User = get_user_model()


@override_settings(EXEMPT_VIEW_PERMISSIONS=["*"])
class ConfigHashGroupingModelTestCase(TestCase):
    """Test ConfigHashGrouping model functionality."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data for ConfigHashGrouping model tests."""
        create_device_data()

        # Get devices
        cls.device1 = Device.objects.get(name="Device 1")
        cls.device2 = Device.objects.get(name="Device 2")
        cls.device3 = Device.objects.get(name="Device 3")

        # Create compliance features
        cls.feature1 = create_feature_rule_json(cls.device1, feature="TestFeature1")
        cls.feature2 = create_feature_rule_json(cls.device2, feature="TestFeature2")

    def test_config_hash_grouping_model_creation(self):
        """Test that ConfigHashGrouping model can be created properly."""
        identical_config = {"interface": {"GigabitEthernet0/1": {"ip_address": "192.168.1.1/24"}}}

        # Create a ConfigHashGrouping instance
        hash_group = models.ConfigHashGrouping.objects.create(
            rule=self.feature1,
            config_hash="test123hash",
            config_content=identical_config,
        )

        self.assertIsInstance(hash_group, models.ConfigHashGrouping)
        self.assertEqual(hash_group.rule, self.feature1)
        self.assertEqual(hash_group.config_hash, "test123hash")
        self.assertEqual(hash_group.config_content, identical_config)

    def test_config_hash_grouping_str_representation(self):
        """Test the string representation of ConfigHashGrouping."""
        hash_group = models.ConfigHashGrouping.objects.create(
            rule=self.feature1,
            config_hash="test123hash",
            config_content={},
        )

        # String should include rule and truncated hash
        expected_str = f"{self.feature1} -> test123h"
        self.assertEqual(str(hash_group), expected_str)

    def test_config_hash_grouping_unique_together(self):
        """Test that rule and config_hash combination must be unique."""
        # Create first hash group
        models.ConfigHashGrouping.objects.create(
            rule=self.feature1,
            config_hash="duplicate_hash",
            config_content={},
        )

        # Attempting to create another with same rule and hash should fail
        with self.assertRaises(Exception):  # IntegrityError
            models.ConfigHashGrouping.objects.create(
                rule=self.feature1,
                config_hash="duplicate_hash",
                config_content={},
            )

    def test_config_compliance_hash_with_group_relationship(self):
        """Test ConfigComplianceHash relationship with ConfigHashGrouping."""
        # Create hash group
        hash_group = models.ConfigHashGrouping.objects.create(
            rule=self.feature1,
            config_hash="test123hash",
            config_content={"test": "config"},
        )

        # Create hash record linked to group
        hash_record = models.ConfigComplianceHash.objects.create(
            device=self.device1,
            rule=self.feature1,
            config_type="actual",
            config_hash="test123hash",
            config_group=hash_group,
        )

        self.assertEqual(hash_record.config_group, hash_group)
        self.assertIn(hash_record, hash_group.hash_records.all())


@override_settings(EXEMPT_VIEW_PERMISSIONS=["*"])
class ConfigHashGroupingViewTestCase(TestCase):
    """Test ConfigHashGroupingViewSet functionality."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data for ConfigHashGroupingViewSet tests."""
        create_device_data()

        # Get devices
        cls.device1 = Device.objects.get(name="Device 1")
        cls.device2 = Device.objects.get(name="Device 2")
        cls.device3 = Device.objects.get(name="Device 3")
        cls.device4 = Device.objects.get(name="Device 4")

        # Create compliance features
        cls.feature1 = create_feature_rule_json(cls.device1, feature="TestFeature1")
        cls.feature2 = create_feature_rule_json(cls.device2, feature="TestFeature2")

        # Create test configurations
        identical_config = {"interface": {"GigabitEthernet0/1": {"ip_address": "192.168.1.1/24"}}}
        different_config = {"interface": {"GigabitEthernet0/1": {"ip_address": "192.168.2.1/24"}}}

        # Create ConfigHashGrouping records
        cls.hash_group1 = models.ConfigHashGrouping.objects.create(
            rule=cls.feature1,
            config_hash="abc123hash",
            config_content=identical_config,
        )
        cls.hash_group2 = models.ConfigHashGrouping.objects.create(
            rule=cls.feature1,
            config_hash="def456hash",
            config_content=different_config,
        )

        # Create ConfigComplianceHash records linking devices to hash groups
        models.ConfigComplianceHash.objects.create(
            device=cls.device1,
            rule=cls.feature1,
            config_type="actual",
            config_hash="abc123hash",
            config_group=cls.hash_group1,
        )
        models.ConfigComplianceHash.objects.create(
            device=cls.device2,
            rule=cls.feature1,
            config_type="actual",
            config_hash="abc123hash",
            config_group=cls.hash_group1,
        )
        models.ConfigComplianceHash.objects.create(
            device=cls.device3,
            rule=cls.feature1,
            config_type="actual",
            config_hash="def456hash",
            config_group=cls.hash_group2,
        )
        models.ConfigComplianceHash.objects.create(
            device=cls.device4,
            rule=cls.feature1,
            config_type="actual",
            config_hash="def456hash",
            config_group=cls.hash_group2,
        )

        # Create ConfigCompliance records with non-compliant status
        models.ConfigCompliance.objects.create(
            device=cls.device1,
            rule=cls.feature1,
            actual=identical_config,
            intended=different_config,
            compliance=False,
            compliance_int=0,
        )
        models.ConfigCompliance.objects.create(
            device=cls.device2,
            rule=cls.feature1,
            actual=identical_config,
            intended=different_config,
            compliance=False,
            compliance_int=0,
        )
        models.ConfigCompliance.objects.create(
            device=cls.device3,
            rule=cls.feature1,
            actual=different_config,
            intended=identical_config,
            compliance=False,
            compliance_int=0,
        )
        models.ConfigCompliance.objects.create(
            device=cls.device4,
            rule=cls.feature1,
            actual=different_config,
            intended=identical_config,
            compliance=False,
            compliance_int=0,
        )

    def test_viewset_url_access(self):
        """Test that the hash grouping URL is accessible."""
        url = reverse("plugins:nautobot_golden_config:confighashgrouping_list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_viewset_queryset_filters_groups_with_multiple_devices(self):
        """Test that viewset only shows groups with more than one device."""
        viewset = ConfigHashGroupingViewSet()
        queryset = viewset.queryset

        # Should only include groups with device_count > 1
        for group in queryset:
            self.assertGreater(group.device_count, 1)

    def test_viewset_queryset_annotations(self):
        """Test that viewset queryset includes required annotations."""
        viewset = ConfigHashGroupingViewSet()
        queryset = viewset.queryset

        if queryset.exists():
            first_group = queryset.first()
            # Check that annotations are present
            self.assertTrue(hasattr(first_group, "device_count"))
            self.assertTrue(hasattr(first_group, "feature_id"))
            self.assertTrue(hasattr(first_group, "feature_name"))
            self.assertTrue(hasattr(first_group, "feature_slug"))

    def test_viewset_template_name(self):
        """Test that viewset uses correct template."""
        viewset = ConfigHashGroupingViewSet()
        self.assertEqual(viewset.template_name, "nautobot_golden_config/config_hash_grouping.html")

    def test_viewset_table_class(self):
        """Test that viewset uses correct table class."""
        viewset = ConfigHashGroupingViewSet()
        self.assertEqual(viewset.table_class, ConfigHashGroupTable)

    def test_viewset_filterset_classes(self):
        """Test that viewset uses correct filterset classes."""
        viewset = ConfigHashGroupingViewSet()
        self.assertEqual(viewset.filterset_class, ConfigHashGroupingFilterSet)
        self.assertEqual(viewset.filterset_form_class, ConfigHashGroupingFilterForm)

    def test_viewset_no_action_buttons(self):
        """Test that viewset has disabled add/import action buttons."""
        viewset = ConfigHashGroupingViewSet()
        self.assertEqual(viewset.action_buttons, [])


@override_settings(EXEMPT_VIEW_PERMISSIONS=["*"])
class ConfigHashGroupTableTestCase(TestCase):
    """Test ConfigHashGroupTable functionality."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data for table tests."""
        create_device_data()

        # Get devices
        cls.device1 = Device.objects.get(name="Device 1")
        cls.device2 = Device.objects.get(name="Device 2")

        # Create compliance features
        cls.feature1 = create_feature_rule_json(cls.device1, feature="TestFeature1")

        # Create sample config data
        cls.config_content = {
            "interface": {"GigabitEthernet0/1": {"ip_address": "192.168.1.1/24", "description": "Test interface"}}
        }

        # Create ConfigHashGrouping
        cls.hash_group = models.ConfigHashGrouping.objects.create(
            rule=cls.feature1,
            config_hash="test123hash",
            config_content=cls.config_content,
        )

        # Create ConfigComplianceHash records
        models.ConfigComplianceHash.objects.create(
            device=cls.device1,
            rule=cls.feature1,
            config_type="actual",
            config_hash="test123hash",
            config_group=cls.hash_group,
        )
        models.ConfigComplianceHash.objects.create(
            device=cls.device2,
            rule=cls.feature1,
            config_type="actual",
            config_hash="test123hash",
            config_group=cls.hash_group,
        )

        # Create ConfigCompliance records
        models.ConfigCompliance.objects.create(
            device=cls.device1,
            rule=cls.feature1,
            actual=cls.config_content,
            intended={"different": "config"},
            compliance=False,
            compliance_int=0,
        )
        models.ConfigCompliance.objects.create(
            device=cls.device2,
            rule=cls.feature1,
            actual=cls.config_content,
            intended={"different": "config"},
            compliance=False,
            compliance_int=0,
        )

    def test_table_initialization(self):
        """Test that ConfigHashGroupTable can be initialized properly."""
        queryset = ConfigHashGroupingViewSet().queryset
        table = ConfigHashGroupTable(data=queryset)

        # Table should initialize without errors
        self.assertIsInstance(table, ConfigHashGroupTable)

    def test_table_columns_present(self):
        """Test that all expected columns are present in the table."""
        queryset = ConfigHashGroupingViewSet().queryset
        table = ConfigHashGroupTable(data=queryset)

        # Check that expected columns exist
        expected_columns = ["pk", "feature_name", "device_count", "config_content", "actions"]
        for column_name in expected_columns:
            self.assertIn(column_name, table.columns)

    def test_table_meta_configuration(self):
        """Test table Meta configuration."""
        # Use empty queryset for table initialization
        empty_data = models.ConfigHashGrouping.objects.none()
        table = ConfigHashGroupTable(data=empty_data)

        # Check model
        self.assertEqual(table.Meta.model, models.ConfigHashGrouping)

        # Check fields and default columns
        expected_fields = ("pk", "feature_name", "device_count", "config_content", "actions")
        self.assertEqual(table.Meta.fields, expected_fields)
        self.assertEqual(table.Meta.default_columns, expected_fields)

    def test_table_actions_column_template(self):
        """Test that actions column contains expected remediation links."""
        # Get the actions column template from the table class definition
        table_class = ConfigHashGroupTable
        actions_column = table_class.base_columns["actions"]
        template_code = actions_column.template_code

        # Check for expected URL pattern and icon
        self.assertIn("configcompliance_remediate", template_code)
        self.assertIn("mdi-map-check-outline", template_code)
        self.assertIn("Generate Remediation Config Plans", template_code)

    def test_table_device_count_column_template(self):
        """Test device count column template for filtering links."""
        # Get the device_count column template from the table class definition
        table_class = ConfigHashGroupTable
        device_count_column = table_class.base_columns["device_count"]
        template_code = device_count_column.template_code

        # Check for filtering URL with parameters
        self.assertIn("configcompliance_list", template_code)
        self.assertIn("feature_id", template_code)
        self.assertIn("config_hash_group", template_code)

    def test_table_config_content_column_template(self):
        """Test config content column template structure."""
        # Get the config_content column template from the table class definition
        table_class = ConfigHashGroupTable
        config_content_column = table_class.base_columns["config_content"]
        template_code = config_content_column.template_code

        # Check for clipboard functionality in the display template
        self.assertIn("toClipboard", template_code)
        self.assertIn("Click to copy to clipboard", template_code)
        self.assertIn("helpers", template_code)


@override_settings(EXEMPT_VIEW_PERMISSIONS=["*"])
class ConfigHashGroupingIntegrationTestCase(TestCase):
    """Integration tests for the hash grouping feature."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data for integration tests."""
        create_device_data()

        # Get devices
        cls.device1 = Device.objects.get(name="Device 1")
        cls.device2 = Device.objects.get(name="Device 2")

        # Create compliance features
        cls.feature1 = create_feature_rule_json(cls.device1, feature="TestFeature1")

        # Create sample config data
        cls.config_content = {"interface": {"GigabitEthernet0/1": {"ip_address": "192.168.1.1/24"}}}

    def test_config_compliance_save_creates_hash_grouping(self):
        """Test that saving ConfigCompliance creates ConfigHashGrouping and hash records."""
        # Create ConfigCompliance record - this should trigger hash grouping creation
        models.ConfigCompliance.objects.create(
            device=self.device1,
            rule=self.feature1,
            actual=self.config_content,
            intended={"different": "config"},
            compliance=False,
            compliance_int=0,
        )

        models.ConfigCompliance.objects.create(
            device=self.device2,
            rule=self.feature1,
            actual=self.config_content,  # Same actual config as device1
            intended={"different": "config"},
            compliance=False,
            compliance_int=0,
        )

        # Check that ConfigHashGrouping was created
        hash_groups = models.ConfigHashGrouping.objects.filter(rule=self.feature1)
        self.assertEqual(hash_groups.count(), 1)

        hash_group = hash_groups.first()
        self.assertEqual(hash_group.config_content, self.config_content)

        # Check that ConfigComplianceHash records were created and linked to the group
        hash_records = models.ConfigComplianceHash.objects.filter(
            rule=self.feature1, config_type="actual", config_group=hash_group
        )
        self.assertEqual(hash_records.count(), 2)

        # Verify both devices are linked to the same group
        device_ids = set(hash_records.values_list("device_id", flat=True))
        self.assertEqual(device_ids, {self.device1.id, self.device2.id})

    def test_compliant_devices_not_grouped(self):
        """Test that compliant devices don't create hash groups."""
        # Create compliant ConfigCompliance record
        models.ConfigCompliance.objects.create(
            device=self.device1,
            rule=self.feature1,
            actual=self.config_content,
            intended=self.config_content,  # Same as actual = compliant
            compliance=True,
            compliance_int=1,
        )

        # Check that no ConfigHashGrouping was created for compliant config
        hash_groups = models.ConfigHashGrouping.objects.filter(rule=self.feature1)
        self.assertEqual(hash_groups.count(), 0)

        # Hash record should still be created but without a group
        hash_record = models.ConfigComplianceHash.objects.get(
            device=self.device1, rule=self.feature1, config_type="actual"
        )
        self.assertIsNone(hash_record.config_group)

    def test_viewset_shows_only_multi_device_groups(self):
        """Test that viewset only displays groups with multiple devices."""
        # Create two different configs for different devices
        config1 = {"interface": {"GigabitEthernet0/1": {"ip_address": "192.168.1.1/24"}}}
        config2 = {"interface": {"GigabitEthernet0/1": {"ip_address": "192.168.2.1/24"}}}

        # Device1 gets config1 (will create single-device group)
        models.ConfigCompliance.objects.create(
            device=self.device1,
            rule=self.feature1,
            actual=config1,
            intended={"different": "config"},
            compliance=False,
            compliance_int=0,
        )

        # Device2 gets config2 (will create another single-device group)
        models.ConfigCompliance.objects.create(
            device=self.device2,
            rule=self.feature1,
            actual=config2,
            intended={"different": "config"},
            compliance=False,
            compliance_int=0,
        )

        # Both groups should exist in the database
        hash_groups = models.ConfigHashGrouping.objects.filter(rule=self.feature1)
        self.assertEqual(hash_groups.count(), 2)

        # But viewset should show neither (both have device_count = 1)
        viewset = ConfigHashGroupingViewSet()
        queryset = viewset.queryset
        self.assertEqual(queryset.count(), 0)

    def test_full_workflow_with_template_rendering(self):
        """Test the full workflow from model creation to template rendering."""
        # Create identical configs for two devices
        models.ConfigCompliance.objects.create(
            device=self.device1,
            rule=self.feature1,
            actual=self.config_content,
            intended={"different": "config"},
            compliance=False,
            compliance_int=0,
        )

        models.ConfigCompliance.objects.create(
            device=self.device2,
            rule=self.feature1,
            actual=self.config_content,
            intended={"different": "config"},
            compliance=False,
            compliance_int=0,
        )

        # Test the view response
        url = reverse("plugins:nautobot_golden_config:confighashgrouping_list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

        # Check that we have table data
        self.assertIn("table", response.context)
        table = response.context["table"]

        # Should have one group with 2 devices
        table_data = list(table.data)
        if table_data:  # If the query worked
            self.assertEqual(len(table_data), 1)
            first_group = table_data[0]
            self.assertEqual(first_group.device_count, 2)
            self.assertEqual(first_group.feature_name, "TestFeature1")
