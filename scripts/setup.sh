#!/usr/bin/env bash
set -euo pipefail

echo "=== Agent Observability Setup ==="

echo "1. Creating .env from example"
if [ ! -f .env ]; then
    cp .env.example .env
    echo "   → .env created — edit it with your values"
else
    echo "   → .env already exists"
fi

echo "2. Generating secret key"
if grep -q "generate-a-random-64" .env; then
    NEW_SECRET=$(openssl rand -hex 64)
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s/AGENT_OBS_SECRET_KEY=.*/AGENT_OBS_SECRET_KEY=$NEW_SECRET/" .env
    else
        sed -i "s/AGENT_OBS_SECRET_KEY=.*/AGENT_OBS_SECRET_KEY=$NEW_SECRET/" .env
    fi
    echo "   → Secret key generated"
fi

echo "3. Starting development environment"
docker compose -f docker-compose.dev.yml up -d --build

echo "4. Waiting for API..."
for i in {1..15}; do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        echo "   → API ready at http://localhost:8000"
        break
    fi
    sleep 2
done

echo "5. Creating default tenant"
curl -s -X POST http://localhost:8000/api/v1/tenants \
    -H "Content-Type: application/json" \
    -d '{"name": "Demo", "slug": "demo", "api_key": "demo-key-1234567890123456"}' > /dev/null

echo ""
echo "=== Setup complete ==="
echo "API:       http://localhost:8000"
echo "Docs:      http://localhost:8000/docs"
echo "Dashboard: http://localhost:8501"
echo ""
echo "Default API Key: demo-key-1234567890123456"
