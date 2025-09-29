#!/bin/bash

set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

# Logging function
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a /var/log/mimic-startup.log
}

log "Starting Mimic service deployment on Debian"

# Install required packages
log "Installing Docker, Docker Compose, and Litestream"
apt-get update -y
apt-get install -y ca-certificates curl wget

# Add Docker GPG key and repository
curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --yes --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list

# Update package index and install Docker
apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Enable and start Docker
systemctl enable docker
systemctl start docker

# Install Litestream
log "Installing Litestream"
LITESTREAM_VERSION="v0.3.13"
wget -O /tmp/litestream.deb "https://github.com/benbjohnson/litestream/releases/download/$LITESTREAM_VERSION/litestream-$LITESTREAM_VERSION-linux-amd64.deb"
dpkg -i /tmp/litestream.deb
rm /tmp/litestream.deb

# Validate GCS bucket access
log "Validating GCS bucket access"
BACKUP_BUCKET="mimic-backups"
if ! gsutil ls "gs://$BACKUP_BUCKET/" >/dev/null 2>&1; then
    log "ERROR: Cannot access backup bucket gs://$BACKUP_BUCKET/"
    log "Please ensure the service account has storage.objectAdmin permissions"
    exit 1
fi
log "GCS bucket access validated successfully"

# Setup SQLite database and restore from Litestream if available
log "Setting up SQLite database"
mkdir -p /opt/mimic

# Restore database from Litestream backup if it exists
DB_PATH="/opt/mimic/mimic.db"
if ! [ -f "$DB_PATH" ]; then
    log "Attempting to restore database from Litestream backup"
    # Try to restore from backup with proper error handling
    if litestream restore -if-db-not-exists gs://mimic-backups/litestream "$DB_PATH" 2>/dev/null; then
        log "Successfully restored database from backup"
    else
        log "No existing backup found, creating new database"
        if ! touch "$DB_PATH"; then
            log "ERROR: Failed to create database file"
            exit 1
        fi
    fi
else
    log "Database file already exists, skipping restore"
fi

# Ensure proper permissions
if ! chown 1000:1000 "$DB_PATH"; then
    log "ERROR: Failed to set database file ownership"
    exit 1
fi

# Restore Caddy certificates if they exist
log "Restoring Caddy certificates from backup"
if ! mkdir -p /opt/mimic/caddy_data_restore; then
    log "ERROR: Failed to create Caddy restore directory"
    exit 1
fi

if gsutil -q stat "gs://mimic-backups/caddy/**" 2>/dev/null; then
    log "Found existing Caddy backup, restoring..."
    if ! gsutil -m rsync -r gs://mimic-backups/caddy/ /opt/mimic/caddy_data_restore/; then
        log "ERROR: Failed to restore Caddy certificates"
        exit 1
    fi
    log "Successfully restored Caddy certificates"
else
    log "No existing Caddy backup found, starting fresh"
fi

cd /opt/mimic

# Create .env file with secrets (fetch fresh on each restart)
log "Fetching secrets from Google Secret Manager"

# Use temporary files to avoid exposing secrets in process list
TEMP_DIR=$(mktemp -d)
chmod 700 "$TEMP_DIR"

# Fetch secrets securely
gcloud secrets versions access latest --secret=mimic-github-token --project=${project_id} > "$TEMP_DIR/github_token"
gcloud secrets versions access latest --secret=mimic-cloudbees-endpoint-id --project=${project_id} > "$TEMP_DIR/cloudbees_endpoint"
gcloud secrets versions access latest --secret=mimic-pat-encryption-key --project=${project_id} > "$TEMP_DIR/pat_key"

# Create .env file
cat > /opt/mimic/.env << EOF
# Mimic environment variables
GITHUB_TOKEN=$(cat "$TEMP_DIR/github_token")
CLOUDBEES_ENDPOINT_ID=$(cat "$TEMP_DIR/cloudbees_endpoint")
PAT_ENCRYPTION_KEY=$(cat "$TEMP_DIR/pat_key")
EOF
chmod 600 /opt/mimic/.env

