"""Regression tests for keeping L0 protocol metadata free of runtime observations."""

from runtime.protocol import L0_PROTOCOLS, registry_path


VOLATILE_TOKENS = (
    "pid ",
    "docker container",
    "integration-agora-1",
    "currently idle",
    "scheduled jobs",
    "tick_interval",
    "launchd label",
)


def test_protocol_registry_yaml_exists():
    """The version-controlled YAML registry must exist."""
    assert registry_path().exists()


def test_protocol_entries_do_not_embed_runtime_observations():
    """L0 protocol metadata should not hardcode transient runtime facts."""
    for entry in L0_PROTOCOLS:
        text_parts = [entry.description, entry.notes, *entry.implementations]
        normalized = " ".join(part.lower() for part in text_parts if part)
        for token in VOLATILE_TOKENS:
            assert token not in normalized, (
                f"{entry.name} contains volatile token: {token}"
            )


def test_runtime_matrix_protocol_points_to_env_backed_source():
    """Runtime Matrix should stay modeled as an env-backed registry path."""
    runtime_matrix = next(
        entry for entry in L0_PROTOCOLS if entry.name == "Runtime Matrix"
    )
    assert runtime_matrix.spec_url == "$RUNTIME_HOME/matrix.yaml"
