# Deployment Guide 🚀

This guide covers deploying Faith Companion in different environments.

## Quick Local Setup

1. **Run the setup script**:
   ```bash
   ./setup.sh
   ```

2. **Edit your configuration**:
   ```bash
   nano .env
   nano config/system-prompt.txt
   ```

3. **Start the application**:
   ```bash
   docker-compose up -d
   ```

## Production Deployment

### Option 1: Standalone Docker

For simple single-server deployment:

```bash
# 1. Configure environment
cp .env.example .env
# Edit .env with production values

# 2. Start with Docker Compose
docker-compose -f docker-compose.yml up -d

# 3. Configure reverse proxy (nginx/caddy) to point to port 8000
```

### Option 2: With Traefik (Recommended)

For automatic SSL and multiple services:

1. **Set up Traefik network**:
   ```bash
   docker network create traefik
   ```

2. **Configure production settings**:
   ```bash
   cp docker-compose.prod.yml docker-compose.override.yml
   # Edit docker-compose.override.yml with your domain
   ```

3. **Set environment variables**:
   ```bash
   export DOMAIN=your-domain.com
   ```

4. **Deploy**:
   ```bash
   docker-compose up -d
   ```

## Server Requirements

### Minimum Requirements
- **CPU**: 1 core
- **RAM**: 1GB
- **Storage**: 5GB
- **OS**: Any Docker-compatible Linux distribution

### Recommended for Production
- **CPU**: 2+ cores
- **RAM**: 2GB+
- **Storage**: 20GB+ (for logs and analytics)
- **OS**: Ubuntu 20.04+ or equivalent

## Environment Variables

### Required Variables

```bash
# API Keys
ANTHROPIC_API_KEY=sk-ant-api03-your-key

# Authentication
ADMIN_PASSWORD=secure-admin-password
PRIEST_ADMIN_PASSWORD=secure-priest-password
```

### Optional Production Variables

```bash
# Organization Info
ORGANIZATION_NAME="Diocese of Example"
ORGANIZATION_WEBSITE="https://example.diocese.com"

# Domain (for Traefik)
DOMAIN=faith.example.com

# Rate Limiting
RATE_LIMIT_REQUESTS=50
RATE_LIMIT_WINDOW=3600
```

## SSL/TLS Configuration

### With Traefik
SSL is handled automatically with Let's Encrypt. Update your DNS to point to your server.

### With Nginx
Example nginx configuration:

```nginx
server {
    listen 80;
    listen 443 ssl;
    server_name your-domain.com;
    
    ssl_certificate /path/to/certificate.crt;
    ssl_certificate_key /path/to/private.key;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Backup Strategy

### Database Backups
```bash
# Create backup
docker exec faith-companion sqlite3 /app/data/analytics.db ".dump" > backup-$(date +%Y%m%d).sql

# Restore from backup
docker exec -i faith-companion sqlite3 /app/data/analytics.db < backup-20241201.sql
```

### Full Data Backup
```bash
# Backup entire data directory
tar -czf faith-companion-backup-$(date +%Y%m%d).tar.gz ./data/
```

## Monitoring

### Health Check
```bash
# Check if application is running
curl -f http://localhost:8000/health || echo "Application is down"
```

### Log Monitoring
```bash
# View application logs
docker logs faith-companion

# Follow logs in real-time
docker logs -f faith-companion
```

### Resource Monitoring
```bash
# Check container resource usage
docker stats faith-companion
```

## Maintenance

### Updates

1. **Backup your data**:
   ```bash
   tar -czf backup-$(date +%Y%m%d).tar.gz ./data/ ./config/
   ```

2. **Pull latest code**:
   ```bash
   git pull origin main
   ```

3. **Rebuild and restart**:
   ```bash
   docker-compose down
   docker-compose build --no-cache
   docker-compose up -d
   ```

### Clean Up
```bash
# Remove unused Docker images
docker image prune -a

# Remove unused volumes
docker volume prune
```

## Security Checklist

- [ ] Strong passwords in `.env`
- [ ] Firewall configured (only ports 80, 443, 22 open)
- [ ] Regular system updates
- [ ] SSL/TLS enabled
- [ ] Regular backups configured
- [ ] Rate limiting enabled
- [ ] Log monitoring in place
- [ ] Admin access restricted to authorized personnel

## Troubleshooting

### Common Issues

**Application won't start**:
```bash
# Check logs
docker logs faith-companion

# Verify environment variables
docker exec faith-companion env | grep -E "(ANTHROPIC|ADMIN)"
```

**High memory usage**:
```bash
# Restart application
docker-compose restart faith-companion

# Check for memory leaks in logs
docker logs faith-companion | grep -i memory
```

**SSL certificate issues**:
```bash
# Check certificate expiration
openssl s_client -connect your-domain.com:443 -servername your-domain.com 2>/dev/null | openssl x509 -noout -dates
```

## Support

For deployment issues:
1. Check the logs: `docker logs faith-companion`
2. Verify your configuration: `.env` and `config/system-prompt.txt`
3. Open an issue on GitHub with your configuration and error messages
4. Join our community discussions for tips and best practices

## Performance Tuning

### For High Traffic

1. **Increase rate limits**:
   ```bash
   RATE_LIMIT_REQUESTS=100
   RATE_LIMIT_WINDOW=3600
   ```

2. **Enable caching** (add to docker-compose.yml):
   ```yaml
   services:
     redis:
       image: redis:alpine
       volumes:
         - redis-data:/data
   ```

3. **Load balancing** with multiple instances:
   ```yaml
   services:
     faith-companion:
       deploy:
         replicas: 3
   ```

Happy deploying! 🕊️