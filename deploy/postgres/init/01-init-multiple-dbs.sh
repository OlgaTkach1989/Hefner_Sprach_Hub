#!/bin/bash
set -e

create_user_and_db() {
  local database="$1"
  local user="$2"
  local password="$3"

  echo "Configuring database '$database' for user '$user'"

  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<-EOSQL
    DO \$\$
    BEGIN
      IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '${user}') THEN
        CREATE ROLE ${user} LOGIN PASSWORD '${password}';
      END IF;
    END
    \$\$;
    SELECT 'CREATE DATABASE ${database} OWNER ${user}'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${database}')\gexec
    GRANT ALL PRIVILEGES ON DATABASE ${database} TO ${user};
EOSQL
}

create_user_and_db "$APP_DB_NAME" "$APP_DB_USER" "$APP_DB_PASSWORD"
create_user_and_db "$DIRECTUS_DB_NAME" "$DIRECTUS_DB_USER" "$DIRECTUS_DB_PASSWORD"

echo "Enabling pgvector in '$APP_DB_NAME'"
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$APP_DB_NAME" <<-EOSQL
  CREATE EXTENSION IF NOT EXISTS vector;
EOSQL
