#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/agent-observability"
BACKUP_DIR="/opt/backups/agent-obs"
DATE=$(date +%Y%m%d_%H%M%S)

echo "=== Deploying Agent Observability ==="

cd "$APP_DIR"

echo "1. Backup database"
docker compose exec -T postgres pg_dump -U postgres agent_obs > "$BACKUP_DIR/dump_$DATE.sql"
echo "   → Backup saved to $BACKUP_DIR/dump_$DATE.sql"

echo "2. Pull latest images"
docker compose pull

echo "3. Run database migrations (auto on startup)"
echo "   → Handled by FastAPI startup event"

echo "4. Deploy with zero-downtime"
docker compose up -d --remove-orphans --wait

echo "5. Health check"
for i in {1..12}; do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        echo "   → API is healthy"
        break
    fi
    echo "   → Waiting... ($i)"
    sleep 5
done

echo "6. Cleanup old images"
docker system prune -f

echo "7. Prune old backups (keep last 30)"
ls -t "$BACKUP_DIR"/dump_*.sql | tail -n +31 | xargs -r rm

echo "=== Deploy complete ==="
