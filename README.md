# Faith Companion 🕊️

> A modern, AI-powered Catholic faith assistant that brings centuries of Church teaching to the digital age.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://docker.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Framework-009688.svg)](https://fastapi.tiangolo.com/)
[![Anthropic Claude](https://img.shields.io/badge/Anthropic-Claude%20AI-orange.svg)](https://www.anthropic.com/)

Faith Companion is a sophisticated Catholic faith assistant designed for dioceses, parishes, and Catholic communities worldwide. Built with cutting-edge AI technology, it provides accurate, pastorally sensitive guidance rooted in official Church teaching.

## 🎯 Purpose & Vision

**Faith Companion bridges the gap between timeless Catholic wisdom and modern accessibility.** 

In an age where people seek instant answers to spiritual questions, Faith Companion provides:
- **Doctrinally accurate** responses grounded in the Catechism and Church documents
- **Pastorally sensitive** guidance that respects the human person
- **Accessible 24/7** faith support for the modern faithful
- **Multilingual capability** for diverse Catholic communities
- **Analytics and insights** for pastoral planning

Perfect for dioceses wanting to extend their pastoral reach, parishes seeking to serve their community better, or any Catholic organization committed to evangelization in the digital age.

## 📸 Screenshots & Demo

### Main Chat Interface
```
🖼️ [Screenshot placeholder: Clean, modern chat interface with Catholic branding]
- Mobile-responsive design
- Intuitive conversation flow
- Source citations from Church documents
```

### Admin Dashboard
```
🖼️ [Screenshot placeholder: Analytics dashboard showing usage statistics]
- Real-time usage analytics
- Popular topics tracking
- User demographics insights
- Export capabilities
```

### Priest Admin Panel
```
🖼️ [Screenshot placeholder: Spiritual direction request management]
- Spiritual direction request management
- Follow-up tracking
- Pastoral care metrics
```

**Live Demo**: *[Add your demo URL here when deployed]*

## ✨ Features

### 🤖 AI-Powered Faith Guidance
- **Claude AI Integration**: Powered by Anthropic's Claude for nuanced, contextual responses
- **RAG Architecture**: Retrieval-Augmented Generation using official Church documents
- **Doctrinal Accuracy**: Grounded in the Catechism, papal encyclicals, and Canon Law
- **Citation System**: Every response includes proper source citations

### 📚 Rich Document Library
- **Catechism of the Catholic Church** (complete text)
- **Papal Encyclicals** (major documents from recent pontificates)
- **Vatican II Documents** (all constitutions and declarations)
- **Code of Canon Law** (searchable and accessible)
- **Custom Document Support** (add your own diocesan materials)

### 🎨 Multiple Interfaces
- **Public Chat** (`/`) - Clean, accessible interface for all users
- **Admin Dashboard** (`/admin`) - Comprehensive analytics and management
- **Priest Panel** (`/phadmin`) - Spiritual direction and pastoral care tools

### 📊 Advanced Analytics
- **Usage Patterns**: Track questions, topics, and user engagement
- **Demographics**: Geographic and device analytics
- **Popular Content**: Identify trending spiritual topics
- **Export Capabilities**: CSV exports for analysis and reporting

### 🛡️ Enterprise Security
- **Rate Limiting**: Configurable request limits per IP
- **Spam Protection**: Advanced content filtering and gibberish detection
- **Input Validation**: Comprehensive security against malicious inputs
- **Admin Authentication**: Secure HTTP Basic Auth for administrative access

### 🌍 Internationalization Ready
- **Configurable System Prompts**: Adapt for any language or cultural context
- **Custom FAQ Responses**: Localize common questions and answers
- **Document Management**: Support for multilingual Church documents

## 🏗️ Architecture Overview

Faith Companion uses a modern, scalable architecture designed for reliability and performance:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   FastAPI       │    │   Anthropic     │
│   (HTML/CSS/JS) │◄──►│   Backend       │◄──►│   Claude AI     │
│                 │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │   ChromaDB      │    │   SQLite        │
                       │   Vector Store  │    │   Analytics DB  │
                       │                 │    │                 │
                       └─────────────────┘    └─────────────────┘
```

### Technology Stack

**Backend**:
- **FastAPI**: High-performance web framework with automatic OpenAPI documentation
- **Python 3.11**: Modern Python with excellent AI/ML library support
- **Anthropic Claude**: State-of-the-art language model for nuanced responses
- **LangChain**: Document processing and RAG pipeline management
- **ChromaDB**: Vector database for semantic document search
- **SQLite**: Lightweight analytics and user data storage

**Frontend**:
- **Vanilla HTML/CSS/JS**: No complex frameworks - fast, accessible, SEO-friendly
- **Progressive Enhancement**: Works without JavaScript, enhanced with it
- **Mobile-First Design**: Responsive across all device types
- **Accessibility Focus**: WCAG 2.1 compliant design principles

**Infrastructure**:
- **Docker**: Containerized deployment for consistency and scalability
- **Docker Compose**: Multi-service orchestration with volume management
- **Traefik Support**: Automatic SSL, load balancing, and service discovery

## 🚀 Installation & Setup

### Prerequisites

- **Docker** (20.10+) and **Docker Compose** (2.0+)
- **Claude API Key** from [Anthropic Console](https://console.anthropic.com/)
- **2GB RAM** minimum, 4GB recommended
- **5GB Storage** minimum for documents and analytics

### Quick Start (5 Minutes)

1. **Clone and Configure**
   ```bash
   git clone https://github.com/gingerol/faith-companion.git
   cd faith-companion
   ./setup.sh  # Interactive setup script
   ```

2. **Start the Application**
   ```bash
   docker-compose up -d
   ```

3. **Access Interfaces**
   - **Main Chat**: http://localhost:8000
   - **Admin Dashboard**: http://localhost:8000/admin
   - **Priest Panel**: http://localhost:8000/phadmin

### Detailed Setup

#### 1. Environment Configuration

```bash
# Copy the example environment file
cp .env.example .env

# Edit with your configuration
nano .env
```

**Required Variables**:
```env
# Anthropic API Key (get from https://console.anthropic.com/)
ANTHROPIC_API_KEY=sk-ant-api03-your-anthropic-key-here

# Admin credentials (choose strong passwords)
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-secure-admin-password-here

# Priest admin credentials
PRIEST_ADMIN_USERNAME=priestadmin
PRIEST_ADMIN_PASSWORD=your-secure-priest-password-here
```

**Optional Configuration**:
```env
# Organization branding
ORGANIZATION_NAME=Diocese of Your City
ORGANIZATION_WEBSITE=https://your-diocese.org

# Rate limiting (requests per hour per IP)
RATE_LIMIT_REQUESTS=50
RATE_LIMIT_WINDOW=3600

# Future AI features
GEMINI_API_KEY=your-gemini-api-key
```

#### 2. System Prompt Customization

Edit `config/system-prompt.txt` to customize the AI's behavior:

```txt
IMPORTANT CURRENT FACTS:
- The current Pope is Pope Francis
- Your Diocese: Most Rev. John Smith, Bishop of Your City
- Contact: info@yourcity-diocese.org

You are Faith Companion, a Catholic faith assistant for the Diocese of Your City.

Guidelines:
[Customize the guidelines for your pastoral context]
```

#### 3. Document Management

**Adding Documents**:
```bash
# Place PDF or text files in the documents directory
cp your-diocesan-documents.pdf documents/
cp parish-guidelines.txt documents/

# Restart the application to reindex
docker-compose restart faith-companion
```

**Supported Formats**:
- PDF documents (automatically extracted)
- Plain text files (.txt, .md)
- Any format supported by LangChain loaders

#### 4. Branding Customization

**Logo Replacement**:
```bash
# Replace with your organization's logo (PNG format recommended)
cp your-logo.png logo.png
cp your-logo.png frontend/logo.png
```

**Color Scheme** (edit `frontend/index.html`):
```css
:root {
    --primary-dark: #your-primary-color;
    --accent-purple: #your-accent-color;
    /* Customize other CSS variables */
}
```

## ⚙️ Configuration Reference

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | ✅ | - | Claude AI API key from Anthropic |
| `ADMIN_USERNAME` | ✅ | admin | Username for admin dashboard |
| `ADMIN_PASSWORD` | ✅ | - | Password for admin dashboard |
| `PRIEST_ADMIN_USERNAME` | ✅ | priestadmin | Username for priest panel |
| `PRIEST_ADMIN_PASSWORD` | ✅ | - | Password for priest panel |
| `ORGANIZATION_NAME` | ❌ | Faith Companion | Organization name for branding |
| `ORGANIZATION_WEBSITE` | ❌ | - | Organization website URL |
| `RATE_LIMIT_REQUESTS` | ❌ | 20 | Max requests per window per IP |
| `RATE_LIMIT_WINDOW` | ❌ | 3600 | Rate limiting window in seconds |
| `GEMINI_API_KEY` | ❌ | - | Google Gemini API key (future features) |

### System Prompt Configuration

The AI's behavior is controlled by `config/system-prompt.txt`. Key sections to customize:

1. **Current Facts**: Update Pope, Bishop, diocese information
2. **Organization Context**: Add your specific pastoral context
3. **Guidelines**: Modify for your theological emphasis
4. **Contact Information**: Include local resources and contacts

### Document Processing

Documents in the `/documents` directory are automatically:
- **Indexed** on startup using ChromaDB vector embeddings
- **Chunked** for optimal retrieval (500 characters with 50 character overlap)
- **Embedded** using HuggingFace sentence transformers
- **Cited** in AI responses with document names and page numbers

## 🔌 API Documentation

Faith Companion provides a RESTful API for integration with other systems.

### Endpoints

#### Chat API
```http
POST /chat
Content-Type: application/json

{
  "message": "What is the Catholic teaching on marriage?",
  "conversation_history": [],
  "session_id": "optional-session-id"
}
```

**Response**:
```json
{
  "response": "Catholic teaching on marriage...",
  "sources": ["Catechism 1601-1666", "Gaudium et Spes 47-52"]
}
```

#### Analytics API
```http
GET /admin/analytics
Authorization: Basic <base64(admin:password)>
```

**Response**:
```json
{
  "total_conversations": 1234,
  "total_messages": 5678,
  "popular_topics": ["Marriage", "Prayer", "Sacraments"],
  "usage_by_day": {...},
  "demographics": {...}
}
```

#### Health Check
```http
GET /health
```

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "version": "1.0.0"
}
```

### Rate Limiting

All endpoints respect rate limiting:
- **Headers**: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
- **Status**: `429 Too Many Requests` when exceeded
- **Configurable**: Via environment variables

## 🚀 Deployment

### Development Deployment

For local development and testing:

```bash
# Clone and setup
git clone https://github.com/gingerol/faith-companion.git
cd faith-companion
./setup.sh

# Start with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f faith-companion
```

### Production Deployment

#### Option 1: Standalone with Nginx

```bash
# Production environment setup
cp .env.example .env
# Configure production values in .env

# Deploy
docker-compose up -d

# Setup Nginx reverse proxy
sudo nano /etc/nginx/sites-available/faith-companion
```

**Nginx Configuration**:
```nginx
server {
    listen 80;
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /path/to/ssl/certificate.pem;
    ssl_certificate_key /path/to/ssl/private.key;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

#### Option 2: Docker Swarm with Traefik (Recommended)

```bash
# Initialize Docker Swarm
docker swarm init

# Create Traefik network
docker network create --driver=overlay traefik-public

# Deploy Traefik
docker stack deploy -c traefik-compose.yml traefik

# Deploy Faith Companion
cp docker-compose.prod.yml docker-compose.override.yml
# Edit override file with your domain
docker stack deploy -c docker-compose.yml -c docker-compose.override.yml faith-companion
```

**Traefik Configuration** (traefik-compose.yml):
```yaml
version: '3.8'

services:
  traefik:
    image: traefik:v2.9
    ports:
      - "80:80"
      - "443:443"
    command:
      - --providers.docker=true
      - --providers.docker.swarmMode=true
      - --entrypoints.web.address=:80
      - --entrypoints.websecure.address=:443
      - --certificatesresolvers.letsencrypt.acme.email=your-email@domain.com
      - --certificatesresolvers.letsencrypt.acme.storage=/letsencrypt/acme.json
      - --certificatesresolvers.letsencrypt.acme.httpchallenge.entrypoint=web
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - traefik-letsencrypt:/letsencrypt
    networks:
      - traefik-public

volumes:
  traefik-letsencrypt:

networks:
  traefik-public:
    external: true
```

### Kubernetes Deployment

```yaml
# k8s-deployment.yml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: faith-companion
spec:
  replicas: 3
  selector:
    matchLabels:
      app: faith-companion
  template:
    metadata:
      labels:
        app: faith-companion
    spec:
      containers:
      - name: faith-companion
        image: your-registry/faith-companion:latest
        ports:
        - containerPort: 8000
        env:
        - name: ANTHROPIC_API_KEY
          valueFrom:
            secretKeyRef:
              name: faith-companion-secrets
              key: anthropic-api-key
        volumeMounts:
        - name: documents
          mountPath: /app/documents
        - name: config
          mountPath: /app/config
      volumes:
      - name: documents
        persistentVolumeClaim:
          claimName: faith-companion-documents
      - name: config
        configMap:
          name: faith-companion-config
```

### Performance Tuning

**For High Traffic Deployments**:

```yaml
# docker-compose.override.yml
services:
  faith-companion:
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
      
  redis:
    image: redis:alpine
    volumes:
      - redis-data:/data
    deploy:
      resources:
        limits:
          memory: 512M

volumes:
  redis-data:
```

## 🔧 Development

### Local Development Setup

1. **Python Environment**:
   ```bash
   # Create virtual environment
   python3.11 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   
   # Install dependencies
   cd backend
   pip install -r requirements.txt
   ```

2. **Environment Variables**:
   ```bash
   export ANTHROPIC_API_KEY=your-key
   export ADMIN_PASSWORD=dev-password
   export PRIEST_ADMIN_PASSWORD=priest-password
   ```

3. **Run Development Server**:
   ```bash
   cd backend
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

### Project Structure

```
faith-companion/
├── backend/
│   ├── main.py                 # FastAPI application core
│   ├── requirements.txt        # Python dependencies
│   └── tests/                  # Unit tests (coming soon)
├── frontend/
│   ├── index.html             # Main chat interface
│   ├── admin.html             # Admin dashboard
│   ├── phadmin.html           # Priest admin panel
│   └── assets/                # Static assets
├── documents/                  # Catholic documents for RAG
│   ├── catechism.pdf          # Catechism of the Catholic Church
│   ├── vatican_ii.pdf         # Vatican II documents
│   ├── canon_law.pdf          # Code of Canon Law
│   └── [custom documents]     # Your diocesan materials
├── config/
│   └── system-prompt.txt      # AI system prompt configuration
├── data/                      # Runtime data (SQLite DB, ChromaDB)
│   ├── analytics.db           # Analytics database
│   └── chroma_db/             # Vector embeddings
├── docker-compose.yml         # Development deployment
├── docker-compose.prod.yml    # Production template
├── Dockerfile                 # Container definition
├── .env.example              # Environment template
├── setup.sh                  # Setup automation script
└── docs/                     # Additional documentation
    ├── DEPLOYMENT.md         # Deployment guide
    ├── API.md               # API documentation
    └── CUSTOMIZATION.md     # Customization guide
```

### Testing

```bash
# Run unit tests (coming soon)
cd backend
python -m pytest tests/

# Run integration tests
docker-compose -f docker-compose.test.yml up --abort-on-container-exit

# Load testing
docker run --rm -it --network=host \
  williamyeh/wrk:latest \
  -t8 -c100 -d30s http://localhost:8000/health
```

### Contributing Workflow

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feature/amazing-feature`
3. **Commit** your changes: `git commit -m 'Add amazing feature'`
4. **Push** to the branch: `git push origin feature/amazing-feature`
5. **Open** a Pull Request

### Code Quality

```bash
# Format code
black backend/
isort backend/

# Lint code
flake8 backend/
pylint backend/

# Type checking
mypy backend/
```

## 📊 Monitoring & Analytics

### Built-in Analytics

Access comprehensive analytics via `/admin`:

- **Usage Metrics**: Total conversations, messages, response times
- **Popular Topics**: Trending spiritual topics and questions  
- **User Demographics**: Geographic distribution, device types, browsers
- **Performance**: Rate limiting stats, error rates, uptime
- **Export Options**: CSV downloads for external analysis

### External Monitoring

**Prometheus Integration** (optional):
```yaml
# Add to docker-compose.yml
services:
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
```

**Health Checks**:
```bash
# Application health
curl -f http://localhost:8000/health

# Container health
docker health ls

# Resource monitoring
docker stats faith-companion
```

## 🔒 Security

### Security Features

- **Input Sanitization**: All user inputs are validated and sanitized
- **Rate Limiting**: Configurable per-IP request limits
- **Spam Detection**: Advanced content filtering and gibberish detection
- **HTTPS Support**: SSL/TLS encryption for all communications
- **Security Headers**: HSTS, CSP, and other security headers via Traefik
- **Data Privacy**: No personal data stored beyond analytics

### Security Best Practices

1. **Strong Passwords**: Use complex passwords for admin accounts
2. **Regular Updates**: Keep Docker images and dependencies updated
3. **Firewall Configuration**: Limit open ports (only 80, 443, 22)
4. **SSL Certificates**: Use Let's Encrypt or commercial certificates
5. **Backup Security**: Encrypt backups and store securely
6. **Access Logging**: Monitor admin access and suspicious activity

### Security Headers

When deployed with Traefik, Faith Companion automatically includes:

```
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
Referrer-Policy: strict-origin-when-cross-origin
Content-Security-Policy: default-src 'self'
```

## 🤝 Contributing

We welcome contributions from Catholic developers worldwide! Here's how to get involved:

### Ways to Contribute

- **🐛 Bug Reports**: Found an issue? Open a GitHub issue with details
- **✨ Feature Requests**: Have an idea? Discuss it in GitHub Discussions
- **📝 Documentation**: Help improve our docs and guides
- **🌍 Localization**: Translate for different languages and regions
- **🧪 Testing**: Help test new features and edge cases
- **💻 Code**: Submit pull requests for bug fixes and new features

### Development Guidelines

#### Code Standards
- **Python**: Follow PEP 8, use type hints, document functions
- **JavaScript**: Use modern ES6+, no external frameworks
- **HTML/CSS**: Semantic HTML, mobile-first CSS, accessibility focus
- **Documentation**: Update README and docs with any changes

#### Pull Request Process

1. **Fork** the repository
2. **Create** a descriptive branch name:
   ```bash
   git checkout -b feature/add-multilingual-support
   git checkout -b fix/rate-limiting-bug
   git checkout -b docs/improve-deployment-guide
   ```

3. **Make changes** following our coding standards
4. **Test thoroughly**:
   ```bash
   # Test your changes locally
   docker-compose up -d
   # Verify functionality works as expected
   ```

5. **Commit** with clear messages:
   ```bash
   git commit -m "feat: Add Spanish language support
   
   - Add es_ES system prompt template
   - Update FAQ responses with Spanish translations
   - Add Spanish document processing capability
   - Update documentation for multilingual setup"
   ```

6. **Submit** pull request with:
   - Clear description of changes
   - Screenshots for UI changes
   - Test results and validation steps
   - Any breaking changes or migration notes

#### Code Review Criteria

- ✅ **Functionality**: Does it work as intended?
- ✅ **Security**: No security vulnerabilities introduced?
- ✅ **Performance**: No significant performance degradation?
- ✅ **Documentation**: Are changes documented?
- ✅ **Compatibility**: Works with existing configurations?
- ✅ **Testing**: Includes appropriate tests?

### Community Guidelines

- **Be Respectful**: Treat all contributors with respect and kindness
- **Stay On Mission**: Keep contributions aligned with Catholic teaching
- **Be Patient**: Code review takes time - be patient with maintainers
- **Ask Questions**: Don't hesitate to ask if you need clarification
- **Have Fun**: Enjoy building something meaningful for the Church!

### Recognition

Contributors will be recognized in:
- **Contributors section** in README
- **Release notes** for significant contributions
- **Credits page** in the application (coming soon)

## 📞 Support & Community

### Getting Help

1. **📖 Documentation**: Check README, DEPLOYMENT.md, and inline docs
2. **🐛 Issues**: Search existing GitHub issues or create a new one
3. **💬 Discussions**: Use GitHub Discussions for questions and ideas
4. **📧 Email**: For sensitive matters, contact the maintainers directly

### Community

- **🌟 Star** the repository to show support
- **👀 Watch** for updates and new releases  
- **🍴 Fork** to create your own Catholic AI assistant
- **🗨️ Share** your experience with other Catholic organizations

### Reporting Issues

When reporting bugs, please include:

```markdown
**Environment**:
- Docker version: 
- OS: 
- Browser (if applicable):

**Steps to Reproduce**:
1. 
2. 
3. 

**Expected Behavior**:
[What should happen]

**Actual Behavior**:
[What actually happens]

**Screenshots**:
[If applicable]

**Logs**:
```
docker logs faith-companion
```
[Paste relevant logs]
```

## 📝 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

### MIT License Summary

✅ **Permissions**:
- ✅ Commercial use
- ✅ Modification  
- ✅ Distribution
- ✅ Private use

❗ **Conditions**:
- 📄 License and copyright notice must be included

❌ **Limitations**:
- ❌ No warranty
- ❌ No liability

### Third-Party Licenses

Faith Companion uses several open-source libraries:

- **FastAPI**: MIT License
- **Anthropic Python SDK**: MIT License  
- **LangChain**: MIT License
- **ChromaDB**: Apache License 2.0
- **Docker**: Apache License 2.0

All third-party libraries retain their original licenses.

## 🙏 Acknowledgments

### Technology Partners

- **[Anthropic](https://www.anthropic.com/)** - Claude AI powers our intelligent responses
- **[FastAPI](https://fastapi.tiangolo.com/)** - Modern, fast web framework
- **[LangChain](https://langchain.com/)** - Document processing and RAG capabilities
- **[ChromaDB](https://www.trychroma.com/)** - Vector database for semantic search

### Catholic Resources

- **Vatican** - Official Church documents and teachings
- **USCCB** - United States Conference of Catholic Bishops resources  
- **Vatican News** - Daily readings and Church news integration
- **Catholic dioceses worldwide** - Inspiration and feedback

### Contributors

Special thanks to all contributors who have helped make Faith Companion better:

- [Contributor list will be automatically generated]

### Inspiration

> *"Go into all the world and proclaim the Gospel to the whole creation."* - Mark 16:15

Faith Companion exists to serve the Church's mission of evangelization in the digital age, making the riches of Catholic teaching accessible to all who seek truth.

---

## 🌟 Star History

[![Star History Chart](https://api.star-history.com/svg?repos=gingerol/faith-companion&type=Date)](https://star-history.com/#gingerol/faith-companion&Date)

---

**Faith Companion** - *Bringing Catholic teaching to the digital age* 🕊️

*Built with ❤️ for the Catholic Church worldwide*