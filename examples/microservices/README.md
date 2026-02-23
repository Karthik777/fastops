# Microservices Deployment Example

This example demonstrates deploying a microservices architecture with dockr:
- API Gateway (Node.js/Express)
- User Service (Python/FastAPI)
- Product Service (Python/FastAPI)
- Shared PostgreSQL database
- Redis cache
- Caddy reverse proxy

## Architecture

```
Internet
    ↓
Caddy (HTTPS)
    ↓
API Gateway (Node.js:3000)
    ├→ User Service (Python:8000)
    ├→ Product Service (Python:8000)
    └→ Redis Cache
           ↓
      PostgreSQL Database
```

## Features

- **Service Isolation**: Each microservice in its own container
- **Shared Database**: Multiple databases on single PostgreSQL instance
- **Caching Layer**: Redis for session and data caching
- **API Gateway**: Centralized routing and authentication
- **Network Isolation**: Separate frontend (web) and backend networks
- **Health Checks**: Built-in health monitoring
- **Auto-restart**: Services automatically restart on failure

## Quick Start

### 1. Create Service Directories

```bash
mkdir -p gateway services/users services/products
```

### 2. Create Sample Gateway (Node.js)

```bash
cat > gateway/package.json << 'EOF'
{
  "name": "api-gateway",
  "version": "1.0.0",
  "dependencies": {
    "express": "^4.18.0",
    "axios": "^1.6.0",
    "redis": "^4.6.0"
  }
}
EOF

cat > gateway/server.js << 'EOF'
const express = require('express');
const axios = require('axios');
const app = express();

app.get('/health', (req, res) => res.json({ status: 'healthy' }));

app.get('/users/*', async (req, res) => {
    const response = await axios.get(`${process.env.USER_SERVICE_URL}${req.path.replace('/users', '')}`);
    res.json(response.data);
});

app.get('/products/*', async (req, res) => {
    const response = await axios.get(`${process.env.PRODUCT_SERVICE_URL}${req.path.replace('/products', '')}`);
    res.json(response.data);
});

app.listen(3000, () => console.log('Gateway listening on port 3000'));
EOF
```

### 3. Create Sample User Service (Python)

```bash
cat > services/users/requirements.txt << 'EOF'
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
psycopg2-binary>=2.9.9
redis>=5.0.0
EOF

cat > services/users/main.py << 'EOF'
from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "healthy", "service": "users"}

@app.get("/")
def list_users():
    return {"users": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]}

@app.get("/{user_id}")
def get_user(user_id: int):
    return {"id": user_id, "name": "User " + str(user_id)}
EOF
```

### 4. Create Sample Product Service (Python)

```bash
cat > services/products/requirements.txt << 'EOF'
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
psycopg2-binary>=2.9.9
redis>=5.0.0
EOF

cat > services/products/main.py << 'EOF'
from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "healthy", "service": "products"}

@app.get("/")
def list_products():
    return {"products": [{"id": 1, "name": "Widget"}, {"id": 2, "name": "Gadget"}]}

@app.get("/{product_id}")
def get_product(product_id: int):
    return {"id": product_id, "name": "Product " + str(product_id)}
EOF
```

### 5. Create Database Init Script

```bash
cat > init-db.sh << 'EOF'
#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    CREATE DATABASE users_db;
    CREATE DATABASE products_db;
EOSQL
EOF
chmod +x init-db.sh
```

### 6. Deploy

```bash
# Set environment variables
export DB_PASSWORD=secure_password_here

# Local development (no HTTPS)
python deploy.py localhost

# Production with HTTPS
export CLOUDFLARE_API_TOKEN=your_token
python deploy.py example.com --https
```

## Testing

```bash
# Test gateway
curl http://localhost:3000/health

# Test user service through gateway
curl http://localhost:3000/users/

# Test product service through gateway
curl http://localhost:3000/products/

# Test individual services (internal)
docker compose exec user-service curl http://localhost:8000/health
docker compose exec product-service curl http://localhost:8000/health
```

## Scaling

To scale services:

```bash
# Scale user service to 3 instances
docker compose up -d --scale user-service=3

# Scale product service to 2 instances
docker compose up -d --scale product-service=2
```

Note: When scaling, you'll need a load balancer (like adding nginx or using Docker Swarm).

## Customization

### Add New Microservice

```python
# In deploy.py, add a new service
compose = compose.svc('order-service',
    build='./services/orders',
    env={
        'DATABASE_URL': 'postgresql://user:${DB_PASSWORD}@db:5432/orders_db',
        'REDIS_URL': 'redis://redis:6379'
    },
    depends_on=['db', 'redis'],
    networks=['backend']
)
```

### Add Message Queue

```python
# Add RabbitMQ or Kafka
compose = compose.svc('rabbitmq',
    image='rabbitmq:3-management-alpine',
    ports={5672: 5672, 15672: 15672},
    env={
        'RABBITMQ_DEFAULT_USER': 'user',
        'RABBITMQ_DEFAULT_PASS': '${RABBITMQ_PASSWORD}'
    },
    networks=['backend']
)
```

### Add Monitoring

```python
# Add Prometheus and Grafana
compose = compose.svc('prometheus',
    image='prom/prometheus',
    volumes={'./prometheus.yml': '/etc/prometheus/prometheus.yml'},
    networks=['backend']
)

compose = compose.svc('grafana',
    image='grafana/grafana',
    ports={3001: 3000},
    networks=['backend', 'web']
)
```

## Management

```bash
# View all services
docker compose ps

# View logs
docker compose logs -f gateway
docker compose logs -f user-service
docker compose logs -f product-service

# Restart a service
docker compose restart user-service

# Scale a service
docker compose up -d --scale user-service=3

# Stop all services
docker compose down

# Stop and remove all data
docker compose down -v
```

## Network Topology

- **web network**: Public-facing services (caddy, gateway)
- **backend network**: Internal services (services, db, redis)

This provides network isolation - microservices cannot be accessed directly from the internet.

## Environment Variables

Required for production:

```bash
# Database
export DB_PASSWORD=your_secure_password

# HTTPS (choose one)
export CLOUDFLARE_API_TOKEN=your_cloudflare_token
# OR
export DUCKDNS_TOKEN=your_duckdns_token
```
