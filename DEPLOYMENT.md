# SalonAI Workforce - Production Deployment Guide

## Pre-Deployment Checklist

- [ ] Environment variables configured (`.env.production`)
- [ ] Database URL points to production database
- [ ] SECRET_KEY changed to a secure random value
- [ ] CORS_ORIGINS updated with production domain
- [ ] API keys configured (Groq, Supabase, etc.)
- [ ] HTTPS/TLS certificates prepared
- [ ] Database backups configured
- [ ] Monitoring and logging setup
- [ ] Health checks verified

## Production Environment Variables

Create `.env.production` with:

```bash
# Application
ENVIRONMENT=production
DEBUG=false
HOST=0.0.0.0
PORT=8000

# Database - Use managed PostgreSQL service
DATABASE_URL=postgresql://user:password@prod-db.example.com:5432/salonai_db

# Security
SECRET_KEY=your-very-secure-random-key-here

# API Configuration
VITE_API_URL=https://api.yourdomain.com/api/v1
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# External Services
GROQ_API_KEY=your-production-key
SUPABASE_URL=your-production-supabase-url
SUPABASE_KEY=your-production-supabase-key

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Features
ENABLE_RAG=true
ENABLE_AGENTS=true
```

## Deployment Options

### Option 1: Docker Compose on VPS/EC2

```bash
# 1. Prepare server
ssh user@your-server.com
cd /opt/salonai-workforce

# 2. Clone repository
git clone https://github.com/yourusername/salonai-workforce.git .

# 3. Setup environment
cp .env.production .env

# 4. Build and deploy
docker-compose -f docker-compose.yml up -d

# 5. Verify deployment
curl https://api.yourdomain.com/health
```

### Option 2: Kubernetes Deployment

#### Prerequisites
- Kubernetes cluster (EKS, GKE, AKS, etc.)
- kubectl configured
- Docker images pushed to registry

#### Create Kubernetes manifests

**`k8s/namespace.yml`**
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: salonai
```

**`k8s/secrets.yml`**
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: salonai-secrets
  namespace: salonai
type: Opaque
stringData:
  DATABASE_URL: postgresql://user:password@postgres:5432/salonai_db
  SECRET_KEY: your-secure-key
  GROQ_API_KEY: your-groq-key
```

**`k8s/backend-deployment.yml`**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: salonai-backend
  namespace: salonai
spec:
  replicas: 3
  selector:
    matchLabels:
      app: salonai-backend
  template:
    metadata:
      labels:
        app: salonai-backend
    spec:
      containers:
      - name: backend
        image: your-registry/salonai-backend:latest
        ports:
        - containerPort: 8000
        envFrom:
        - secretRef:
            name: salonai-secrets
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
```

**`k8s/backend-service.yml`**
```yaml
apiVersion: v1
kind: Service
metadata:
  name: salonai-backend
  namespace: salonai
spec:
  type: LoadBalancer
  selector:
    app: salonai-backend
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
```

**Deploy to Kubernetes:**
```bash
kubectl apply -f k8s/

# Verify deployment
kubectl get pods -n salonai
kubectl logs -n salonai -f deployment/salonai-backend
```

### Option 3: Managed Services (Heroku, Railway, Fly.io)

#### Heroku Deployment

```bash
# 1. Install Heroku CLI
brew install heroku

# 2. Login
heroku login

# 3. Create app
heroku create salonai-workforce

# 4. Add PostgreSQL addon
heroku addons:create heroku-postgresql:standard-0 -a salonai-workforce

# 5. Configure environment
heroku config:set ENVIRONMENT=production -a salonai-workforce
heroku config:set SECRET_KEY=your-secure-key -a salonai-workforce

# 6. Deploy
git push heroku main

# 7. View logs
heroku logs --tail
```

#### Railway Deployment

```bash
# 1. Install Railway CLI
npm i -g @railway/cli

# 2. Login
railway login

# 3. Create project
railway init

# 4. Add PostgreSQL
railway add --plugin postgresql

# 5. Deploy
railway up

