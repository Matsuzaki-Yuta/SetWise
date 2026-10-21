from uuid import uuid4
from .constants import GRADES, SUBS, STYLES
from .planning_service import generate_plan
from .validation import nonnegative_int

def apply_action(state, op, form):
    wall_ids = {w["id"] for w in state["walls"]}
    if op == "add_wall":
        name = form.get("name", "").strip()
        angle = float(form.get("angle", ""))
        if not name or len(name) > 60 or not -90 <= angle <= 90: raise ValueError("Enter a wall name and valid angle between -90 and 90")
        state["walls"].append(dict(id=uuid4().hex, name=name, angle=angle))
        message = "Wall added."
    elif op == "delete_wall":
        wid = form["wall_id"]
        if wid not in wall_ids: raise ValueError("Wall not found")
        if any(c["wallId"] == wid and c["status"] != "Removed" for c in state["climbs"]):
            raise ValueError("Remove or reset this wall's climbs before deleting it")
        state["walls"] = [w for w in state["walls"] if w["id"] != wid]
        state["selected"] = [w for w in state["selected"] if w != wid]
        state["newCounts"].pop(wid, None)
        message = "Wall removed."
    elif op == "add_climb":
        wid, grade, sub, style = (form[k] for k in ("wall_id", "grade", "sub", "style"))
        if wid not in wall_ids or grade not in GRADES or sub not in SUBS or style not in STYLES: raise ValueError("Invalid climb details")
        state["climbs"].append(dict(id=uuid4().hex, wallId=wid, grade=grade, sub=sub, style=style, status="Active"))
        message = "Climb added."
    elif op == "remove_climb":
        cid = form["climb_id"]
        climb = next((c for c in state["climbs"] if c["id"] == cid), None)
        if not climb: raise ValueError("Climb not found")
        climb["status"] = "Removed"
        message = "Climb marked removed."
    elif op == "save_targets":
        for g in GRADES:
            state["gradeTargets"][g] = [nonnegative_int(form[f"grade_{g}_{sub}"], 200) for sub in SUBS]
        for s in STYLES:
            state["styleTargets"][s] = nonnegative_int(form[f"style_{s}"], 1000)
        message = "Targets saved."
    elif op == "select_walls":
        state["selected"] = [w["id"] for w in state["walls"] if w["id"] in set(form.getlist("wall_ids"))]
        state["newCounts"] = {wid: nonnegative_int(form.get(f"count_{wid}", 5),30) for wid in state["selected"]}
        state["plan"] = []
        message = "Setting-day walls and counts updated."
    elif op == "generate_plan":
        if not state["selected"]: raise ValueError("Select at least one wall first")
        state["plan"] = generate_plan(state)
        message = "Plan generated locally (not by an LLM)."
    elif op == "edit_plan":
        for c in state["plan"]:
            g, sub, style = (form[f"{k}_{c['id']}"] for k in ("grade", "sub", "style"))
            if g not in GRADES or sub not in SUBS or style not in STYLES: raise ValueError("Invalid plan entry")
            c.update(grade=g, sub=sub, style=style)
        message = "Suggested plan updated."
    elif op == "save_plan":
        if not state["plan"]: raise ValueError("Generate a plan first")
        for c in state["plan"]:
            state["climbs"].append({**c, "id":uuid4().hex, "status":"Planned"})
        state["plan"] = []
        message = "Suggestions saved as planned climbs."
    elif op == "activate_planned":
        for c in state["climbs"]:
            if c["status"] == "Planned": c["status"] = "Active"
        message = "Planned climbs activated."
    elif op == "confirm_reset":
        if form.get("confirm") != "yes": raise ValueError("Reset confirmation is required")
        for c in state["climbs"]:
            if c["status"] == "Active" and c["wallId"] in state["selected"]:
                c["status"] = "Removed"
        message = "Active climbs on selected walls marked removed."
    else:
        raise ValueError("Unknown action")
    return message
