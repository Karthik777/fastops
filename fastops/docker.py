"""Docker primitives: Dockerfile builder, CLI wrappers, Compose, Caddy, and app templates"""

__all__ = [
    # core
    'Dockerfile', 'Cli', 'calldocker', 'Docker', 'dk',
    'test', 'run', 'containers', 'images', 'stop', 'logs', 'rm', 'rmi',
    # compose
    'SWAG_MODS', 'dict2str', 'service', 'DockerCompose', 'Compose', 'swag_conf', 'swag', 'appfile',
    # caddy
    'caddyfile', 'caddy', 'cloudflared_svc', 'crowdsec',
    # apps
    'python_app', 'fasthtml_app', 'fastapi_react', 'go_app', 'rust_app',
]

import os, re, json, subprocess
import yaml
from pathlib import Path
from fastcore.all import listify, joins, is_listy, L, patch, concat, bind, merge, filter_values

# ── Dockerfile instruction builders ───────────────────────────────────────────

def _build_flags(*a, short=True, **kw):
    'Build CLI flag list from args/kwargs'
    k2f = lambda k: f'--{k.rstrip("_").replace("_","-")}'
    flags = list(a)
    if short:
        flags += concat([f'-{k}', str(v)] for k,v in kw.items() if len(k) == 1 and v not in (True, False, None))
        flags += [f'-{k}' for k,v in kw.items() if len(k) == 1 and v is True]
        kw = {k: v for k,v in kw.items() if len(k) > 1}
    flags += [f'{k2f(k)}={v}' for k,v in kw.items() if v not in (True, False, None)]
    flags += [k2f(k) for k,v in kw.items() if v is True]
    return flags

def _i(kw, v):    return f'{kw} {v}'
def _from(image, tag=None, as_=None): return _i('FROM', f'{image}{f":{tag}" if tag else ""}{f" AS {as_}" if as_ else ""}')
def _run(cmd):   return _i('RUN', joins(' && ', listify(cmd)))
def _apt_install(*pkgs, y=False): return _run(['apt-get update', f'apt-get install {"-y " if y else ""}{" ".join(pkgs)}'])
def _cmd(cmd):   return _i('CMD', json.dumps(cmd) if is_listy(cmd) else cmd)
def _copy(src, dst, from_=None, link=False): return _i('COPY', ' '.join([*_build_flags(short=False, link=link, from_=from_), src, dst]))
def _add(src, dst):       return _i('ADD', f'{src} {dst}')
def _workdir(path):       return _i('WORKDIR', path)
def _env(k, v=None):      return _i('ENV', f'{k}{"=" + str(v) if v else ""}')
def _expose(port):         return _i('EXPOSE', str(port))
def _entrypoint(cmd):      return _i('ENTRYPOINT', json.dumps(cmd) if is_listy(cmd) else cmd)
def _arg(nm, def_=None):   return _i('ARG', f'{nm}{"=" + str(def_) if def_ else ""}')
def _label(**kw):          return _i('LABEL', joins(' ', (f'{k}="{v}"' for k,v in kw.items())))
def _user(u):              return _i('USER', u)
def _volume(path):         return _i('VOLUME', json.dumps(path) if is_listy(path) else path)
def _shell(cmd):           return _i('SHELL', json.dumps(cmd))
def _stopsig(sig):         return _i('STOPSIGNAL', sig)
def _onbuild(ins):         return _i('ONBUILD', str(ins))

def _healthcheck(cmd, i=None, t=None, r=None, sp=None):
    opts = joins(' ', _build_flags(short=False, interval=i, timeout=t, retries=r, start_period=sp))
    return _i('HEALTHCHECK', f'{opts} CMD {json.dumps(cmd) if is_listy(cmd) else cmd}'.strip())

