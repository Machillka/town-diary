from town_diary.core.config import load_config_bundle
from town_diary.core.contracts import TimeBlock, Weather
from town_diary.core.random import DeterministicRandom
from town_diary.simulation.weather import WeatherSystem


def make_weather(seed: int = 42) -> WeatherSystem:
    config = load_config_bundle("configs")
    return WeatherSystem(config=config.world, random=DeterministicRandom(seed))


def test_fixed_seed_replays_the_same_weather_sequence() -> None:
    first = make_weather(42)
    second = make_weather(42)

    first_sequence = [
        first.advance(day=day, time_block=TimeBlock.MORNING).current
        for day in range(1, 8)
    ]
    second_sequence = [
        second.advance(day=day, time_block=TimeBlock.MORNING).current
        for day in range(1, 8)
    ]

    assert first_sequence == second_sequence


def test_weather_only_transitions_once_at_configured_time() -> None:
    weather = make_weather()

    assert weather.advance(day=1, time_block=TimeBlock.NOON) is None
    first_change = weather.advance(day=1, time_block=TimeBlock.MORNING)
    assert first_change is not None
    assert weather.advance(day=1, time_block=TimeBlock.MORNING) is None
    assert len(weather.snapshot().changes) == 1


def test_heavy_rain_reduces_movement_score() -> None:
    config = load_config_bundle("configs")
    heavy_rain_snapshot = {
        "current": "heavy_rain",
        "last_transition_day": None,
        "changes": [],
        "schema_version": "0.1",
    }
    weather = WeatherSystem.from_snapshot(
        config=config.world,
        random=DeterministicRandom(42),
        snapshot=heavy_rain_snapshot,
    )

    assert weather.current is Weather.HEAVY_RAIN
    assert weather.movement_score(10.0) == 4.0


def test_weather_snapshot_restores_state_and_change_log() -> None:
    config = load_config_bundle("configs")
    random = DeterministicRandom(42)
    weather = WeatherSystem(config=config.world, random=random)
    weather.advance(day=1, time_block=TimeBlock.MORNING)
    snapshot = weather.snapshot().to_dict()

    restored = WeatherSystem.from_snapshot(
        config=config.world,
        random=DeterministicRandom.from_snapshot(random.snapshot()),
        snapshot=snapshot,
    )

    assert restored.snapshot() == weather.snapshot()


def test_weather_snapshot_exposes_current_weather_without_future_state() -> None:
    weather = make_weather()

    assert weather.snapshot().current is Weather.CLEAR
    assert not hasattr(weather.snapshot(), "future_weather")
