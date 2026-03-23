"""Quickly deploy a local lab environment for developing on the Golden Config app."""

import os
from typing import Dict, List

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import DEFAULT_DB_ALIAS
from django.db.utils import IntegrityError
from nautobot.dcim.models import Platform
from nautobot.dcim.models.devices import Device, DeviceType, Manufacturer
from nautobot.dcim.models.locations import Location, LocationType
from nautobot.extras.models import DynamicGroup, GraphQLQuery
from nautobot.extras.models.datasources import GitRepository
from nautobot.extras.models.jobs import Job
from nautobot.extras.models.roles import Role
from nautobot.extras.models.statuses import Status

from nautobot_golden_config.models import ComplianceFeature, ComplianceRule, GoldenConfigSetting, RemediationSetting

VENDOR_CONFIGS = {
    "nokia": {
        "manufacturer": "Nokia",
        "platform_name": "srlinux",
        "napalm_driver": "nokia_srl",
        "network_driver": "nokia_srl",
        "device_type_model": "srlinux",
        "device_name_prefix": "srl",
        "features": {"DNS": "dns", "NTP": "ntp", "SNMP": "snmp"},
        "remediation_type": "hierconfig",
        "interfaces": [
            {"name": "ethernet-1/1", "type": "100base-tx"},
            {"name": "ethernet-1/2", "type": "100base-tx"},
            {"name": "lo0", "type": "virtual"},
            {"name": "mgmt0", "type": "100base-tx", "mgmt_only": True},
        ],
    },
    "arista": {
        "manufacturer": "Arista",
        "platform_name": "ceos",
        "napalm_driver": "eos",
        "network_driver": "arista_eos",
        "device_type_model": "ceos",
        "device_name_prefix": "ceos",
        "features": {"DNS": "dns", "NTP": "ntp server", "SNMP": "snmp-server"},
        "remediation_type": "hierconfig",
        "interfaces": [
            {"name": "Ethernet1", "type": "100base-tx"},
            {"name": "Ethernet2", "type": "100base-tx"},
            {"name": "Loopback0", "type": "virtual"},
            {"name": "Management1", "type": "100base-tx", "mgmt_only": True},
        ],
    },
}