def _parse(path_or_str):
    t = Path(path_or_str).read_text() if isinstance(path_or_str, Path) else path_or_str
    return L.splitlines(re.sub(r'\\\n\s*', '', t)).filter(lambda l: l.strip() and not l.strip().startswith('#'))

# ── Dockerfile ─────────────────────────────────────────────────────────────────

class Dockerfile(L):
    'Fluent builder for Dockerfiles'
    def _new(self, items, **kw): return type(self)(items, use_list=None, **kw)
    def _add(self, i): return self._new(self.items + [i])
    @classmethod
    def load(cls, path=Path('Dockerfile')): return cls(_parse(Path(path)))
    def from_(self, base, tag=None, as_=None): return self._add(_from(base, tag, as_))
    def run(self, cmd):                        return self._add(_run(cmd))
    def cmd(self, cmd):                        return self._add(_cmd(cmd))
    def copy(self, src, dst, from_=None, link=False): return self._add(_copy(src, dst, from_, link))
    def add(self, src, dst):                   return self._add(_add(src, dst))
    def workdir(self, path='/app'):            return self._add(_workdir(path))
    def env(self, key, value=None):            return self._add(_env(key, value))
    def expose(self, port):                    return self._add(_expose(port))
    def entrypoint(self, cmd):                 return self._add(_entrypoint(cmd))
    def arg(self, name, default=None):         return self._add(_arg(name, default))
    def label(self, **kwargs):                 return self._add(_label(**kwargs))
    def user(self, user):                      return self._add(_user(user))
    def volume(self, path):                    return self._add(_volume(path))
    def shell(self, cmd):                      return self._add(_shell(cmd))
    def healthcheck(self, cmd, **kw):          return self._add(_healthcheck(cmd, **kw))
    def stopsignal(self, signal):              return self._add(_stopsig(signal))
    def onbuild(self, instruction):            return self._add(_onbuild(instruction))
    def apt_install(self, *pkgs, y=False):     return self._add(_apt_install(*pkgs, y=y))
    def run_mount(self, cmd, type='cache', target=None, **kw):
        'RUN --mount=... for build caches (uv, pip, apt) and secrets'
        opts = f'type={type}' + (f',target={target}' if target else '') + ''.join(f',{k.replace("_","-")}={v}' for k,v in kw.items())
        return self._add(f'RUN --mount={opts} {cmd}')
    def __call__(self, kw, *args, **kwargs):
        return self._add(f'{kw} {" ".join([*_build_flags(short=False, **kwargs), *map(str, args)])}')
    def __getattr__(self, nm):
        if nm.startswith('_'): raise AttributeError(nm)
        return bind(self, nm.upper().rstrip('_'))
    def __str__(self):  return chr(10).join(self)
    def __repr__(self): return str(self)
    def save(self, path=Path('Dockerfile')): Path(path).mk_write(str(self)); return path

# ── Docker CLI ─────────────────────────────────────────────────────────────────

class Cli:
    'Base: __call__ builds flags → _run(), __getattr__ dispatches subcommands'
    def __call__(self, cmd, *a, **kw): return self._run(cmd, *_build_flags(*a, **kw))
    def _run(self, cmd, *a): raise NotImplementedError
    def __getattr__(self, nm):
        if nm.startswith('_'): raise AttributeError(nm)
        return bind(self, nm.replace('_', '-'))

def _clean_cfg():
    'Docker config dir with credential helpers stripped'
    src = Path(os.environ.get('DOCKER_CONFIG', Path.home()/'.docker'))
    dst = Path.home()/'.fastops'/'config'; cfgf = dst/'config.json'
    if cfgf.exists(): return str(dst)
    cfg = src.joinpath('config.json').read_json() if (src/'config.json').exists() else {}
    cfg.pop('credsStore', None); cfg.pop('credHelpers', None)
    cfgf.write_json(cfg)
    ctx_src, ctx_dst = src/'contexts', dst/'contexts'
    if ctx_src.exists() and not ctx_dst.exists(): ctx_dst.symlink_to(ctx_src)
    return str(dst)

