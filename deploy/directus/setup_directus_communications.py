from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from setup_training_directus import (
    DirectusSetupError,
    directus_base_url,
    directus_login,
    directus_request,
    env_required,
    fetch_all,
    find_by_name,
    load_env,
)


ONLINE_EMAIL_FLOW_NAME = "online-email"
ONLINE_EMAIL_OPERATION_KEY = "online_email_send"
COURSE_ACCESS_FLOW_NAME = "course-access"
COURSE_ACCESS_OPERATION_KEY = "course_access_send"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Provision Directus communication flows for learning-hub.")
    parser.add_argument("--env-file", default=".env", help="Path to the deployment .env file.")
    parser.add_argument(
        "--write-env",
        action="store_true",
        help="Write resolved flow URLs and mode back into the deployment .env file.",
    )
    return parser.parse_args()


def env_set(env_file: Path, key: str, value: str) -> None:
    lines = env_file.read_text(encoding="utf-8").splitlines()
    updated = False
    output: list[str] = []
    for line in lines:
        if line.startswith(f"{key}="):
            output.append(f"{key}={value}")
            updated = True
        else:
            output.append(line)
    if not updated:
        output.append(f"{key}={value}")
    env_file.write_text("\n".join(output) + "\n", encoding="utf-8")


def upsert_webhook_mail_flow(
    *,
    base_url: str,
    token: str,
    flow_name: str,
    operation_key: str,
    to_expression: str,
) -> str:
    desired_flow = {
        "name": flow_name,
        "status": "active",
        "trigger": "webhook",
        "accountability": "$full",
        "options": {
            "method": "POST",
            "async": False,
        },
    }
    desired_operation = {
        "name": f"{flow_name}-send-mail",
        "key": operation_key,
        "type": "mail",
        "position_x": 19,
        "position_y": 1,
        "options": {
            "to": to_expression,
            "subject": "{{$trigger.body.subject}}",
            "type": "markdown",
            "body": "{{$trigger.body.text}}",
        },
    }

    flows = fetch_all(base_url=base_url, token=token, path="/flows", fields="id,name,operation")
    flow = find_by_name(flows, name=flow_name)
    if flow is None:
        status_code, response = directus_request(
            base_url=base_url,
            method="POST",
            path="/flows",
            token=token,
            payload=desired_flow,
        )
        if status_code != 200:
            raise DirectusSetupError(f"Failed to create flow {flow_name}: {response}")
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
            raise DirectusSetupError(f"Failed to update flow {flow_name}: {response}")
        flow = response["data"]

    operations = fetch_all(base_url=base_url, token=token, path="/operations", fields="id,key,flow")
    operation = next((item for item in operations if item.get("key") == operation_key), None)
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
            raise DirectusSetupError(f"Failed to create operation {operation_key}: {response}")
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
            raise DirectusSetupError(f"Failed to update operation {operation_key}: {response}")
        operation = response["data"]

    status_code, response = directus_request(
        base_url=base_url,
        method="PATCH",
        path=f"/flows/{flow['id']}",
        token=token,
        payload={"operation": operation["id"]},
    )
    if status_code != 200:
        raise DirectusSetupError(f"Failed to connect flow {flow_name} to operation: {response}")
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

    online_email_flow_id = upsert_webhook_mail_flow(
        base_url=base_url,
        token=token,
        flow_name=ONLINE_EMAIL_FLOW_NAME,
        operation_key=ONLINE_EMAIL_OPERATION_KEY,
        to_expression="{{$trigger.body.to}}",
    )
    course_access_flow_id = upsert_webhook_mail_flow(
        base_url=base_url,
        token=token,
        flow_name=COURSE_ACCESS_FLOW_NAME,
        operation_key=COURSE_ACCESS_OPERATION_KEY,
        to_expression="{{$trigger.body.to}}",
    )

    internal_base_url = "http://directus:8055"
    online_email_flow_url = f"{internal_base_url}/flows/trigger/{online_email_flow_id}"
    course_access_flow_url = f"{internal_base_url}/flows/trigger/{course_access_flow_id}"

    if args.write_env:
        env_set(env_file, "ONLINE_EMAIL_MODE", "directus_flow")
        env_set(env_file, "ONLINE_EMAIL_DIRECTUS_TOKEN", "")
        env_set(env_file, "ONLINE_EMAIL_DIRECTUS_FLOW_URL", online_email_flow_url)
        env_set(env_file, "ONLINE_COURSE_ACCESS_DIRECTUS_FLOW_URL", course_access_flow_url)

    result = {
        "onlineEmailFlowId": online_email_flow_id,
        "onlineEmailFlowUrl": online_email_flow_url,
        "courseAccessFlowId": course_access_flow_id,
        "courseAccessFlowUrl": course_access_flow_url,
        "updatedEnv": bool(args.write_env),
        "directusBaseUrl": base_url,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except DirectusSetupError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
