from copy import deepcopy
from pathlib import Path

import pytest

from town_diary.core.config import load_config_bundle, validate_config_documents
from town_diary.core.contracts import TimeBlock
from town_diary.core.errors import ConfigValidationError
from town_diary.simulation.location import LocationSystem


def test_formal_location_config_has_no_dangling_references() -> None:
    bundle = load_config_bundle("configs")
    locations = LocationSystem.from_config(bundle.locations)

    assert len(bundle.locations) == 10
    assert len(bundle.agents) == 6
    assert all(locations.exists(agent.home_location_id) for agent in bundle.agents)
    assert all(locations.exists(agent.initial_location_id) for agent in bundle.agents)


def test_location_topology_and_opening_rules() -> None:
    bundle = load_config_bundle("configs")
    locations = LocationSystem.from_config(bundle.locations)

    assert locations.are_connected("novelist_home", "cafe")
    assert locations.are_connected("cafe", "novelist_home")
    assert not locations.are_connected("novelist_home", "station")
    assert locations.is_open("station", TimeBlock.NIGHT)
    assert not locations.is_open("library", TimeBlock.NIGHT)
    assert not locations.is_open("market", TimeBlock.EVENING)
    for location in bundle.locations:
        for time_block in TimeBlock:
            assert isinstance(locations.is_open(location.id, time_block), bool)


def test_public_and_private_location_boundaries() -> None:
    locations = LocationSystem.from_config(load_config_bundle("configs").locations)

    assert {str(location.id) for location in locations.public_locations()} == {
        "cafe",
        "library",
        "market",
        "station",
    }
    assert "novelist_home" in {
        str(location.id) for location in locations.private_locations()
    }
    assert {str(location.id) for location in locations.core_narrative_locations()} == {
        "novelist_home",
        "cafe",
        "library",
        "market",
        "station",
    }


def test_location_snapshots_are_immutable_and_time_specific() -> None:
    locations = LocationSystem.from_config(load_config_bundle("configs").locations)

    night = {str(item.location_id): item for item in locations.snapshots(TimeBlock.NIGHT)}

    assert night["library"].is_open is False
    assert night["station"].is_open is True
    with pytest.raises(AttributeError):
        night["library"].is_open = True  # type: ignore[misc]


def test_one_way_location_connection_is_rejected() -> None:
    import yaml

    world = yaml.safe_load(Path("configs/world.yaml").read_text(encoding="utf-8"))
    locations = yaml.safe_load(Path("configs/locations.yaml").read_text(encoding="utf-8"))
    agents = yaml.safe_load(Path("configs/agents.yaml").read_text(encoding="utf-8"))
    documents = deepcopy({"world": world, "locations": locations, "agents": agents})
    cafe = next(
        location
        for location in documents["locations"]["locations"]
        if location["id"] == "cafe"
    )
    cafe["connected_locations"].remove("novelist_home")

    with pytest.raises(ConfigValidationError, match="bidirectional"):
        validate_config_documents(
            world_document=documents["world"],
            locations_document=documents["locations"],
            agents_document=documents["agents"],
        )