def calldocker(*args, no_creds=False):
    'Run docker CLI command. Respects DOCKR_RUNTIME env var.'
    rt = os.environ.get('DOCKR_RUNTIME', 'docker')
    pre = ('--config', _clean_cfg()) if no_creds and rt == 'docker' else ()
    return subprocess.run((rt,) + pre + args, capture_output=True, text=True, check=True).stdout.strip()

class Docker(Cli):
    'Wrap docker CLI: __getattr__ dispatches subcommands, kwargs become flags'
    def __init__(self, no_creds=False): self.no_creds = no_creds
    def _run(self, cmd, *a): return calldocker(cmd, *a, no_creds=self.no_creds)

dk = Docker()

@patch
def build(df:Dockerfile, tag=None, path='.', rm=True, no_creds=False):
    'Build image from Dockerfile'
    df.save(Path(path)/'Dockerfile'); Docker(no_creds=no_creds).build(str(path), t=tag, rm=rm); return tag

def test(img_or_tag, cmd):
    'Run cmd in image, return True if exit 0'
    try: dk.run('--rm', str(img_or_tag), *listify(cmd)); return True
    except Exception: return False

def run(img_or_tag, detach=False, ports=None, name=None, remove=False, command=None):
    'Run a container'
    args = (['-d'] if detach else []) + (['--rm'] if remove else []) + (['--name', name] if name else [])
    for cp, hp in (ports or {}).items(): args += ['-p', f'{hp}:{cp.split("/")[0]}']
    return dk('run', *args, str(img_or_tag), *listify(command or []))

def containers(all=False): return dk.ps(format='{{.Names}}', a=all).splitlines()
def images():              return dk.images(format='{{.Repository}}:{{.Tag}}').splitlines()
def stop(name_or_id):      dk.stop(name_or_id)
def logs(name_or_id, n=10): return dk.logs(name_or_id, tail=n)
def rm(name_or_id, force=False):  dk.rm(name_or_id, f=force)
def rmi(image, force=False):      dk.rmi(image, f=force)

# ── Docker Compose ─────────────────────────────────────────────────────────────

def dict2str(d, sep=':'): return [f'{k}{sep}{v}' for k,v in d.items()] if isinstance(d, dict) else d

def service(image=None, build=None, ports=None, env=None, volumes=None, depends_on=None, command=None, **kw):
    'Create a docker-compose service dict'
    if isinstance(build, Dockerfile): build = '.'
    return filter_values(dict(image=image, command=command, depends_on=depends_on,
        ports=dict2str(ports), build=build, environment=dict2str(env, '='),
        volumes=dict2str(volumes)), lambda v: v is not None) | kw

class DockerCompose(Cli):
    'Wrap docker compose CLI'
    def __init__(self, path='docker-compose.yml'): self.path = path
    def _run(self, cmd, *args): return calldocker('compose', '-f', self.path, cmd, *args)

class Compose(L):
    'Fluent builder for docker-compose.yml files'
    def _add(self, item): return self._new(self.items + [item])
    def svc(self, name, **kw):    return self._add(('svc', name, service(**kw)))
    def network(self, name, **kw): return self._add(('net', name, kw or None))
    def volume(self, name, **kw):  return self._add(('vol', name, kw or None))

    @classmethod
    def load(cls, path='docker-compose.yml'):
        d = yaml.safe_load(Path(path).read_text())
        it  = [('svc', n, c) for n,c in (d.get('services') or {}).items()]
        it += [('net', n, c) for n,c in (d.get('networks') or {}).items()]
        it += [('vol', n, c) for n,c in (d.get('volumes')  or {}).items()]
        return cls(it)

    def to_dict(self):
        d = {'services': {n: c for t,n,c in self if t == 'svc'}}
        nets = {n: c for t,n,c in self if t == 'net'}
        vols = {n: c for t,n,c in self if t == 'vol'}
        if nets: d['networks'] = nets
        if vols: d['volumes']  = vols
        return d

    def __str__(self):  return yaml.dump(self.to_dict(), default_flow_style=False, sort_keys=False)
    def __repr__(self): return str(self)
    def save(self, path='docker-compose.yml'): Path(path).write_text(str(self))
    def up(self, detach=True, path='docker-compose.yml', **kw):
        self.save(path); return DockerCompose(path).up(d=detach, **kw)
    def down(self, path='docker-compose.yml', **kw):
        self.save(path); return DockerCompose(path).down(**kw)

