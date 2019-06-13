# -*- coding: utf-8 -*-
from typing import List, Optional, Tuple
import collections
import math

import vpython
import numpy as np

from orbitx import common
from orbitx import state

Point = collections.namedtuple('Point', ['x', 'y', 'z'])
OrbitCoords = collections.namedtuple(
    'OrbitCoords',
    ['centre', 'major_axis', 'minor_axis', 'eccentricity'])


def angle_to_vpy(angle: float) -> vpython.vector:
    return vpython.vector(np.cos(angle), np.sin(angle), 0)


def phase_angle(A: state.Entity, B: state.Entity, C: state.Entity) -> \
        Optional[float]:
    """The orbital phase angle, between A-B-C, of the angle at B.
    i.e. the angle between the ref-hab vector and the ref-targ vector."""
    # Code from Newton Excel Bach blog, 2014, "the angle between two vectors"
    if B.name == C.name:
        return None
    AB = A.pos - B.pos
    CB = C.pos - B.pos

    return np.degrees(
        np.arctan2(AB[1], AB[0]) -
        np.arctan2(CB[1], CB[0])
    ) % 360


def orb_speed(habitat: state.Entity, reference: state.Entity) -> float:
    """The orbital speed of an astronomical body or object.
    Equation referenced from https://en.wikipedia.org/wiki/Orbital_speed"""
    return math.sqrt(
        (reference.mass**2 * common.G) /
        ((habitat.mass + reference.mass) *
         distance(reference, habitat)))


def altitude(A: state.Entity, B: state.Entity) -> float:
    """Caculate distance between ref_planet and Habitat
    returns: the number of metres"""
    return distance(A, B) - A.r - B.r


def distance(A: state.Entity, B: state.Entity) -> float:
    return np.linalg.norm(A.pos - B.pos)


def speed(A: state.Entity, B: state.Entity) -> float:
    """Caculate speed between ref_planet and Habitat"""
    return np.linalg.norm(A.v - B.v)


def v_speed(A: state.Entity, B: state.Entity) -> float:
    """Centripetal velocity of the habitat relative to planet_name.

    Returns a negative number of m/s when the habitat is falling,
    and positive when the habitat is rising."""
    normal = A.pos - B.pos
    normal = normal / np.linalg.norm(normal)
    radial_v = np.dot(normal, A.v - B.v)
    return np.linalg.norm(radial_v)


def h_speed(A: state.Entity, B: state.Entity) -> float:
    """Tangential velocity of the habitat relative to planet_name.

    Always returns a positive number of m/s, of how fast the habitat is
    moving side-to-side relative to the reference surface."""
    normal = A.pos - B.pos
    normal = normal / np.linalg.norm(normal)
    tangent = np.array([normal[1], -normal[0]])
    tangent_v = np.dot(tangent, A.v - B.v)
    return np.linalg.norm(tangent_v)


def engine_acceleration(habitat: state.Entity) -> float:
    """Acceleration due to engine thrust."""
    return np.linalg.norm(state.Habitat.thrust(
        throttle=habitat.throttle, heading=habitat.heading) /
        (habitat.mass + habitat.fuel))


def landing_acceleration(A: state.Entity, B: state.Entity) -> Optional[float]:
    """Constant acceleration required to slow to a stop at the surface of B.
    If the the entities are landed, returns 0."""
    if A.attached_to == B.name:
        return None

    # We check if the two entities will ever intersect, by looking at the
    # scalar expansion of |pos + v*t| = r, and seeing if there are any
    # real number values for t that will make that equation be true. Turns out
    # we can find if there are real solutions by solving the scalar expansion:
    # https://www.wolframalpha.com/input/?i=solve+sqrt((a+%2B+x*t)%5E2+%2B+(b+%2B+y*t)%5E2)+%3D+r+for+t
    # (in the above equation [a, b] and [x, y] represent pos and v vectors)
    # and checking if the value inside the square root is ever negative (which
    # would mean there are only imaginary solutions) or if the denominator is 0
    pos = A.pos - B.pos
    x, y = pos
    v = A.v - B.v
    vx, vy = v
    r = A.r + B.r
    if (-x**2 * vy**2 + 2 * x * y * vx * vy -
        y**2 * vx**2 + r**2 * vx**2 + r**2 * vy**2) < 0 or \
            vx**2 + vy**2 == 0:
        return None

    # np.inner(vector, vector) is the squared norm, i.e. |vector|^2
    return ((common.G * (A.mass + B.mass)) / np.inner(pos, pos) +
            np.inner(v, v) / (2 * np.linalg.norm(A.pos - B.pos)))


