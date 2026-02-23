# dockr Deployment Examples

This directory contains real-world deployment examples demonstrating how to use dockr to replace traditional Dockerfiles and docker-compose configurations.

## Examples

### 1. Simple Python Web Application (`python_webapp/`)
Perfect for: Flask, FastAPI, Django applications

**Features:**
- Python web application (FastAPI/Flask)
- PostgreSQL database with persistent storage
- Optional Caddy reverse proxy with automatic HTTPS
- Production-ready configuration

**Quick Start:**
```bash
cd python_webapp
python deploy.py localhost
```

### 2. Microservices Architecture (`microservices/`)
Perfect for: Complex multi-service applications

**Features:**
- API Gateway (Node.js)
- Multiple microservices (Python/FastAPI)
- Shared PostgreSQL database
- Redis cache
- Network isolation (frontend/backend)
- Caddy reverse proxy with HTTPS
- Health checks and auto-restart

**Quick Start:**
```bash
cd microservices
python deploy.py localhost
```

### 3. Static Sites & SPAs (`static_site/`)
Perfect for: React, Vue, Angular, static HTML sites

**Features:**
- nginx-based static file serving
- Multi-stage builds for SPAs
- Optimized caching and compression
- SPA routing support
- Automatic HTTPS with Caddy

**Quick Start:**
```bash
cd static_site
python deploy.py localhost
# Or for SPAs:
python deploy.py localhost --spa
```

## Common Patterns

All examples demonstrate:
- ✓ Programmatic Dockerfile generation (no manual Dockerfile writing)
- ✓ Fluent docker-compose configuration in Python
- ✓ Automatic HTTPS with Caddy or SWAG
- ✓ Environment-based configuration (dev vs production)
- ✓ Database persistence with volumes
- ✓ Network isolation for security
- ✓ Health checks and restart policies

## Getting Started

### Prerequisites

```bash
# Install dockr
pip install -e /path/to/dockr

# Or from git
pip install git+https://github.com/Karthik777/dockr.git

# Ensure Docker or Podman is installed
docker --version
# or
podman --version
```

### Environment Variables

For HTTPS deployments, set one of:

```bash
# For Cloudflare DNS
export CLOUDFLARE_API_TOKEN=your_token

# For DuckDNS
export DUCKDNS_TOKEN=your_token

# For database passwords
export DB_PASSWORD=secure_password
```

### Local Development

Run any example locally without HTTPS:

```bash
cd <example-directory>
python deploy.py localhost
```

### Production Deployment

Deploy with automatic HTTPS:

```bash
cd <example-directory>
export CLOUDFLARE_API_TOKEN=your_token
python deploy.py yourdomain.com --caddy
# or
python deploy.py yourdomain.com --https
```

## Comparison with Traditional Approach

### Traditional Way

You would need to manage:
1. **Dockerfile** - Multiple files with Dockerfile syntax
2. **docker-compose.yml** - YAML configuration
3. **Caddyfile** or **nginx.conf** - Separate reverse proxy config
4. **Shell scripts** - For orchestration
5. **Documentation** - In multiple formats

### With dockr

Everything in Python:
```python
from dockr.core import Dockerfile
from dockr.compose import Compose
from dockr.caddy import caddy

# Define everything in code
df = Dockerfile().from_('python:3.12')...
dc = Compose().svc('app', build='.')...
dc = dc.svc('caddy', **caddy(...))

# Deploy
dc.up()
```

**Benefits:**
- Single language (Python)
- Type safety and IDE support
- Reusable functions and modules
- Version control friendly
- Easy to test and validate
- Programmatic generation

## Architecture Patterns

### Simple App Pattern
```
Internet → Caddy (HTTPS) → App → Database
```
Use: `python_webapp/`

### Microservices Pattern
```
Internet → Caddy → Gateway → Microservices → Database/Cache
```
Use: `microservices/`

### Static Site Pattern
```
Internet → Caddy (HTTPS) → nginx (static files)
```
Use: `static_site/`

## Next Steps

1. **Choose an example** that matches your use case
2. **Read the example's README** for detailed instructions
3. **Customize** the deployment script for your needs
4. **Test locally** without HTTPS
5. **Deploy to production** with HTTPS

## Support

For more information:
- [Main README](../README.md)
- [Deployment Verification](../DEPLOYMENT_VERIFICATION.md)
- [GitHub Issues](https://github.com/Karthik777/dockr/issues)

