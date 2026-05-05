#!/bin/bash
# WinExtraFlow — Deploy Script
# Usage: bash deploy.sh [setup|update|ssl|backup|logs|status]

set -e

PROJECT_DIR="/opt/winextraflow"
DOMAIN="${DOMAIN:-winextraflow.com}"

case "$1" in
  setup)
    echo "=== WinExtraFlow Initial Setup ==="

    # Install dependencies
    apt update && apt upgrade -y
    curl -fsSL https://get.docker.com | sh
    apt install -y docker-compose-plugin git certbot

    # Clone project
    if [ ! -d "$PROJECT_DIR" ]; then
      echo "Clone your repository to $PROJECT_DIR first!"
      exit 1
    fi

    cd "$PROJECT_DIR"

    # Create .env if not exists
    if [ ! -f .env ]; then
      cp .env.production.example .env
      # Generate random secret key
      SECRET=$(openssl rand -hex 32)
      sed -i "s/CHANGE_ME_RANDOM_32_CHAR_STRING_HERE/$SECRET/" .env
      echo ">>> EDIT .env with your settings: nano .env"
      exit 0
    fi

    # Build and start
    docker compose up -d --build
    echo "=== Setup complete! ==="
    docker compose ps
    ;;

  update)
    echo "=== Updating WinExtraFlow ==="
    cd "$PROJECT_DIR"
    git pull
    docker compose up -d --build
    echo "=== Update complete! ==="
    docker compose ps
    ;;

  ssl)
    echo "=== Setting up SSL for $DOMAIN ==="
    cd "$PROJECT_DIR"
    docker compose stop nginx
    certbot certonly --standalone -d "$DOMAIN" -d "www.$DOMAIN" --non-interactive --agree-tos -m "admin@$DOMAIN"

    # Switch to SSL nginx config
    cp nginx/nginx.prod.conf nginx/nginx.conf
    sed -i "s/winextraflow.com/$DOMAIN/g" nginx/nginx.conf

    docker compose up -d nginx
    echo "=== SSL configured for $DOMAIN ==="
    ;;

  backup)
    echo "=== Creating backup ==="
    cd "$PROJECT_DIR"
    BACKUP_FILE="backup_$(date +%Y%m%d_%H%M%S).sql"
    docker compose exec -T postgres pg_dump -U winextraflow winextraflow > "$BACKUP_FILE"
    echo "Backup saved to: $BACKUP_FILE ($(du -h $BACKUP_FILE | cut -f1))"
    ;;

  logs)
    cd "$PROJECT_DIR"
    docker compose logs -f --tail 50 "${2:-backend}"
    ;;

  status)
    cd "$PROJECT_DIR"
    echo "=== Services ==="
    docker compose ps
    echo ""
    echo "=== Resources ==="
    docker stats --no-stream
    echo ""
    echo "=== Disk ==="
    df -h /
    echo ""
    echo "=== Health ==="
    curl -s http://localhost/health 2>/dev/null || echo "Backend not responding"
    ;;

  *)
    echo "Usage: bash deploy.sh [setup|update|ssl|backup|logs|status]"
    echo ""
    echo "Commands:"
    echo "  setup   - Initial server setup (Docker, deps, first build)"
    echo "  update  - Pull latest code and rebuild"
    echo "  ssl     - Configure SSL certificate (Let's Encrypt)"
    echo "  backup  - Backup PostgreSQL database"
    echo "  logs    - View logs (default: backend, or specify service)"
    echo "  status  - Show services, resources, health"
    ;;
esac