class Command(BaseCommand):
    """Populate the database with default static data to use in a local dev enviroment."""

    help = __doc__

    def __init__(self, *args, **kwargs):
        """Initialize the command."""
        super().__init__(*args, **kwargs)
        self.features: Dict[str, str] = {}
        self.git_url: str = os.getenv("GIT_URL", "http://git-server:3000/gclab")
        self.device_name_prefix: str = ""
        self.devices: List[str] = []
        self.device_count: int = 4  # Default to creating 4 devices
        self.interfaces: list = []
        self.vendor_config: dict = {}

    def add_arguments(self, parser):  # noqa: D102
        parser.add_argument(
            "--database",
            default=DEFAULT_DB_ALIAS,
            help='The database to generate the test data in. Defaults to the "default" database.',
        )
        parser.add_argument(
            "--device-count",
            default=1,
            help="Define how many lab devices to create.",
        )
        parser.add_argument(
            "--vendor",
            default="nokia",
            choices=list(VENDOR_CONFIGS.keys()),
            help='Vendor platform to provision. Defaults to "nokia".',
        )

    def _deploy_local_lab(self, db: str):
        """Deploy a local lab environment for developing on the Golden Config app."""
        status_active_obj = Status.objects.get(name="Active")
        ct_device_obj = ContentType.objects.get(model="device")

        # --- 1. Create LocationType and Location --- #
        try:
            location_type_obj, _ = LocationType.objects.using(db).get_or_create(name="Main")
            location_type_obj.content_types.add(ct_device_obj)
            location_type_obj.validated_save()
            self.stdout.write(self.style.SUCCESS(f"Location Type {location_type_obj} created"))
        except Exception as e:
            self.stderr.write(str(e))
            self.stdout.write(self.style.ERROR("Error creating Location Type"))

        try:
            location_obj, _ = Location.objects.get_or_create(
                name="Data Center 1", location_type=location_type_obj, status=status_active_obj
            )
            self.stdout.write(self.style.SUCCESS(f"Location {location_obj} created"))
        except Exception as e:
            self.stderr.write(str(e))
            self.stdout.write(self.style.ERROR("Error creating Location"))

        # --- 2. Device Role --- #
        try:
            role_obj, _ = Role.objects.using(db).get_or_create(name="Lab Leaf", color="0000ff")
            role_obj.content_types.add(ct_device_obj)
            role_obj.validated_save()
            self.stdout.write(self.style.SUCCESS(f"Device Role {role_obj} created"))
        except IntegrityError:
            pass  # Role already exists
            self.stdout.write(self.style.ERROR("Error creating Device Role"))

        # --- 3. Manufacturer --- #
        try:
            mfg_obj, _ = Manufacturer.objects.using(db).get_or_create(name=self.vendor_config["manufacturer"])
            self.stdout.write(self.style.SUCCESS(f"Manufacturer {mfg_obj} created"))
        except Exception as e:
            self.stderr.write(str(e))
            self.stdout.write(self.style.ERROR("Error creating Manufacturer"))

        # --- 4. Platform --- #
        try:
            platform_kwargs = {
                "name": self.vendor_config["platform_name"],
                "manufacturer": mfg_obj,
                "network_driver": self.vendor_config["network_driver"],
            }
            if self.vendor_config["napalm_driver"]:
                platform_kwargs["napalm_driver"] = self.vendor_config["napalm_driver"]
            platform_obj, _ = Platform.objects.using(db).get_or_create(**platform_kwargs)
            self.stdout.write(self.style.SUCCESS(f"Platform {platform_obj} created"))
        except Exception as e:
            self.stderr.write(str(e))
            self.stdout.write(self.style.ERROR("Error creating Platform"))

        # --- 5. Device Type and Interfaces --- #
        try:
            device_type_obj, _ = DeviceType.objects.using(db).get_or_create(model=self.vendor_config["device_type_model"], manufacturer=mfg_obj)
            for interface in self.interfaces:
                try:
                    device_type_obj.interface_templates.create(
                        name=interface["name"], type=interface["type"], mgmt_only=interface.get("mgmt_only", False)
                    )
                except IntegrityError:
                    pass  # Interface already exists
            device_type_obj.validated_save()
            self.stdout.write(self.style.SUCCESS(f"Device Type {device_type_obj} created"))
        except Exception as e:
            self.stderr.write(str(e))
            self.stdout.write(self.style.ERROR("Error creating Device Type and Interfaces"))

        # --- 6. Devices --- #
        device_objects = []
        try:
            for device_name in self.devices:
                device_obj, _ = Device.objects.using(db).get_or_create(
                    name=device_name,
                    device_type=device_type_obj,
                    role=role_obj,
                    platform=platform_obj,
                    location=location_obj,
                    status=status_active_obj,
                )
                device_objects.append(device_obj)
            self.stdout.write(self.style.SUCCESS(f"Devices {', '.join([d.name for d in device_objects])} created"))
        except Exception as e:
            self.stderr.write(str(e))
            self.stdout.write(self.style.ERROR("Error creating Devices"))

        # --- 7. Git Repository --- #
        try:
            git_repo_obj, _ = GitRepository.objects.using(db).get_or_create(
                name="localgit",
                remote_url=self.git_url,
                branch="main",
                provided_contents=[
                    "nautobot_golden_config.backupconfigs",
                    "nautobot_golden_config.jinjatemplate",
                    "nautobot_golden_config.intendedconfigs",
                    "extras.configcontext",
                    "extras.configcontextschema",
                ],
            )
            self.stdout.write(self.style.SUCCESS(f"Git Repository {git_repo_obj} created"))
        except Exception as e:
            self.stderr.write(str(e))
            self.stdout.write(self.style.ERROR("Error creating Git Repository"))

        # --- 8. Remediation Setting --- #
        try:
            gc_remediation_obj, _ = RemediationSetting.objects.using(db).get_or_create(
                platform=platform_obj, remediation_type=self.vendor_config["remediation_type"]
            )
            self.stdout.write(self.style.SUCCESS(f"Remediation Setting {gc_remediation_obj} created"))
        except Exception as e:
            self.stderr.write(str(e))
            self.stdout.write(self.style.ERROR("Error creating Remediation Setting"))

        # --- 9. Compliance Features and Rules --- #
        try:
            for feature in self.features:
                gc_feature_obj, _ = ComplianceFeature.objects.using(db).get_or_create(
                    name=feature, slug=feature.lower()
                )

                gc_rule_obj, _ = ComplianceRule.objects.using(db).get_or_create(
                    feature=gc_feature_obj,
                    platform=platform_obj,
                    match_config=self.features[feature],
                    config_remediation=True,
                )
                self.stdout.write(
                    self.style.SUCCESS(f"Compliance Feature {gc_feature_obj} and Rule {gc_rule_obj} created")
                )
        except Exception as e:
            self.stderr.write(str(e))
            self.stdout.write(self.style.ERROR("Error creating Compliance Features and Rules"))

        # --- 10. Enable Golden Config Jobs --- #
        try:
            Job.objects.filter(enabled=False).update(enabled=True)
            self.stdout.write(self.style.SUCCESS("Golden Config Jobs enabled"))
        except Exception as e:
            self.stderr.write(str(e))
            self.stdout.write(self.style.ERROR("Error enabling Golden Config Jobs"))

        # --- 11. GraphQL Query --- #
        graphql_query = """
            query ($device_id: ID!) {
              device(id: $device_id) {
                config_context
                hostname: name
                interfaces {
                  name
                }
                device_type { model }
                role { name }
                platform { name }
                location { name }
                tags { name }
              }
            }
            """

        try:
            gql_query_obj, _ = GraphQLQuery.objects.using(db).get_or_create(
                name="Golden Config Lab Query",
                query=graphql_query,
            )
            self.stdout.write(self.style.SUCCESS(f"GraphQL Query {gql_query_obj} created"))
        except Exception as e:
            self.stderr.write(str(e))
            self.stdout.write(self.style.ERROR("Error creating GraphQL Query"))

        # --- 13. Update Dynamic Group for Golden Config --- #
        try:
            dynamic_group_obj, _ = DynamicGroup.objects.using(db).get_or_create(
                name="GoldenConfigSetting Lab Settings scope",
                group_type="dynamic-filter",
                content_type_id=ct_device_obj.id,
                filter={"platform": [self.vendor_config["platform_name"]]},
            )
            self.stdout.write(self.style.SUCCESS(f"Dynamic Group {dynamic_group_obj} created"))
        except Exception as e:
            self.stderr.write(str(e))
            self.stdout.write(self.style.ERROR("Error creating Dynamic Group"))

        # --- 14. Update Golden Config settings --- #
        try:
            GoldenConfigSetting.objects.using(db).get_or_create(
                name="Lab Settings",
                slug="lab-settings",
                weight=2000,
                dynamic_group_id=dynamic_group_obj.id,
                backup_repository=git_repo_obj,
                intended_repository=git_repo_obj,
                jinja_repository=git_repo_obj,
                sot_agg_query=gql_query_obj,
                backup_path_template="backups/{{ obj.name }}.cfg",
                intended_path_template="intended/{{ obj.name }}.cfg",
                jinja_path_template="templates/{{ obj.platform.network_driver }}.j2",
            )
            self.stdout.write(self.style.SUCCESS("Lab Golden Config Settings updated"))
        except Exception as e:
            self.stderr.write(str(e))
            self.stdout.write(self.style.ERROR("Error creating Lab Golden Config Settings"))

    def handle(self, *args, **options):
        """Entry point to the management command."""
        self.stdout.write(f"options: {options}")

        # Apply vendor config
        vendor = options["vendor"]
        self.vendor_config = VENDOR_CONFIGS[vendor]
        self.features = self.vendor_config["features"]
        self.interfaces = self.vendor_config["interfaces"]
        self.device_name_prefix = os.getenv("DEVICE_NAME_PREFIX", self.vendor_config["device_name_prefix"])

        if options["device_count"]:
            try:
                if int(options["device_count"]) < 1:
                    raise ValueError
            except ValueError:
                self.stdout.write(self.style.ERROR("Please define --device-count as a positive integer"))
                return
            self.device_count = int(options["device_count"])

        self.stdout.write(f"This command will create {options['device_count']} {vendor} devices in Nautobot.")
        self.devices = [f"{self.device_name_prefix}{i+1}" for i in range(int(options["device_count"]))]

        self._deploy_local_lab(db=options["database"])

        self.stdout.write(self.style.SUCCESS(f"Database {options['database']} populated with lab device data!"))
