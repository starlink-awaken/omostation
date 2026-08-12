"""Release contract for the Workspace omlxc MOF component."""

from pathlib import Path

import yaml

COMPONENT = (
    Path(__file__).parents[1] / "src/ecos/ssot/mof/m1/component/COMP-WS-omlxc.yaml"
)


def test_omlxc_component_tracks_the_released_hotfix() -> None:
    payload = yaml.safe_load(COMPONENT.read_text(encoding="utf-8"))

    assert payload["id"] == "COMP-WS-omlxc"
    assert payload["project"] == "omlxc"
    assert payload["version"] == "3.0.1"
