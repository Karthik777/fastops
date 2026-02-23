#!/usr/bin/env python3
"""
Static Site Deployment with dockr

This example demonstrates deploying a static website with:
- nginx web server
- Optional Caddy reverse proxy with automatic HTTPS
- Cloudflare integration for CDN
"""

from dockr.core import Dockerfile
from dockr.compose import Compose
from dockr.caddy import caddy

def create_static_site_dockerfile():
    """Create Dockerfile for static site with nginx"""
    return (Dockerfile()
        .from_('nginx:alpine')
        .copy('site/', '/usr/share/nginx/html/')
        .copy('nginx.conf', '/etc/nginx/nginx.conf')
        .expose(80)
        .cmd(['nginx', '-g', 'daemon off;'])
    )

def create_spa_dockerfile():
    """Create Dockerfile for Single Page Application (React/Vue/etc)"""
    return (Dockerfile()
        # Build stage
        .from_('node:18-alpine', as_='build')
        .workdir('/app')
        .copy('package*.json', '.')
        .run('npm ci')
        .copy('.', '.')
        .run('npm run build')
        # Production stage
        .from_('nginx:alpine')
        .copy('/app/dist', '/usr/share/nginx/html', from_='build')
        .copy('nginx.conf', '/etc/nginx/nginx.conf')
        .expose(80)
        .cmd(['nginx', '-g', 'daemon off;'])
    )

def create_static_compose(domain='localhost', use_https=False, spa=False):
    """Create docker-compose configuration for static site"""
    compose = Compose()
    
    # Static site service
    compose = compose.svc('web',
        build='.',
        restart='unless-stopped',
        networks=['web']
    )
    
    # Caddy reverse proxy (for HTTPS)
    if use_https:
        compose = compose.svc('caddy', **caddy(
            domain=domain,
            app='web',
            port=80,
            email='admin@example.com',
            dns='cloudflare',
            cloudflared=False  # Set True for Cloudflare Tunnel
        ))
        compose = compose.volume('caddy_data')
        compose = compose.volume('caddy_config')
    else:
        # Expose web directly for local development
        web_svc = next(s for t, n, s in compose if n == 'web')
        web_svc['ports'] = {80: 8080}
    
    # Network
    compose = compose.network('web')
    
    return compose

def deploy(domain='localhost', use_https=False, spa=False):
    """Deploy the static site"""
    print("Creating Dockerfile...")
    
    if spa:
        df = create_spa_dockerfile()
        print("✓ SPA Dockerfile created (with build stage)")
    else:
        df = create_static_site_dockerfile()
        print("✓ Static site Dockerfile created")
    
    df.save('Dockerfile')
    
    print(f"\nCreating docker-compose.yml...")
    compose = create_static_compose(domain=domain, use_https=use_https, spa=spa)
    compose.save('docker-compose.yml')
    print(f"✓ docker-compose.yml created")
    
    # Create sample nginx config if it doesn't exist
    from pathlib import Path
    if not Path('nginx.conf').exists():
        nginx_conf = """
events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    
    sendfile on;
    keepalive_timeout 65;
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;
    
    server {
        listen 80;
        server_name _;
        root /usr/share/nginx/html;
        index index.html;
        
        # SPA fallback
        location / {
            try_files $uri $uri/ /index.html;
        }
        
        # Cache static assets
        location ~* \\.(jpg|jpeg|png|gif|ico|css|js|svg|woff|woff2|ttf|eot)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }
}
""".strip()
        Path('nginx.conf').write_text(nginx_conf)
        print("✓ nginx.conf created")
    
    print("\nStarting services...")
    try:
        compose.up(detach=True)
        print("✓ Services started successfully")
        print(f"\nSite should be available at:")
        if use_https:
            print(f"  https://{domain}")
        else:
            print(f"  http://localhost:8080")
    except Exception as e:
        print(f"✗ Error starting services: {e}")
        return False
    
    return True

if __name__ == '__main__':
    import sys
    
    # Parse command line arguments
    domain = sys.argv[1] if len(sys.argv) > 1 else 'localhost'
    use_https = '--https' in sys.argv or domain != 'localhost'
    spa = '--spa' in sys.argv
    
    print(f"Deploying {'SPA' if spa else 'Static Site'}")
    print(f"Domain: {domain}")
    print(f"HTTPS: {'Enabled' if use_https else 'Disabled'}")
    print("-" * 60)
    
    success = deploy(domain=domain, use_https=use_https, spa=spa)
    
    if success:
        print("\n✓ Deployment complete!")
        if spa:
            print("\nNote: For SPA, make sure you have:")
            print("  - package.json with build script")
            print("  - Source code in the current directory")
        else:
            print("\nNote: Place your static files in the 'site/' directory")
        print("\nTo stop services:")
        print("  docker compose down")
    else:
        print("\n✗ Deployment failed!")
        sys.exit(1)
