
"""Read-only data tools for the SetWise Bedrock agent."""

from collections import Counter

from app.database import repository
from app.services.constants import GRADES, SUBS, STYLES



def classify_terrain(angle):
    """
    Classify wall terrain based on its angle.

    Negative angles represent slabs.
    Positive angles represent overhangs.
    """
    if angle < -5:
        return "Slab"

    if angle <= 10:
        return "Vertical"

    if angle <= 35:
        return "Overhang"

    return "Steep overhang"



def get_gym_inventory(gym_id):
    """Return gym walls and active climbs."""
    state = repository.get_state(gym_id)

    return {
        "walls": state["walls"],
        "active_climbs": [
            climb
            for climb in state["climbs"]
            if climb["status"] == "Active"
        ],
    }


def get_wall_details(gym_id):
    """Return wall angles and active climb distributions."""
    state = repository.get_state(gym_id)
    result = []

    for wall in state["walls"]:
        climbs = [
            climb
            for climb in state["climbs"]
            if climb["wallId"] == wall["id"]
            and climb["status"] == "Active"
        ]

        result.append({
            "wall_id": wall["id"],
            "name": wall["name"],
            "angle": wall["angle"],
            "active_climb_count": len(climbs),
            "grade_distribution": dict(
                Counter(c["grade"] for c in climbs)
            ),
        })

    return result


def get_gym_targets(gym_id):
    """Return the gym's configured grade and style targets."""
    state = repository.get_state(gym_id)

    return {
        "grade_targets": state["gradeTargets"],
        "style_targets": state["styleTargets"],
    }


def get_setting_gaps(gym_id, selected_wall_ids):
    """
    Calculate grade and style deficits after removing
    active climbs from the selected reset walls.
    """
    state = repository.get_state(gym_id)

    valid_ids = {wall["id"] for wall in state["walls"]}
    selected = set(selected_wall_ids)

    if not selected or not selected.issubset(valid_ids):
        raise ValueError("Select valid walls for the reset")

    remaining = [
        climb
        for climb in state["climbs"]
        if climb["status"] == "Active"
        and climb["wallId"] not in selected
    ]

    grade_counts = Counter(
        (climb["grade"], climb["sub"])
        for climb in remaining
    )

    style_counts = Counter(
        climb["style"] for climb in remaining
    )

    grade_gaps = {}

    for grade in GRADES:
        grade_gaps[grade] = {}

        for index, sub in enumerate(SUBS):
            target = state["gradeTargets"][grade][index]
            current = grade_counts[(grade, sub)]

            grade_gaps[grade][sub] = {
                "current": current,
                "target": target,
                "deficit": max(0, target - current),
            }

    style_gaps = {}

    for style in STYLES:
        target = state["styleTargets"][style]
        current = style_counts[style]

        style_gaps[style] = {
            "current": current,
            "target": target,
            "deficit": max(0, target - current),
        }

    return {
        "remaining_active_climbs": len(remaining),
        "selected_wall_ids": sorted(selected),
        "grade_gaps": grade_gaps,
        "style_gaps": style_gaps,
    }


def get_climb_combination_distribution(gym_id, selected_wall_ids):
    """
    Analyse grade, subgrade, style and terrain combinations
    after excluding active climbs on reset walls.

    This function is read-only.
    """
    state = repository.get_state(gym_id)

    wall_map = {
        wall["id"]: wall
        for wall in state["walls"]
    }

    selected = set(selected_wall_ids)

    if not selected or not selected.issubset(wall_map):
        raise ValueError("Select valid walls for the reset")

    # These climbs remain after the selected walls are reset.
    remaining = [
        climb
        for climb in state["climbs"]
        if climb["status"] == "Active"
        and climb["wallId"] not in selected
    ]

    # Count each combination of grade, style and terrain.
    combination_counts = Counter()

    for climb in remaining:
        wall = wall_map.get(climb["wallId"])

        if wall is None:
            continue

        terrain = classify_terrain(wall["angle"])

        combination = (
            climb["grade"],
            climb["sub"],
            climb["style"],
            terrain,
        )

        combination_counts[combination] += 1

    # Format the results as JSON-compatible dictionaries.
    combinations = []

    for combination, count in sorted(
        combination_counts.items()
    ):
        grade, sub, style, terrain = combination

        combinations.append({
            "grade": grade,
            "subgrade": sub,
            "style": style,
            "terrain": terrain,
            "current_count": count,
        })

    selected_walls = [
        {
            "wall_id": wall["id"],
            "name": wall["name"],
            "angle": wall["angle"],
            "terrain": classify_terrain(wall["angle"]),
            "new_climb_count": state["newCounts"].get(
                wall["id"], 0
            ),
        }
        for wall in state["walls"]
        if wall["id"] in selected
    ]

    return {
        "gym_id": gym_id,
        "remaining_climb_count": len(remaining),
        "selected_walls": selected_walls,
        "combinations": combinations,
    }

