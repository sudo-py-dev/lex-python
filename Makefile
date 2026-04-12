# Lex Bot - Pro Management Makefile

.PHONY: up stop restart logs shell clean fix-perms setup help

# Default target
help:
	@echo "🏠 Lex Bot Management"
	@echo "Usage: make [target]"
	@echo ""
	@echo "🚀 Production:"
	@echo "  up      - Deploy/Update the bot (Build + Start + Perms)"
	@echo "  stop    - Stop the bot services"
	@echo "  restart - Quick restart of the bot container"
	@echo ""
	@echo "📝 Monitoring & Debug:"
	@echo "  logs    - Stream live bot logs"
	@echo "  shell   - Open a shell in the running bot"
	@echo ""
	@echo "🧹 Maintenance:"
	@echo "  fix-perms - Automatically fix folder permissions for non-root"
	@echo "  clean     - Remove temporary files and containers"

# Deploy/Update
up: setup fix-perms
	@echo "⚡ Building and starting Lex Bot..."
	sudo docker compose up -d --build
	@echo "🎉 Bot is running. Use 'make logs' to monitor."

# Stop
stop:
	@echo "🛑 Stopping services..."
	sudo docker compose down

# Restart
restart:
	@echo "🔄 Restarting bot..."
	sudo docker compose restart bot

# Logs
logs:
	sudo docker compose logs -f bot

# Shell
shell:
	sudo docker compose exec bot bash

# Fix permissions for internal bot user (UID 1000)
fix-perms:
	@echo "📂 Fixing directory permissions..."
	mkdir -p pgdata sessions logs
	sudo chown -R 1000:1000 sessions logs
	sudo chown -R 70:70 pgdata

# Initial Setup
setup:
	@if [ ! -f .env ]; then \
		echo "⚠️  .env missing. Creating from example..."; \
		cp .env.example .env; \
		echo "🚨 Edit .env and run 'make up' again."; \
		exit 1; \
	fi
	@bash scripts/setup_docker.sh

# Cleanup
clean:
	@echo "🧹 Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	sudo docker compose down --rmi local --volumes --remove-orphans