# ── SWAG reverse proxy ─────────────────────────────────────────────────────────

SWAG_MODS = {
    'auto-proxy':         'linuxserver/mods:swag-auto-proxy',
    'docker':             'linuxserver/mods:universal-docker',
    'cloudflare-real-ip': 'linuxserver/mods:swag-cloudflare-real-ip',
    'crowdsec':           'linuxserver/mods:swag-crowdsec',
    'dashboard':          'linuxserver/mods:swag-dashboard',
    'auto-reload':        'linuxserver/mods:swag-auto-reload',
    'maxmind':            'linuxserver/mods:swag-maxmind',
    'dbip':               'linuxserver/mods:swag-dbip',
}

def swag_conf(domain, port, app='app'):
    'SWAG nginx site-conf for reverse-proxying to app'
    return (f'server {{\n    listen 443 ssl;\n    server_name {domain};\n'
            f'    include /config/nginx/ssl.conf;\n    location / {{\n'
            f'        proxy_pass http://{app}:{port};\n        include /config/nginx/proxy.conf;\n    }}\n}}\n')

def swag(domain, app='app', port=None, conf_path='proxy.conf',
         validation='http', subdomains='wildcard', cloudflared=False, mods=None, **kw):
    'SWAG reverse-proxy service kwargs for Compose.svc()'
    if port: Path(conf_path).mk_write(swag_conf(domain, port, app))
    env = merge({'PUID': '1000', 'PGID': '1000', 'TZ': 'Etc/UTC',
                 'URL': domain, 'SUBDOMAINS': subdomains, 'VALIDATION': validation}, kw)
    mod_tags = [SWAG_MODS[m] for m in listify(mods) if m in SWAG_MODS]
    if cloudflared:
        mod_tags.append('linuxserver/mods:universal-cloudflared')
        env['CF_REMOTE_MANAGE_TOKEN'] = '${CF_TUNNEL_TOKEN}'
    if mod_tags: env['DOCKER_MODS'] = '|'.join(mod_tags)
    r = dict(image='lscr.io/linuxserver/swag', env=env,
        volumes={'swag_config': '/config', './proxy.conf': '/config/nginx/site-confs/proxy.conf'},
        networks=['web'], depends_on=[app], cap_add=['NET_ADMIN'], restart='unless-stopped')
    if not cloudflared: r['ports'] = {443: 443, 80: 80}
    return r

def appfile(port=5001, volume='/app/data', image='python:3.12-slim'):
    'Standard Python webapp Dockerfile'
    df = (Dockerfile().from_(image).workdir('/app')
          .copy('requirements.txt', '.').run('pip install --no-cache-dir -r requirements.txt').copy('.', '.'))
    if volume: df = df.run(f'mkdir -p {volume}')
    return df.expose(port).cmd(['python', 'main.py'])

# ── Caddy + CrowdSec + Cloudflare tunnel ───────────────────────────────────────

_CADDY_IMG = {
    (False, False): 'caddy:2',
    (True,  False): 'serfriz/caddy-crowdsec:latest',
    (False, True):  'serfriz/caddy-cloudflare:latest',
    (True,  True):  'ghcr.io/buildplan/csdp-caddy:latest',
}