# 6. View deployment
railway logs
```

## Reverse Proxy Setup (Nginx)

Create `/etc/nginx/sites-available/salonai.conf`:

```nginx
# HTTP to HTTPS redirect
server {
    listen 80;
    server_name api.yourdomain.com yourdomain.com www.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

# HTTPS configuration
server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;

    # SSL certificates (use Let's Encrypt with certbot)
    ssl_certificate /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.yourdomain.com/privkey.pem;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Proxy to backend
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 300s;
    }
}

# Frontend
server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    root /var/www/salonai/frontend/dist;
    index index.html;

    # Gzip compression
    gzip on;
    gzip_types text/plain text/css text/javascript application/javascript;

    # Cache static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # SPA routing
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
}
```

Enable site:
```bash
sudo ln -s /etc/nginx/sites-available/salonai.conf /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## SSL/TLS Certificate (Let's Encrypt)

```bash
# Install certbot
sudo apt-get install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot certonly --nginx -d yourdomain.com -d api.yourdomain.com

# Auto-renewal
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer

# Verify renewal
sudo certbot renew --dry-run
```

## Database Setup (Production)

### PostgreSQL (Managed)

Use cloud-managed PostgreSQL:
- **AWS RDS**: https://aws.amazon.com/rds/postgresql/
- **Heroku PostgreSQL**: https://www.heroku.com/postgres
- **DigitalOcean Managed Databases**: https://www.digitalocean.com/products/managed-databases/
- **Azure Database for PostgreSQL**: https://azure.microsoft.com/services/postgresql/

### Database Migrations

```bash
# Run migrations
docker exec salonai_backend alembic upgrade head

# Create migration (when schema changes)
alembic revision --autogenerate -m "Add user table"
```

## Monitoring & Logging

### Application Logs

Configure log aggregation:
- **Datadog**: https://www.datadoghq.com/
- **New Relic**: https://newrelic.com/
- **CloudWatch**: AWS CloudWatch
- **ELK Stack**: Elasticsearch, Logstash, Kibana

### Health Monitoring

```bash
# Monitor health endpoint
curl -f https://api.yourdomain.com/health || echo "Service down!"

# Add to crontab for periodic checks
*/5 * * * * curl -f https://api.yourdomain.com/health || (echo "Service down" | mail -s "Alert" admin@example.com)
```

### Uptime Monitoring

Services:
- **UptimeRobot**: https://uptimerobot.com/
- **Pingdom**: https://www.pingdom.com/
- **Grafana Cloud**: https://grafana.com/

## Performance Optimization

### Database
```bash
# Analyze query performance
EXPLAIN ANALYZE SELECT * FROM users WHERE email = 'user@example.com';

# Add indexes for frequently queried fields
CREATE INDEX idx_user_email ON users(email);
CREATE INDEX idx_task_user_id ON tasks(user_id);
```

### Backend
```bash
# Use connection pooling
MAX_OVERFLOW=10
POOL_SIZE=5
POOL_RECYCLE=3600

# Cache responses
pip install redis fastapi-cache2
```

### Frontend
- Enable Gzip compression in Nginx
- Use CDN for static assets
- Implement lazy loading for components
- Optimize images and assets

## Backup & Recovery

### Database Backups

```bash
# Manual backup
pg_dump postgresql://user:password@host/salonai_db > backup.sql

# Automated backup (add to crontab)
0 2 * * * pg_dump postgresql://user:password@host/salonai_db | gzip > /backups/salonai_$(date +%Y%m%d).sql.gz

# Restore from backup
psql postgresql://user:password@host/salonai_db < backup.sql
```

### Application Backups

```bash
# Backup important files
tar -czf salonai-backup-$(date +%Y%m%d).tar.gz ./backend ./frontend ./config/

# Upload to S3
aws s3 cp salonai-backup-*.tar.gz s3://your-backup-bucket/
```

## Security Hardening