def semimajor_axis(A: state.Entity, B: state.Entity) -> float:
    """Calculate semimajor axis: the mean distance between bodies in an
    elliptical orbit. See 'calculation of semi-major axis from state vectors'
    on the wikipedia article for semi-major axes."""
    v = np.array([A.vx - B.vx, A.vy - B.vy])
    r = distance(A, B)
    mu = (B.mass + A.mass) * common.G
    return 1 / (2 / r - np.dot(v, v) / mu)


def eccentricity(A: state.Entity, B: state.Entity) -> np.ndarray:
    """Calculates the eccentricity vector - a defining feature of ellipses.
    See https://space.stackexchange.com/a/1919 for the equation.

    "Why don't you just find a scalar value instead of a vector?"
    The direction of this eccentricity vector points to the periapsis,
    through the two focii of the orbit ellipse, and from the apoapsis.
    This allows us to do some vector math and project an orbit ellipse."""
    v = A.v - B.v
    r = A.pos - B.pos
    mu = common.G * (B.mass + A.mass)
    # e⃗ = [ (v*v - μ/r)r⃗  - (r⃗ ∙ v⃗)v⃗ ] / μ
    return (
        (np.linalg.norm(v)**2 - mu / np.linalg.norm(r)) * r - np.dot(r, v) * v
    ) / mu


def periapsis(A: state.Entity, B: state.Entity) -> float:
    """Calculates the lowest altitude in the orbit of A above B.

    A negative periapsis means at some point in A's orbit, A will crash into
    the surface of B."""
    peri_distance = (
        semimajor_axis(A, B) *
        (1 - np.linalg.norm(eccentricity(A, B)))
    )
    return max(peri_distance - B.r, 0)


def apoapsis(A: state.Entity, B: state.Entity) -> float:
    """Calculates the highest altitude in the orbit of A above B.

    A positive apoapsis means at some point in A's orbit, A will
    be above the surface of B."""
    apo_distance = (
        semimajor_axis(A, B) *
        (1 + np.linalg.norm(eccentricity(A, B)))
    )
    return max(apo_distance - B.r, 0)


def pitch(A: state.Entity, B: state.Entity) -> float:
    """The angle that A is facing, relative to the surface of B.
    Should be 270 degrees when facing ccw prograde, 90 when facing
    cw retrograde, and 0 when facing directly away from B."""
    normal = A.pos - B.pos
    normal_angle = np.arctan2(normal[1], normal[0])
    return normal_angle - A.heading


def orbit_parameters(A: state.Entity, B: state.Entity) -> OrbitCoords:
    if B.mass > A.mass:
        # Ensure A has the larger mass
        return orbit_parameters(B, A)
    # eccentricity is a vector pointing along the major axis of the ellipse of
    # the orbit. i.e. From the orbited-body's centre towards the apoapsis.
    e = eccentricity(A, B)
    e_mag = np.linalg.norm(e)
    e_unit = e / e_mag
    a = semimajor_axis(A, B)

    periapsis_coords = A.pos + a * (1 + e_mag) * e_unit
    apoapsis_coords = A.pos - a * (1 - e_mag) * e_unit

    centre = (periapsis_coords + apoapsis_coords) / 2
    major_axis = 2 * a
    minor_axis = major_axis * math.sqrt(abs(1 - e_mag**2))
    return OrbitCoords(centre=centre, major_axis=major_axis,
                       minor_axis=minor_axis, eccentricity=e)


def midpoint(left: np.ndarray, right: np.ndarray, radius: float) -> np.ndarray:
    # Find the midpoint between the xyz-tuples left and right, but also
    # on the surface of a sphere (so not just a simple average).
    midpoint = (left + right) / 2
    midpoint_radial_dist = np.linalg.norm(midpoint)
    return radius * midpoint / midpoint_radial_dist


