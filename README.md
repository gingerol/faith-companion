# Faith Companion 🕊️

A modern, AI-powered Catholic faith assistant that helps users explore Catholic teaching, Scripture, and doctrine. Built with FastAPI and Claude AI, designed for dioceses and parishes to provide accessible faith guidance to their communities.

## ✨ Features

- **AI-Powered Faith Guidance**: Answers questions about Catholic doctrine, Scripture, sacraments, and moral teaching
- **Rich Document Library**: Includes the Catechism, papal encyclicals, Vatican II documents, and Canon Law
- **Multiple Interfaces**: 
  - Public chat interface for faithful
  - Admin dashboard for content management
  - Priest admin panel for spiritual direction requests
- **Advanced Analytics**: Track usage patterns, popular topics, and user demographics
- **Rate Limiting & Spam Protection**: Built-in safeguards against abuse
- **Mobile-Responsive Design**: Works seamlessly on all devices
- **Multi-language Support**: Configurable for different languages and contexts

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- Claude API key from Anthropic

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/gingerol/faith-companion.git
   cd faith-companion
   ```

2. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your actual values
   ```

3. **Customize for your diocese/parish**
   - Edit `config/system-prompt.txt` to customize the AI's responses
   - Replace logo images in `frontend/` and root directory
   - Update branding in `frontend/index.html`

4. **Deploy with Docker**
   ```bash
   docker-compose up -d
   ```

5. **Access the application**
   - Main interface: `http://localhost:8000`
   - Admin dashboard: `http://localhost:8000/admin`
   - Priest admin: `http://localhost:8000/phadmin`

## ⚙️ Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```env
# Required: Anthropic API key for Claude AI
ANTHROPIC_API_KEY=your-anthropic-api-key

# Admin access credentials
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-secure-admin-password

# Priest admin access
PRIEST_ADMIN_USERNAME=priestadmin
PRIEST_ADMIN_PASSWORD=your-secure-priest-password

# Optional: Google Gemini API for future features
GEMINI_API_KEY=your-gemini-key

# Optional: Customize domain and branding
ORGANIZATION_NAME=Your Diocese/Parish Name
ORGANIZATION_WEBSITE=https://your-website.com
```

### Docker Deployment

For production deployment, update `docker-compose.yml`:

1. **Configure your domain**:
   ```yaml
   labels:
     - traefik.http.routers.faithcompanion.rule=Host(`your-domain.com`)
   ```

2. **Set up networks** (if using Traefik):
   ```yaml
   networks:
     - your-network-name
   ```

### System Prompt Customization

The AI's behavior is controlled by `config/system-prompt.txt`. Customize it for your diocese by:

1. Updating bishop/diocese information
2. Adding local contact information  
3. Modifying pastoral tone and emphasis
4. Including region-specific context

## 📁 Project Structure

```
faith-companion/
├── backend/
│   ├── main.py              # FastAPI application
│   └── requirements.txt     # Python dependencies
├── frontend/
│   ├── index.html          # Main chat interface
│   ├── admin.html          # Admin dashboard
│   └── phadmin.html        # Priest admin panel
├── documents/              # Catholic documents for AI training
├── config/
│   └── system-prompt.txt   # AI system prompt
├── docker-compose.yml      # Docker deployment
├── Dockerfile             # Container definition
└── .env.example           # Environment template
```

## 🔧 Development

### Running Locally

1. **Install Python dependencies**:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. **Set environment variables**:
   ```bash
   export ANTHROPIC_API_KEY=your-key
   export ADMIN_PASSWORD=admin123
   export PRIEST_ADMIN_PASSWORD=priest123
   ```

3. **Run the development server**:
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

### Adding Documents

Place PDF or text files in the `documents/` directory. The system will automatically:
- Process and index new documents
- Make them searchable for the AI
- Include them in responses with proper citations

### Customization

#### Branding
- Replace `logo.png` files with your organization's logo
- Update colors and styling in `frontend/index.html`
- Modify the favicon and app icons

#### Content
- Edit FAQ responses in `backend/main.py` (search for `FAQ_CACHE`)
- Update topic categorization keywords
- Modify rate limiting and spam detection settings

## 📊 Analytics & Administration

### Admin Dashboard (`/admin`)
- View chat statistics and usage patterns
- Monitor popular topics and questions
- Export data for analysis
- Manage system settings

### Priest Admin Panel (`/phadmin`)
- Review spiritual direction requests
- Follow up with parishioners
- Track pastoral care metrics

## 🔒 Security Features

- **Rate limiting**: 20 requests per hour per IP
- **Spam detection**: Content filtering and gibberish detection  
- **Input validation**: Message length and content restrictions
- **Admin authentication**: HTTP Basic Auth for administrative access
- **Environment isolation**: All secrets in environment variables

## 🌍 Localization

To adapt for different languages/regions:

1. **Update system prompt** with local context
2. **Modify FAQ responses** for local customs
3. **Add regional documents** to the documents folder
4. **Update contact links** and websites

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

### Development Guidelines

1. Maintain all existing functionality
2. Follow security best practices
3. Test thoroughly before submitting
4. Update documentation as needed

## 💬 Support

For support:
- Open an issue on GitHub
- Check the documentation
- Review the FAQ in the admin dashboard

## 🙏 Acknowledgments

- Built with [Claude AI](https://www.anthropic.com/) by Anthropic
- Uses [FastAPI](https://fastapi.tiangolo.com/) framework
- Document processing via [LangChain](https://langchain.com/)
- Vector storage with [ChromaDB](https://www.trychroma.com/)

---

**Faith Companion** - Bringing Catholic teaching to the digital age 🕊️