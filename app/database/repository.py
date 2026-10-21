
"""Select the configured persistence backend."""

from flask import current_app

from . import sqlite_repository
from . import dynamodb_repository


def get_backend():
    backend = current_app.config["DATABASE_BACKEND"]

    if backend == "sqlite":
        return sqlite_repository

    if backend == "dynamodb":
        return dynamodb_repository

    raise ValueError(
        f"Unsupported database backend: {backend}"
    )


def get_state(gym_id="gym-a"):
    return get_backend().get_state(gym_id)


def save_state(state, gym_id="gym-a", original_state=None):
    backend = current_app.config["DATABASE_BACKEND"]

    if backend == "sqlite":
        return sqlite_repository.save_state(state, gym_id)

    if backend == "dynamodb":
        return dynamodb_repository.save_state(
            state,
            gym_id,
            original_state=original_state,
        )

    raise ValueError(
        f"Unsupported database backend: {backend}"
    )
