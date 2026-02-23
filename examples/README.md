# dockr Deployment Examples

This directory contains real-world deployment examples demonstrating how to use dockr to replace traditional Dockerfiles and docker-compose configurations.

## Examples

### 1. Simple Python Web Application
- FastAPI/Flask application
- PostgreSQL database
- Nginx reverse proxy
- See: `python_webapp/`

### 2. Full-Stack Application with Caddy
- Python backend (FastAPI)
- PostgreSQL database  
- Caddy reverse proxy with automatic HTTPS
- See: `fullstack_caddy/`

### 3. Multi-Service Application with SWAG
- Multiple microservices
- Shared database
- SWAG reverse proxy with Let's Encrypt
- See: `multiservice_swag/`

## Quick Start

Each example includes:
- `deploy.py` - Deployment script using dockr
- `README.md` - Specific instructions
- Sample application code

To run an example:
```bash
cd examples/<example-name>
python deploy.py
```
