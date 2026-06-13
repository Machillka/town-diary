from copy import deepcopy

import pytest

from town_diary.core.config import load_config_bundle, validate_config_documents
from town_diary.core.contracts import Weather
from town_diary.core.errors import ConfigLoadError, ConfigValidationError
from town_diary.core.schema import SCHEMA_VERSION


@pytest.fixture
def valid_documents() -> dict[str, dict]:
    return {
        "world": {
            "schema_version": SCHEMA_VERSION,
            "initial_weather": "clear",
            "allowed_weather": ["clear", "cloudy", "light_rain", "heavy_rain"],
            "weather_transition_time": "morning",
            "weather_transitions": [
                {"from": weather, "to": weather, "weight": 1}
                for weather in ("clear", "cloudy", "light_rain", "heavy_rain")
            ],
            "weather_effects": {
                weather: {
                    "movement_multiplier": 1,
                    "foot_traffic_multiplier": 1,
                    "observation_multiplier": 1,
                    "rumor_multiplier": 1,
                }
                for weather in ("clear", "cloudy", "light_rain", "heavy_rain")
            },
        },
        "locations": {
            "schema_version": SCHEMA_VERSION,
            "locations": [
                {
                    "id": "novelist_home",
                    "name": "Novelist Home",
                    "kind": "home",
                    "is_public": False,
                    "is_core_narrative": True,
                    "connected_locations": ["cafe"],
                    "open_rule": "always",
                },
                {
                    "id": "cafe",
                    "name": "Cafe",
                    "kind": "social",
                    "is_public": True,
                    "is_core_narrative": True,
                    "connected_locations": ["novelist_home"],
                    "open_rule": {
                        "open_blocks": ["morning", "noon", "afternoon", "evening"]
                    },
                },
            ],
        },
        "agents": {
            "schema_version": SCHEMA_VERSION,
            "agents": [
                {
                    "id": "novelist",
                    "name": "Novelist",
                    "role": "novelist",
                    "home_location_id": "novelist_home",
                    "initial_location_id": "novelist_home",
                }
            ],
        },
    }


def validate(documents: dict[str, dict]):
    return validate_config_documents(
        world_document=documents["world"],
        locations_document=documents["locations"],
        agents_document=documents["agents"],
    )


def test_valid_minimal_configuration_passes(valid_documents) -> None:
    bundle = validate(valid_documents)

    assert bundle.schema_version == SCHEMA_VERSION
    assert bundle.world.initial_weather is Weather.CLEAR
    assert {str(location.id) for location in bundle.locations} == {"novelist_home", "cafe"}


def test_loader_reads_required_yaml_documents(tmp_path, valid_documents) -> None:
    import yaml

    for name, document in valid_documents.items():
        (tmp_path / f"{name}.yaml").write_text(
            yaml.safe_dump(document, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    assert load_config_bundle(tmp_path).schema_version == SCHEMA_VERSION


def test_loader_rejects_missing_required_document(tmp_path) -> None:
    with pytest.raises(ConfigLoadError, match="world.yaml"):
        load_config_bundle(tmp_path)


def test_duplicate_location_id_is_rejected(valid_documents) -> None:
    documents = deepcopy(valid_documents)
    documents["locations"]["locations"].append(
        deepcopy(documents["locations"]["locations"][0])
    )

    with pytest.raises(ConfigValidationError, match="duplicate location id"):
        validate(documents)


def test_unknown_location_reference_is_rejected(valid_documents) -> None:
    documents = deepcopy(valid_documents)
    documents["agents"]["agents"][0]["home_location_id"] = "missing_home"

    with pytest.raises(ConfigValidationError, match="unknown home location"):
        validate(documents)


def test_invalid_weather_enum_is_rejected(valid_documents) -> None:
    documents = deepcopy(valid_documents)
    documents["world"]["initial_weather"] = "storm"

    with pytest.raises(ConfigValidationError, match="world.initial_weather"):
        validate(documents)


def test_missing_required_field_is_rejected(valid_documents) -> None:
    documents = deepcopy(valid_documents)
    del documents["locations"]["locations"][0]["name"]

    with pytest.raises(ConfigValidationError, match=r"locations\.locations\[0\]\.name"):
        validate(documents)


def test_schema_version_mismatch_is_rejected(valid_documents) -> None:
    documents = deepcopy(valid_documents)
    documents["agents"]["schema_version"] = "0.2"

    with pytest.raises(ConfigValidationError, match="same schema_version"):
        validate(documents)


def test_missing_weather_effect_is_rejected(valid_documents) -> None:
    documents = deepcopy(valid_documents)
    del documents["world"]["weather_effects"]["heavy_rain"]

    with pytest.raises(ConfigValidationError, match="weather effects missing states"):
        validate(documents)


def test_invalid_location_open_block_is_rejected(valid_documents) -> None:
    documents = deepcopy(valid_documents)
    documents["locations"]["locations"][1]["open_rule"]["open_blocks"] = ["midnight"]

    with pytest.raises(ConfigValidationError, match="open_blocks"):
        validate(documents)
