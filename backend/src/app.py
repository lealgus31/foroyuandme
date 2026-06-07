import json
import os
from datetime import datetime, timezone

import boto3

TABLE_NAME = os.environ["TABLE_NAME"]
ADMIN_TOKEN = os.environ["ADMIN_TOKEN"]
STAGE1_UNLOCK_AT = datetime.fromisoformat(os.environ.get("STAGE1_UNLOCK_AT", "2026-06-08T18:00:00Z").replace("Z", "+00:00")).astimezone(timezone.utc)
STAGE2_UNLOCK_AT = datetime.fromisoformat(os.environ.get("STAGE2_UNLOCK_AT", "2026-06-09T07:00:00Z").replace("Z", "+00:00")).astimezone(timezone.utc)

STAGES = ("sehh", "ukq", "iwnnu", "ia")
TABLE = boto3.resource("dynamodb").Table(TABLE_NAME)
GAME_PK = "game"


def utc_now():
    return datetime.now(timezone.utc)


def iso_now():
    return utc_now().isoformat()


def empty_state():
    return {
        "pk": GAME_PK,
        "solvedStages": {},
        "forcedUnlocks": {},
        "updatedAt": iso_now()
    }


def load_state():
    response = TABLE.get_item(Key={"pk": GAME_PK})
    item = response.get("Item") or empty_state()
    item.setdefault("solvedStages", {})
    item.setdefault("forcedUnlocks", {})
    return item


def save_state(state):
    TABLE.put_item(Item=state)


def cors_headers():
    return {
        "content-type": "application/json",
        "access-control-allow-origin": "*",
        "access-control-allow-methods": "GET,POST,OPTIONS",
        "access-control-allow-headers": "content-type,authorization"
    }


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": cors_headers(),
        "body": json.dumps(body, ensure_ascii=False)
    }


def parse_json_body(event):
    body = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        import base64
        body = base64.b64decode(body).decode("utf-8")
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {}


def compute_available(state, now=None):
    now = now or utc_now()
    solved = state.get("solvedStages", {})
    forced = state.get("forcedUnlocks", {})

    available = {
        "sehh": bool(forced.get("sehh")) or now >= STAGE1_UNLOCK_AT,
        "ukq": bool(forced.get("ukq")) or (now >= STAGE2_UNLOCK_AT and bool(solved.get("sehh"))),
        "iwnnu": bool(forced.get("iwnnu")) or bool(solved.get("ukq")),
        "ia": bool(forced.get("ia")) or bool(solved.get("iwnnu"))
    }

    return available


def public_state(state):
    solved = {stage: bool(state.get("solvedStages", {}).get(stage)) for stage in STAGES}
    available = compute_available(state)
    return {
        "solvedStages": solved,
        "availableStages": available,
        "serverTime": iso_now(),
        "updatedAt": state.get("updatedAt", "")
    }


def require_stage(stage_id):
    if stage_id not in STAGES:
        raise ValueError("Unknown stage")
    return stage_id


def authorize_admin(event):
    headers = event.get("headers") or {}
    auth_header = headers.get("authorization") or headers.get("Authorization") or ""
    token = auth_header.replace("Bearer ", "", 1).strip()
    return token and token == ADMIN_TOKEN


def lambda_handler(event, context):
    method = (event.get("requestContext", {}).get("http", {}) or {}).get("method") or event.get("httpMethod") or "GET"
    raw_path = event.get("rawPath") or event.get("path") or "/"
    path = raw_path.rstrip("/") or "/"

    if method == "OPTIONS":
        return response(200, {"ok": True})

    state = load_state()

    if method == "GET" and path in {"/", "/state"}:
        return response(200, public_state(state))

    if method == "POST" and path == "/solve":
        body = parse_json_body(event)
        try:
            stage_id = require_stage(body.get("stageId"))
        except ValueError as error:
            return response(400, {"ok": False, "message": str(error)})

        available = compute_available(state)
        if not available.get(stage_id):
            return response(403, {"ok": False, "message": "Stage is not unlocked yet."})

        solved = state.setdefault("solvedStages", {})
        solved[stage_id] = True
        state["updatedAt"] = iso_now()
        save_state(state)
        return response(200, {"ok": True, **public_state(state)})

    if method == "POST" and path == "/admin/unlock":
        if not authorize_admin(event):
            return response(401, {"ok": False, "message": "Unauthorized."})

        body = parse_json_body(event)
        try:
            stage_id = require_stage(body.get("stageId"))
        except ValueError as error:
            return response(400, {"ok": False, "message": str(error)})

        forced = state.setdefault("forcedUnlocks", {})
        forced[stage_id] = True
        state["updatedAt"] = iso_now()
        save_state(state)
        return response(200, {"ok": True, **public_state(state)})

    return response(404, {"ok": False, "message": "Not found"})
