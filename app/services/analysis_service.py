from collections import Counter
from .constants import GRADES, SUBS, STYLES

def dashboard_data(state):
    active = [c for c in state["climbs"] if c["status"] == "Active"]
    planned = [c for c in state["climbs"] if c["status"] == "Planned"]
    grade_counts = Counter(c["grade"] for c in active)
    style_counts = Counter(c["style"] for c in active)
    total_goal = sum(sum(v) for v in state["gradeTargets"].values())
    grade_rows = [dict(name=g, current=grade_counts[g], goal=sum(state["gradeTargets"][g])) for g in GRADES]
    style_rows = [dict(name=s, current=style_counts[s], goal=state["styleTargets"][s]) for s in STYLES]
    max_grade = max([1]+[max(r["current"],r["goal"]) for r in grade_rows])
    max_style = max([1]+[max(r["current"],r["goal"]) for r in style_rows])
    for rows, limit in ((grade_rows, max_grade), (style_rows, max_style)):
        for r in rows:
            r["current_pct"] = round(r["current"] / limit * 100, 1)
            r["goal_pct"] = round(r["goal"] / limit * 100, 1)
    selected_set = set(state["selected"])
    removal_count = sum(c["wallId"] in selected_set for c in active)
    by_wall = {w["id"]: [c for c in active if c["wallId"] == w["id"]] for w in state["walls"]}
    return dict(active=active, planned=planned, grade_rows=grade_rows, style_rows=style_rows,
                by_wall=by_wall, total_goal=total_goal, removal_count=removal_count,
                selected_set=selected_set, wall_map={w["id"]:w for w in state["walls"]})