def _build_sphere_segment_vertices(
        radius: float,
        size: float,
        refine_steps=3) -> List[Tuple[Point, Point, Point]]:
    """Returns a segment of a sphere, which has a specified radius.
    The return is a list of xyz-tuples, each representing a vertex."""
    # This code inspired by:
    # http://blog.andreaskahler.com/2009/06/creating-icosphere-mesh-in-code.html
    # Thanks, Andreas Kahler.
    # TODO: limit the number of vertices generated to 65536 (the max in a
    # vpython compound object).

    # We set the 'middle' of the surface we're constructing
    # to be (0, 0, r). Think of this as a point on the surface of
    # the sphere centred on (0,0,0) with radius r.
    # Then, we construct four equilateral triangles that will all meet at
    # this point. Each triangle is `size` metres long.

    # The values of 100 are placeholders,
    # and get replaced by cos(theta) * r
    tris = np.array([
        (Point(0, 1, 100), Point(1, 0, 100), Point(0, 0, 100)),
        (Point(1, 0, 100), Point(0, -1, 100), Point(0, 0, 100)),
        (Point(0, -1, 100), Point(-1, 0, 100), Point(0, 0, 100)),
        (Point(-1, 0, 100), Point(0, 1, 100), Point(0, 0, 100))
    ])
    # Each Point gets coerced to a length-3 numpy array

    # Set the z of each xyz-tuple to be radius, and everything else to be
    # the coordinates on the radius-sphere times -1, 0, or 1.
    theta = np.arctan(size / radius)
    tris = np.where(
        [True, True, False],
        radius * np.sin(theta) * tris,
        radius * np.cos(theta))

    for _ in range(0, refine_steps):
        new_tris = np.ndarray(shape=(0, 3, 3))
        for tri in tris:
            # A tri is a 3-tuple of xyz-tuples.
            a = midpoint(tri[0], tri[1], radius)
            b = midpoint(tri[1], tri[2], radius)
            c = midpoint(tri[2], tri[0], radius)

            # Turn one triangle into a triforce projected onto a sphere.
            new_tris = np.append(new_tris, [
                (tri[0], a, c),
                (tri[1], b, a),
                (tri[2], c, b),
                (a, b, c)  # The centre triangle of the triforce
            ], axis=0)
        tris = new_tris

    return tris
# end of _build_sphere_segment_vertices


def grav_acc(X, Y, M):
    # Turn X, Y, M into column vectors, which is easier to do math with.
    # (row vectors won't transpose)
    X = X.reshape(1, -1)
    Y = Y.reshape(1, -1)
    M = M.reshape(1, -1)
    MM = np.outer(M, M)  # A square matrix of masses, units of kg^2
    ang = _angle_matrix(X, Y)
    FORCE = _force(MM, X, Y)
    Xf, Yf = _polar_to_cartesian(ang, FORCE)
    Xf = _force_sum(Xf)
    Yf = _force_sum(Yf)
    Xa = _f_to_a(Xf, M)
    Ya = _f_to_a(Yf, M)
    return np.array(Xa).reshape(-1), np.array(Ya).reshape(-1)


def _force(MM, X, Y):
    common.G = 6.674e-11
    D2 = np.square(X - X.transpose()) + np.square(Y - Y.transpose())
    # Calculate common.G * m1*m2/d^2 for each object pair.
    # In the diagonal case, i.e. an object paired with itself, force = 0.
    force_matrix = np.divide(MM, np.where(D2 != 0, D2, 1))
    np.fill_diagonal(force_matrix, 0)
    return common.G * force_matrix


def _force_sum(_force):
    return np.sum(_force, 0)


def _angle_matrix(X, Y):
    Xd = X - X.transpose()
    Yd = Y - Y.transpose()
    return np.arctan2(Yd, Xd)


def _polar_to_cartesian(ang, hyp):
    X = np.multiply(np.cos(ang), hyp)
    Y = np.multiply(np.sin(ang), hyp)
    return X.T, Y.T


def _f_to_a(f, M):
    return np.divide(f, M)


