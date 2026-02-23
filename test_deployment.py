#!/usr/bin/env python3
"""
Test script to verify dockr deployment capabilities

This script tests various dockr features to ensure they work correctly
for typical deployment scenarios.
"""

import sys
from pathlib import Path

# Add parent directory to path to import dockr
sys.path.insert(0, str(Path(__file__).parent))

def test_dockerfile_generation():
    """Test Dockerfile generation capabilities"""
    print("\n=== Testing Dockerfile Generation ===")
    
    from dockr.core import Dockerfile
    
    # Test basic Dockerfile
    df = (Dockerfile()
        .from_('python:3.12-slim')
        .workdir('/app')
        .copy('requirements.txt', '.')
        .run('pip install -r requirements.txt')
        .copy('.', '.')
        .expose(8000)
        .cmd(['uvicorn', 'main:app', '--host', '0.0.0.0'])
    )
    
    result = str(df)
    assert 'FROM python:3.12-slim' in result
    assert 'WORKDIR /app' in result
    assert 'EXPOSE 8000' in result
    assert 'CMD ["uvicorn", "main:app", "--host", "0.0.0.0"]' in result
    print("✓ Basic Dockerfile generation works")
    
    # Test multi-stage build
    df_multi = (Dockerfile()
        .from_('node:18', as_='builder')
        .workdir('/build')
        .copy('package.json', '.')
        .run('npm install')
        .copy('.', '.')
        .run('npm run build')
        .from_('nginx:alpine')
        .copy('/build/dist', '/usr/share/nginx/html', from_='builder')
    )
    
    result_multi = str(df_multi)
    assert 'FROM node:18 AS builder' in result_multi
    assert 'COPY --from=builder /build/dist /usr/share/nginx/html' in result_multi
    print("✓ Multi-stage Dockerfile generation works")
    
    # Test advanced features
    df_advanced = (Dockerfile()
        .from_('python:3.12-slim')
        .arg('VERSION', '1.0.0')
        .label(maintainer='admin@example.com', version='${VERSION}')
        .env('PYTHONUNBUFFERED', '1')
        .user('nobody')
        .healthcheck(['curl', '-f', 'http://localhost/health'], i='30s', t='10s', r=3)
        .volume('/data')
    )
    
    result_advanced = str(df_advanced)
    assert 'ARG VERSION=1.0.0' in result_advanced
    assert 'LABEL' in result_advanced
    assert 'ENV PYTHONUNBUFFERED=1' in result_advanced
    assert 'USER nobody' in result_advanced
    assert 'HEALTHCHECK' in result_advanced
    assert 'VOLUME' in result_advanced
    print("✓ Advanced Dockerfile features work")
    
    return True

def test_compose_generation():
    """Test docker-compose generation capabilities"""
    print("\n=== Testing Docker Compose Generation ===")
    
    from dockr.compose import Compose
    
    # Test basic compose
    dc = (Compose()
        .svc('web', image='nginx:alpine', ports={80: 80})
        .svc('redis', image='redis:7-alpine')
    )
    
    result = dc.to_dict()
    assert 'services' in result
    assert 'web' in result['services']
    assert 'redis' in result['services']
    assert result['services']['web']['ports'] == ['80:80']
    print("✓ Basic Compose generation works")
    
    # Test with database and volumes
    dc_db = (Compose()
        .svc('app', build='.', depends_on=['db'])
        .svc('db',
             image='postgres:15-alpine',
             env={'POSTGRES_PASSWORD': 'secret'},
             volumes={'pgdata': '/var/lib/postgresql/data'})
        .network('backend')
        .volume('pgdata')
    )
    
    result_db = dc_db.to_dict()
    assert 'db' in result_db['services']
    assert 'networks' in result_db
    assert 'volumes' in result_db
    assert result_db['services']['db']['environment'] == ['POSTGRES_PASSWORD=secret']
    assert result_db['services']['db']['volumes'] == ['pgdata:/var/lib/postgresql/data']
    assert result_db['services']['app']['depends_on'] == ['db']
    print("✓ Compose with database and volumes works")
    
    return True

def test_caddy_integration():
    """Test Caddy reverse proxy integration"""
    print("\n=== Testing Caddy Integration ===")
    
    from dockr.caddy import caddyfile, caddy
    
    # Test Caddyfile generation
    cf = caddyfile('example.com', app='web', port=8000)
    assert 'example.com' in cf
    assert 'reverse_proxy web:8000' in cf
    print("✓ Basic Caddyfile generation works")
    
    # Test with DNS
    cf_dns = caddyfile('example.com', app='api', port=9000, 
                       dns='cloudflare', email='admin@example.com')
    assert 'acme_dns cloudflare' in cf_dns
    assert 'email admin@example.com' in cf_dns
    print("✓ Caddyfile with DNS challenge works")
    
    # Test Caddy service configuration
    caddy_svc = caddy(domain='example.com', app='web', port=8000)
    assert caddy_svc['image'] == 'caddy:2'
    assert 'volumes' in caddy_svc
    assert 'networks' in caddy_svc
    assert caddy_svc['depends_on'] == ['web']
    print("✓ Caddy service configuration works")
    
    # Test with Cloudflare
    caddy_cf = caddy(domain='example.com', app='web', port=8000,
                     dns='cloudflare')
    assert 'cloudflare' in caddy_cf['image'].lower()
    assert 'env' in caddy_cf
    print("✓ Caddy with Cloudflare DNS works")
    
    return True

