# GitHub And Server Checklist

## 1. What I need from you for GitHub

To push `Learning Hub` into your separate GitHub repository, send me:

1. Repository URL.
Example: `https://github.com/<user-or-org>/learning-hub.git`

2. Whether the repository already exists or I should prepare the project first and wait for you to create it.

3. Authentication method for GitHub push.
Choose one:
- HTTPS + Personal Access Token
- SSH key already configured on this machine for your GitHub account

4. Target default branch.
Recommended: `main`

5. Visibility expectation.
Tell me if the repository must stay `private`.

## 2. What I will do after you send that

1. Initialize `Learning Hub` as a standalone Git repository.
2. Make sure ignored local files are not included.
3. Create the first clean commit.
4. Add your GitHub remote.
5. Push the new standalone project to the branch you specify.

## 3. Ubuntu 24.04 server checklist

These commands assume:
- server user: `ubuntu`
- domain: `onlinelesson.serveftp.com`
- repository root on server: `/opt/learning-hub`

The repository now also contains deploy automation:

```bash
bash deploy/server/bootstrap-ubuntu.sh
bash deploy/server/deploy.sh --domain your-domain.example --email admin@your-domain.example
```

### 3.1 Connect to the server

```bash
ssh ubuntu@51.195.117.210
```

### 3.2 Update system packages

```bash
sudo apt update
sudo apt upgrade -y
```

### 3.3 Install Docker, Compose plugin, Git, and utilities

```bash
sudo apt install -y ca-certificates curl gnupg git ufw
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo \"$VERSION_CODENAME\") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker ubuntu
```

After that, reconnect once:

```bash
exit
ssh ubuntu@51.195.117.210
docker --version
docker compose version
```

### 3.4 Configure firewall

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

### 3.5 Check DNS before issuing certificates

```bash
getent hosts onlinelesson.serveftp.com
```

Expected target:
- IPv4: `51.195.117.210`
- optional IPv6: `2001:41d0:701:1100::8b23`

### 3.6 Clone the repository

```bash
sudo mkdir -p /opt/learning-hub
sudo chown ubuntu:ubuntu /opt/learning-hub
git clone <YOUR_GITHUB_REPO_URL> /opt/learning-hub
cd /opt/learning-hub
```

### 3.7 Prepare environment file

```bash
cp .env.example .env
nano .env
```

Fill at minimum:
- `DJANGO_SECRET_KEY`
- `POSTGRES_SUPERPASSWORD`
- `APP_DB_PASSWORD`
- `DIRECTUS_DB_PASSWORD`
- `DIRECTUS_KEY`
- `DIRECTUS_SECRET`
- `DIRECTUS_ADMIN_PASSWORD`
- `CERTBOT_EMAIL`

### 3.8 Start infra stack in HTTP mode

```bash
docker compose -f deploy/infra/docker-compose.yml --env-file .env up -d
```

### 3.9 Issue the first Let's Encrypt certificate

```bash
chmod +x deploy/infra/certbot/issue-initial-cert.sh
bash deploy/infra/certbot/issue-initial-cert.sh
```

### 3.10 Restart infra stack with TLS enabled

```bash
docker compose -f deploy/infra/docker-compose.yml -f deploy/infra/docker-compose.tls.yml --env-file .env up -d
```

### 3.11 Start the app stack

```bash
docker compose -f deploy/app/docker-compose.yml --env-file .env up --build -d
```

### 3.12 Verify services

```bash
docker compose -f deploy/infra/docker-compose.yml --env-file .env ps
docker compose -f deploy/app/docker-compose.yml --env-file .env ps
curl -I https://onlinelesson.serveftp.com
curl -I https://onlinelesson.serveftp.com/api/health/
bash deploy/server/smoke-test.sh
```

Operational references:
- [OPERATIONS_RUNBOOK.md](docs/OPERATIONS_RUNBOOK.md)
- [DIRECTUS_TRAINING_SETUP.md](docs/DIRECTUS_TRAINING_SETUP.md)

### 3.13 Update workflow after the first deployment

```bash
cd /opt/learning-hub
git pull
bash deploy/server/deploy.sh --domain onlinelesson.serveftp.com --email admin@onlinelesson.serveftp.com
```

If infra files changed:

```bash
bash deploy/server/deploy.sh --domain onlinelesson.serveftp.com --email admin@onlinelesson.serveftp.com --skip-build
```
