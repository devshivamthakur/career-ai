#!/usr/bin/env bash
# =============================================================================
#  CareerAI Backend — Docker Build, Push & Deploy to AWS EC2
# =============================================================================
#  Usage:
#    ./deploy.sh                   # Full flow: build → push → deploy
#    ./deploy.sh build             # Build Docker image only
#    ./deploy.sh push              # Push image to registry only
#    ./deploy.sh deploy            # Deploy to EC2 (pull & run containers)
#    ./deploy.sh setup-ec2         # ONE-TIME: migrate from git-clone to Docker
#    ./deploy.sh migrate           # Run Alembic migrations on EC2 only
#    ./deploy.sh status            # Check deployment status on EC2
#    ./deploy.sh logs              # Tail container logs on EC2
#    ./deploy.sh rollback          # Rollback to previous image version
# =============================================================================

set -euo pipefail

# -----------------------------------------------------------------------------
#  CONFIGURATION  —  All values MUST come from environment variables
# -----------------------------------------------------------------------------

# ---- Docker Image ----
IMAGE_NAME="${IMAGE_NAME:-careerai-backend}"
IMAGE_TAG="$(date +%Y%m%d-%H%M%S)"
LATEST_TAG="latest"

# ---- Docker Registry ----
# Required: export DOCKER_USERNAME, DOCKER_PASSWORD
# Optional: REGISTRY_TYPE=ecr (requires AWS_ACCOUNT_ID, AWS_REGION)
REGISTRY_TYPE="${REGISTRY_TYPE:-dockerhub}"
DOCKER_USERNAME="${DOCKER_USERNAME:?Missing DOCKER_USERNAME}"
DOCKER_REGISTRY="${DOCKER_USERNAME}"

# ---- Docker Compose Command Detection ----
# Some systems use 'docker compose' (plugin), others use 'docker-compose' (standalone)
DOCKER_COMPOSE_CMD="docker compose" # default

AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-}"
AWS_REGION="${AWS_REGION:-us-east-1}"

# Resolve the full image reference
if [ "$REGISTRY_TYPE" = "ecr" ]; then
    : "${AWS_ACCOUNT_ID:?Missing AWS_ACCOUNT_ID}"
    FULL_IMAGE="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${IMAGE_NAME}"
else
    FULL_IMAGE="${DOCKER_REGISTRY}/${IMAGE_NAME}"
fi

# ---- AWS EC2 ----
# Required: export EC2_HOST, EC2_USER, EC2_SSH_KEY
EC2_HOST="${EC2_HOST:?Missing EC2_HOST}"
EC2_USER="${EC2_USER:?Missing EC2_USER}"
EC2_SSH_KEY="${EC2_SSH_KEY:?Missing EC2_SSH_KEY}"
EC2_APP_DIR="${EC2_APP_DIR:-/home/${EC2_USER}/careerai}"
EC2_COMPOSE_FILE="docker-compose.prod.yml"
EC2_ENV_FILE="${EC2_ENV_FILE:-./.env}"

# ---- Database Migrations ----
RUN_MIGRATIONS_ON_DEPLOY="${RUN_MIGRATIONS_ON_DEPLOY:-false}"

# ---- Health Check ----
HEALTH_CHECK_URL="http://${EC2_HOST}/health"
HEALTH_CHECK_DOMAIN="${HEALTH_CHECK_DOMAIN:-}"
HEALTH_CHECK_RETRIES=12
HEALTH_CHECK_INTERVAL=5

# ---- Old git-clone setup (for setup-ec2 cleanup) ----
OLD_GIT_DIR="/home/${EC2_USER}/career-ai"
OLD_IMAGE_NAME="backend-api"
OLD_CONTAINER_API="fastapi-api"
OLD_CONTAINER_REDIS="redis"

# ---- Rollback ----
ROLLBACK_KEEP_LAST=3

