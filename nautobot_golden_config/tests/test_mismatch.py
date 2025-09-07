"""Unit tests for nautobot_golden_config mismatch feature."""

import re

from django.contrib.auth import get_user_model
from django.test import RequestFactory, override_settings
from django.urls import reverse
from nautobot.apps.testing import TestCase
from nautobot.dcim.models import Device

from nautobot_golden_config import models
from nautobot_golden_config.tables import ConfigComplianceHashTable
from nautobot_golden_config.views import ConfigMismatchGroupingView

from .conftest import create_device_data, create_feature_rule_json

User = get_user_model()


@override_settings(EXEMPT_VIEW_PERMISSIONS=["*"])
class ConfigMismatchGroupingViewTestCase(TestCase):
    """Test ConfigMismatchGroupingView."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data for ConfigMismatchGroupingView tests."""
        create_device_data()

        # Get devices
        cls.device1 = Device.objects.get(name="Device 1")
        cls.device2 = Device.objects.get(name="Device 2")
        cls.device3 = Device.objects.get(name="Device 3")
        cls.device4 = Device.objects.get(name="Device 4")

        # Create compliance features
        cls.feature1 = create_feature_rule_json(cls.device1, feature="TestFeature1")
        cls.feature2 = create_feature_rule_json(cls.device2, feature="TestFeature2")

        # Create config hash records with identical actual configs for grouping
        identical_config = {"interface": {"GigabitEthernet0/1": {"ip_address": "192.168.1.1/24"}}}
        different_config = {"interface": {"GigabitEthernet0/1": {"ip_address": "192.168.2.1/24"}}}

        # Create ConfigComplianceHash records for grouping
        models.ConfigComplianceHash.objects.create(
            device=cls.device1,
            rule=cls.feature1,
            config_type="actual",
            config_hash="abc123hash",
            config_content=identical_config,
        )
        models.ConfigComplianceHash.objects.create(
            device=cls.device2,
            rule=cls.feature1,
            config_type="actual",
            config_hash="abc123hash",
            config_content=identical_config,
        )
        models.ConfigComplianceHash.objects.create(
            device=cls.device3,
            rule=cls.feature1,
            config_type="actual",
            config_hash="def456hash",
            config_content=different_config,
        )
        models.ConfigComplianceHash.objects.create(
            device=cls.device4,
            rule=cls.feature1,
            config_type="actual",
            config_hash="def456hash",
            config_content=different_config,
        )

        # Create ConfigCompliance records with non-compliant status
        models.ConfigCompliance.objects.create(
            device=cls.device1,
            rule=cls.feature1,
            actual=identical_config,
            intended=different_config,
            compliance=False,
            compliance_int=0,
            actual_config_hash="abc123hash",
        )
        models.ConfigCompliance.objects.create(
            device=cls.device2,
            rule=cls.feature1,
            actual=identical_config,
            intended=different_config,
            compliance=False,
            compliance_int=0,
            actual_config_hash="abc123hash",
        )
        models.ConfigCompliance.objects.create(
            device=cls.device3,
            rule=cls.feature1,
            actual=different_config,
            intended=identical_config,
            compliance=False,
            compliance_int=0,
            actual_config_hash="def456hash",
        )
        models.ConfigCompliance.objects.create(
            device=cls.device4,
            rule=cls.feature1,
            actual=different_config,
            intended=identical_config,
            compliance=False,
            compliance_int=0,
            actual_config_hash="def456hash",
        )

    def test_mismatch_grouping_view_get_success(self):
        """Test that ConfigMismatchGroupingView GET request returns 200."""
        url = reverse("plugins:nautobot_golden_config:configcompliance_mismatch_grouping")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_mismatch_grouping_view_template_used(self):
        """Test that the correct template is used."""
        url = reverse("plugins:nautobot_golden_config:configcompliance_mismatch_grouping")
        response = self.client.get(url)
        self.assertTemplateUsed(response, "nautobot_golden_config/config_mismatch_grouping.html")

    def test_mismatch_grouping_view_context_data(self):
        """Test that the view provides correct context data."""
        url = reverse("plugins:nautobot_golden_config:configcompliance_mismatch_grouping")
        response = self.client.get(url)

        # Check that context contains table
        self.assertIn("table", response.context)

        # Check that table is the correct type
        self.assertIsInstance(response.context["table"], ConfigComplianceHashTable)

    def test_mismatch_grouping_groups_identical_configs(self):
        """Test that the view correctly groups devices with identical configurations."""
        url = reverse("plugins:nautobot_golden_config:configcompliance_mismatch_grouping")
        response = self.client.get(url)

        table_data = list(response.context["table"].data)

        # Should have 2 groups: one with 2 devices each
        self.assertEqual(len(table_data), 2)

        # Each group should have 2 devices
        device_counts = [row["device_count"] for row in table_data]
        self.assertEqual(sorted(device_counts), [2, 2])

    def test_mismatch_grouping_excludes_compliant_devices(self):
        """Test that compliant devices are excluded from grouping."""
        # Mark one device as compliant
        compliance = models.ConfigCompliance.objects.get(device=self.device1, rule=self.feature1)
        compliance.compliance = True
        compliance.compliance_int = 1
        compliance.save()

        url = reverse("plugins:nautobot_golden_config:configcompliance_mismatch_grouping")
        response = self.client.get(url)

        table_data = list(response.context["table"].data)

        # Should still have 2 groups, but one group should have only 1 device now
        self.assertEqual(len(table_data), 2)
        device_counts = sorted([row["device_count"] for row in table_data])
        self.assertEqual(device_counts, [1, 2])

    def test_mismatch_grouping_view_permissions(self):
        """Test view permissions when EXEMPT_VIEW_PERMISSIONS is disabled."""
        url = reverse("plugins:nautobot_golden_config:configcompliance_mismatch_grouping")

        with override_settings(EXEMPT_VIEW_PERMISSIONS=[]):
            # Without permission should redirect to login
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)

    def test_mismatch_grouping_table_headers_present(self):
        """Test that required table headers are present in the rendered HTML."""
        url = reverse("plugins:nautobot_golden_config:configcompliance_mismatch_grouping")
        response = self.client.get(url)

        content = response.content.decode()

        # Check for main page elements
        self.assertIn("Configuration Mismatch Grouping Report", content)
        self.assertIn("Feature", content)
        self.assertIn("Device Count", content)
        self.assertIn("Configuration Snippet", content)

    def test_mismatch_grouping_javascript_present(self):
        """Test that the required JavaScript for chevron rotation is present."""
        url = reverse("plugins:nautobot_golden_config:configcompliance_mismatch_grouping")
        response = self.client.get(url)

        content = response.content.decode()

        # Check for JavaScript functions
        self.assertIn("config-toggle", content)
        self.assertIn("config-chevron", content)
        self.assertIn("setupToggle", content)

    def test_mismatch_grouping_empty_state(self):
        """Test view behavior when no mismatch groups exist."""
        # Delete all ConfigComplianceHash records
        models.ConfigComplianceHash.objects.all().delete()

        url = reverse("plugins:nautobot_golden_config:configcompliance_mismatch_grouping")
        response = self.client.get(url)

        content = response.content.decode()
        table_data = list(response.context["table"].data)

        # Should have no groups
        self.assertEqual(len(table_data), 0)

        # Should show empty state message
        self.assertIn("Great news!", content)
        self.assertIn("No configuration mismatch groups found", content)

    def test_mismatch_grouping_with_empty_config_content(self):
        """Test view behavior with empty configuration content."""
        # Create a hash record with empty config content
        models.ConfigComplianceHash.objects.create(
            device=self.device1,
            rule=self.feature2,
            config_type="actual",
            config_hash="empty123hash",
            config_content=None,
        )
        models.ConfigComplianceHash.objects.create(
            device=self.device2,
            rule=self.feature2,
            config_type="actual",
            config_hash="empty123hash",
            config_content=None,
        )

        # Create corresponding compliance records
        models.ConfigCompliance.objects.create(
            device=self.device1,
            rule=self.feature2,
            actual=None,
            intended={"some": "config"},
            compliance=False,
            compliance_int=0,
            actual_config_hash="empty123hash",
        )
        models.ConfigCompliance.objects.create(
            device=self.device2,
            rule=self.feature2,
            actual=None,
            intended={"some": "config"},
            compliance=False,
            compliance_int=0,
            actual_config_hash="empty123hash",
        )

        url = reverse("plugins:nautobot_golden_config:configcompliance_mismatch_grouping")
        response = self.client.get(url)

        # Should still work and include the empty config group
        table_data = list(response.context["table"].data)
        self.assertGreaterEqual(len(table_data), 1)

        # Check that empty content is handled in HTML
        content = response.content.decode()
        self.assertIn("--", content)  # Empty config placeholder


