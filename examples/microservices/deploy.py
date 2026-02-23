#!/usr/bin/env python3
"""
Microservices Deployment Example with dockr

This example demonstrates deploying multiple microservices with:
- API gateway
- User service
- Product service
- Shared PostgreSQL database
- Redis cache
- Caddy reverse proxy with automatic HTTPS
"""

from dockr.core import Dockerfile
from dockr.compose import Compose
from dockr.caddy import caddy

def create_api_gateway_dockerfile():
    """Create Dockerfile for API Gateway (Node.js/Express)"""
    return (Dockerfile()
        .from_('node:18-alpine')
        .workdir('/app')
        .copy('package*.json', '.')
        .run('npm ci --only=production')
        .copy('.', '.')
        .expose(3000)
        .cmd(['node', 'server.js'])
    )

def create_python_service_dockerfile():
    """Create Dockerfile for Python microservices (FastAPI)"""
    return (Dockerfile()
        .from_('python:3.12-slim')
        .workdir('/app')
        .copy('requirements.txt', '.')
        .run('pip install --no-cache-dir -r requirements.txt')
        .copy('.', '.')
        .expose(8000)
        .healthcheck(
            ['curl', '-f', 'http://localhost:8000/health'],
            i='30s', t='10s', r=3
        )
        .cmd(['uvicorn', 'main:app', '--host', '0.0.0.0', '--port', '8000'])
    )

def create_microservices_compose(domain='localhost', use_https=False):
    """Create docker-compose configuration for microservices"""
    compose = Compose()
    
    # API Gateway (Node.js)
    compose = compose.svc('gateway',
        build='./gateway',
        env={
            'PORT': '3000',
            'USER_SERVICE_URL': 'http://user-service:8000',
            'PRODUCT_SERVICE_URL': 'http://product-service:8000',
            'REDIS_URL': 'redis://redis:6379'
        },
        depends_on=['user-service', 'product-service', 'redis'],
        restart='unless-stopped',
        networks=['web', 'backend']
    )
    
    # User Service (Python/FastAPI)
    compose = compose.svc('user-service',
        build='./services/users',
        env={
            'DATABASE_URL': 'postgresql://user:${DB_PASSWORD}@db:5432/users_db',
            'REDIS_URL': 'redis://redis:6379',
            'SERVICE_NAME': 'user-service'
        },
        depends_on=['db', 'redis'],
        restart='unless-stopped',
        networks=['backend']
    )
    
    # Product Service (Python/FastAPI)
    compose = compose.svc('product-service',
        build='./services/products',
        env={
            'DATABASE_URL': 'postgresql://user:${DB_PASSWORD}@db:5432/products_db',
            'REDIS_URL': 'redis://redis:6379',
            'SERVICE_NAME': 'product-service'
        },
        depends_on=['db', 'redis'],
        restart='unless-stopped',
        networks=['backend']
    )
    
    # PostgreSQL Database
    compose = compose.svc('db',
        image='postgres:15-alpine',
        env={
            'POSTGRES_USER': 'user',
            'POSTGRES_PASSWORD': '${DB_PASSWORD}',
            'POSTGRES_MULTIPLE_DATABASES': 'users_db,products_db'
        },
        volumes={
            'postgres_data': '/var/lib/postgresql/data',
            './init-db.sh': '/docker-entrypoint-initdb.d/init-db.sh'
        },
        restart='unless-stopped',
        networks=['backend']
    )
    
    # Redis Cache
    compose = compose.svc('redis',
        image='redis:7-alpine',
        command='redis-server --appendonly yes',
        volumes={'redis_data': '/data'},
        restart='unless-stopped',
        networks=['backend']
    )
    
    # Caddy Reverse Proxy (optional)
    if use_https:
        compose = compose.svc('caddy', **caddy(
            domain=domain,
            app='gateway',
            port=3000,
            email='admin@example.com',
            dns='cloudflare'
        ))
        compose = compose.volume('caddy_data')
        compose = compose.volume('caddy_config')
    else:
        # Expose gateway directly for local development
        gateway_svc = next(s for t, n, s in compose if n == 'gateway')
        gateway_svc['ports'] = {3000: 3000}
    
    # Networks
    compose = compose.network('web')
    compose = compose.network('backend')
    
    # Volumes
    compose = compose.volume('postgres_data')
    compose = compose.volume('redis_data')
    
    return compose

def deploy(domain='localhost', use_https=False):
    """Deploy the microservices"""
    print("Creating Dockerfiles...")
    
    # API Gateway Dockerfile
    gateway_df = create_api_gateway_dockerfile()
    gateway_df.save('gateway/Dockerfile')
    print("✓ Gateway Dockerfile created")
    
    # Service Dockerfiles
    service_df = create_python_service_dockerfile()
    service_df.save('services/users/Dockerfile')
    service_df.save('services/products/Dockerfile')
    print("✓ Service Dockerfiles created")
    
    print(f"\nCreating docker-compose.yml...")
    compose = create_microservices_compose(domain=domain, use_https=use_https)
    compose.save('docker-compose.yml')
    print(f"✓ docker-compose.yml created")
    
    print("\nStarting services...")
    try:
        compose.up(detach=True)
        print("✓ Services started successfully")
        print(f"\nApplication should be available at:")
        if use_https:
            print(f"  https://{domain}")
        else:
            print(f"  http://localhost:3000")
        print("\nService URLs (internal):")
        print("  - User Service: http://user-service:8000")
        print("  - Product Service: http://product-service:8000")
    except Exception as e:
        print(f"✗ Error starting services: {e}")
        return False
    
    return True

if __name__ == '__main__':
    import sys
    
    # Parse command line arguments
    domain = sys.argv[1] if len(sys.argv) > 1 else 'localhost'
    use_https = '--https' in sys.argv or domain != 'localhost'
    
    print(f"Deploying Microservices Architecture")
    print(f"Domain: {domain}")
    print(f"HTTPS: {'Enabled' if use_https else 'Disabled'}")
    print("-" * 60)
    
    success = deploy(domain=domain, use_https=use_https)
    
    if success:
        print("\n✓ Deployment complete!")
        print("\nArchitecture:")
        print("  Internet → Caddy → API Gateway → Microservices → Database/Cache")
        print("\nTo stop services:")
        print("  docker compose down")
        print("\nTo view logs:")
        print("  docker compose logs -f gateway")
        print("  docker compose logs -f user-service")
    else:
        print("\n✗ Deployment failed!")
        sys.exit(1)