### System Updates
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get upgrade
sudo apt-get autoremove
```

### Firewall
```bash
# UFW (Uncomplicated Firewall)
sudo ufw enable
sudo ufw allow 22/tcp  # SSH
sudo ufw allow 80/tcp  # HTTP
sudo ufw allow 443/tcp # HTTPS
```

### SSH Security
```bash
# Disable root login
# Edit /etc/ssh/sshd_config
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes

# Restart SSH
sudo systemctl restart ssh
```

### Environment Variables Security
- Never commit `.env` files
- Use secret management: AWS Secrets Manager, HashiCorp Vault
- Rotate API keys regularly
- Use IAM roles for cloud services

## Load Balancing

### Docker Swarm

```bash
# Initialize swarm
docker swarm init

# Deploy stack
docker stack deploy -c docker-compose.yml salonai

# Scale services
docker service scale salonai_backend=3
docker service scale salonai_frontend=2
```

### Multiple Server Deployment

1. **Load Balancer** (HAProxy/Nginx)
2. **Backend Servers** (2-3+ instances)
3. **Database** (Single managed instance)
4. **Cache** (Redis cluster)

```
                     ┌─────────────┐
                     │   Nginx     │
                     │ Load Bal.   │
                     └──────┬──────┘
                ┌─────────┬─┴──────────────┐
        ┌───────▼──┐  ┌───▼────────┐  ┌───▼────────┐
        │ Backend  │  │ Backend    │  │ Backend    │
        │ Server 1 │  │ Server 2   │  │ Server 3   │
        └──────────┘  └────────────┘  └────────────┘
                            │
        ┌───────────────────┴────────────────────┐
        │                                        │
    ┌───▼────────┐                      ┌───────▼──┐
    │ PostgreSQL │                      │  Redis  │
    │ (Primary)  │                      │ (Cache) │
    └────────────┘                      └─────────┘
```

## CI/CD Pipeline

### GitHub Actions Example

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    
    - name: Build Docker images
      run: |
        docker build -f Dockerfile.backend -t salonai-backend:${{ github.sha }} .
        docker build -f Dockerfile.frontend -t salonai-frontend:${{ github.sha }} .
    
    - name: Push to registry
      run: |
        docker tag salonai-backend:${{ github.sha }} registry.example.com/salonai-backend:latest
        docker push registry.example.com/salonai-backend:latest
    
    - name: Deploy to server
      env:
        DEPLOY_KEY: ${{ secrets.DEPLOY_KEY }}
      run: |
        mkdir -p ~/.ssh
        echo "$DEPLOY_KEY" > ~/.ssh/deploy_key
        chmod 600 ~/.ssh/deploy_key
        ssh -i ~/.ssh/deploy_key user@your-server.com 'cd /opt/salonai && docker-compose pull && docker-compose up -d'
```

## Troubleshooting Production Issues

### Application Won't Start

```bash
# Check logs
docker-compose logs -f backend

# Verify configuration
docker exec salonai_backend python -c "from core.config import get_settings; print(get_settings())"

# Test database connection
docker exec salonai_backend python -c "from db import engine; engine.connect()"
```

### High CPU/Memory Usage

```bash
# Monitor containers
docker stats

# Identify processes
ps aux | grep uvicorn

# Check database queries
EXPLAIN ANALYZE SELECT ...
```

### Database Connection Issues

```bash
# Test connection
psql postgresql://user:password@host/db

# Check pool settings
# Adjust POOL_SIZE and MAX_OVERFLOW in config

# Restart service
docker-compose restart backend
```

## Post-Deployment Checklist

- [ ] Health check passing
- [ ] All endpoints responding
- [ ] Database migrations completed
- [ ] Environment variables configured
- [ ] SSL certificate valid
- [ ] Logging working
- [ ] Monitoring configured
- [ ] Backups scheduled
- [ ] Alert notifications configured
- [ ] Documentation updated

## Support & Escalation

For production issues:
1. Check application logs: `docker-compose logs`
2. Check system resources: `docker stats`
3. Review recent deployments: `git log --oneline`
4. Check database status: `psql -c "SELECT version();"`
5. Contact DevOps team if critical

---

**For issues, refer to ARCHITECTURE.md and QUICKSTART.md**