def caddyfile(domain, app='app', port=5001, *,
              dns=None, email=None, crowdsec=False, cloudflared=False):
    'Minimal Caddyfile for reverse-proxying app:port from domain'
    g = []
    if email: g += [f'    email {email}']
    if dns:
        p, tenv = (dns, f'{dns.upper()}_API_TOKEN') if isinstance(dns, str) else dns
        g += [f'    acme_dns {p} {{${tenv}}}']
    if crowdsec: g += ['    crowdsec {', '        api_url http://crowdsec:8080',
                        '        api_key {$CROWDSEC_API_KEY}', '    }']
    s = (['    crowdsec'] if crowdsec else []) + [f'    reverse_proxy {app}:{port}']
    parts = (['{\n' + '\n'.join(g) + '\n}'] if g else []) + [f'{"http://" if cloudflared else ""}{domain} {{\n' + '\n'.join(s) + '\n}']
    return '\n\n'.join(parts) + '\n'

def caddy(domain, app='app', port=5001, *,
          dns=None, email=None, crowdsec=False, cloudflared=False, conf='Caddyfile', **kw):
    'Write Caddyfile and return Caddy service kwargs for Compose.svc()'
    Path(conf).write_text(caddyfile(domain, app, port, dns=dns, email=email,
                                    crowdsec=crowdsec, cloudflared=cloudflared))
    img = _CADDY_IMG.get((crowdsec, dns == 'cloudflare'), f'serfriz/caddy-{dns}:latest' if dns else 'caddy:2')
    env = {}
    if dns == 'cloudflare': env['CLOUDFLARE_API_TOKEN'] = '${CLOUDFLARE_API_TOKEN}'
    if dns == 'duckdns':    env['DUCKDNS_TOKEN']        = '${DUCKDNS_TOKEN}'
    if crowdsec:            env['CROWDSEC_API_KEY']      = '${CROWDSEC_API_KEY}'
    return dict(image=img, env=env or None,
        ports=None if cloudflared else ['80:80', '443:443', '443:443/udp'],
        volumes={f'./{conf}': '/etc/caddy/Caddyfile', 'caddy_data': '/data', 'caddy_config': '/config'},
        networks=['web'], depends_on=[app], restart='unless-stopped') | kw

def cloudflared_svc(token_env='CF_TUNNEL_TOKEN', **kw):
    'Cloudflare tunnel service kwargs for Compose.svc()'
    return dict(image='cloudflare/cloudflared:latest', command='tunnel --no-autoupdate run',
                env={'TUNNEL_TOKEN': f'${{{token_env}}}'}, restart='unless-stopped') | kw

def crowdsec(collections=None, bouncer_key_env='CROWDSEC_BOUNCER_KEY', **kw):
    'CrowdSec agent service kwargs for Compose.svc()'
    cols = ' '.join(listify(collections) or ['crowdsecurity/linux', 'crowdsecurity/caddy', 'crowdsecurity/http-cve'])
    return dict(image='crowdsecurity/crowdsec:latest',
        env={'COLLECTIONS': cols, 'BOUNCER_KEY_caddy': f'${{{bouncer_key_env}}}'},
        volumes={'crowdsec-db': '/var/lib/crowdsec/data', 'crowdsec-config': '/etc/crowdsec'},
        networks=['web'], restart='unless-stopped') | kw

# ── App templates ──────────────────────────────────────────────────────────────

