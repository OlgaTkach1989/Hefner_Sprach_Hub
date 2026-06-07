from __future__ import annotations

import os

import requests
from jupyterhub.auth import Authenticator
from traitlets import Unicode


class ExternalTokenAuthenticator(Authenticator):
    auto_login = True
    token_exchange_url = Unicode(config=True)
    token_exchange_service_token = Unicode(config=True)

    async def authenticate(self, handler, data=None):
        login_token = str(handler.get_argument("login_token", "") or "").strip()
        if not login_token:
            return None
        if not self.token_exchange_url or not self.token_exchange_service_token:
            return None

        response = requests.post(
            self.token_exchange_url,
            json={"loginToken": login_token},
            headers={"Authorization": f"Bearer {self.token_exchange_service_token}"},
            timeout=int(os.getenv("JUPYTERHUB_LOGIN_EXCHANGE_TIMEOUT_SECONDS", "10")),
        )
        if response.status_code != 200:
            return None

        payload = response.json()
        return {
            "name": payload["name"],
            "auth_state": payload.get("authState") or {},
        }
