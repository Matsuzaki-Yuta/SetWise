from flask import Blueprint, abort, flash,redirect, render_template, request, url_for
from app.database import repository
from app.services.actions import apply_action
from app.services.analysis_service import dashboard_data
from app.services.constants import GRADES, SUBS, STYLES, PAGES
import copy
from app.database.dynamodb_repository import ConcurrentUpdateError,DataMigrationError


bp = Blueprint("main", __name__)

GYMS = {
    "gym-a": "SetWise Demo Gym A",
    "gym-b": "SetWise Demo Gym B",
    "gym-c": "SetWise Demo Gym C",
}


def get_gym_id():
    """Get and validate the selected demonstration gym."""
    gym_id = request.values.get("gym_id", "gym-a")

    if gym_id not in GYMS:
        abort(404)

    return gym_id


@bp.get("/")
def home():
    page = request.args.get("page", "overview")

    if page not in PAGES:
        abort(404)

    gym_id = get_gym_id()
    state = repository.get_state(gym_id)

    return render_template(
        "index.html",
        page=page,
        state=state,
        gym_id=gym_id,
        gyms=GYMS,
        grades=GRADES,
        subs=SUBS,
        styles=STYLES,
        **dashboard_data(state)
    )



@bp.post("/action")
def action():
    page = request.form.get("page", "overview")

    if page not in PAGES:
        page = "overview"

    gym_id = get_gym_id()

    try:
        original_state = repository.get_state(gym_id)
        state = copy.deepcopy(original_state)

        message = apply_action(
            state,
            request.form.get("action", ""),
            request.form,
        )

        repository.save_state(
            state,
            gym_id,
            original_state=original_state,
        )

        flash(message)

    except ConcurrentUpdateError:
        flash(
            "Another update may have occurred. "
            "Please refresh the page and try again."
        )

    except (ValueError, KeyError, TypeError) as exc:
        flash(f"Could not complete action: {exc}")

    except DataMigrationError as exc:
        flash(str(exc))

    return redirect(
        url_for("home", page=page, gym_id=gym_id)
    )
