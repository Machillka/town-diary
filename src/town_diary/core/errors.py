"""Domain-specific errors used by shared infrastructure."""


class TownDiaryError(Exception):
    """Base error for the project."""


class ConfigError(TownDiaryError):
    """Base error for configuration loading and validation."""


class ConfigLoadError(ConfigError):
    """Raised when configuration documents cannot be loaded."""


class ConfigValidationError(ConfigError):
    """Raised when configuration documents violate the schema."""

    def __init__(self, issues: list[str] | tuple[str, ...]) -> None:
        self.issues = tuple(issues)
        super().__init__("Invalid configuration:\n- " + "\n- ".join(self.issues))


class SnapshotValidationError(TownDiaryError):
    """Raised when a runtime snapshot cannot be restored."""
