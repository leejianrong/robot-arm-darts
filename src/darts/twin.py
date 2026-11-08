"""Strict loader for twin.yaml, the single source of calibratable parameters (ADR-0006)."""

from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

import yaml

SCHEMA_VERSION = 1


class TwinConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Sim:
    timestep_s: float
    gravity_m_s2: float


@dataclass(frozen=True)
class Servo:
    kp: float
    kv: float
    torque_limit_nm: float
    velocity_limit_rad_s: float
    no_load_speed_rad_s: float  # torque falls linearly to zero at this speed; 0 keeps it flat


@dataclass(frozen=True)
class Power:
    """Bigger actuators on shoulder_lift and elbow_flex; torque_limit_nm 0 keeps the stock servo."""

    torque_limit_nm: float
    no_load_speed_rad_s: float  # torque falls linearly to zero here; 0 keeps it flat
    velocity_limit_rad_s: float
    shoulder_mass_kg: float  # actuator mass added to the shoulder body (does not swing)
    elbow_mass_kg: float  # added to the upper arm (swings with the shoulder lift)


@dataclass(frozen=True)
class Dart:
    mass_kg: float
    length_m: float
    radius_m: float


@dataclass(frozen=True)
class Aero:
    drag_kg_m: float  # force = drag * speed^2, i.e. 0.5 * air density * Cd * area
    fin_torque_nm: float  # torque per (m/s)^2 per radian of misalignment
    spin_damping_nm_s: float  # torque per rad/s of spin


@dataclass(frozen=True)
class Release:
    jaw_hold_rad: float
    jaw_open_rad: float
    pad_friction: float


@dataclass(frozen=True)
class Board:
    distance_m: float
    centre_height_m: float
    radius_m: float  # outer edge of the double ring; also the scoring radius
    stick_min_speed_m_s: float  # slower than this at the tip and the dart bounces
    stick_max_angle_rad: float  # angle between dart axis and board normal beyond which it bounces


@dataclass(frozen=True)
class Mount:
    height_m: float


@dataclass(frozen=True)
class Camera:
    """Rigid on a mast beside the arm, looking at the board centre (ADR-0007). x and y are
    from the base axis, z above the floor."""

    x_m: float
    y_m: float
    z_m: float
    fovy_deg: float
    width_px: float
    height_px: float


@dataclass(frozen=True)
class Randomise:
    """Per-episode training spread: each value is drawn uniformly within +-this fraction of the
    nominal. Latency and jaw timing are not in the model, so they cannot be randomised yet."""

    servo_gain_frac: float  # kp and kv
    servo_torque_frac: float
    dart_mass_frac: float
    pad_friction_frac: float
    drag_frac: float
    fin_torque_frac: float
    spin_damping_frac: float


@dataclass(frozen=True)
class Twin:
    schema_version: int
    sim: Sim
    servo: Servo
    power: Power
    dart: Dart
    aero: Aero
    release: Release
    board: Board
    mount: Mount
    camera: Camera
    randomise: Randomise


_SECTIONS: dict[str, type] = {
    "sim": Sim,
    "servo": Servo,
    "power": Power,
    "dart": Dart,
    "aero": Aero,
    "release": Release,
    "board": Board,
    "mount": Mount,
    "camera": Camera,
    "randomise": Randomise,
}


def _build(cls: type, raw: Any, where: str):
    if not isinstance(raw, dict):
        raise TwinConfigError(f"{where}: expected a mapping")
    names = {f.name for f in fields(cls)}
    unknown = set(raw) - names
    missing = names - set(raw)
    if unknown:
        raise TwinConfigError(f"{where}: unknown keys {sorted(unknown)}")
    if missing:
        raise TwinConfigError(f"{where}: missing keys {sorted(missing)}")
    for k, v in raw.items():
        if isinstance(v, bool) or not isinstance(v, int | float):
            raise TwinConfigError(f"{where}.{k}: expected a number, got {v!r}")
    return cls(**{k: float(v) for k, v in raw.items()})


def parse_twin(raw: dict[str, Any]) -> Twin:
    expected = {"schema_version", *_SECTIONS}
    unknown = set(raw) - expected
    missing = expected - set(raw)
    if unknown:
        raise TwinConfigError(f"unknown top-level keys {sorted(unknown)}")
    if missing:
        raise TwinConfigError(f"missing top-level keys {sorted(missing)}")
    if raw["schema_version"] != SCHEMA_VERSION:
        raise TwinConfigError(
            f"schema_version {raw['schema_version']!r} unsupported (want {SCHEMA_VERSION})"
        )
    sections = {name: _build(cls, raw[name], name) for name, cls in _SECTIONS.items()}
    return Twin(schema_version=SCHEMA_VERSION, **sections)


def load_twin(path: str | Path = "twin.yaml") -> Twin:
    return parse_twin(yaml.safe_load(Path(path).read_text()))