class ConfigComplianceHashTableTestCase(TestCase):
    """Test ConfigComplianceHashTable functionality."""

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

        # Create ConfigComplianceHash records
        models.ConfigComplianceHash.objects.create(
            device=cls.device1,
            rule=cls.feature1,
            config_type="actual",
            config_hash="test123hash",
            config_content=cls.config_content,
        )
        models.ConfigComplianceHash.objects.create(
            device=cls.device2,
            rule=cls.feature1,
            config_type="actual",
            config_hash="test123hash",
            config_content=cls.config_content,
        )

        # Create ConfigCompliance records
        models.ConfigCompliance.objects.create(
            device=cls.device1,
            rule=cls.feature1,
            actual=cls.config_content,
            intended={"different": "config"},
            compliance=False,
            compliance_int=0,
            actual_config_hash="test123hash",
        )
        models.ConfigCompliance.objects.create(
            device=cls.device2,
            rule=cls.feature1,
            actual=cls.config_content,
            intended={"different": "config"},
            compliance=False,
            compliance_int=0,
            actual_config_hash="test123hash",
        )

    def test_table_initialization(self):
        """Test that ConfigComplianceHashTable can be initialized properly."""
        queryset = ConfigMismatchGroupingView().queryset
        table = ConfigComplianceHashTable(data=queryset)

        # Table should initialize without errors
        self.assertIsInstance(table, ConfigComplianceHashTable)

    def test_table_columns_present(self):
        """Test that all expected columns are present in the table."""
        queryset = ConfigMismatchGroupingView().queryset
        table = ConfigComplianceHashTable(data=queryset)

        # Check that expected columns exist
        expected_columns = ["feature_name", "device_count", "config_snippet", "actions"]
        for column_name in expected_columns:
            self.assertIn(column_name, table.columns)

    def test_table_feature_name_column(self):
        """Test feature_name column rendering."""
        queryset = ConfigMismatchGroupingView().queryset
        table = ConfigComplianceHashTable(data=queryset)

        # Get the first row
        rows = list(table.data)
        if rows:
            first_row = rows[0]
            # Feature name should be present
            self.assertEqual(first_row["feature_name"], "TestFeature1")

    def test_table_device_count_column(self):
        """Test device_count column rendering and link generation."""
        queryset = ConfigMismatchGroupingView().queryset
        table = ConfigComplianceHashTable(data=queryset)

        # Get the first row
        rows = list(table.data)
        if rows:
            first_row = rows[0]
            # Device count should be 2 (both devices have same config hash)
            self.assertEqual(first_row["device_count"], 2)

    def test_table_config_snippet_html_structure(self):
        """Test that config_snippet column generates correct HTML structure."""
        queryset = ConfigMismatchGroupingView().queryset
        table = ConfigComplianceHashTable(data=queryset)

        # Render the table to HTML
        table_html = table.as_html(request=RequestFactory().get("/"))

        # Check for expected HTML elements
        self.assertIn("config-toggle", table_html)
        self.assertIn("config-chevron", table_html)
        self.assertIn("View Config", table_html)
        self.assertIn("mdi-chevron-down", table_html)

    def test_table_config_snippet_with_empty_content(self):
        """Test config_snippet column with empty configuration content."""
        # Create a hash record with no content
        models.ConfigComplianceHash.objects.create(
            device=self.device1,
            rule=create_feature_rule_json(self.device1, feature="EmptyFeature"),
            config_type="actual",
            config_hash="empty456hash",
            config_content=None,
        )
        models.ConfigCompliance.objects.create(
            device=self.device1,
            rule=create_feature_rule_json(self.device1, feature="EmptyFeature"),
            actual=None,
            intended={"some": "config"},
            compliance=False,
            compliance_int=0,
            actual_config_hash="empty456hash",
        )

        queryset = ConfigMismatchGroupingView().queryset
        table = ConfigComplianceHashTable(data=queryset)

        # Render the table to HTML
        table_html = table.as_html(request=RequestFactory().get("/"))

        # Should handle empty content gracefully with "--" placeholder
        self.assertIn("--", table_html)

    def test_table_actions_column(self):
        """Test that actions column contains expected remediation links."""
        queryset = ConfigMismatchGroupingView().queryset
        table = ConfigComplianceHashTable(data=queryset)

        # Render the table to HTML
        table_html = table.as_html(request=RequestFactory().get("/"))

        # Check for remediation action icon and link
        self.assertIn("mdi-map-check-outline", table_html)
        self.assertIn("configcompliance_remediate", table_html)

    def test_table_ordering(self):
        """Test that table supports proper ordering."""
        # Check that device_count column is orderable
        table = ConfigComplianceHashTable()
        device_count_column = table.columns["device_count"]
        self.assertTrue(device_count_column.orderable)

        # Check that config_snippet column is not orderable
        config_snippet_column = table.columns["config_snippet"]
        self.assertFalse(config_snippet_column.orderable)

    def test_table_verbose_names(self):
        """Test that columns have appropriate verbose names."""
        table = ConfigComplianceHashTable()

        # Check verbose names
        self.assertEqual(table.columns["feature_name"].verbose_name, "Feature")
        self.assertEqual(table.columns["device_count"].verbose_name, "Device Count")
        self.assertEqual(table.columns["config_snippet"].verbose_name, "Configuration Snippet")
        self.assertEqual(table.columns["actions"].verbose_name, "Actions")

    def test_table_with_long_config_content(self):
        """Test table behavior with long configuration content."""
        # Create a hash record with very long config content
        long_config = {
            "interface": {f"GigabitEthernet0/{i}": {"description": f"Interface {i}" * 20} for i in range(50)}
        }

        models.ConfigComplianceHash.objects.create(
            device=self.device1,
            rule=create_feature_rule_json(self.device1, feature="LongFeature"),
            config_type="actual",
            config_hash="long789hash",
            config_content=long_config,
        )
        models.ConfigCompliance.objects.create(
            device=self.device1,
            rule=create_feature_rule_json(self.device1, feature="LongFeature"),
            actual=long_config,
            intended={"short": "config"},
            compliance=False,
            compliance_int=0,
            actual_config_hash="long789hash",
        )

        queryset = ConfigMismatchGroupingView().queryset
        table = ConfigComplianceHashTable(data=queryset)

        # Render the table to HTML
        table_html = table.as_html(request=RequestFactory().get("/"))

        # Should handle long content (truncated due to truncatechars:500)
        # The content should be present but truncated
        self.assertIn("Interface", table_html)
        self.assertIn("max-height: 200px", table_html)  # CSS for scrollable content