# Clean up temporary files
rm -rf "$TEMP_DIR"

# Create docker-compose.yml with Mimic, Caddy, and Watchtower
log "Creating Docker Compose configuration"
cat > /opt/mimic/docker-compose.yml << EOF
services:
  mimic:
    image: cloudbeesdemo/mimic:latest
    restart: unless-stopped
    ports:
      - "127.0.0.1:8000:8000"
    environment:
      - MODE=api
    env_file:
      - /opt/mimic/.env
    volumes:
      - /opt/mimic/mimic.db:/app/mimic.db
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s

  caddy:
    image: cloudbeesdemo/caddy-cloud-dns:latest
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
      - "8080:8080"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - /opt/mimic/caddy_data_restore:/data
      - caddy_config:/config
      - caddy_logs:/var/log/caddy
    environment:
      - GCP_PROJECT=${project_id}
    healthcheck:
      test: ["CMD-SHELL", "caddy version || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s

  watchtower:
    image: containrrr/watchtower:latest
    restart: unless-stopped
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - WATCHTOWER_CLEANUP=true
      - WATCHTOWER_POLL_INTERVAL=300
      - WATCHTOWER_INCLUDE_STOPPED=true
      - WATCHTOWER_REVIVE_STOPPED=false
    command: --interval 300 --cleanup mimic-mimic-1 mimic-caddy-1

volumes:
  caddy_config:
  caddy_logs:
EOF

# Create Litestream configuration
log "Creating Litestream configuration"
cat > /etc/litestream.yml << EOF
dbs:
  - path: /opt/mimic/mimic.db
    replicas:
      - type: gcs
        bucket: mimic-backups
        path: litestream
        retention: 72h
        sync-interval: 1s
EOF

# Create Caddyfile for containerized Caddy
log "Creating Caddy configuration"
cat > /opt/mimic/Caddyfile << EOF
{
  admin off
  email ${admin_email}
}

${domain} {
  tls {
    dns googleclouddns {
      gcp_project ${project_id}
    }
  }

  # Handle MCP endpoints specifically for SSE support
  handle /mcp* {
    reverse_proxy mimic:8000 {
      health_uri /health
      health_interval 30s
      health_timeout 10s
      flush_interval -1
      header_up X-Real-IP {remote_host}
      header_up X-Forwarded-For {remote_host}
      header_up X-Forwarded-Proto {scheme}
    }
    header {
      Cache-Control "no-cache"
      Connection "keep-alive"
      X-Accel-Buffering "no"
    }
  }

  # Handle all other endpoints
  reverse_proxy mimic:8000 {
    health_uri /health
    health_interval 30s
    health_timeout 10s
  }
  
  header {
    Strict-Transport-Security "max-age=31536000; includeSubdomains"
    X-Content-Type-Options "nosniff"
    X-Frame-Options "DENY"
    X-XSS-Protection "1; mode=block"
  }
  
  log {
    output file /var/log/caddy/access.log
    format filter {
      wrap json
      fields {
        request>headers>Unify_api_key delete
        request>headers>unify_api_key delete
        request>headers>Github_token delete
        request>headers>github_token delete
        request>headers>Authorization delete
        request>headers>authorization delete
      }
    }
  }

  log {
    level ERROR
    output file /var/log/caddy/error.log
    format filter {
      wrap json
      fields {
        request>headers>Unify_api_key delete
        request>headers>unify_api_key delete
        request>headers>Github_token delete
        request>headers>github_token delete
        request>headers>Authorization delete
        request>headers>authorization delete
      }
    }
  }
}

# Health check endpoint for load balancer
:8080 {
  respond /health 200 {
    body "OK"
  }
}
EOF

# Start Litestream replication FIRST to avoid race condition
log "Starting Litestream replication"
systemctl start litestream

# Wait for Litestream to initialize
log "Waiting for Litestream to initialize"
sleep 10

# Pull and start containers
log "Pulling Docker images"
docker compose pull

log "Starting Docker services"
docker compose up -d

# Wait for services to be healthy
log "Waiting for services to be healthy"
sleep 60

# Check Docker service status
log "Checking Docker service status"
docker compose ps

# Create systemd service for Docker containers
log "Creating Docker systemd service"
cat > /etc/systemd/system/mimic-docker.service << 'EOF'
[Unit]
Description=Mimic Docker Services (Mimic + Caddy + Watchtower)
Requires=docker.service litestream.service
After=docker.service litestream.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
User=root
WorkingDirectory=/opt/mimic
ExecStartPre=/opt/mimic/fetch-secrets.sh
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
ExecReload=/opt/mimic/fetch-secrets.sh
ExecReload=/usr/bin/docker compose pull
ExecReload=/usr/bin/docker compose up -d
TimeoutStartSec=300
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

# Create secrets fetch script for restarts
log "Creating secrets fetch script"
cat > /opt/mimic/fetch-secrets.sh << 'EOF'
#!/bin/bash
set -euo pipefail

PROJECT_ID="${project_id}"
ENV_FILE="/opt/mimic/.env"

# Create .env file with fresh secrets using secure method
TEMP_DIR=$(mktemp -d)
chmod 700 "$TEMP_DIR"

# Fetch secrets securely
gcloud secrets versions access latest --secret=mimic-github-token --project=$PROJECT_ID > "$TEMP_DIR/github_token"
gcloud secrets versions access latest --secret=mimic-cloudbees-endpoint-id --project=$PROJECT_ID > "$TEMP_DIR/cloudbees_endpoint"
gcloud secrets versions access latest --secret=mimic-pat-encryption-key --project=$PROJECT_ID > "$TEMP_DIR/pat_key"

# Create .env file
{
  echo "# Mimic environment variables"
  echo "GITHUB_TOKEN=$(cat "$TEMP_DIR/github_token")"
  echo "CLOUDBEES_ENDPOINT_ID=$(cat "$TEMP_DIR/cloudbees_endpoint")"
  echo "PAT_ENCRYPTION_KEY=$(cat "$TEMP_DIR/pat_key")"
} > "$ENV_FILE"

chmod 600 "$ENV_FILE"

# Clean up temporary files
rm -rf "$TEMP_DIR"
EOF
chmod +x /opt/mimic/fetch-secrets.sh

# Create Litestream systemd service
log "Creating Litestream systemd service"
cat > /etc/systemd/system/litestream.service << 'EOF'
[Unit]
Description=Litestream replication service
After=network.target

[Service]
Type=exec
User=root
ExecStart=/usr/bin/litestream replicate
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Create Caddy backup script
log "Creating Caddy backup script"
cat > /opt/mimic/backup-caddy.sh << 'EOF'
#!/bin/bash
set -euo pipefail

# Logging function
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" >> /var/log/caddy-backup.log
}

# Backup Caddy certificates to GCS
if [ -d "/opt/mimic/caddy_data_restore" ] && [ "$(ls -A /opt/mimic/caddy_data_restore)" ]; then
    log "Starting Caddy certificate backup"
    if gsutil -m rsync -r -d /opt/mimic/caddy_data_restore/ gs://mimic-backups/caddy/; then
        log "Successfully backed up Caddy certificates"
    else
        log "ERROR: Failed to backup Caddy certificates"
        exit 1
    fi
else
    log "No Caddy certificates to backup"
fi
EOF
chmod +x /opt/mimic/backup-caddy.sh

# Create cron job for Caddy backups
log "Setting up Caddy backup cron job"
echo "0 * * * * /opt/mimic/backup-caddy.sh" | crontab -

systemctl enable mimic-docker.service
systemctl enable litestream.service

# Wait a bit for SSL certificate to be obtained
log "Waiting for SSL certificate provisioning"
sleep 30

# Check service status
log "Checking final service status"
systemctl status mimic-docker --no-pager -l
docker compose ps
docker compose logs caddy --tail=20

log "Mimic service deployment complete. Service available at https://${domain}"
log "Startup script completed successfully"