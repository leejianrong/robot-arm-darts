"""Dart air loads: quadratic drag, fin restoring torque and spin damping (ADR-0005)."""

import numpy as np

from darts.twin import Aero


def aero_wrench(
    vel: np.ndarray, omega: np.ndarray, axis: np.ndarray, aero: Aero
) -> tuple[np.ndarray, np.ndarray]:
    """World-frame force and torque on a dart moving at `vel` with spin `omega`.

    `axis` is the unit vector from the dart's tail to its tip. The fins turn it toward the
    velocity direction, with a torque growing with speed squared.
    """
    speed = float(np.linalg.norm(vel))
    if speed < 1e-6:
        return np.zeros(3), -aero.spin_damping_nm_s * omega
    force = -aero.drag_kg_m * speed * vel
    torque = aero.fin_torque_nm * speed * np.cross(axis, vel) - aero.spin_damping_nm_s * omega
    return force, torque
