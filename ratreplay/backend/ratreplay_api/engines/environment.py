"""
An environment's geometry in the room frame, in metres, as plain lists for the browser.
"""

from environments import load_environment


def geometry(name):
    """
    The environment config's walls, centerline, boundary and reward sites, and for a circle its centre and radius.
    """
    spec = load_environment(name)
    circle = {"center": [spec.room[0] / 2, spec.room[1] / 2], "radius": spec.params["diameter"] / 2} if spec.kind == "circle" else None
    return {"name": spec.name, "kind": spec.kind, "room": spec.room, "boundary": spec.boundary, "walls": spec.walls,
            "centerline": spec.centerline, "reward_sites": spec.reward_sites, "circle": circle}
