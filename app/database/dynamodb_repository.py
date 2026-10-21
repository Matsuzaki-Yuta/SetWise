
"""Structured DynamoDB repository for SetWise."""

import copy
import json
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError
from flask import current_app
from app.services.inventory_service import initial_state
from boto3.dynamodb.types import TypeSerializer

class ConcurrentUpdateError(Exception):
    """A record changed after it was read."""


class DataMigrationError(Exception):
    """Structured gym records are missing."""


def get_table():
    dynamodb = boto3.resource(
        "dynamodb",
        region_name=current_app.config["AWS_REGION"],
    )
    return dynamodb.Table(current_app.config["DYNAMODB_TABLE"])


def to_dynamodb(value):
    """Recursively convert floats into DynamoDB-compatible Decimals."""
    if isinstance(value, float):
        return Decimal(str(value))

    if isinstance(value, dict):
        return {
            key: to_dynamodb(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [to_dynamodb(item) for item in value]

    return value


def to_python(value):
    """Convert DynamoDB Decimals to normal Python numbers."""
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)

    if isinstance(value, list):
        return [to_python(item) for item in value]

    if isinstance(value, dict):
        return {
            key: to_python(item)
            for key, item in value.items()
        }

    return value


def query_gym_items(gym_id):
    """Read all structured items belonging to one gym."""
    from boto3.dynamodb.conditions import Key

    table = get_table()
    items = []
    query_args = {
        "KeyConditionExpression": Key("gym_id").eq(gym_id),
        "ConsistentRead": True,
    }

    while True:
        response = table.query(**query_args)
        items.extend(response.get("Items", []))

        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break

        query_args["ExclusiveStartKey"] = last_key

    return [to_python(item) for item in items]


def initialize_gym(gym_id):
    """Create structured records for a new gym."""

    table = get_table()

    state = initial_state()

    records = state_to_records(state)

    records["META"] = {
        "record_type": "gym",
        "schema_version": 1,
    }

    with table.batch_writer(
        overwrite_by_pkeys=["gym_id", "item_key"]
    ) as batch:
        for key, attributes in records.items():
            batch.put_item(
                Item=to_dynamodb({
                    "gym_id": gym_id,
                    "item_key": key,
                    **attributes,
                })
            )


def get_state(gym_id="gym-a"):
    """Reconstruct the state expected by existing Flask services."""
    items = query_gym_items(gym_id)

    state = {
        "walls": [],
        "climbs": [],
        "gradeTargets": {},
        "styleTargets": {},
        "selected": [],
        "newCounts": {},
        "plan": [],
    }

    versions = {}
    found_targets = False
    found_planner = False
    found_meta = False

    for item in items:
        key = item["item_key"]

        # The original JSON document is a backup only.
        if key == "STATE":
            continue

        versions[key] = item.get("version", 0)

        if key == "META":
            found_meta = True

        elif key.startswith("WALL#"):
            state["walls"].append({
                field: item[field]
                for field in ("id", "name", "angle")
            })

        elif key.startswith("CLIMB#"):
            state["climbs"].append({
                field: item[field]
                for field in (
                    "id", "wallId", "grade",
                    "sub", "style", "status"
                )
            })

        elif key == "TARGETS":
            state["gradeTargets"] = item["gradeTargets"]
            state["styleTargets"] = item["styleTargets"]
            found_targets = True

        elif key == "PLANNER":
            state["selected"] = item.get("selected", [])
            state["newCounts"] = item.get("newCounts", {})
            state["plan"] = item.get("plan", [])
            found_planner = True

    if not (found_meta and found_targets and found_planner):
        raise DataMigrationError(
            f"Gym {gym_id} has not been migrated to "
            "structured DynamoDB records."
        )

    state["walls"].sort(key=lambda wall: wall["id"])
    state["climbs"].sort(key=lambda climb: climb["id"])

    # Private metadata used by our repository.
    # It is NOT persisted as a gym attribute.
    state["_versions"] = versions

    return state


def state_to_records(state):
    """Convert an application state into DynamoDB records."""
    records = {}

    for wall in state["walls"]:
        key = f"WALL#{wall['id']}"
        records[key] = {
            "record_type": "wall",
            **wall,
        }

    for climb in state["climbs"]:
        key = f"CLIMB#{climb['id']}"
        records[key] = {
            "record_type": "climb",
            **climb,
        }

    records["TARGETS"] = {
        "record_type": "targets",
        "gradeTargets": state["gradeTargets"],
        "styleTargets": state["styleTargets"],
    }

    records["PLANNER"] = {
        "record_type": "planner",
        "selected": state["selected"],
        "newCounts": state["newCounts"],
        "plan": state["plan"],
    }

    return records


def save_state(state, gym_id="gym-a", original_state=None):
    """Write only changed records, checking their versions."""
    if original_state is None:
        raise ValueError(
            "original_state is required for safe DynamoDB writes"
        )

    before = state_to_records(original_state)
    after = state_to_records(state)
    versions = original_state["_versions"]

    operations = []

    for key in sorted(set(before) | set(after)):
        old_record = before.get(key)
        new_record = after.get(key)

        # Ignore records that have not changed.
        if old_record == new_record:
            continue

        dynamodb_key = {
            "gym_id": gym_id,
            "item_key": key,
        }

        if new_record is None:
            operation = {
                "Delete": {
                    "TableName": current_app.config["DYNAMODB_TABLE"],
                    "Key": to_dynamodb(dynamodb_key),
                }
            }
            operation_type = "Delete"

        else:
            previous_version = versions.get(key, 0)

            new_item = {
                **dynamodb_key,
                **copy.deepcopy(new_record),
                "version": previous_version + 1,
            }

            operation = {
                "Put": {
                    "TableName": current_app.config["DYNAMODB_TABLE"],
                    "Item": to_dynamodb(new_item),
                }
            }
            operation_type = "Put"

        params = operation[operation_type]

        if old_record is None:
            # Creating a new item must not overwrite another item.
            params["ConditionExpression"] = (
                "attribute_not_exists(item_key)"
            )

        elif versions.get(key, 0) == 0:
            # Migrated records initially have no version field.
            params["ConditionExpression"] = (
                "attribute_not_exists(#version)"
            )
            params["ExpressionAttributeNames"] = {
                "#version": "version",
            }

        else:
            # Ensure nobody changed this item after our read.
            params["ConditionExpression"] = (
                "#version = :expected"
            )
            params["ExpressionAttributeNames"] = {
                "#version": "version",
            }
            params["ExpressionAttributeValues"] = {
                ":expected": versions[key],
            }

        operations.append(operation)

    if not operations:
        return

    if len(operations) > 100:
        raise ValueError(
            "Too many records changed in one operation "
            "(maximum 100 transaction actions)."
        )

    
    # Use the low-level DynamoDB client for transactions.
    client = boto3.client(
        "dynamodb",
        region_name=current_app.config["AWS_REGION"],
    )

    serializer = TypeSerializer()

    def encode(attributes):
        """Convert regular Python attributes to DynamoDB API format."""
        return {
            key: serializer.serialize(value)
            for key, value in attributes.items()
        }

    # Serialize request values exactly once.
    for operation in operations:
        params = next(iter(operation.values()))

        if "Key" in params:
            params["Key"] = encode(params["Key"])

        if "Item" in params:
            params["Item"] = encode(params["Item"])

        if "ExpressionAttributeValues" in params:
            params["ExpressionAttributeValues"] = encode(
                params["ExpressionAttributeValues"]
            )

    try:
        client.transact_write_items(
            TransactItems=operations
        )

    except ClientError as exc:
        error = exc.response["Error"]["Code"]

        if error == "TransactionCanceledException":
            raise ConcurrentUpdateError(
                "DynamoDB rejected the transaction. "
                "A record may have changed since it was loaded. "
                "Refresh the page and try again."
            ) from exc

        raise
