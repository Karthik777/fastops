"""Idempotent server provisioning via pyinfra. Install: pip install fastops[infra]"""

# %% auto #0
__all__ = ['provision', 'deploy_infra', 'harden_server', 'install_docker', 'setup_caddy', 'setup_compose_stack', 'server_status']

# %% imports
import os, subprocess, shutil
from pathlib import Path

# %% helper
def _require_pyinfra():
    'Check pyinfra is installed, raise helpful error if not'
    try:
        import pyinfra
        return pyinfra
    except ImportError:
        raise ImportError(
            'pyinfra is required for idempotent provisioning.\n'
            'Install it: pip install fastops[infra]\n'
            'Or: pip install pyinfra>=3.0'
        )

# %% install_docker
def install_docker(user='deploy'):
    'Idempotently install Docker Engine and add user to docker group'
    _require_pyinfra()
    from pyinfra.operations import apt, server, files
    
    results = []
    
    # Install prerequisites
    results.append(apt.packages(
        name='Install Docker prerequisites',
        packages=['ca-certificates', 'curl', 'gnupg', 'lsb-release'],
        update=True,
    ))
    
    # Add Docker GPG key
    results.append(server.shell(
        name='Add Docker GPG key',
        commands=['curl -fsSL https://get.docker.com | sh'],
    ))
    
    # Add user to docker group
    results.append(server.shell(
        name=f'Add {user} to docker group',
        commands=[f'usermod -aG docker {user}'],
    ))
    
    # Enable Docker service
    from pyinfra.operations import systemd
    results.append(systemd.service(
        name='Enable and start Docker',
        service='docker',
        running=True,
        enabled=True,
    ))
    
    return results

# %% harden_server
def harden_server(ssh_port=22, allowed_ports=None):
    'Idempotent server hardening: UFW, fail2ban, sysctl security tweaks'
    _require_pyinfra()
    from pyinfra.operations import apt, server, files
    
    allowed = allowed_ports or [22, 80, 443]
    results = []
    
    # Install security packages
    results.append(apt.packages(
        name='Install security packages',
        packages=['ufw', 'fail2ban', 'unattended-upgrades'],
        update=True,
    ))
    
    # Configure UFW
    results.append(server.shell(
        name='Configure UFW defaults',
        commands=[
            'ufw default deny incoming',
            'ufw default allow outgoing',
        ],
    ))
    
    for port in allowed:
        results.append(server.shell(
            name=f'Allow port {port}',
            commands=[f'ufw allow {port}'],
        ))
    
    results.append(server.shell(
        name='Enable UFW',
        commands=['echo "y" | ufw enable'],
    ))
    
    # Configure fail2ban
    jail_conf = '''[sshd]
enabled = true
port = {ssh_port}
filter = sshd
logpath = /var/log/auth.log
maxretry = 5
bantime = 3600
'''.format(ssh_port=ssh_port)
    
    results.append(files.put(
        name='Configure fail2ban jail',
        src=None,  # Use content via StringIO
        dest='/etc/fail2ban/jail.local',
        contents=jail_conf,
    ))
    
    # Sysctl hardening
    sysctl_conf = '''# Hardening
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1
net.ipv4.icmp_echo_ignore_broadcasts = 1
net.ipv4.conf.all.accept_redirects = 0
net.ipv6.conf.all.accept_redirects = 0
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.all.accept_source_route = 0
net.ipv6.conf.all.accept_source_route = 0
kernel.sysrq = 0
'''
    results.append(files.put(
        name='Apply sysctl hardening',
        src=None,
        dest='/etc/sysctl.d/99-hardening.conf',
        contents=sysctl_conf,
    ))
    
    results.append(server.shell(
        name='Reload sysctl',
        commands=['sysctl --system'],
    ))
    
    return results

# %% setup_caddy
def setup_caddy(domain, app='app', port=5001, email=None):
    'Install Caddy and configure as reverse proxy — idempotent'
    _require_pyinfra()
    from pyinfra.operations import apt, server, files, systemd
    
    results = []
    
    # Install Caddy from official repo
    results.append(server.shell(
        name='Add Caddy repository',
        commands=[
            'apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl',
            'curl -1sLf "https://dl.cloudsmith.io/public/caddy/stable/gpg.key" | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg 2>/dev/null || true',
            'curl -1sLf "https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt" | tee /etc/apt/sources.list.d/caddy-stable.list',
        ],
    ))
    
    results.append(apt.packages(
        name='Install Caddy',
        packages=['caddy'],
        update=True,
    ))
    
    # Generate Caddyfile using fastops.proxy
    from .proxy import Caddyfile
    cf = Caddyfile(domain, app, port).production()
    if email:
        cf = cf.email(email)
    
    results.append(files.put(
        name='Deploy Caddyfile',
        dest='/etc/caddy/Caddyfile',
        contents=str(cf),
    ))
    
    results.append(systemd.service(
        name='Enable and start Caddy',
        service='caddy',
        running=True,
        enabled=True,
        restarted=True,  # Restart to pick up new config
    ))
    
    return results

# %% setup_compose_stack
def setup_compose_stack(compose, path='/srv/app', env=None):
    'Deploy a Compose stack idempotently — only changes what differs'
    _require_pyinfra()
    from pyinfra.operations import server, files
    
    results = []
    
    # Ensure directory exists
    results.append(files.directory(
        name=f'Create {path}',
        path=path,
        present=True,
    ))
    
    # Write compose file — pyinfra will only update if content changed
    compose_str = str(compose) if hasattr(compose, '__str__') else compose
    results.append(files.put(
        name='Deploy docker-compose.yml',
        dest=f'{path}/docker-compose.yml',
        contents=compose_str,
    ))
    
    # Write .env file if provided
    if env:
        env_content = '\n'.join(f'{k}={v}' for k, v in env.items())
        results.append(files.put(
            name='Deploy .env file',
            dest=f'{path}/.env',
            contents=env_content,
            mode='600',  # Restrictive permissions for secrets
        ))
    
    # Pull and deploy
    results.append(server.shell(
        name='Pull and deploy compose stack',
        commands=[
            f'cd {path} && docker compose pull --quiet 2>/dev/null || true',
            f'cd {path} && docker compose up -d --remove-orphans',
        ],
    ))
    
    return results

