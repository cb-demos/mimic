#!/bin/bash

set -euo pipefail

# Logging function
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a /var/log/mimic-startup.log
}

log "Starting Mimic service deployment on Debian"

# Install required packages
log "Installing Docker and Docker Compose"
apt-get update -y
apt-get install -y ca-certificates curl

# Add Docker GPG key and repository
curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list

# Update package index and install Docker
apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Enable and start Docker
systemctl enable docker
systemctl start docker

# Mount and format the persistent disk for database storage
log "Setting up persistent disk for database"
DEVICE="/dev/disk/by-id/google-mimic-data"
MOUNT_POINT="/opt/mimic/data"

# Check if the disk is already formatted
if ! blkid "$DEVICE" > /dev/null 2>&1; then
    log "Formatting persistent disk"
    mkfs.ext4 -F "$DEVICE"
fi

# Create mount point and mount the disk
mkdir -p "$MOUNT_POINT"
mount "$DEVICE" "$MOUNT_POINT"

# Add to fstab for automatic mounting on reboot
echo "$DEVICE $MOUNT_POINT ext4 defaults 0 2" >> /etc/fstab

# Set permissions for the mimic user (will be created by Docker)
chown 1000:1000 "$MOUNT_POINT"

# Create mimic directory
mkdir -p /opt/mimic
cd /opt/mimic

# Create .env file with secrets (fetch fresh on each restart)
log "Fetching secrets from Google Secret Manager"
cat > /opt/mimic/.env << EOF
# Mimic environment variables
GITHUB_TOKEN=$(gcloud secrets versions access latest --secret=mimic-github-token --project=${project_id})
CLOUDBEES_ENDPOINT_ID=$(gcloud secrets versions access latest --secret=mimic-cloudbees-endpoint-id --project=${project_id})
PAT_ENCRYPTION_KEY=$(gcloud secrets versions access latest --secret=mimic-pat-encryption-key --project=${project_id})
EOF
chmod 600 /opt/mimic/.env

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
      - /opt/mimic/data/mimic.db:/app/mimic.db
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
      - caddy_data:/data
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
  caddy_data:
  caddy_config:
  caddy_logs:
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
    format json
  }
  
  log {
    level ERROR
    output file /var/log/caddy/error.log
  }
}

# Health check endpoint for load balancer
:8080 {
  respond /health 200 {
    body "OK"
  }
}
EOF

# Pull and start containers
log "Pulling Docker images"
docker compose pull

# Ensure database file exists for first run
log "Ensuring database file exists"
touch /opt/mimic/data/mimic.db
chown 1000:1000 /opt/mimic/data/mimic.db

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
Requires=docker.service
After=docker.service network-online.target
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

# Create .env file with fresh secrets
{
  echo "# Mimic environment variables"
  echo "GITHUB_TOKEN=$(gcloud secrets versions access latest --secret=mimic-github-token --project=$PROJECT_ID)"
  echo "CLOUDBEES_ENDPOINT_ID=$(gcloud secrets versions access latest --secret=mimic-cloudbees-endpoint-id --project=$PROJECT_ID)"
  echo "PAT_ENCRYPTION_KEY=$(gcloud secrets versions access latest --secret=mimic-pat-encryption-key --project=$PROJECT_ID)"
} > "$ENV_FILE"

chmod 600 "$ENV_FILE"
EOF
chmod +x /opt/mimic/fetch-secrets.sh

systemctl enable mimic-docker.service

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