# Current VPS Migration

This note captures the current state of the OVH VPS `51.195.117.210` and the migration path to the self-contained `Hefner Sprach Hub` stack.

## Current server state

Confirmed on `2026-03-25`:

- Docker is installed and running.
- `open-webui` is published on port `3000`.
- System `nginx` is active on ports `80` and `443`.
- `onlinelesson.serveftp.com` is currently proxied by system `nginx` to `http://localhost:3000`.
- A valid Let's Encrypt certificate for `onlinelesson.serveftp.com` already exists on the host.
- Ports needed by the new stack are otherwise free:
  - `5432`
  - `6379`
  - `8055`
  - `1212`
  - `5180`
  - `5182`
  - `5183`
  - `5184`

## What this means

There is one real conflict:

- the domain and ports `80/443` are currently owned by the host-level `nginx` test setup

This does **not** block the new project architecture, but it means the first deployment must explicitly reclaim the domain before the self-contained Docker `nginx` stack starts.

## Recommended migration command on this VPS

After cloning the repository to the server and preparing `.env`, run:

```bash
bash deploy/server/bootstrap-ubuntu.sh
bash deploy/server/deploy.sh --domain onlinelesson.serveftp.com --email admin@onlinelesson.serveftp.com --stop-host-nginx --remove-open-webui-test-stack
```

That will:

- stop and disable the host `nginx`
- tear down the test `open-webui` / `ollama` compose stack if present
- bring up the repo-managed `infra` stack
- issue the initial certificate if the repo copy is not present yet
- switch the Docker `nginx` to TLS mode
- build and start the `Hefner Sprach Hub` app stack

## What is preserved

- SSH access and firewall rules
- host-level security files such as existing `/etc/letsencrypt`

The repo-managed stack keeps its own certbot data under `deploy/infra/certbot/`, so future deployments remain self-contained and portable.