def test_swag_integration():
    """Test SWAG reverse proxy integration"""
    print("\n=== Testing SWAG Integration ===")
    
    from dockr.compose import swag, swag_conf
    
    # Test SWAG config generation
    conf = swag_conf('example.com', port=8000, app='web')
    assert 'server_name example.com' in conf
    assert 'proxy_pass http://web:8000' in conf
    print("✓ SWAG config generation works")
    
    # Test SWAG service configuration
    swag_svc = swag(domain='example.com', app='web', port=8000)
    assert swag_svc['image'] == 'lscr.io/linuxserver/swag'
    assert 'env' in swag_svc  # swag() returns raw dict with 'env', not 'environment'
    assert 'volumes' in swag_svc
    assert swag_svc['depends_on'] == ['web']
    print("✓ SWAG service configuration works")
    
    # Test with mods
    swag_mods = swag(domain='example.com', app='web', port=8000,
                     mods=['auto-proxy', 'dashboard'])
    env_dict = swag_mods['env']  # swag() returns dict with 'env' as a dict
    assert 'DOCKER_MODS' in env_dict
    assert 'auto-proxy' in env_dict['DOCKER_MODS']
    print("✓ SWAG with mods works")
    
    return True

def test_helper_functions():
    """Test core helper functions"""
    print("\n=== Testing Helper Functions ===")
    
    from dockr.core import _from, _run, _cmd, _copy, _env, _expose
    from dockr.compose import dict2str, service
    
    # Test Dockerfile helpers
    assert _from('python', '3.12') == 'FROM python:3.12'
    assert _from('node', as_='builder') == 'FROM node AS builder'
    assert _run(['apt-get update', 'apt-get install curl']) == 'RUN apt-get update && apt-get install curl'
    assert _cmd(['python', 'app.py']) == 'CMD ["python", "app.py"]'
    assert _copy('src', 'dst') == 'COPY src dst'
    assert _env('KEY', 'value') == 'ENV KEY=value'
    assert _expose(8000) == 'EXPOSE 8000'
    print("✓ Dockerfile helper functions work")
    
    # Test Compose helpers
    assert dict2str({'80': 80}) == ['80:80']
    assert dict2str({'KEY': 'value'}, sep='=') == ['KEY=value']
    
    svc = service(image='nginx', ports={80: 80})
    assert svc['image'] == 'nginx'
    assert svc['ports'] == ['80:80']
    
    svc_full = service(
        image='postgres:15',
        env={'POSTGRES_PASSWORD': 'secret'},
        volumes={'data': '/var/lib/postgresql/data'},
        depends_on=['redis']
    )
    assert svc_full['environment'] == ['POSTGRES_PASSWORD=secret']
    assert svc_full['volumes'] == ['data:/var/lib/postgresql/data']
    assert svc_full['depends_on'] == ['redis']
    print("✓ Compose helper functions work")
    
    return True

def test_full_stack_example():
    """Test a complete full-stack deployment"""
    print("\n=== Testing Full Stack Example ===")
    
    from dockr.core import Dockerfile
    from dockr.compose import Compose
    from dockr.caddy import caddy
    
    # Create app Dockerfile
    app_df = (Dockerfile()
        .from_('python:3.12-slim')
        .workdir('/app')
        .copy('requirements.txt', '.')
        .run('pip install --no-cache-dir -r requirements.txt')
        .copy('.', '.')
        .expose(8000)
        .cmd(['uvicorn', 'main:app', '--host', '0.0.0.0', '--port', '8000'])
    )
    
    assert 'FROM python:3.12-slim' in str(app_df)
    print("✓ Application Dockerfile created")
    
    # Create full stack compose
    dc = (Compose()
        # Application
        .svc('app',
             build='.',
             env={'DATABASE_URL': 'postgresql://user:pass@db:5432/appdb'},
             depends_on=['db', 'redis'],
             networks=['web'])
        
        # Database
        .svc('db',
             image='postgres:15-alpine',
             env={'POSTGRES_USER': 'user', 'POSTGRES_PASSWORD': 'pass', 'POSTGRES_DB': 'appdb'},
             volumes={'pgdata': '/var/lib/postgresql/data'},
             networks=['web'])
        
        # Cache
        .svc('redis',
             image='redis:7-alpine',
             networks=['web'])
        
        # Reverse Proxy
        .svc('caddy', **caddy(
            domain='localhost',
            app='app',
            port=8000
        ))
        
        # Infrastructure
        .network('web')
        .volume('pgdata')
        .volume('caddy_data')
        .volume('caddy_config')
    )
    
    result = dc.to_dict()
    assert len(result['services']) == 4  # app, db, redis, caddy
    assert 'networks' in result
    assert 'volumes' in result
    assert 'web' in result['networks']
    print("✓ Full stack compose configuration created")
    
    # Verify YAML generation
    yaml_str = str(dc)
    assert 'services:' in yaml_str
    assert 'app:' in yaml_str
    assert 'db:' in yaml_str
    assert 'redis:' in yaml_str
    assert 'caddy:' in yaml_str
    print("✓ YAML generation works")
    
    return True

def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("dockr Deployment Capabilities Test Suite")
    print("=" * 60)
    
    tests = [
        ("Dockerfile Generation", test_dockerfile_generation),
        ("Compose Generation", test_compose_generation),
        ("Caddy Integration", test_caddy_integration),
        ("SWAG Integration", test_swag_integration),
        ("Helper Functions", test_helper_functions),
        ("Full Stack Example", test_full_stack_example),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"\n✓ {name}: PASSED")
        except Exception as e:
            failed += 1
            print(f"\n✗ {name}: FAILED")
            print(f"  Error: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    if failed > 0:
        print("\n⚠ Some tests failed. Check the output above for details.")
        return False
    else:
        print("\n✓ All tests passed! dockr is ready for deployment.")
        return True

if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