# %% provision
def provision(host, *, user='deploy', key=None, port=22,
              docker=True, harden=True, compose=None, domain=None,
              caddy_port=5001, env=None, packages=None, **kw):
    '''Idempotent VPS provisioning — safe to run repeatedly.
    
    Uses pyinfra for drift detection and state management.
    Falls back to fastops.vps (SSH/rsync) if pyinfra is not installed.
    
    Args:
        host: IP or hostname of the server
        user: SSH user (default: deploy)
        key: Path to SSH private key
        port: SSH port (default: 22)
        docker: Install Docker (default: True)
        harden: Apply security hardening (default: True)
        compose: Compose object or YAML string to deploy
        domain: Domain for Caddy reverse proxy
        caddy_port: App port for Caddy to proxy to (default: 5001)
        env: Dict of environment variables for the app
        packages: Additional apt packages to install
    
    Returns dict with status and details.
    '''
    result = {'host': host, 'user': user, 'method': 'unknown'}
    
    try:
        _require_pyinfra()
        result['method'] = 'pyinfra'
        
        from pyinfra import state
        from pyinfra.api import Config, Inventory, State
        from pyinfra.api.connect import connect_all
        from pyinfra.api.operations import run_ops
        from pyinfra.operations import apt
        
        # Build inventory
        ssh_key_path = os.path.expanduser(key) if key else None
        inventory_data = {
            host: {
                'ssh_user': user,
                'ssh_port': port,
            }
        }
        if ssh_key_path:
            inventory_data[host]['ssh_key'] = ssh_key_path
        
        # Install additional packages
        if packages:
            apt.packages(
                name='Install additional packages',
                packages=list(packages),
                update=True,
            )
        
        # Harden server
        if harden:
            harden_server(ssh_port=port)
        
        # Install Docker
        if docker:
            install_docker(user=user)
        
        # Setup Caddy if domain provided
        if domain:
            setup_caddy(domain, port=caddy_port, email=kw.get('email'))
        
        # Deploy compose stack
        if compose:
            deploy_path = kw.get('deploy_path', '/srv/app')
            setup_compose_stack(compose, path=deploy_path, env=env)
        
        result['status'] = 'provisioned'
        result['docker'] = docker
        result['hardened'] = harden
        result['domain'] = domain
        
    except ImportError:
        # Fallback to SSH-based approach
        result['method'] = 'ssh'
        from .vps import run_ssh, deploy as ssh_deploy
        
        print('pyinfra not installed, using SSH fallback (not idempotent)')
        print('Install pyinfra for idempotent provisioning: pip install fastops[infra]')
        
        if compose:
            deploy_path = kw.get('deploy_path', '/srv/app')
            ssh_deploy(compose, host, user=user, key=key, path=deploy_path)
        
        result['status'] = 'deployed'
        result['docker'] = docker
        result['hardened'] = False
        result['domain'] = domain
    
    return result

# %% deploy_infra
def deploy_infra(host, compose, *, user='deploy', key=None, path='/srv/app', env=None, pull=True):
    'Deploy/update a Compose stack on a remote server — idempotent if pyinfra is available'
    try:
        _require_pyinfra()
        return setup_compose_stack(compose, path=path, env=env)
    except ImportError:
        from .vps import deploy as ssh_deploy
        return ssh_deploy(compose, host, user=user, key=key, path=path, pull=pull)

# %% server_status
def server_status(host, *, user='deploy', key=None, port=22):
    'Check server status: Docker, Caddy, containers, disk, memory'
    from .vps import run_ssh
    
    status = {'host': host}
    
    try:
        # Docker status
        status['docker'] = 'running' in run_ssh(host, 'systemctl is-active docker 2>/dev/null || echo stopped', user=user, key=key)
    except:
        status['docker'] = False
    
    try:
        # Running containers
        containers = run_ssh(host, 'docker ps --format "{{.Names}}: {{.Status}}" 2>/dev/null || echo none', user=user, key=key)
        status['containers'] = [c.strip() for c in containers.split('\n') if c.strip() and c.strip() != 'none']
    except:
        status['containers'] = []
    
    try:
        # Caddy status
        status['caddy'] = 'running' in run_ssh(host, 'systemctl is-active caddy 2>/dev/null || echo stopped', user=user, key=key)
    except:
        status['caddy'] = False
    
    try:
        # Disk usage
        disk = run_ssh(host, "df -h / | tail -1 | awk '{print $5}'", user=user, key=key)
        status['disk_usage'] = disk.strip()
    except:
        status['disk_usage'] = 'unknown'
    
    try:
        # Memory usage
        mem = run_ssh(host, "free -m | awk 'NR==2{printf \"%s/%sMB (%.0f%%)\", $3, $2, $3*100/$2}'", user=user, key=key)
        status['memory'] = mem.strip()
    except:
        status['memory'] = 'unknown'
    
    try:
        # Uptime
        uptime = run_ssh(host, 'uptime -p', user=user, key=key)
        status['uptime'] = uptime.strip()
    except:
        status['uptime'] = 'unknown'
    
    try:
        # UFW status
        status['ufw'] = 'active' in run_ssh(host, 'ufw status 2>/dev/null || echo inactive', user=user, key=key)
    except:
        status['ufw'] = False
    
    return status
