#!/usr/bin/env python3
"""
Simple Python Web Application Deployment with dockr

This example demonstrates deploying a FastAPI application with PostgreSQL 
database and Caddy reverse proxy using dockr.
"""

from dockr.core import Dockerfile
from dockr.compose import Compose
from dockr.caddy import caddy

def create_app_dockerfile():
    """Create Dockerfile for Python web application"""
    return (Dockerfile()
        .from_('python:3.12-slim')
        .workdir('/app')
        .copy('requirements.txt', '.')
        .run('pip install --no-cache-dir -r requirements.txt')
        .copy('.', '.')
        .expose(8000)
        .cmd(['uvicorn', 'main:app', '--host', '0.0.0.0', '--port', '8000'])
    )

def create_compose(domain='example.com', use_caddy=True):
    """Create docker-compose configuration"""
    compose = Compose()
    
    # Add web application service
    compose = compose.svc('app',
        build='.',
        env={
            'DATABASE_URL': 'postgresql://user:password@db:5432/appdb',
            'APP_ENV': 'production'
        },
        volumes={'./app': '/app/app'},
        depends_on=['db'],
        restart='unless-stopped',
        networks=['web']
    )
    
    # Add PostgreSQL database
    compose = compose.svc('db',
        image='postgres:15-alpine',
        env={
            'POSTGRES_USER': 'user',
            'POSTGRES_PASSWORD': 'password',
            'POSTGRES_DB': 'appdb'
        },
        volumes={'pgdata': '/var/lib/postgresql/data'},
        restart='unless-stopped',
        networks=['web']
    )
    
    # Add Caddy reverse proxy (optional)
    if use_caddy:
        compose = compose.svc('caddy', **caddy(
            domain=domain,
            app='app',
            port=8000,
            email='admin@example.com',
            dns='cloudflare'  # Use Cloudflare DNS for HTTPS
        ))
        compose = compose.volume('caddy_data')
        compose = compose.volume('caddy_config')
    
    # Add network and volumes
    compose = compose.network('web')
    compose = compose.volume('pgdata')
    
    return compose

def deploy(domain='localhost', use_caddy=False):
    """Deploy the application"""
    print("Creating Dockerfile...")
    dockerfile = create_app_dockerfile()
    dockerfile.save('Dockerfile')
    print(f"✓ Dockerfile created")
    
    print(f"\nCreating docker-compose.yml...")
    compose = create_compose(domain=domain, use_caddy=use_caddy)
    compose.save('docker-compose.yml')
    print(f"✓ docker-compose.yml created")
    
    print("\nStarting services...")
    try:
        compose.up(detach=True)
        print("✓ Services started successfully")
        print(f"\nApplication should be available at:")
        if use_caddy:
            print(f"  https://{domain}")
        else:
            print(f"  http://localhost:8000")
    except Exception as e:
        print(f"✗ Error starting services: {e}")
        return False
    
    return True

if __name__ == '__main__':
    import sys
    
    # Parse command line arguments
    domain = sys.argv[1] if len(sys.argv) > 1 else 'localhost'
    use_caddy = '--caddy' in sys.argv or domain != 'localhost'
    
    print(f"Deploying Python Web Application")
    print(f"Domain: {domain}")
    print(f"Reverse Proxy: {'Caddy' if use_caddy else 'None'}")
    print("-" * 50)
    
    success = deploy(domain=domain, use_caddy=use_caddy)
    
    if success:
        print("\n✓ Deployment complete!")
        print("\nTo stop services:")
        print("  docker compose down")
        print("\nTo view logs:")
        print("  docker compose logs -f")
    else:
        print("\n✗ Deployment failed!")
        sys.exit(1)
