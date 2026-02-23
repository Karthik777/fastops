# Python Web Application Example

This example demonstrates deploying a FastAPI application with PostgreSQL database using dockr.

## Features

- FastAPI web application
- PostgreSQL database with persistent storage
- Optional Caddy reverse proxy with automatic HTTPS
- Production-ready configuration

## Requirements

- Python 3.10+
- Docker or Podman
- dockr installed (`pip install -e ../..`)

## Quick Start

### Local Development (No HTTPS)

```bash
# Create sample application files
cat > main.py << 'EOF'
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Hello from dockr!"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}
EOF

cat > requirements.txt << 'EOF'
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
psycopg2-binary>=2.9.9
EOF

# Deploy
python deploy.py localhost

# Application will be available at http://localhost:8000
```

### Production Deployment with HTTPS

```bash
# Set environment variables
export CLOUDFLARE_API_TOKEN=your_cloudflare_token

# Deploy with Caddy
python deploy.py example.com --caddy

# Application will be available at https://example.com
```

## File Structure

```
python_webapp/
├── deploy.py           # Deployment script
├── README.md          # This file
├── main.py            # FastAPI application (create this)
└── requirements.txt   # Python dependencies (create this)
```

## What dockr Replaces

### Traditional Approach

You would typically need:
1. **Dockerfile** - Manually written with multiple RUN, COPY, etc.
2. **docker-compose.yml** - YAML configuration for services
3. **Caddyfile** - Separate configuration for reverse proxy
4. Manual commands to build and deploy

### With dockr

All configuration is in Python code:
- Fluent Dockerfile builder
- Programmatic compose file generation
- Integrated reverse proxy configuration
- Single command deployment

## Customization

### Change Application Port

```python
compose = compose.svc('app',
    ...
    expose=9000  # Change port
)

compose = compose.svc('caddy', **caddy(
    ...
    port=9000  # Update reverse proxy
))
```

### Add Redis Cache

```python
compose = compose.svc('redis',
    image='redis:7-alpine',
    networks=['web'],
    restart='unless-stopped'
)
```

### Multiple Databases

```python
compose = compose.svc('db_users',
    image='postgres:15-alpine',
    env={'POSTGRES_DB': 'users'},
    ...
)

compose = compose.svc('db_content',
    image='postgres:15-alpine',
    env={'POSTGRES_DB': 'content'},
    ...
)
```

## Environment Variables

For production deployments:

```bash
# Database credentials
export POSTGRES_PASSWORD=your_secure_password

# Cloudflare (for HTTPS)
export CLOUDFLARE_API_TOKEN=your_token

# DuckDNS (alternative to Cloudflare)
export DUCKDNS_TOKEN=your_token
```

## Management Commands

```bash
# View status
docker compose ps

# View logs
docker compose logs -f app

# Restart a service
docker compose restart app

# Stop all services
docker compose down

# Stop and remove volumes
docker compose down -v
```

## Verification

After deployment, verify:

```bash
# Check health endpoint
curl http://localhost:8000/health

# Or with HTTPS
curl https://example.com/health

# Check database connection
docker compose exec db psql -U user -d appdb -c "SELECT version();"

# Check logs
docker compose logs app
```
