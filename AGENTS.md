# Developer Agent Guide for octoDNS Google Cloud Provider

This repository contains the Google Cloud DNS provider for octoDNS. It enables planning, syncing, and applying DNS record states directly to Google Cloud DNS using the official `google-cloud-dns` client library.

> [!IMPORTANT]
> **Core Workflow and Guidelines**
>
> All agents working on this repository must read and follow the general instructions and workflow guidelines defined in the core octoDNS `AGENTS.md` file.
> - **Local check**: Look for the file at `../octodns/AGENTS.md`.
> - **Remote check**: If the local file is not available, fetch it from GitHub: [octoDNS Core AGENTS.md](https://github.com/octodns/octodns/raw/refs/heads/main/AGENTS.md).
>
> You must align your code structure, style, pull request guidelines, and overall development workflows with the instructions specified there.

## Repository & Module Information

### Key Components

- **Provider Class**: [GoogleCloudProvider](file:///home/ross/octodns/octodns-googlecloud/octodns_googlecloud/__init__.py#L42-L543) (defined in [octodns_googlecloud/__init__.py](file:///home/ross/octodns/octodns-googlecloud/octodns_googlecloud/__init__.py)). This class integrates with Google Cloud DNS using `google.cloud.dns`.
- **Authentication**: Supports explicit service account credentials files (`credentials_file`) or fallback to Google Cloud application default credentials.
- **Private Zone Support**: Configured via the `private` initialization argument to plan/apply changes to GCP private zones.
- **Record Batching**: Changes are grouped into transaction batches configured by `batch_size` (defaults to `1000`) for high-performance updates.

### Key Workflows & Features

1. **Supported Record Types**: `A`, `AAAA`, `ALIAS`, `CAA`, `CNAME`, `DS`, `MX`, `NAPTR`, `NS`, `PTR`, `SPF`, `SRV`, and `TXT`.
2. **Root Name Server Support**: Fully supports managing root NS records (`SUPPORTS_ROOT_NS=True`).
3. **Trailing Dots handling**: Handles automatic normalization of trailing dots for record targets as required by GCP API.
4. **Dynamic Routing**: Not supported (`SUPPORTS_DYNAMIC=False`, `SUPPORTS_GEO=False`).
5. **Dynamic Subnets**: Not supported (`SUPPORTS_DYNAMIC_SUBNETS=False`).
6. **Pool Value Status**: Not supported (`SUPPORTS_POOL_VALUE_STATUS=False`).

## Development & Testing

- **Setup Script**: Run `./script/bootstrap` to create a virtual environment, install runtime and development dependencies (including `black`, `isort`, `pyflakes`, and `pytest`), and configure pre-commit hooks.
- **Test Suite**: Run unit tests using `pytest` via `./script/test` (or `pytest tests/`). Test files are located in [tests/](file:///home/ross/octodns/octodns-googlecloud/tests).
- **Code Coverage**: Verify code coverage using `./script/coverage`.

## Key Constraints & Behaviors

- **Python Version**: Targets Python `>=3.9`.
- **Formatting**: Code formatting is enforced via `black` (version `>=26.0.0,<27.0.0`) and `isort`.