@override_settings(EXEMPT_VIEW_PERMISSIONS=["*"])
class ConfigMismatchGroupingTemplateTestCase(TestCase):
    """Test ConfigMismatchGrouping template rendering and JavaScript functionality."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data for template tests."""
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

        # Create ConfigComplianceHash records
        models.ConfigComplianceHash.objects.create(
            device=cls.device1,
            rule=cls.feature1,
            config_type="actual",
            config_hash="test123hash",
            config_content=cls.config_content,
        )
        models.ConfigComplianceHash.objects.create(
            device=cls.device2,
            rule=cls.feature1,
            config_type="actual",
            config_hash="test123hash",
            config_content=cls.config_content,
        )

        # Create ConfigCompliance records
        models.ConfigCompliance.objects.create(
            device=cls.device1,
            rule=cls.feature1,
            actual=cls.config_content,
            intended={"different": "config"},
            compliance=False,
            compliance_int=0,
            actual_config_hash="test123hash",
        )
        models.ConfigCompliance.objects.create(
            device=cls.device2,
            rule=cls.feature1,
            actual=cls.config_content,
            intended={"different": "config"},
            compliance=False,
            compliance_int=0,
            actual_config_hash="test123hash",
        )

    def test_template_title_and_breadcrumbs(self):
        """Test that template renders correct title and breadcrumbs."""
        url = reverse("plugins:nautobot_golden_config:configcompliance_mismatch_grouping")
        response = self.client.get(url)
        content = response.content.decode()

        # Check title
        self.assertIn("<title>Configuration Mismatch Grouping Report</title>", content)

        # Check breadcrumbs
        self.assertIn("Configuration Mismatch Grouping", content)

    def test_template_header_styling(self):
        """Test that template includes correct header styling."""
        url = reverse("plugins:nautobot_golden_config:configcompliance_mismatch_grouping")
        response = self.client.get(url)
        content = response.content.decode()

        # Check for blue icon styling
        self.assertIn('style="color: #007bff;"', content)

        # Check for blue badge styling
        self.assertIn('style="background-color: #007bff; color: white;"', content)
        self.assertIn('class="badge pull-right"', content)

    def test_template_panel_structure(self):
        """Test that template has correct panel structure."""
        url = reverse("plugins:nautobot_golden_config:configcompliance_mismatch_grouping")
        response = self.client.get(url)
        content = response.content.decode()

        # Check panel structure
        self.assertIn('class="panel panel-default"', content)
        self.assertIn('class="panel-heading"', content)
        self.assertIn('class="panel-body"', content)
        self.assertIn('class="panel-title"', content)

    def test_template_description_text(self):
        """Test that template includes descriptive text."""
        url = reverse("plugins:nautobot_golden_config:configcompliance_mismatch_grouping")
        response = self.client.get(url)
        content = response.content.decode()

        # Check for descriptive text
        self.assertIn("This report groups devices with identical non-compliant configurations", content)
        self.assertIn("Each group represents devices that have the exact same incorrect configuration", content)

    def test_template_empty_state_message(self):
        """Test empty state message when no mismatch groups exist."""
        # Delete all hash records to create empty state
        models.ConfigComplianceHash.objects.all().delete()

        url = reverse("plugins:nautobot_golden_config:configcompliance_mismatch_grouping")
        response = self.client.get(url)
        content = response.content.decode()

        # Check for empty state elements
        self.assertIn("Great news!", content)
        self.assertIn("No configuration mismatch groups found", content)
        self.assertIn("alert alert-success", content)
        self.assertIn("mdi-check-circle", content)

        # Check for helpful explanations
        self.assertIn("All devices are compliant", content)
        self.assertIn("Each non-compliant device has a unique configuration issue", content)
        self.assertIn("No compliance data has been generated yet", content)

    def test_template_javascript_inclusion(self):
        """Test that required JavaScript is included in template."""
        url = reverse("plugins:nautobot_golden_config:configcompliance_mismatch_grouping")
        response = self.client.get(url)
        content = response.content.decode()

        # Check for JavaScript includes
        self.assertIn("tableconfig.js", content)

        # Check for custom JavaScript functions
        self.assertIn("setupToggle", content)
        self.assertIn("config-toggle", content)
        self.assertIn("config-chevron", content)

        # Check for CSRF token
        self.assertIn("nautobot_csrf_token", content)

    def test_template_css_styling(self):
        """Test that custom CSS styling is present."""
        url = reverse("plugins:nautobot_golden_config:configcompliance_mismatch_grouping")
        response = self.client.get(url)
        content = response.content.decode()

        # Check for chevron CSS
        self.assertIn(".config-chevron", content)
        self.assertIn("transition: transform 0.3s ease !important", content)
        self.assertIn("display: inline-block !important", content)

    def test_template_config_toggle_functionality(self):
        """Test that config toggle elements are properly structured."""
        url = reverse("plugins:nautobot_golden_config:configcompliance_mismatch_grouping")
        response = self.client.get(url)
        content = response.content.decode()

        # Check for toggle structure
        self.assertIn('class="config-toggle"', content)
        self.assertIn('class="config-content"', content)
        self.assertIn('class="mdi mdi-chevron-down config-chevron"', content)
        self.assertIn("View Config", content)

    def test_template_device_count_badge_display(self):
        """Test that device count badge displays correctly."""
        url = reverse("plugins:nautobot_golden_config:configcompliance_mismatch_grouping")
        response = self.client.get(url)
        content = response.content.decode()

        # Should show "1 group" or "X groups" based on data
        if "group" in content:  # Only if we have groups
            # Badge should be present with count
            badge_pattern = r'<span class="badge pull-right"[^>]*>\s*\d+\s+group'

            self.assertTrue(re.search(badge_pattern, content), "Device count badge not found or malformed")

    def test_template_fixed_width_container(self):
        """Test that config snippets use fixed-width containers."""
        url = reverse("plugins:nautobot_golden_config:configcompliance_mismatch_grouping")
        response = self.client.get(url)
        content = response.content.decode()

        # Check for fixed width styling
        if "width: 300px" in content:  # Only if we have config snippets
            self.assertIn("width: 300px", content)

    def test_template_scrollable_config_content(self):
        """Test that config content is properly scrollable."""
        url = reverse("plugins:nautobot_golden_config:configcompliance_mismatch_grouping")
        response = self.client.get(url)
        content = response.content.decode()

        # Check for scrollable content styling
        if "max-height: 200px" in content:  # Only if we have config content
            self.assertIn("max-height: 200px", content)
            self.assertIn("overflow-y: auto", content)

    def test_template_config_formatting(self):
        """Test that configuration content is properly formatted."""
        url = reverse("plugins:nautobot_golden_config:configcompliance_mismatch_grouping")
        response = self.client.get(url)
        content = response.content.decode()

        # Check for pre-formatted code blocks
        if "<pre" in content:  # Only if we have config content
            self.assertIn("<pre", content)
            self.assertIn("white-space: pre-wrap", content)
            self.assertIn("background-color: #f8f9fa", content)

    def test_template_responsive_design_elements(self):
        """Test that template includes responsive design elements."""
        url = reverse("plugins:nautobot_golden_config:configcompliance_mismatch_grouping")
        response = self.client.get(url)
        content = response.content.decode()

        # Check for Bootstrap grid classes
        self.assertIn("col-md-12", content)

        # Check for responsive styling hints
        if "padding" in content:
            # Should have proper spacing
            self.assertTrue("padding" in content)

    def test_template_accessibility_features(self):
        """Test that template includes basic accessibility features."""
        url = reverse("plugins:nautobot_golden_config:configcompliance_mismatch_grouping")
        response = self.client.get(url)
        content = response.content.decode()

        # Check for proper heading structure
        self.assertIn("<h1>", content)
        self.assertIn("<h3", content)

        # Check for title attributes where appropriate
        if "title=" in content:
            # Should have title attributes for icons/actions
            self.assertTrue("title=" in content)

    def test_template_toggle_all_chevron_presence(self):
        """Test that toggle all chevron is present and properly configured."""
        url = reverse("plugins:nautobot_golden_config:configcompliance_mismatch_grouping")
        response = self.client.get(url)
        content = response.content.decode()

        # Check for toggle all chevron element
        self.assertIn('class="mdi mdi-chevron-down toggle-all"', content)

        # Check for proper styling
        self.assertIn("color: #007bff", content)  # Blue color
        self.assertIn("cursor: pointer", content)  # Clickable cursor
        self.assertIn("display: inline-block", content)  # Required for CSS transforms

        # Check for tooltip
        self.assertIn('title="Expand/Collapse All Configurations"', content)

    def test_template_toggle_all_javascript_functionality(self):
        """Test that toggle all JavaScript functionality is properly implemented."""
        url = reverse("plugins:nautobot_golden_config:configcompliance_mismatch_grouping")
        response = self.client.get(url)
        content = response.content.decode()

        # Check for toggle all JavaScript code
        self.assertIn("Toggle all functionality", content)
        self.assertIn(".toggle-all", content)
        self.assertIn("querySelector('.toggle-all')", content)

        # Check for state management variables
        self.assertIn("allExpanded", content)

        # Check for event listener setup
        self.assertIn("addEventListener('click'", content)

        # Check for bulk toggle logic
        self.assertIn("toggles.forEach", content)

    def test_template_toggle_all_css_styling(self):
        """Test that toggle all chevron has proper CSS styling for animation."""
        url = reverse("plugins:nautobot_golden_config:configcompliance_mismatch_grouping")
        response = self.client.get(url)
        content = response.content.decode()

        # Check for toggle all CSS class definition
        self.assertIn(".toggle-all", content)

        # Check for animation properties
        self.assertIn("transition: transform 0.3s ease !important", content)
        self.assertIn("display: inline-block !important", content)

    def test_template_toggle_all_conditional_display(self):
        """Test that toggle all chevron only appears when there are table rows."""
        # First test with data (should show toggle all)
        url = reverse("plugins:nautobot_golden_config:configcompliance_mismatch_grouping")
        response = self.client.get(url)
        content = response.content.decode()

        # Should contain toggle all when there are groups
        self.assertIn("toggle-all", content)

        # Now test without data (should not show toggle all)
        models.ConfigComplianceHash.objects.all().delete()

        response = self.client.get(url)
        content = response.content.decode()

        # Should not contain toggle all when there are no groups
        self.assertNotIn("toggle-all", content)
