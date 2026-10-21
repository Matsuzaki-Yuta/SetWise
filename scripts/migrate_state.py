
"""Migrate a gym's legacy STATE into structured DynamoDB items.

Usage:
    python scripts/migrate_state.py gym-a

The original STATE item is preserved.
"""

import json
import os
import sys
from decimal import Decimal

import boto3
from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import ClientError


REGION = os.environ.get("AWS_REGION", "ap-southeast-2")
TABLE_NAME = os.environ.get(
    "DYNAMODB_TABLE",
    "n11761776-setwise-data",
)

serializer = TypeSerializer()


def serialize_item(item):
    """Convert Python values to DynamoDB attribute values."""
    return {
        key: serializer.serialize(value)
        for key, value in item.items()
    }


def make_item(gym_id, item_key, **attributes):
    """Create a DynamoDB item with our composite primary key."""
    return {
        "gym_id": gym_id,
        "item_key": item_key,
        **attributes,
    }


def build_items(gym_id, state):
    """Convert a legacy gym document into individual records."""
    items = [
        make_item(
            gym_id,
            "META",
            record_type="gym",
            schema_version=1,
        ),
        make_item(
            gym_id,
            "TARGETS",
            record_type="targets",
            gradeTargets=state["gradeTargets"],
            styleTargets=state["styleTargets"],
        ),
        make_item(
            gym_id,
            "PLANNER",
            record_type="planner",
            selected=state.get("selected", []),
            newCounts=state.get("newCounts", {}),
            plan=state.get("plan", []),
        ),
    ]

    for wall in state["walls"]:
        items.append(
            make_item(
                gym_id,
                f"WALL#{wall['id']}",
                record_type="wall",
                **wall,
            )
        )

    for climb in state["climbs"]:
        items.append(
            make_item(
                gym_id,
                f"CLIMB#{climb['id']}",
                record_type="climb",
                **climb,
            )
        )

    return items


def migrate(gym_id):
    client = boto3.client("dynamodb", region_name=REGION)

    # Read the original gym record without modifying it.
    response = client.get_item(
        TableName=TABLE_NAME,
        Key=serialize_item({
            "gym_id": gym_id,
            "item_key": "STATE",
        }),
        ConsistentRead=True,
    )

    original = response.get("Item")

    if not original:
        raise RuntimeError(
            f"No legacy STATE item exists for {gym_id}"
        )

    state = json.loads(
        original["document"]["S"],
        parse_float=Decimal,
    )

    items = build_items(gym_id, state)

    # DynamoDB transactions support a maximum of 100 actions.
    if len(items) > 100:
        raise RuntimeError(
            f"{len(items)} items exceed this migration's "
            "100-action transaction limit."
        )

    print(f"Gym: {gym_id}")
    print(f"Walls: {len(state['walls'])}")
    print(f"Climbs: {len(state['climbs'])}")
    print(f"New records: {len(items)}")

    operations = []

    for item in items:
        operations.append({
            "Put": {
                "TableName": TABLE_NAME,
                "Item": serialize_item(item),
                "ConditionExpression":
                    "attribute_not_exists(gym_id)",
            }
        })

    # All records are written together or none are written.
    try:
        client.transact_write_items(
            TransactItems=operations
        )

    except ClientError as exc:
        code = exc.response["Error"]["Code"]

        if code == "TransactionCanceledException":
            raise RuntimeError(
                "Migration stopped. Records may already exist "
                "or the transaction was cancelled. "
                "No existing records were overwritten."
            ) from exc

        raise

    print("Migration completed successfully.")
    print("Original STATE record preserved.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: python scripts/migrate_state.py <gym_id>"
        )

    migrate(sys.argv[1])
