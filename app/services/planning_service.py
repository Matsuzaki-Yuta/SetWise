from collections import Counter
from uuid import uuid4
from .constants import GRADES, SUBS, STYLES

def generate_plan(state):
    """Simple deterministic suggestions; Bedrock is NOT integrated."""
    wall_ids = {w["id"] for w in state["walls"]}
    selected = [wid for wid in state["selected"] if wid in wall_ids]
    remaining = [c for c in state["climbs"] if c["status"] == "Active" and c["wallId"] not in selected]
    counts = Counter((c["grade"], c["sub"]) for c in remaining)
    styles = Counter(c["style"] for c in remaining)
    wall_grades = Counter((c["wallId"], c["grade"]) for c in remaining)
    result = []
    for wall_id in selected:
        for _ in range(max(0, min(30, int(state["newCounts"].get(wall_id, 0))))):
            candidates = []
            for grade in GRADES:
                for i, sub in enumerate(SUBS):
                    target = state["gradeTargets"][grade][i]
                    deficit = target - counts[(grade, sub)]
                    candidates.append((deficit*8 - wall_grades[(wall_id, grade)]*1.5 + (0.2 if target > 0 else 0), grade, sub))
            _, grade, sub = max(candidates, key=lambda x: x[0])
            style = max(STYLES, key=lambda s: state["styleTargets"][s] - styles[s])
            result.append(dict(id=uuid4().hex, wallId=wall_id, grade=grade, sub=sub, style=style))
            counts[(grade, sub)] += 1
            styles[style] += 1
            wall_grades[(wall_id, grade)] += 1
    return result
