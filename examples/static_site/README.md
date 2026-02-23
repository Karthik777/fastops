# Static Site Deployment Example

Deploy static websites and Single Page Applications (SPAs) with dockr.

## Features

- nginx-based static file serving
- Multi-stage builds for SPAs (React, Vue, Angular, etc.)
- Automatic HTTPS with Caddy
- Optimized caching and compression
- SPA routing support (fallback to index.html)

## Use Cases

1. **Simple Static Site**: HTML, CSS, JS files
2. **Single Page Application**: React, Vue, Svelte, Angular apps
3. **Documentation Sites**: MkDocs, Jekyll, Hugo output
4. **Landing Pages**: Marketing sites, portfolios

## Quick Start - Simple Static Site

### 1. Create Your Site

```bash
mkdir -p site
cat > site/index.html << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <title>My Site</title>
    <style>
        body { font-family: sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
        h1 { color: #333; }
    </style>
</head>
<body>
    <h1>Hello from dockr!</h1>
    <p>This static site is deployed with dockr.</p>
</body>
</html>
EOF
```

### 2. Deploy Locally

```bash
python deploy.py localhost
# Site available at http://localhost:8080
```

### 3. Deploy to Production with HTTPS

```bash
export CLOUDFLARE_API_TOKEN=your_token
python deploy.py example.com --https
# Site available at https://example.com
```

## Quick Start - Single Page Application

### 1. For React App

```bash
# In your React app directory
npx create-react-app my-app
cd my-app

# Copy the deploy script
cp ../examples/static_site/deploy.py .

# Deploy
python deploy.py localhost --spa
```

### 2. For Vue App

```bash
# In your Vue app directory
npm create vue@latest my-app
cd my-app
npm install

# Copy the deploy script
cp ../examples/static_site/deploy.py .

# Deploy
python deploy.py localhost --spa
```

### 3. For Production

```bash
export CLOUDFLARE_API_TOKEN=your_token
python deploy.py example.com --https --spa
```

## nginx Configuration

The generated `nginx.conf` includes:

- **Gzip compression** for text files
- **Static asset caching** (1 year for images, fonts, etc.)
- **SPA routing** support (fallback to index.html)
- **MIME type** handling

### Custom nginx Configuration

Create your own `nginx.conf`:

```nginx
events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    
    # Enable compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript;
    
    server {
        listen 80;
        root /usr/share/nginx/html;
        index index.html;
        
        # Your custom rules here
        location /api {
            proxy_pass http://backend:8000;
        }
        
        # SPA routing
        location / {
            try_files $uri $uri/ /index.html;
        }
    }
}
```

## Directory Structure

### For Static Sites

```
static_site/
├── deploy.py
├── site/
│   ├── index.html
│   ├── about.html
│   ├── css/
│   │   └── style.css
│   ├── js/
│   │   └── script.js
│   └── images/
│       └── logo.png
└── nginx.conf (optional)
```

### For SPAs

```
my-spa/
├── deploy.py
├── package.json
├── src/
│   ├── App.js
│   ├── index.js
│   └── ...
├── public/
│   └── index.html
└── nginx.conf (optional)
```

## Advanced: API Proxy

To proxy API requests to a backend:

```python
# In deploy.py, modify the compose configuration:

compose = compose.svc('web',
    build='.',
    networks=['web', 'backend']
)

# Add backend service
compose = compose.svc('api',
    image='your-api-image',
    networks=['backend']
)

compose = compose.network('backend')
```

Then in `nginx.conf`:

```nginx
location /api {
    proxy_pass http://api:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

## Advanced: Multiple Sites

To host multiple sites on different domains:

```python
from dockr.compose import Compose
from pathlib import Path

# Create custom Caddyfile
caddy_conf = """
site1.example.com {
    reverse_proxy web1:80
}

site2.example.com {
    reverse_proxy web2:80
}

blog.example.com {
    reverse_proxy blog:80
}
"""

Path('Caddyfile').write_text(caddy_conf)

dc = (Compose()
    .svc('web1', build='./site1', networks=['web'])
    .svc('web2', build='./site2', networks=['web'])
    .svc('blog', build='./blog', networks=['web'])
    .svc('caddy',
         image='caddy:2',
         ports=['80:80', '443:443'],
         volumes={
             './Caddyfile': '/etc/caddy/Caddyfile',
             'caddy_data': '/data'
         },
         networks=['web'])
    .network('web')
    .volume('caddy_data')
)
```

## Performance Tips

### 1. Asset Optimization

Optimize images before deploying:

```bash
# Install optimization tools
apt-get install optipng jpegoptim

# Optimize images
find site/images -name "*.png" -exec optipng -o5 {} \;
find site/images -name "*.jpg" -exec jpegoptim --strip-all {} \;
```

### 2. Enable Brotli Compression

Use nginx with Brotli support:

```python
df = (Dockerfile()
    .from_('nginx:alpine')
    .run('apk add --no-cache nginx-mod-http-brotli')
    .copy('site/', '/usr/share/nginx/html/')
    # ... rest of dockerfile
)
```

### 3. CDN Integration

For CloudFlare CDN, enable in Caddy:

```python
compose = compose.svc('caddy', **caddy(
    domain='example.com',
    app='web',
    port=80,
    dns='cloudflare',
    cloudflared=True  # Enable CloudFlare tunnel
))
```

## Testing

```bash
# Test locally
curl http://localhost:8080

# Test with headers
curl -I http://localhost:8080

# Test compression
curl -H "Accept-Encoding: gzip" http://localhost:8080 -I

# Load test (requires apache bench)
ab -n 1000 -c 10 http://localhost:8080/
```

## Management

```bash
# View logs
docker compose logs -f web

# Restart web server
docker compose restart web

# Update site (for static sites)
# 1. Update files in site/
# 2. Rebuild and restart
docker compose build web
docker compose up -d web

# Stop everything
docker compose down
```

## Troubleshooting

### Issue: 404 errors on SPA routes

**Solution**: Make sure nginx.conf has the SPA fallback:
```nginx
location / {
    try_files $uri $uri/ /index.html;
}
```

### Issue: Static assets not loading

**Solution**: Check MIME types in nginx.conf:
```nginx
http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
}
```

### Issue: HTTPS not working

**Solution**: Verify DNS is pointed to your server and CloudFlare token is set:
```bash
export CLOUDFLARE_API_TOKEN=your_token
python deploy.py example.com --https
```
