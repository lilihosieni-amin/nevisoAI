#!/bin/bash

# Neviso Backend Deployment Script
# Usage: ./deploy.sh [build|up|down|logs|restart|backup]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if .env.production exists
check_env() {
    if [ ! -f .env.production ]; then
        echo -e "${RED}Error: .env.production file not found!${NC}"
        echo "Please create .env.production with your production settings."
        exit 1
    fi
}

# Check if MySQL passwords are set
check_passwords() {
    if [ -z "$MYSQL_PASSWORD" ] || [ -z "$MYSQL_ROOT_PASSWORD" ]; then
        echo -e "${YELLOW}MySQL passwords not set. Please enter them:${NC}"
        read -sp "Enter MYSQL_ROOT_PASSWORD: " MYSQL_ROOT_PASSWORD
        echo
        read -sp "Enter MYSQL_PASSWORD: " MYSQL_PASSWORD
        echo
        export MYSQL_ROOT_PASSWORD
        export MYSQL_PASSWORD
    fi
}

# Build images
build() {
    echo -e "${GREEN}Building Docker images...${NC}"
    check_env
    check_passwords
    docker compose build
    echo -e "${GREEN}Build completed!${NC}"
}

# Start services
up() {
    echo -e "${GREEN}Starting services...${NC}"
    check_env
    check_passwords
    docker compose up -d
    echo -e "${GREEN}Services started!${NC}"
    echo -e "${YELLOW}Waiting for services to be healthy...${NC}"
    sleep 10
    docker compose ps
}

# Stop services
down() {
    echo -e "${YELLOW}Stopping services...${NC}"
    docker compose down
    echo -e "${GREEN}Services stopped!${NC}"
}

# View logs
logs() {
    SERVICE=${2:-}
    if [ -z "$SERVICE" ]; then
        docker compose logs -f
    else
        docker compose logs -f "$SERVICE"
    fi
}

# Restart services
restart() {
    echo -e "${YELLOW}Restarting services...${NC}"
    check_passwords
    docker compose restart
    echo -e "${GREEN}Services restarted!${NC}"
}

# Backup database
backup() {
    echo -e "${GREEN}Creating database backup...${NC}"
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_FILE="backups/neviso_backup_${TIMESTAMP}.sql"
    mkdir -p backups

    docker compose exec -T db mysqldump -u neviso -p"${MYSQL_PASSWORD}" neviso_db > "$BACKUP_FILE"

    if [ -f "$BACKUP_FILE" ]; then
        echo -e "${GREEN}Backup created: ${BACKUP_FILE}${NC}"
        echo "Size: $(ls -lh "$BACKUP_FILE" | awk '{print $5}')"
    else
        echo -e "${RED}Backup failed!${NC}"
        exit 1
    fi
}

# Run database migrations
migrate() {
    echo -e "${GREEN}Running database migrations...${NC}"
    docker compose exec app alembic upgrade head
    echo -e "${GREEN}Migrations completed!${NC}"
}

# Show status
status() {
    echo -e "${GREEN}Service Status:${NC}"
    docker compose ps
}

# Show help
help() {
    echo "Neviso Backend Deployment Script"
    echo ""
    echo "Usage: ./deploy.sh [command]"
    echo ""
    echo "Commands:"
    echo "  build     Build Docker images"
    echo "  up        Start all services"
    echo "  down      Stop all services"
    echo "  restart   Restart all services"
    echo "  logs      View logs (optionally specify service: logs app)"
    echo "  backup    Create database backup"
    echo "  migrate   Run database migrations"
    echo "  status    Show service status"
    echo "  help      Show this help message"
    echo ""
    echo "Environment Variables:"
    echo "  MYSQL_ROOT_PASSWORD  MySQL root password"
    echo "  MYSQL_PASSWORD       MySQL user password"
    echo ""
    echo "Example:"
    echo "  export MYSQL_ROOT_PASSWORD=your_root_password"
    echo "  export MYSQL_PASSWORD=your_user_password"
    echo "  ./deploy.sh up"
}

# Main
case "${1:-help}" in
    build)
        build
        ;;
    up)
        up
        ;;
    down)
        down
        ;;
    logs)
        logs "$@"
        ;;
    restart)
        restart
        ;;
    backup)
        backup
        ;;
    migrate)
        migrate
        ;;
    status)
        status
        ;;
    help|*)
        help
        ;;
esac
