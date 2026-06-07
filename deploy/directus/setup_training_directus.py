from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


TRAINING_COLLECTION = "training_content"
TRAINING_FLOW_NAME = "training-content-sync"
TRAINING_OPERATION_KEY = "training_content_sync_request"


class DirectusSetupError(RuntimeError):
    """Raised when Directus provisioning fails."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Provision Directus training authoring collection and sync flow.")
    parser.add_argument("--env-file", default=".env", help="Path to the deployment .env file.")
    return parser.parse_args()


def load_env(env_file: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not env_file.exists():
        raise DirectusSetupError(f"Env file was not found: {env_file}")

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in raw_line:
            continue
        key, value = raw_line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def env_required(env: dict[str, str], key: str) -> str:
    value = str(env.get(key, "")).strip()
    if not value:
        raise DirectusSetupError(f"Required env var is empty: {key}")
    return value


def directus_base_url(env: dict[str, str]) -> str:
    bind_host = str(env.get("DIRECTUS_HTTP_BIND", "127.0.0.1") or "127.0.0.1").strip()
    port = str(env.get("DIRECTUS_HTTP_PORT", "8055") or "8055").strip()
    if bind_host in {"0.0.0.0", "::"}:
        bind_host = "127.0.0.1"
    return f"http://{bind_host}:{port}"


def directus_request(
    *,
    base_url: str,
    method: str,
    path: str,
    token: str | None = None,
    payload: Any | None = None,
    query: dict[str, str] | None = None,
) -> tuple[int, Any | None]:
    url = f"{base_url}{path}"
    if query:
        url = f"{url}?{urlencode(query, doseq=True)}"

    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else None
    except HTTPError as exc:
        body = exc.read().decode("utf-8")
        parsed = json.loads(body) if body else None
        return exc.code, parsed


def directus_login(*, base_url: str, email: str, password: str) -> str:
    status_code, payload = directus_request(
        base_url=base_url,
        method="POST",
        path="/auth/login",
        payload={"email": email, "password": password},
    )
    if status_code != 200 or not payload:
        raise DirectusSetupError(f"Directus login failed with status {status_code}: {payload}")
    return str(payload["data"]["access_token"])


def fetch_all(*, base_url: str, token: str, path: str, fields: str) -> list[dict[str, Any]]:
    status_code, payload = directus_request(
        base_url=base_url,
        method="GET",
        path=path,
        token=token,
        query={"limit": "-1", "fields": fields},
    )
    if status_code != 200 or not payload:
        raise DirectusSetupError(f"Directus GET {path} failed with status {status_code}: {payload}")
    return list(payload.get("data") or [])


def ensure_collection(*, base_url: str, token: str) -> None:
    collections = fetch_all(base_url=base_url, token=token, path="/collections", fields="collection")
    if any(item.get("collection") == TRAINING_COLLECTION for item in collections):
        return

    payload = {
        "collection": TRAINING_COLLECTION,
        "meta": {
            "icon": "article",
            "note": "Authoring source for backend TrainingContentItem sync.",
            "hidden": False,
            "singleton": False,
            "accountability": "all",
            "collapse": "open",
        },
        "schema": {
            "name": TRAINING_COLLECTION,
        },
    }
    status_code, response = directus_request(
        base_url=base_url,
        method="POST",
        path="/collections",
        token=token,
        payload=payload,
    )
    if status_code != 200:
        raise DirectusSetupError(f"Failed to create Directus collection {TRAINING_COLLECTION}: {response}")


def ensure_field(*, base_url: str, token: str, collection: str, field_payload: dict[str, Any]) -> None:
    field_name = str(field_payload["field"])
    fields = fetch_all(base_url=base_url, token=token, path=f"/fields/{collection}", fields="field")
    if any(item.get("field") == field_name for item in fields):
        return

    status_code, response = directus_request(
        base_url=base_url,
        method="POST",
        path=f"/fields/{collection}",
        token=token,
        payload=field_payload,
    )
    if status_code != 200:
        raise DirectusSetupError(f"Failed to create field {collection}.{field_name}: {response}")


def ensure_fields(*, base_url: str, token: str) -> None:
    field_payloads = [
        {
            "field": "slug",
            "type": "string",
            "meta": {"interface": "input", "required": True, "width": "half", "note": "Backend slug"},
            "schema": {"is_nullable": False, "is_unique": True, "max_length": 120},
        },
        {
            "field": "name",
            "type": "string",
            "meta": {"interface": "input", "required": True, "width": "half"},
            "schema": {"is_nullable": False, "max_length": 220},
        },
        {
            "field": "description",
            "type": "text",
            "meta": {"interface": "input-multiline", "width": "full"},
            "schema": {"is_nullable": True},
        },
        {
            "field": "body_markdown",
            "type": "text",
            "meta": {"interface": "input-multiline", "width": "full"},
            "schema": {"is_nullable": False, "default_value": ""},
        },
        {
            "field": "content_kind",
            "type": "string",
            "meta": {"interface": "input", "width": "half", "note": "article | faq | exercise | notebook"},
            "schema": {"is_nullable": False, "max_length": 40, "default_value": "article"},
        },
        {
            "field": "status",
            "type": "string",
            "meta": {"interface": "input", "width": "half", "note": "draft | review | published | retired"},
            "schema": {"is_nullable": False, "max_length": 32, "default_value": "draft"},
        },
        {
            "field": "access_scope",
            "type": "string",
            "meta": {"interface": "input", "width": "half", "note": "public | entitled | internal"},
            "schema": {"is_nullable": False, "max_length": 32, "default_value": "entitled"},
        },
        {
            "field": "difficulty",
            "type": "string",
            "meta": {"interface": "input", "width": "half", "note": "introductory | intermediate | advanced"},
            "schema": {"is_nullable": False, "max_length": 32, "default_value": "intermediate"},
        },
        {
            "field": "audience_match_mode",
            "type": "string",
            "meta": {"interface": "input", "width": "half", "note": "any | all"},
            "schema": {"is_nullable": False, "max_length": 16, "default_value": "any"},
        },
        {
            "field": "course_slug",
            "type": "string",
            "meta": {"interface": "input", "width": "half", "note": "Existing OnlineCourse slug"},
            "schema": {"is_nullable": False, "max_length": 120, "default_value": "investment-analysis-demo"},
        },
        {
            "field": "owner_email",
            "type": "string",
            "meta": {"interface": "input", "width": "half", "note": "Optional Course Owner email"},
            "schema": {"is_nullable": False, "max_length": 255, "default_value": ""},
        },
        {
            "field": "source_url",
            "type": "string",
            "meta": {"interface": "input", "width": "full"},
            "schema": {"is_nullable": False, "max_length": 500, "default_value": ""},
        },
        {
            "field": "search_keywords",
            "type": "string",
            "meta": {"interface": "input", "width": "full"},
            "schema": {"is_nullable": False, "max_length": 400, "default_value": ""},
        },
        {
            "field": "version_label",
            "type": "string",
            "meta": {"interface": "input", "width": "half"},
            "schema": {"is_nullable": False, "max_length": 40, "default_value": ""},
        },
        {
            "field": "estimated_minutes",
            "type": "integer",
            "meta": {"interface": "input", "width": "half"},
            "schema": {"is_nullable": False, "default_value": 0},
        },
        {
            "field": "is_repeatable_on_demand",
            "type": "boolean",
            "meta": {"interface": "boolean", "width": "half"},
            "schema": {"is_nullable": False, "default_value": True},
        },
        {
            "field": "supports_inline_lab",
            "type": "boolean",
            "meta": {"interface": "boolean", "width": "half"},
            "schema": {"is_nullable": False, "default_value": False},
        },
        {
            "field": "asset_classes",
            "type": "json",
            "meta": {"width": "full", "note": 'Example: [{"slug":"credit","name":"Credit"}]'},
            "schema": {"is_nullable": False, "default_value": []},
        },
        {
            "field": "topics",
            "type": "json",
            "meta": {"width": "full", "note": 'Example: ["cva","pricing"]'},
            "schema": {"is_nullable": False, "default_value": []},
        },
        {
            "field": "audience_slugs",
            "type": "json",
            "meta": {"width": "full", "note": 'Example: ["interns","institutional-skills"]'},
            "schema": {"is_nullable": False, "default_value": []},
        },
        {
            "field": "cross_references",
            "type": "json",
            "meta": {"width": "full", "note": 'Example: [{"slug":"reference-faq","relationType":"related"}]'},
            "schema": {"is_nullable": False, "default_value": []},
        },
    ]

    for field_payload in field_payloads:
        ensure_field(base_url=base_url, token=token, collection=TRAINING_COLLECTION, field_payload=field_payload)


def find_by_name(items: list[dict[str, Any]], *, name: str) -> dict[str, Any] | None:
    for item in items:
        if item.get("name") == name:
            return item
    return None


def find_by_key(items: list[dict[str, Any]], *, key: str) -> dict[str, Any] | None:
    for item in items:
        if item.get("key") == key:
            return item
    return None


def ensure_training_sync_flow(*, base_url: str, token: str, env: dict[str, str]) -> str:
    sync_token = env_required(env, "TRAINING_DIRECTUS_SYNC_TOKEN")
    sync_url = str(
        env.get("TRAINING_DIRECTUS_SYNC_INTERNAL_URL")
        or "http://backend:1212/api/training/internal/directus/content-sync/"
    ).strip()
    if not sync_url:
        raise DirectusSetupError("TRAINING_DIRECTUS_SYNC_INTERNAL_URL resolved to an empty value.")

    desired_flow = {
        "name": TRAINING_FLOW_NAME,
        "status": "active",
        "trigger": "event",
        "accountability": "$full",
        "options": {
            "type": "action",
            "scope": ["items.create", "items.update"],
            "collections": [TRAINING_COLLECTION],
        },
    }

    desired_operation = {
        "name": "training-content-sync-request",
        "key": TRAINING_OPERATION_KEY,
        "type": "request",
        "position_x": 19,
        "position_y": 1,
        "options": {
            "method": "POST",
            "url": sync_url,
            "headers": [
                {"header": "Content-Type", "value": "application/json"},
                {"header": "Authorization", "value": f"Bearer {sync_token}"},
            ],
            "body": {
                "operation": "upsert",
                "externalId": "{{$trigger.key}}",
                "slug": "{{$trigger.payload.slug}}",
                "name": "{{$trigger.payload.name}}",
                "description": "{{$trigger.payload.description}}",
                "bodyMarkdown": "{{$trigger.payload.body_markdown}}",
                "contentKind": "{{$trigger.payload.content_kind}}",
                "status": "{{$trigger.payload.status}}",
                "accessScope": "{{$trigger.payload.access_scope}}",
                "difficulty": "{{$trigger.payload.difficulty}}",
                "audienceMatchMode": "{{$trigger.payload.audience_match_mode}}",
                "courseSlug": "{{$trigger.payload.course_slug}}",
                "ownerEmail": "{{$trigger.payload.owner_email}}",
                "sourceUrl": "{{$trigger.payload.source_url}}",
                "searchKeywords": "{{$trigger.payload.search_keywords}}",
                "versionLabel": "{{$trigger.payload.version_label}}",
                "estimatedMinutes": "{{$trigger.payload.estimated_minutes}}",
                "isRepeatableOnDemand": "{{$trigger.payload.is_repeatable_on_demand}}",
                "supportsInlineLab": "{{$trigger.payload.supports_inline_lab}}",
                "assetClasses": "{{$trigger.payload.asset_classes}}",
                "topics": "{{$trigger.payload.topics}}",
                "audienceSlugs": "{{$trigger.payload.audience_slugs}}",
                "crossReferences": "{{$trigger.payload.cross_references}}",
            },
        },
    }

    flows = fetch_all(base_url=base_url, token=token, path="/flows", fields="id,name,operation")
    flow = find_by_name(flows, name=TRAINING_FLOW_NAME)
    if flow is None:
        status_code, response = directus_request(
            base_url=base_url,
            method="POST",
            path="/flows",
            token=token,
            payload=desired_flow,
        )
        if status_code != 200:
            raise DirectusSetupError(f"Failed to create flow {TRAINING_FLOW_NAME}: {response}")
        flow = response["data"]
    else:
        status_code, response = directus_request(
            base_url=base_url,
            method="PATCH",
            path=f"/flows/{flow['id']}",
            token=token,
            payload=desired_flow,
        )
        if status_code != 200:
            raise DirectusSetupError(f"Failed to update flow {TRAINING_FLOW_NAME}: {response}")
        flow = response["data"]

    operations = fetch_all(base_url=base_url, token=token, path="/operations", fields="id,key,flow")
    operation = find_by_key(operations, key=TRAINING_OPERATION_KEY)
    operation_payload = dict(desired_operation)
    operation_payload["flow"] = flow["id"]
    if operation is None:
        status_code, response = directus_request(
            base_url=base_url,
            method="POST",
            path="/operations",
            token=token,
            payload=operation_payload,
        )
        if status_code != 200:
            raise DirectusSetupError(f"Failed to create Directus request operation: {response}")
        operation = response["data"]
    else:
        status_code, response = directus_request(
            base_url=base_url,
            method="PATCH",
            path=f"/operations/{operation['id']}",
            token=token,
            payload=operation_payload,
        )
        if status_code != 200:
            raise DirectusSetupError(f"Failed to update Directus request operation: {response}")
        operation = response["data"]

    status_code, response = directus_request(
        base_url=base_url,
        method="PATCH",
        path=f"/flows/{flow['id']}",
        token=token,
        payload={"operation": operation["id"]},
    )
    if status_code != 200:
        raise DirectusSetupError(f"Failed to connect flow {TRAINING_FLOW_NAME} to its operation: {response}")
    return str(flow["id"])


def main() -> int:
    args = parse_args()
    env_file = Path(args.env_file).resolve()
    env = load_env(env_file)
    base_url = directus_base_url(env)
    token = directus_login(
        base_url=base_url,
        email=env_required(env, "DIRECTUS_ADMIN_EMAIL"),
        password=env_required(env, "DIRECTUS_ADMIN_PASSWORD"),
    )

    ensure_collection(base_url=base_url, token=token)
    ensure_fields(base_url=base_url, token=token)
    flow_id = ensure_training_sync_flow(base_url=base_url, token=token, env=env)

    result = {
        "collection": TRAINING_COLLECTION,
        "flowName": TRAINING_FLOW_NAME,
        "flowId": flow_id,
        "directusBaseUrl": base_url,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except DirectusSetupError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
