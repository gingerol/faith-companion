#!/bin/bash

# Faith Companion Setup Script
# This script helps you configure Faith Companion for your diocese/parish

set -e

echo "🕊️  Faith Companion Setup"
echo "========================="
echo

# Check if .env exists
if [ -f .env ]; then
    echo "⚠️  .env file already exists. Backup created as .env.backup"
    cp .env .env.backup
fi

# Copy example
echo "📝 Creating .env from template..."
cp .env.example .env

echo "✅ Configuration file created!"
echo
echo "📋 Next steps:"
echo "1. Edit .env with your API keys and credentials:"
echo "   nano .env"
echo
echo "2. Customize the system prompt for your diocese:"
echo "   nano config/system-prompt.txt"
echo
echo "3. Replace the logo files with your organization's branding:"
echo "   - Replace logo.png in the root directory"
echo "   - Replace frontend/logo.png"
echo
echo "4. Update branding in frontend/index.html (search for organization-specific text)"
echo
echo "5. Start the application:"
echo "   docker-compose up -d"
echo
echo "🔗 Access points after startup:"
echo "   - Main interface: http://localhost:8000"
echo "   - Admin dashboard: http://localhost:8000/admin"
echo "   - Priest admin: http://localhost:8000/phadmin"
echo
echo "📚 For production deployment, see README.md"
echo
echo "🎉 Setup complete! Edit the configuration files and start the application."