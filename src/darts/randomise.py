"""A twin with its uncertain numbers redrawn, for training that survives a real arm (DART-17)."""

import dataclasses

import numpy as np

from darts.twin import Twin


def sample(twin: Twin, rng: np.random.Generator) -> Twin:
    """The twin with gains, torque, dart mass, pad friction and aero guesses each scaled by a
    uniform draw inside the `randomise` fractions of twin.yaml."""
    r = twin.randomise

    def scale(frac: float) -> float:
        return float(rng.uniform(1.0 - frac, 1.0 + frac))

    gain = scale(r.servo_gain_frac)
    return dataclasses.replace(
        twin,
        servo=dataclasses.replace(
            twin.servo,
            kp=twin.servo.kp * gain,
            kv=twin.servo.kv * gain,
            torque_limit_nm=twin.servo.torque_limit_nm * scale(r.servo_torque_frac),
        ),
        dart=dataclasses.replace(twin.dart, mass_kg=twin.dart.mass_kg * scale(r.dart_mass_frac)),
        release=dataclasses.replace(
            twin.release, pad_friction=twin.release.pad_friction * scale(r.pad_friction_frac)
        ),
        aero=dataclasses.replace(
            twin.aero,
            drag_kg_m=twin.aero.drag_kg_m * scale(r.drag_frac),
            fin_torque_nm=twin.aero.fin_torque_nm * scale(r.fin_torque_frac),
            spin_damping_nm_s=twin.aero.spin_damping_nm_s * scale(r.spin_damping_frac),
        ),
    )