def navmode_heading(flight_state: state.PhysicsState) -> float:
    """
    Returns the heading that the craft should be facing in current navmode.

    Don't call this with Manual navmode.
    If the navmode is relative to the reference, and the reference is set to
    the craft, this will return the craft's current heading as a sane default.
    """
    navmode = flight_state.navmode
    craft = flight_state.craft_entity()
    ref = flight_state.reference_entity()
    targ = flight_state.target_entity()
    requested_vector: np.ndarray

    if navmode == state.Navmode['Manual']:
        raise ValueError('Autopilot requested for manual navmode')
    elif navmode.name == 'CCW Prograde':
        if flight_state.reference == flight_state.craft:
            return craft.heading
        normal = craft.pos - ref.pos
        requested_vector = np.array([-normal[1], normal[0]])
    elif navmode == state.Navmode['CW Retrograde']:
        if flight_state.reference == flight_state.craft:
            return craft.heading
        normal = craft.pos - ref.pos
        requested_vector = np.array([normal[1], -normal[0]])
    elif navmode == state.Navmode['Depart Reference']:
        if flight_state.reference == flight_state.craft:
            return craft.heading
        requested_vector = craft.pos - ref.pos
    elif navmode == state.Navmode['Approach Target']:
        if flight_state.target == flight_state.craft:
            return craft.heading
        requested_vector = targ.pos - craft.pos
    elif navmode == state.Navmode['Pro Targ Velocity']:
        if flight_state.target == flight_state.craft:
            return craft.heading
        requested_vector = craft.v - targ.v
    elif navmode == state.Navmode['Anti Targ Velocity']:
        if flight_state.target == flight_state.craft:
            return craft.heading
        requested_vector = targ.v - craft.v
    else:
        raise ValueError(f'Got an unexpected NAVMODE: {flight_state.navmode}')

    return np.arctan2(requested_vector[1], requested_vector[0])


def navmode_spin(flight_state: state.PhysicsState) -> float:
    """Returns a spin that will orient the craft according to the navmode."""

    craft = flight_state.craft_entity()
    requested_heading = navmode_heading(flight_state)
    ccw_distance = (requested_heading - craft.heading) % np.radians(360)
    cw_distance = (craft.heading - requested_heading) % np.radians(360)
    if ccw_distance < cw_distance:
        heading_difference = ccw_distance
    else:
        heading_difference = -cw_distance
    if abs(heading_difference) < common.AUTOPILOT_FINE_CONTROL_RADIUS:
        # The unit analysis doesn't work out here I'm sorry. Basically,
        # the closer we are to the target heading, the slower we adjust.
        return heading_difference
    else:
        # We can spin at most common.AUTOPILOT_SPEED
        return np.sign(heading_difference) * common.AUTOPILOT_SPEED


def drag(flight_state: state.PhysicsState) -> np.ndarray:
    craft = flight_state.craft_entity()

    closest_atmosphere: Optional[state.Entity] = None
    closest_exponential = -np.inf
    previous_distance_sq = np.inf

    for entity in flight_state:
        if entity.atmosphere_scaling == 0 or entity.atmosphere_thickness == 0:
            # Entity has no atmosphere
            continue

        displacement = entity.pos - craft.pos
        distance_sq = np.inner(displacement, displacement)
        # np.inner is the same as the magnitude squared
        # https://stackoverflow.com/a/35213951
        # We use the squared distance because it's much faster to calculate.
        if distance_sq < previous_distance_sq:
            # Entity has an atmosphere but is too far away
            exponential = (
                -altitude(craft, entity) / 1000 / entity.atmosphere_scaling)
            if exponential > -20:
                previous_distance_sq = distance_sq
                closest_atmosphere = entity
                closest_exponential = exponential

    if closest_atmosphere is None:
        return np.array([0, 0])

    wind = craft.v - closest_atmosphere.v
    if np.inner(wind, wind) < 0.01:
        # The craft is stationary
        return np.array([0, 0])
    wind_angle = np.arctan2(wind[1], wind[0])

    # I know I've said this about other pieces of code, but I really have no
    # idea how this code works. I just lifted it from OrbitV because I couldn't
    # find simple atmospheric drag models.
    # Also sorry, unit analysis doesn't work inside this function.
    # TODO: how does this work outside of the atmosphere?
    # TODO: disabled while I figure out if this only works during telemetry
    i_know_what_this_aoa_code_does = False
    if i_know_what_this_aoa_code_does:
        aoa = wind_angle - pitch(craft, closest_atmosphere)
        aoa = np.sign(np.sign(np.cos(aoa)) - 1)
        aoa = aoa**3
        if aoa > 0.5:
            aoa = 1 - aoa
        aoa_vector = -abs(aoa) * np.array([
            np.sin(wind_angle + (np.pi / 2) * np.sign(aoa)),
            np.cos(wind_angle + (np.pi / 2) * np.sign(aoa))
        ])
        return aoa_vector

    # This exponential-form equation seems to be the barometric formula:
    # https://en.wikipedia.org/wiki/Barometric_formula
    pressure = (
        closest_atmosphere.atmosphere_thickness *
        np.exp(closest_exponential)
    )

    drag_acc = pressure * np.linalg.norm(wind)**2 * common.DRAG_PROFILE
    return drag_acc * (wind / np.linalg.norm(wind))
