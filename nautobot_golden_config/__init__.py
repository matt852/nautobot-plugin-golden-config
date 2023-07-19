"""Plugin declaration for nautobot_golden_config."""
# Metadata is inherited from Nautobot. If not including Nautobot in the environment, this should be added
try:
    from importlib import metadata
except ImportError:
    # Python version < 3.8
    import importlib_metadata as metadata

__version__ = metadata.version(__name__)

from django.db.models.signals import post_migrate
from nautobot.extras.plugins import PluginConfig


class GoldenConfig(PluginConfig):
    """Plugin configuration for the nautobot_golden_config plugin."""

    name = "nautobot_golden_config"
    verbose_name = "Golden Configuration"
    version = __version__
    author = "Network to Code, LLC"
    author_email = "opensource@networktocode.com"
    description = "Nautobot Apps that embraces NetDevOps and automates configuration backups, performs configuration compliance, and generates intended configurations. Includes native Git integration and gives users the flexibility to mix and match the supported features."
    base_url = "golden-config"
    min_version = "1.5.3"
    max_version = "1.99"
    default_settings = {
        "enable_backup": True,
        "enable_compliance": True,
        "enable_intended": True,
        "enable_sotagg": True,
        "enable_postprocessing": False,
        "postprocessing_callables": [],
        "postprocessing_subscribed": [],
        "per_feature_bar_width": 0.3,
        "per_feature_width": 13,
        "per_feature_height": 4,
        "get_custom_compliance": None,
        "enable_config_context_sync": False,
    }

    def ready(self):
        """Register custom signals."""
        import nautobot_golden_config.jobs  # pylint: disable=unused-import, import-outside-toplevel
        from nautobot_golden_config.models import ConfigCompliance  # pylint: disable=import-outside-toplevel

        from .signals import config_compliance_platform_cleanup  # pylint: disable=import-outside-toplevel

        super().ready()
        post_migrate.connect(config_compliance_platform_cleanup, sender=ConfigCompliance)


config = GoldenConfig  # pylint:disable=invalid-name