def python_app(port=8000, cmd=None, image='python:3.12-slim', workdir='/app',
               pkgs=None, volumes=None, uv=True, healthcheck=None):
    'Single-stage Python app Dockerfile. uv=True uses uv for fast installs.'
    df = Dockerfile().from_(image).workdir(workdir)
    if pkgs: df = df.apt_install(*listify(pkgs), y=True).run('rm -rf /var/lib/apt/lists/*')
    if uv:
        df = (df.copy('/uv', '/usr/local/bin/uv', from_='ghcr.io/astral-sh/uv:latest')
                .copy('pyproject.toml', '.').copy('uv.lock', '.')
                .run_mount('uv sync --frozen --no-dev', target='/root/.cache/uv'))
    else: df = df.copy('requirements.txt', '.').run('pip install --no-cache-dir -r requirements.txt')
    df = df.copy('.', '.')
    for v in listify(volumes or []): df = df.run(f'mkdir -p {v}')
    if healthcheck: df = df.healthcheck(f'curl -f http://localhost:{port}{healthcheck}', i='30s', t='5s', r='3')
    _cmd = cmd or ['python', 'main.py']
    return df.expose(port).cmd(_cmd if isinstance(_cmd, list) else _cmd.split())

def fasthtml_app(port=5001, cmd=None, image='python:3.12-slim', pkgs=None, volumes=None, healthcheck=None):
    'FastHTML/FastAPI single-stage Dockerfile with uv'
    return python_app(port=port, cmd=cmd, image=image, pkgs=pkgs, volumes=volumes, uv=True, healthcheck=healthcheck)

def fastapi_react(port=8000, node_version='20', frontend_dir='frontend', build_dir='dist',
                  image='python:3.12-slim', pkgs=None, uv=True, healthcheck='/health'):
    'Two-stage Dockerfile: Node.js frontend build + Python/FastAPI backend'
    df = (Dockerfile()
        .from_(f'node:{node_version}-slim', as_='frontend').workdir('/build')
        .copy(f'{frontend_dir}/package*.json', '.').run('npm ci')
        .copy(frontend_dir, '.').run('npm run build')
        .from_(image).workdir('/app'))
    if pkgs: df = df.apt_install(*listify(pkgs), y=True).run('rm -rf /var/lib/apt/lists/*')
    if uv:
        df = (df.copy('/uv', '/usr/local/bin/uv', from_='ghcr.io/astral-sh/uv:latest')
                .copy('pyproject.toml', '.').copy('uv.lock', '.')
                .run_mount('uv sync --frozen --no-dev', target='/root/.cache/uv'))
    else: df = df.copy('requirements.txt', '.').run('pip install --no-cache-dir -r requirements.txt')
    df = df.copy('.', '.').copy(f'/build/{build_dir}', '/app/static', from_='frontend')
    if healthcheck: df = df.healthcheck(f'curl -f http://localhost:{port}{healthcheck}', i='30s', t='5s', r='3')
    return df.expose(port).cmd(['uvicorn', 'main:app', '--host', '0.0.0.0', f'--port={port}'])

def go_app(port=8080, go_version='1.22', binary='app', runtime='gcr.io/distroless/static', cmd=None, cgo=False):
    'Two-stage Go Dockerfile: compiler + go mod cache → distroless'
    df = (Dockerfile()
        .from_(f'golang:{go_version}-alpine', as_='builder').workdir('/src')
        .copy('go.mod', '.').copy('go.sum', '.')
        .run_mount('go mod download', target='/go/pkg/mod')
        .copy('.', '.').env('CGO_ENABLED', '0' if not cgo else '1')
        .run('go build -ldflags="-s -w" -o /app .')
        .from_(runtime).copy('/app', '/app', from_='builder').expose(port))
    return df.cmd(cmd or ['/app'])

def rust_app(port=8080, rust_version='1', binary='app', runtime='gcr.io/distroless/static', features=None, release=True):
    'Two-stage Rust Dockerfile: cargo build → distroless'
    build_cmd = 'cargo build --release' + (f' --features {features}' if features else '')
    df = (Dockerfile()
        .from_(f'rust:{rust_version}-slim-bookworm', as_='builder').workdir('/src')
        .copy('.', '.').run_mount(build_cmd, target='/usr/local/cargo/registry')
        .from_(runtime).copy(f'/src/target/release/{binary}', f'/{binary}', from_='builder').expose(port))
    return df.cmd([f'/{binary}'])
