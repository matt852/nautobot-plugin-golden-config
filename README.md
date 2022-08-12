# Nautobot Golden Config

<p align="center">
  <img src="https://raw.githubusercontent.com/nautobot/nautobot-plugin-golden-config/develop/docs/images/icon-NautobotGoldenConfig.png" class="logo" height="200px">
  <br>
  <a href="https://github.com/nautobot/nautobot-plugin-golden-config/actions"><img src="https://github.com/nautobot/nautobot-plugin-golden-config/actions/workflows/ci.yml/badge.svg?branch=main"></a>
  <!-- TODO: uncomment after RTD project is up! <a href="https://docs.nautobot.com/projects/golden-config/en/latest/"><img src="https://readthedocs.org/projects/golden-config/badge/"></a> -->
  <a href="https://pypi.org/project/nautobot-golden-config/"><img src="https://img.shields.io/pypi/v/nautobot-golden-config"></a>
  <a href="https://pypi.org/project/nautobot-golden-config/"><img src="https://img.shields.io/pypi/dm/nautobot-golden-config"></a>
  <br>
  An App for <a href="https://github.com/nautobot/nautobot">Nautobot</a>.
</p>

## Overview

The Golden Config plugin is a Nautobot plugin that provides a NetDevOps approach to golden configuration and configuration compliance.

### Key Use Cases

This plugin enable four (4) key use cases.

1. **Configuration Backups** - Is a Nornir process to connect to devices, optionally parse out lines/secrets, backup the configuration, and save to a Git repository.
2. **Intended Configuration** - Is a Nornir process to generate configuration based on a Git repo of Jinja files to combine with a GraphQL generated data and a Git repo to store the intended configuration.
3. **Source of Truth Aggregation** - Is a GraphQL query per device that creates a data structure used in the generation of configuration.
4. **Configuration Compliance** - Is a process to run comparison of the actual (via backups) and intended (via Jinja file creation) CLI configurations upon saving the actual and intended configuration. This is started by either a Nornir process for cli-like configurations or calling the API for json-like configurations

> Notice: The operators of their own Nautobot instance are welcome to use any combination of these features. Though the appearance may seem like they are tightly coupled, this isn't actually the case. For example, one can obtain backup configurations from their current RANCID/Oxidized process and simply provide a Git Repo of the location of the backup configurations, and the compliance process would work the same way. Also, another user may only want to generate configurations, but not want to use other features, which is perfectly fine to do so.

## Screenshots

There are many features and capabilities the plugin provides into the Nautobot ecosystem. The following screenshots are intended to provide a quick visual overview of some of these features.

The golden configuration is driven by jobs that run a series of tasks and the result is captured in this overview.

![Overview](https://raw.githubusercontent.com/nautobot/nautobot-plugin-golden-config/develop/docs/images/ss_golden-overview.png)

The compliance report provides a high-level overview on the compliance of your network.
![Compliance Report](https://raw.githubusercontent.com/nautobot/nautobot-plugin-golden-config/develop/docs/images/ss_compliance-report.png)

The compliance overview will provide a per device and feature overview on the compliance of your network devices.
![Compliance Overview](https://raw.githubusercontent.com/nautobot/nautobot-plugin-golden-config/develop/docs/images/ss_compliance-overview.png)

Drilling into a specific device and feature, you can get an immediate detailed understanding of your device.
![Compliance Device](https://raw.githubusercontent.com/nautobot/nautobot-plugin-golden-config/develop/docs/images/ss_compliance-device.png)

![Compliance Rule](https://raw.githubusercontent.com/nautobot/nautobot-plugin-golden-config/develop/docs/images/ss_compliance-rule.png)

## Try it out!

This App is installed in the Nautobot Community Sandbox found over at [demo.nautobot.com](https://demo.nautobot.com/)!

> For a full list of all the available always-on sandbox environments, head over to the main page on [networktocode.com](https://www.networktocode.com/nautobot/sandbox-environments/).

## Documentation

- [User Guide](./docs/user/app_overview.md) - Overview, Using the App, Getting Started, Navigating compliance (cli, json, custom), backup, app usage, intended state creation.
- [Administrator Guide](./docs/admin/admin_install.md) - How to Install, Configure, Upgrade, or Uninstall the App.
- [Developer Guide](./docs/dev/dev_contributing.md) - Extending the App, Code Reference, Contribution Guide.
- [Release Notes / Changelog](./docs/admin/release_notes/)
- [Frequently Asked Questions](./docs/user/app_faq.md) 

<!--  Uncomment out once docs are updated.
Full web-based HTML documentation for this app can be found over on the [Nautobot Docs](https://docs.nautobot.com/projects/golden-config/en/latest/) website:

- [User Guide](https://docs.nautobot.com/projects/golden-config/en/latest/user/app_overview/) - Overview, Using the App, Getting Started, Navigating compliance (cli, json, custom), backup, app usage, intended state creation.
- [Administrator Guide](https://docs.nautobot.com/projects/golden-config/en/latest/admin/admin_install/) - How to Install, Configure, Upgrade, or Uninstall the App.
- [Developer Guide](https://docs.nautobot.com/projects/golden-config/en/latest/dev/dev_contributing/) - Extending the App, Code Reference, Contribution Guide.
- [Release Notes / Changelog](https://docs.nautobot.com/projects/golden-config/en/latest/admin/release_notes/)
- [Frequently Asked Questions](https://docs.nautobot.com/projects/golden-config/en/latest/user/app_faq/) 
-->

### Contributing to the Docs

You can find all the Markdown source for the App documentation under the [docs](https://github.com/nautobot/nautobot-plugin-golden-config/tree/develop/docs) folder in this repository. Any PRs with fixes or improvements are very welcome!


<!-- Uncomment out once docs are released
Project documentation is generated by [mkdocs](https://www.mkdocs.org/) from the documentation located in the docs folder. A container hosting the docs will be started using the invoke commands (details in the [Development Environment Guide](https://docs.nautobot.com/projects/golden-config/en/latest/dev/dev_environment/)) on [http://localhost:8001](http://localhost:8001), as changes are saved the docs will be automatically reloaded. 
-->

Project documentation is generated by [mkdocs](https://www.mkdocs.org/) from the documentation located in the docs folder. A container hosting the docs will be started using the invoke commands (details in the [Development Environment Guide](./docs/dev/dev_environment.md)) or on [http://localhost:8001](http://localhost:8001), as changes are saved the docs will be automatically reloaded.

## Questions

<!-- Uncomment out once docs are released
 For any questions or comments, please check the [FAQ](https://docs.nautobot.com/projects/golden-config/en/latest/user/app_faq/) first. Feel free to also swing by the [Network to Code slack channel](https://networktocode.slack.com/) (channel #nautobot), sign up [here](http://slack.networktocode.com/).
 -->
 
For any questions or comments, please check the [FAQ](./docs/user/app_faq.md/) first. Feel free to also swing by the [Network to Code slack channel](https://networktocode.slack.com/) (channel #nautobot), sign up [here](http://slack.networktocode.com/).