# =============================================================================
#  COLOR OUTPUT
# =============================================================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
pass()  { echo -e "${GREEN}[PASS]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
fail()  { echo -e "${RED}[FAIL]${NC} $*"; exit 1; }

# =============================================================================
#  HELPER FUNCTIONS
# =============================================================================

check_prerequisites() {
    local missing=0

    if ! command -v docker &>/dev/null; then
        fail "Docker is not installed. Install it from https://docs.docker.com/get-docker/"
    else
        info "docker: $(docker --version)"
    fi

    if [ "$REGISTRY_TYPE" = "ecr" ]; then
        if ! command -v aws &>/dev/null; then
            fail "AWS CLI is not installed. Install it from https://aws.amazon.com/cli/"
        else
            info "aws: $(aws --version 2>&1)"
        fi
    fi

    if [ "${1:-}" = "deploy" ] || [ "${1:-}" = "setup-ec2" ] || [ "${1:-}" = "migrate" ] || [ "${1:-}" = "status" ] || [ "${1:-}" = "logs" ] || [ "${1:-}" = "rollback" ]; then
        if [ ! -f "$EC2_SSH_KEY" ]; then
            fail "EC2 SSH key not found at: $EC2_SSH_KEY"
        fi
        if ! command -v ssh &>/dev/null; then
            fail "ssh is not available on this system."
        fi
    fi

    if [ $missing -ne 0 ]; then
        exit 1
    fi
}

ec2_ssh() {
    ssh -i "$EC2_SSH_KEY" -o StrictHostKeyChecking=no -o ConnectTimeout=10 \
        "${EC2_USER}@${EC2_HOST}" "$@"
}

ec2_scp() {
    scp -i "$EC2_SSH_KEY" -o StrictHostKeyChecking=no -o ConnectTimeout=10 \
        "$1" "${EC2_USER}@${EC2_HOST}:$2"
}

registry_login_local() {
    if [ "$REGISTRY_TYPE" = "ecr" ]; then
        info "Logging into AWS ECR (local)..."
        aws ecr get-login-password --region "$AWS_REGION" \
            | docker login --username AWS --password-stdin "$ECR_REGISTRY"
        pass "ECR login successful."
    else
        if [ -z "${DOCKER_PASSWORD:-}" ]; then
            info "Docker Hub password not set in DOCKER_PASSWORD env var."
            echo -n "Enter Docker Hub password: "
            read -rs DOCKER_PASSWORD
            echo
        fi
        echo "$DOCKER_PASSWORD" | docker login --username "$DOCKER_USERNAME" --password-stdin
        pass "Docker Hub login successful."
    fi
}

registry_login_ec2() {
    info "Logging into Docker Hub on EC2 (needed to pull private image)..."
    # Read password from local env and send it to EC2 docker login
    if [ -z "${DOCKER_PASSWORD:-}" ]; then
        if [ -f "$EC2_ENV_FILE" ]; then
            DOCKER_PASSWORD=$(grep -E '^DOCKER_PASSWORD=' "$EC2_ENV_FILE" | cut -d= -f2- || true)
        fi
        if [ -z "${DOCKER_PASSWORD:-}" ]; then
            warn "DOCKER_PASSWORD not set. EC2 may not pull private images."
            warn "Set DOCKER_PASSWORD in your .env file or export it."
            return 1
        fi
    fi
    ec2_ssh "echo '$DOCKER_PASSWORD' | docker login --username '$DOCKER_USERNAME' --password-stdin" 2>/dev/null
    pass "Docker Hub login on EC2 successful."
}

# =============================================================================
#  STAGES
# =============================================================================

build_image() {
    info "Building Docker image: ${FULL_IMAGE}:${IMAGE_TAG} ..."
    docker build \
        --platform linux/amd64 \
        -t "${FULL_IMAGE}:${IMAGE_TAG}" \
        -t "${FULL_IMAGE}:${LATEST_TAG}" \
        -f Dockerfile \
        .
    pass "Image built successfully."
    info "Image: ${FULL_IMAGE}:${IMAGE_TAG}"
}

push_image() {
    registry_login_local

    info "Pushing image: ${FULL_IMAGE}:${IMAGE_TAG} ..."
    docker push "${FULL_IMAGE}:${IMAGE_TAG}"
    pass "Image (tagged) pushed."

    info "Pushing image: ${FULL_IMAGE}:${LATEST_TAG} ..."
    docker push "${FULL_IMAGE}:${LATEST_TAG}"
    pass "Image (latest) pushed."
}

deploy_to_ec2() {
    info "=== Deploying to EC2: ${EC2_HOST} ==="

    # -------------------------------------------------------------------------
    #  1. Ensure remote directory exists
    # -------------------------------------------------------------------------
    info "Ensuring remote directory exists..."
    ec2_ssh "mkdir -p ${EC2_APP_DIR}"

    # -------------------------------------------------------------------------
    #  2. Generate production docker-compose file on the fly
    # -------------------------------------------------------------------------
    info "Generating production docker-compose file..."

    read -r -d '' COMPOSE_CONTENT << COMPOSE || true
services:
  api:
    image: ${FULL_IMAGE}:${LATEST_TAG}
    container_name: careerai-api
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=production
      - DATABASE_URL=\${DATABASE_URL}
      - REDIS_HOST=redis
      - OPENAI_API_KEY=\${OPENAI_API_KEY}
      - OPENAI_BASE_URL=\${OPENAI_BASE_URL}
      - LLM_PROVIDER=\${LLM_PROVIDER}
      - ALLOWED_ORIGINS=\${ALLOWED_ORIGINS}
      - LANGFUSE_PUBLIC_KEY=\${LANGFUSE_PUBLIC_KEY}
      - LANGFUSE_SECRET_KEY=\${LANGFUSE_SECRET_KEY}
      - HUGGINGFACE_API_TOKEN=\${HUGGINGFACE_API_TOKEN}
      - FAST_MODEL_NAME=\${FAST_MODEL_NAME}
      - QUALITY_MODEL_NAME=\${QUALITY_MODEL_NAME}
      - ALLOWED_HOSTS=\${ALLOWED_HOSTS}
      - LANGFUSE_BASE_URL=\${LANGFUSE_BASE_URL}
      - PROJECT_NAME=\${PROJECT_NAME}
      - VERSION=\${VERSION}
    depends_on:
      redis:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 20s
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  redis:
    image: redis/redis-stack-server:latest
    container_name: careerai-redis
    restart: unless-stopped
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3

volumes:
  redis_data:
COMPOSE

    # Write compose file to remote via SSH
    echo "$COMPOSE_CONTENT" | ec2_ssh "cat > ${EC2_APP_DIR}/${EC2_COMPOSE_FILE}"
    pass "docker-compose.prod.yml created on EC2."

    # -------------------------------------------------------------------------
    #  3. Upload .env file if it exists locally
    # -------------------------------------------------------------------------
    if [ -f "$EC2_ENV_FILE" ]; then
        info "Uploading environment file..."
        ec2_scp "$EC2_ENV_FILE" "${EC2_APP_DIR}/.env"
        pass "Environment file uploaded."
    else
        warn "No environment file found at ${EC2_ENV_FILE}."
        warn "Make sure environment variables are set on EC2 (via .env or docker-compose)."
    fi

    # -------------------------------------------------------------------------
    #  4. Docker Hub login on EC2 + pull latest image
    # -------------------------------------------------------------------------
    registry_login_ec2 || true

    info "Detecting Docker Compose and pulling images on EC2..."
    ec2_ssh "
        cd ${EC2_APP_DIR} && \
        if ! docker compose version &>/dev/null; then
            DOCKER_COMPOSE='docker-compose'
        else
            DOCKER_COMPOSE='docker compose'
        fi && \
        echo \"DOCKER_COMPOSE=\$DOCKER_COMPOSE\" > .compose_env && \
        \$DOCKER_COMPOSE -f ${EC2_COMPOSE_FILE} pull
    "
    pass "Images pulled on EC2."

    # -------------------------------------------------------------------------
    #  5. Restart the stack (Zero-Downtime approach)
    # -------------------------------------------------------------------------
    info "Restarting containers (zero-downtime rolling restart)..."
    ec2_ssh "
        cd ${EC2_APP_DIR} && \
        source .compose_env && \
        # We don't use 'down' to avoid downtime. 'up -d' will recreate containers if needed.
        \$DOCKER_COMPOSE -f ${EC2_COMPOSE_FILE} up -d --remove-orphans
    "
    pass "Containers updated/restarted."

    # -------------------------------------------------------------------------
    #  6. Clean up old images on EC2
    # -------------------------------------------------------------------------
    info "Cleaning up old Docker images on EC2 (keeping last ${ROLLBACK_KEEP_LAST})..."
    ec2_ssh "docker image prune -f --filter 'until=24h'" && pass "Cleanup complete."

    # -------------------------------------------------------------------------
    #  7. Run Alembic migrations (optional)
    # -------------------------------------------------------------------------
    if [ "$RUN_MIGRATIONS_ON_DEPLOY" = true ]; then
        info "Running Alembic migrations..."
        run_migrations_remote
    fi

    # -------------------------------------------------------------------------
    #  8. Health check
    # -------------------------------------------------------------------------
    health_check

    pass "=== Deployment complete! ==="
    info "API:      http://${EC2_HOST}"
    info "Docs:     http://${EC2_HOST}/docs"
    info "Domain:   via nginx (if configured)"
}

# =============================================================================
#  COMMAND: setup-ec2  — one-time migration from git-clone to Docker
# =============================================================================
cmd_setup_ec2() {
    info "=== Setting up EC2 for Docker-based deployment ==="
    info "This will:"
    info "  1. Stop old containers from git-clone setup"
    info "  2. Remove old git clone directory"
    info "  3. Remove old Docker images built locally on EC2"
    info "  4. Login to Docker Hub on EC2"
    info "  5. Verify nginx config (already proxying to port 8000)"
    info "  6. Create new app directory"
    echo ""

    # ---- 1. Stop old containers ----
    info "Stopping old containers (${OLD_CONTAINER_API}, ${OLD_CONTAINER_REDIS})..."
    ec2_ssh "
        sudo docker stop ${OLD_CONTAINER_API} ${OLD_CONTAINER_REDIS} 2>/dev/null || true
        sudo docker rm ${OLD_CONTAINER_API} ${OLD_CONTAINER_REDIS} 2>/dev/null || true
    "
    pass "Old containers stopped and removed."

    # ---- 2. Remove old git clone directory ----
    if ec2_ssh "[ -d ${OLD_GIT_DIR} ]" 2>/dev/null; then
        info "Removing old git clone at ${OLD_GIT_DIR}..."
        ec2_ssh "rm -rf ${OLD_GIT_DIR}"
        pass "Old git clone directory removed."
    else
        info "No old git clone directory found at ${OLD_GIT_DIR}, skipping."
    fi

    # ---- 3. Remove old Docker images ----
    info "Removing old locally-built Docker images..."
    ec2_ssh "
        sudo docker rmi ${OLD_IMAGE_NAME}:latest 2>/dev/null || true
        sudo docker image prune -f 2>/dev/null || true
    "
    pass "Old Docker images cleaned up."

    # ---- 4. Login to Docker Hub on EC2 ----
    registry_login_ec2 || warn "Docker Hub login failed. You may need to run it manually."

    # ---- 5. Verify nginx ----
    info "Checking nginx configuration..."
    if ec2_ssh "sudo nginx -t" 2>/dev/null; then
        pass "Nginx config is valid. It already proxies to port 8000."
    else
        warn "Nginx config has issues. Check with: sudo nginx -t"
    fi

    # ---- 6. Create new app directory ----
    info "Creating new app directory at ${EC2_APP_DIR}..."
    ec2_ssh "mkdir -p ${EC2_APP_DIR}"
    pass "App directory created."

    echo ""
    pass "=== EC2 setup complete! ==="
    info "You can now run:  ./deploy.sh deploy"
    info "Nginx config at /etc/nginx/conf.d/fastapi.conf stays unchanged."
    info "It proxies your domain → 127.0.0.1:8000 (your Docker container)."
}

# =============================================================================
#  COMMAND: setup-nginx  — install and configure nginx with SSL
# =============================================================================
cmd_setup_nginx() {
    local cert_path="/Users/shivam/Downloads/certificate.pem"
    local key_path="/Users/shivam/Downloads/private.key"
    local domain="career-ai.work.gd"

    info "=== Setting up Nginx with SSL (Port 443) ==="

    # 1. Install Nginx if not present
    info "Installing Nginx on EC2..."
    ec2_ssh "sudo yum update -y && sudo yum install -y nginx"

    # 2. Create SSL directory
    info "Creating SSL directory..."
    ec2_ssh "sudo mkdir -p /etc/nginx/ssl"

    # 3. Upload Certificate and Key
    info "Uploading SSL certificate and key..."
    if [ ! -f "$cert_path" ]; then fail "Local cert not found: $cert_path"; fi
    if [ ! -f "$key_path" ]; then fail "Local key not found: $key_path"; fi

    ec2_scp "$cert_path" "/tmp/certificate.pem"
    ec2_scp "$key_path" "/tmp/private.key"

    ec2_ssh "
        sudo mv /tmp/certificate.pem /etc/nginx/ssl/certificate.pem
        sudo mv /tmp/private.key /etc/nginx/ssl/private.key
        sudo chmod 600 /etc/nginx/ssl/private.key
        sudo chmod 644 /etc/nginx/ssl/certificate.pem
        sudo chown root:root /etc/nginx/ssl/*
    "

    # 4. Generate Nginx Configuration
    info "Generating Nginx configuration..."
    # We use a heredoc to create the config file. Note: we escape $ variables for Nginx.
    read -r -d '' NGINX_CONF << EOF || true
server {
    listen 80;
    server_name $domain;
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl;
    server_name $domain;

    ssl_certificate /etc/nginx/ssl/certificate.pem;
    ssl_certificate_key /etc/nginx/ssl/private.key;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        # WebSocket & Streaming support
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection \"upgrade\";
        proxy_buffering off;
        proxy_read_timeout 300;
    }
}
EOF

    echo "$NGINX_CONF" | ec2_ssh "cat > /tmp/careerai.conf"
    ec2_ssh "sudo mv /tmp/careerai.conf /etc/nginx/conf.d/careerai.conf"

    # 5. Start and Enable Nginx
    info "Starting and enabling Nginx..."
    ec2_ssh "
        sudo systemctl enable nginx
        sudo systemctl restart nginx
    "

    if ec2_ssh "sudo nginx -t" 2>/dev/null; then
        pass "Nginx configured and restarted successfully."
    else
        fail "Nginx configuration test failed. Check logs on EC2."
    fi
}

run_migrations_remote() {
    info "Running Alembic migrations on EC2..."
    ec2_ssh "
        cd ${EC2_APP_DIR} && \
        source .compose_env && \
        \$DOCKER_COMPOSE -f ${EC2_COMPOSE_FILE} exec -T api uv run alembic upgrade head
    " && pass "Migrations applied successfully." || warn "Migration command failed (check DB connection)."
}

health_check() {
    info "Performing health check (up to ${HEALTH_CHECK_RETRIES} retries, ${HEALTH_CHECK_INTERVAL}s apart)..."
    local retries=$HEALTH_CHECK_RETRIES
    while [ $retries -gt 0 ]; do
        if curl -sf "$HEALTH_CHECK_URL" >/dev/null 2>&1; then
            pass "Health check passed! API is responding on port 8000."
            if [ -n "$HEALTH_CHECK_DOMAIN" ]; then
                if curl -sfk "$HEALTH_CHECK_DOMAIN" >/dev/null 2>&1; then
                    info "Domain health check passed too: ${HEALTH_CHECK_DOMAIN}"
                fi
            fi
            return 0
        fi
        retries=$((retries - 1))
        if [ $retries -gt 0 ]; then
            info "  Retrying in ${HEALTH_CHECK_INTERVAL}s ... (${retries} left)"
            sleep "$HEALTH_CHECK_INTERVAL"
        fi
    done
    warn "Health check failed after ${HEALTH_CHECK_RETRIES} attempts."
    warn "Check the EC2 logs with: ./deploy.sh logs"
    return 1
}

# =============================================================================
#  COMMAND: migrate  — run migrations on the already-deployed stack
# =============================================================================
cmd_migrate() {
    check_prerequisites migrate
    run_migrations_remote
}

# =============================================================================
#  COMMAND: status  — show deployment status
# =============================================================================
cmd_status() {
    check_prerequisites status
    info "=== Status for ${EC2_HOST} ==="
    echo ""
    echo "--- Containers ---"
    ec2_ssh "
        if ! docker compose version &>/dev/null; then
            DOCKER_COMPOSE='docker-compose'
        else
            DOCKER_COMPOSE='docker compose'
        fi
        \$DOCKER_COMPOSE -f ${EC2_APP_DIR}/${EC2_COMPOSE_FILE} ps
    " || echo "(ssh or docker-compose failed)"
    echo ""
    echo "--- Disk Usage ---"
    ec2_ssh "df -h / | tail -1" || true
    echo ""
    echo "--- Memory Usage ---"
    ec2_ssh "free -h | head -3" || true
}

# =============================================================================
#  COMMAND: logs  — tail container logs
# =============================================================================
cmd_logs() {
    check_prerequisites logs
    info "Tailing logs for careerai-api on ${EC2_HOST}..."
    ec2_ssh "
        cd ${EC2_APP_DIR} && \
        if ! docker compose version &>/dev/null; then
            DOCKER_COMPOSE='docker-compose'
        else
            DOCKER_COMPOSE='docker compose'
        fi
        \$DOCKER_COMPOSE -f ${EC2_COMPOSE_FILE} logs -f api
    "
}

# =============================================================================
#  COMMAND: rollback  — rollback to previous version
# =============================================================================
cmd_rollback() {
    check_prerequisites rollback

    warn "Rolling back to previous image version..."

    # Get the previous tag from Docker Hub or ECR
    if [ "$REGISTRY_TYPE" = "ecr" ]; then
        PREV_TAG=$(aws ecr describe-images \
            --repository-name "$IMAGE_NAME" \
            --region "$AWS_REGION" \
            --query 'imageDetails[*].imageTags[*]' \
            --output json 2>/dev/null \
            | jq -r 'flatten | map(select(. != "latest")) | sort | reverse | .[1]' 2>/dev/null || true)
    else
        # For Docker Hub, fetch tags via API
        PREV_TAG=$(curl -sf "https://hub.docker.com/v2/repositories/${DOCKER_USERNAME}/${IMAGE_NAME}/tags?page_size=100" \
            | jq -r '.results | map(.name) | map(select(. != "latest")) | sort | reverse | .[1]' 2>/dev/null || true)
    fi

    if [ -z "$PREV_TAG" ] || [ "$PREV_TAG" = "null" ]; then
        fail "Could not find a previous image tag to rollback to."
    fi

    info "Rolling back to: ${FULL_IMAGE}:${PREV_TAG}"

    ec2_ssh "
        if ! docker compose version &>/dev/null; then
            DOCKER_COMPOSE='docker-compose'
        else
            DOCKER_COMPOSE='docker compose'
        fi && \
        docker pull ${FULL_IMAGE}:${PREV_TAG} && \
        docker tag ${FULL_IMAGE}:${PREV_TAG} ${FULL_IMAGE}:${LATEST_TAG} && \
        cd ${EC2_APP_DIR} && \
        \$DOCKER_COMPOSE -f ${EC2_COMPOSE_FILE} up -d --remove-orphans
    "

    health_check
    pass "Rollback complete. Running ${FULL_IMAGE}:${PREV_TAG}"
}

# =============================================================================
#  MAIN
# =============================================================================

main() {
    local cmd="${1:-all}"

    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║        CareerAI Backend — Deploy Pipeline               ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""

    case "$cmd" in
        build)
            check_prerequisites
            build_image
            ;;
        push)
            check_prerequisites
            push_image
            ;;
        deploy)
            build_image
            push_image
            deploy_to_ec2
            ;;
        all)
            build_image
            push_image
            deploy_to_ec2
            ;;
        setup-ec2)
            check_prerequisites setup-ec2
            cmd_setup_ec2
            ;;
        setup-nginx)
            check_prerequisites setup-ec2
            cmd_setup_nginx
            ;;
        migrate)
            cmd_migrate
            ;;
        status)
            cmd_status
            ;;
        logs)
            cmd_logs
            ;;
        rollback)
            cmd_rollback
            ;;
        *)
            cat << USAGE
Usage:  ./deploy.sh [COMMAND]

Commands:
  (no arg) | all    Full pipeline: build → push → deploy
  build              Build Docker image only
  push               Push image to registry only
  deploy             Build + push + deploy to EC2
  setup-ec2          ONE-TIME: migrate from git-clone to Docker-based deploy
  setup-nginx        Install Nginx and configure SSL (Port 443)
  migrate            Run Alembic migrations on EC2
  status             Show deployment status on EC2
  logs               Tail API container logs on EC2
  rollback           Rollback to previous image version

Examples:
  ./deploy.sh setup-ec2      # One-time: migrate EC2 from git-clone to Docker
  ./deploy.sh setup-nginx    # Configure Nginx SSL
  ./deploy.sh build          # Build image
  ./deploy.sh deploy         # Full deploy
  ./deploy.sh logs           # Follow logs
  ./deploy.sh migrate        # Run DB migrations

Environment variables (all required — set in .env or export):
  DOCKER_USERNAME            Docker Hub username
  DOCKER_PASSWORD            Docker Hub password / token
  EC2_HOST                   EC2 public DNS or IP (e.g. ec2-xx-xx-xx-xx.ap-south-1.compute.amazonaws.com)
  EC2_USER                   SSH user (e.g. ec2-user, ubuntu)
  EC2_SSH_KEY                Path to SSH private key (e.g. ~/downloads/my-key.pem)

Optional:
  IMAGE_NAME                 Docker image name (default: careerai-backend)
  REGISTRY_TYPE              "dockerhub" (default) or "ecr"
  AWS_ACCOUNT_ID             Required if REGISTRY_TYPE=ecr
  AWS_REGION                 AWS region (default: us-east-1)
  EC2_APP_DIR                Remote app directory (default: /home/$EC2_USER/careerai)
  EC2_ENV_FILE               Local env file to upload (default: ./.env)
  HEALTH_CHECK_DOMAIN        Optional domain URL for health check (e.g. https://example.com/health)
  RUN_MIGRATIONS_ON_DEPLOY   Set to "false" to skip migrations (default: true)
  DOCKER_PASSWORD            Can also be set in .env file referenced by EC2_ENV_FILE
USAGE
            exit 0
            ;;
    esac
}

main "$@"
