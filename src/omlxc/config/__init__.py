"""Public configuration and migration API."""

from .io import (
    AtomicRollbackError,
    AtomicWriteError,
    AtomicWriteResult,
    render_toml,
    write_config_atomic,
)
from .loading import (
    ConfigError,
    default_config_directory,
    default_config_path,
    load_config,
    load_user_config,
    safe_defaults,
)
from .migration import MigrationPlan, build_migration_plan, migrate_legacy_json
from .schema import (
    AppConfig,
    BackendConfig,
    DaemonConfig,
    ModelConfig,
    NodeConfig,
    PlacementConfig,
    PoliciesConfig,
    RemoteResidentConfig,
    StorageConfig,
    TailscaleConfig,
    TailscaleNodePolicyConfig,
)

__all__ = [
    "AppConfig",
    "AtomicWriteError",
    "AtomicRollbackError",
    "AtomicWriteResult",
    "BackendConfig",
    "ConfigError",
    "DaemonConfig",
    "MigrationPlan",
    "ModelConfig",
    "NodeConfig",
    "PlacementConfig",
    "PoliciesConfig",
    "RemoteResidentConfig",
    "StorageConfig",
    "TailscaleConfig",
    "TailscaleNodePolicyConfig",
    "build_migration_plan",
    "default_config_directory",
    "default_config_path",
    "load_config",
    "load_user_config",
    "migrate_legacy_json",
    "render_toml",
    "safe_defaults",
    "write_config_atomic",
]
