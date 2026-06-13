"""YAML configuration loading and cross-document validation."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from town_diary.core.contracts import TimeBlock, Weather
from town_diary.core.errors import ConfigLoadError, ConfigValidationError
from town_diary.core.ids import AgentId, LocationId, is_stable_static_id
from town_diary.core.schema import SCHEMA_VERSION, SUPPORTED_SCHEMA_VERSIONS


@dataclass(frozen=True, slots=True)
class WorldConfig:
    schema_version: str
    initial_weather: Weather
    allowed_weather: tuple[Weather, ...]
    weather_transition_time: TimeBlock
    weather_transitions: tuple["WeatherTransitionConfig", ...]
    weather_effects: tuple["WeatherEffectConfig", ...]


@dataclass(frozen=True, slots=True)
class WeatherTransitionConfig:
    source: Weather
    target: Weather
    weight: float


@dataclass(frozen=True, slots=True)
class WeatherEffectConfig:
    weather: Weather
    movement_multiplier: float
    foot_traffic_multiplier: float
    observation_multiplier: float
    rumor_multiplier: float


@dataclass(frozen=True, slots=True)
class OpenRuleConfig:
    always: bool
    open_blocks: tuple[TimeBlock, ...] = ()


@dataclass(frozen=True, slots=True)
class LocationConfig:
    id: LocationId
    name: str
    kind: str
    is_public: bool
    is_core_narrative: bool
    connected_locations: tuple[LocationId, ...]
    open_rule: OpenRuleConfig


@dataclass(frozen=True, slots=True)
class AgentConfig:
    id: AgentId
    name: str
    role: str
    home_location_id: LocationId
    initial_location_id: LocationId


@dataclass(frozen=True, slots=True)
class ConfigBundle:
    schema_version: str
    world: WorldConfig
    locations: tuple[LocationConfig, ...]
    agents: tuple[AgentConfig, ...]


def load_config_bundle(config_dir: str | Path) -> ConfigBundle:
    """Load and validate the three required MVP configuration documents."""
    base = Path(config_dir)
    documents = {
        name: _load_yaml_mapping(base / f"{name}.yaml")
        for name in ("world", "locations", "agents")
    }
    return validate_config_documents(
        world_document=documents["world"],
        locations_document=documents["locations"],
        agents_document=documents["agents"],
    )


def validate_config_documents(
    *,
    world_document: Mapping[str, Any],
    locations_document: Mapping[str, Any],
    agents_document: Mapping[str, Any],
) -> ConfigBundle:
    """Validate documents and return typed immutable configuration."""
    issues: list[str] = []
    versions = {
        "world": _schema_version(world_document, "world", issues),
        "locations": _schema_version(locations_document, "locations", issues),
        "agents": _schema_version(agents_document, "agents", issues),
    }

    non_empty_versions = {version for version in versions.values() if version}
    if len(non_empty_versions) > 1:
        issues.append("all configuration documents must use the same schema_version")

    world = _parse_world(world_document, issues)
    locations = _parse_locations(locations_document, issues)
    agents = _parse_agents(agents_document, issues)
    _validate_references(locations, agents, issues)

    if issues:
        raise ConfigValidationError(issues)

    return ConfigBundle(
        schema_version=versions["world"],
        world=world,
        locations=locations,
        agents=agents,
    )


def _load_yaml_mapping(path: Path) -> Mapping[str, Any]:
    if not path.is_file():
        raise ConfigLoadError(f"Missing required configuration file: {path}")
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ConfigLoadError(f"Unable to load configuration file: {path}") from error
    if not isinstance(document, Mapping):
        raise ConfigLoadError(f"Configuration document must be a mapping: {path}")
    return document


def _schema_version(
    document: Mapping[str, Any],
    document_name: str,
    issues: list[str],
) -> str:
    version = document.get("schema_version")
    if not isinstance(version, str):
        issues.append(f"{document_name}.schema_version must be a string")
        return ""
    if version not in SUPPORTED_SCHEMA_VERSIONS:
        issues.append(f"{document_name}.schema_version is unsupported: {version}")
    return version


def _parse_world(document: Mapping[str, Any], issues: list[str]) -> WorldConfig:
    initial = _weather(document.get("initial_weather"), "world.initial_weather", issues)
    allowed_raw = document.get("allowed_weather")
    allowed: list[Weather] = []
    if not _is_sequence(allowed_raw):
        issues.append("world.allowed_weather must be a list")
    else:
        for index, value in enumerate(allowed_raw):
            parsed = _weather(value, f"world.allowed_weather[{index}]", issues)
            if parsed is not None:
                allowed.append(parsed)
    if initial is not None and initial not in allowed:
        issues.append("world.initial_weather must be included in world.allowed_weather")
    transition_time = _time_block(
        document.get("weather_transition_time"),
        "world.weather_transition_time",
        issues,
    )
    transitions = _parse_weather_transitions(document.get("weather_transitions"), issues)
    effects = _parse_weather_effects(document.get("weather_effects"), issues)
    _validate_weather_coverage(allowed, transitions, effects, issues)
    return WorldConfig(
        schema_version=str(document.get("schema_version", SCHEMA_VERSION)),
        initial_weather=initial or Weather.CLEAR,
        allowed_weather=tuple(allowed),
        weather_transition_time=transition_time or TimeBlock.MORNING,
        weather_transitions=transitions,
        weather_effects=effects,
    )


def _parse_locations(
    document: Mapping[str, Any],
    issues: list[str],
) -> tuple[LocationConfig, ...]:
    raw_locations = document.get("locations")
    if not _is_sequence(raw_locations):
        issues.append("locations.locations must be a list")
        return ()

    parsed: list[LocationConfig] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_locations):
        path = f"locations.locations[{index}]"
        if not isinstance(raw, Mapping):
            issues.append(f"{path} must be a mapping")
            continue
        location_id = _static_id(raw.get("id"), f"{path}.id", issues)
        if location_id in seen:
            issues.append(f"duplicate location id: {location_id}")
        seen.add(location_id)
        connected = _id_list(
            raw.get("connected_locations"),
            f"{path}.connected_locations",
            issues,
        )
        parsed.append(
            LocationConfig(
                id=LocationId(location_id),
                name=_required_string(raw.get("name"), f"{path}.name", issues),
                kind=_required_string(raw.get("kind"), f"{path}.kind", issues),
                is_public=_required_bool(raw.get("is_public"), f"{path}.is_public", issues),
                is_core_narrative=_required_bool(
                    raw.get("is_core_narrative"),
                    f"{path}.is_core_narrative",
                    issues,
                ),
                connected_locations=tuple(LocationId(item) for item in connected),
                open_rule=_parse_open_rule(raw.get("open_rule"), f"{path}.open_rule", issues),
            )
        )
    return tuple(parsed)


def _parse_agents(
    document: Mapping[str, Any],
    issues: list[str],
) -> tuple[AgentConfig, ...]:
    raw_agents = document.get("agents")
    if not _is_sequence(raw_agents):
        issues.append("agents.agents must be a list")
        return ()

    parsed: list[AgentConfig] = []
    seen: set[str] = set()
    novelist_count = 0
    for index, raw in enumerate(raw_agents):
        path = f"agents.agents[{index}]"
        if not isinstance(raw, Mapping):
            issues.append(f"{path} must be a mapping")
            continue
        agent_id = _static_id(raw.get("id"), f"{path}.id", issues)
        if agent_id in seen:
            issues.append(f"duplicate agent id: {agent_id}")
        seen.add(agent_id)
        role = _required_string(raw.get("role"), f"{path}.role", issues)
        if role not in {"novelist", "resident"}:
            issues.append(f"{path}.role must be novelist or resident")
        if role == "novelist":
            novelist_count += 1
        parsed.append(
            AgentConfig(
                id=AgentId(agent_id),
                name=_required_string(raw.get("name"), f"{path}.name", issues),
                role=role,
                home_location_id=LocationId(
                    _static_id(raw.get("home_location_id"), f"{path}.home_location_id", issues)
                ),
                initial_location_id=LocationId(
                    _static_id(
                        raw.get("initial_location_id"),
                        f"{path}.initial_location_id",
                        issues,
                    )
                ),
            )
        )
    if novelist_count != 1:
        issues.append("agents must contain exactly one novelist")
    return tuple(parsed)


def _validate_references(
    locations: tuple[LocationConfig, ...],
    agents: tuple[AgentConfig, ...],
    issues: list[str],
) -> None:
    location_ids = {str(location.id) for location in locations}
    for location in locations:
        for connected_id in location.connected_locations:
            if str(connected_id) not in location_ids:
                issues.append(
                    f"location {location.id} references unknown connected location {connected_id}"
                )
                continue
            connected_location = next(
                item for item in locations if item.id == connected_id
            )
            if location.id not in connected_location.connected_locations:
                issues.append(
                    f"location connection must be bidirectional: {location.id} -> {connected_id}"
                )
    for agent in agents:
        if str(agent.home_location_id) not in location_ids:
            issues.append(
                f"agent {agent.id} references unknown home location {agent.home_location_id}"
            )
        if str(agent.initial_location_id) not in location_ids:
            issues.append(
                f"agent {agent.id} references unknown initial location {agent.initial_location_id}"
            )


def _weather(value: object, path: str, issues: list[str]) -> Weather | None:
    try:
        return Weather(value)
    except (ValueError, TypeError):
        issues.append(f"{path} must be one of: {', '.join(Weather)}")
        return None


def _time_block(value: object, path: str, issues: list[str]) -> TimeBlock | None:
    try:
        return TimeBlock(value)
    except (ValueError, TypeError):
        issues.append(f"{path} must be one of: {', '.join(TimeBlock)}")
        return None


def _parse_weather_transitions(
    value: object,
    issues: list[str],
) -> tuple[WeatherTransitionConfig, ...]:
    if not _is_sequence(value):
        issues.append("world.weather_transitions must be a list")
        return ()
    transitions: list[WeatherTransitionConfig] = []
    for index, raw in enumerate(value):
        path = f"world.weather_transitions[{index}]"
        if not isinstance(raw, Mapping):
            issues.append(f"{path} must be a mapping")
            continue
        source = _weather(raw.get("from"), f"{path}.from", issues)
        target = _weather(raw.get("to"), f"{path}.to", issues)
        weight = _positive_number(raw.get("weight"), f"{path}.weight", issues)
        if source is not None and target is not None:
            transitions.append(WeatherTransitionConfig(source, target, weight))
    return tuple(transitions)


def _parse_weather_effects(
    value: object,
    issues: list[str],
) -> tuple[WeatherEffectConfig, ...]:
    if not isinstance(value, Mapping):
        issues.append("world.weather_effects must be a mapping")
        return ()
    effects: list[WeatherEffectConfig] = []
    for weather_name, raw in value.items():
        path = f"world.weather_effects.{weather_name}"
        weather = _weather(weather_name, path, issues)
        if not isinstance(raw, Mapping):
            issues.append(f"{path} must be a mapping")
            continue
        if weather is not None:
            effects.append(
                WeatherEffectConfig(
                    weather=weather,
                    movement_multiplier=_non_negative_number(
                        raw.get("movement_multiplier"),
                        f"{path}.movement_multiplier",
                        issues,
                    ),
                    foot_traffic_multiplier=_non_negative_number(
                        raw.get("foot_traffic_multiplier"),
                        f"{path}.foot_traffic_multiplier",
                        issues,
                    ),
                    observation_multiplier=_non_negative_number(
                        raw.get("observation_multiplier"),
                        f"{path}.observation_multiplier",
                        issues,
                    ),
                    rumor_multiplier=_non_negative_number(
                        raw.get("rumor_multiplier"),
                        f"{path}.rumor_multiplier",
                        issues,
                    ),
                )
            )
    return tuple(effects)


def _validate_weather_coverage(
    allowed: list[Weather],
    transitions: tuple[WeatherTransitionConfig, ...],
    effects: tuple[WeatherEffectConfig, ...],
    issues: list[str],
) -> None:
    allowed_set = set(allowed)
    transition_sources = {transition.source for transition in transitions}
    effect_weather = {effect.weather for effect in effects}
    missing_transitions = allowed_set.difference(transition_sources)
    missing_effects = allowed_set.difference(effect_weather)
    if missing_transitions:
        issues.append(
            "weather transitions missing source states: "
            + ", ".join(sorted(missing_transitions))
        )
    if missing_effects:
        issues.append(
            "weather effects missing states: " + ", ".join(sorted(missing_effects))
        )
    for transition in transitions:
        if transition.source not in allowed_set or transition.target not in allowed_set:
            issues.append(
                f"weather transition uses state outside allowed_weather: "
                f"{transition.source} -> {transition.target}"
            )


def _parse_open_rule(value: object, path: str, issues: list[str]) -> OpenRuleConfig:
    if value == "always":
        return OpenRuleConfig(always=True)
    if not isinstance(value, Mapping):
        issues.append(f"{path} must be 'always' or a mapping with open_blocks")
        return OpenRuleConfig(always=False)
    raw_blocks = value.get("open_blocks")
    if not _is_sequence(raw_blocks):
        issues.append(f"{path}.open_blocks must be a list")
        return OpenRuleConfig(always=False)
    blocks: list[TimeBlock] = []
    for index, block in enumerate(raw_blocks):
        parsed = _time_block(block, f"{path}.open_blocks[{index}]", issues)
        if parsed is not None:
            blocks.append(parsed)
    if not blocks:
        issues.append(f"{path}.open_blocks must contain at least one time block")
    if len(set(blocks)) != len(blocks):
        issues.append(f"{path}.open_blocks must not contain duplicates")
    return OpenRuleConfig(always=False, open_blocks=tuple(blocks))


def _static_id(value: object, path: str, issues: list[str]) -> str:
    if not is_stable_static_id(value):
        issues.append(f"{path} must be a lower snake-case identifier")
        return "invalid"
    return str(value)


def _id_list(value: object, path: str, issues: list[str]) -> list[str]:
    if not _is_sequence(value):
        issues.append(f"{path} must be a list")
        return []
    return [_static_id(item, f"{path}[{index}]", issues) for index, item in enumerate(value)]


def _required_string(value: object, path: str, issues: list[str]) -> str:
    if not isinstance(value, str) or not value.strip():
        issues.append(f"{path} must be a non-empty string")
        return ""
    return value


def _required_bool(value: object, path: str, issues: list[str]) -> bool:
    if not isinstance(value, bool):
        issues.append(f"{path} must be a boolean")
        return False
    return value


def _positive_number(value: object, path: str, issues: list[str]) -> float:
    parsed = _non_negative_number(value, path, issues)
    if parsed == 0:
        issues.append(f"{path} must be greater than zero")
    return parsed


def _non_negative_number(value: object, path: str, issues: list[str]) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        issues.append(f"{path} must be a non-negative number")
        return 0.0
    return float(value)


def _is_sequence(value: object) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))
