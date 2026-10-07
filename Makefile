# ================================================
# Makefile - Portal PPSA
# Comandos úteis para gerenciar a aplicação
# ================================================

.PHONY: help build up down restart logs clean test shell db-shell

# Variáveis
COMPOSE = docker-compose
APP_CONTAINER = portal-ppsa-app
DB_CONTAINER = portal-ppsa-mongodb

# Comando padrão
.DEFAULT_GOAL := help

# ================================================
# Help
# ================================================
help: ## Exibe esta mensagem de ajuda
	@echo "================================================"
	@echo "Portal PPSA - Comandos Make Disponíveis"
	@echo "================================================"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ================================================
# Docker Commands
# ================================================
build: ## Build das imagens Docker
	@echo "🔨 Building Docker images..."
	$(COMPOSE) build --no-cache

build-fast: ## Build rápido (usa cache)
	@echo "⚡ Fast building Docker images..."
	$(COMPOSE) build

up: ## Inicia todos os containers
	@echo "🚀 Starting containers..."
	$(COMPOSE) up -d
	@echo "✅ Containers started!"
	@echo "📱 Application: http://localhost:5005"
	@echo "🗄️  MongoDB: localhost:27017"

up-debug: ## Inicia containers incluindo Mongo Express
	@echo "🚀 Starting containers with debug tools..."
	$(COMPOSE) --profile debug up -d
	@echo "✅ Containers started!"
	@echo "📱 Application: http://localhost:5005"
	@echo "🗄️  MongoDB: localhost:27017"
	@echo "🔍 Mongo Express: http://localhost:8081"

down: ## Para e remove todos os containers
	@echo "🛑 Stopping containers..."
	$(COMPOSE) down
	@echo "✅ Containers stopped!"

down-volumes: ## Para containers e remove volumes (CUIDADO: apaga dados)
	@echo "⚠️  WARNING: This will delete all data!"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		$(COMPOSE) down -v; \
		echo "✅ Containers and volumes removed!"; \
	fi

restart: ## Reinicia todos os containers
	@echo "🔄 Restarting containers..."
	$(COMPOSE) restart
	@echo "✅ Containers restarted!"

restart-app: ## Reinicia apenas o container da aplicação
	@echo "🔄 Restarting application..."
	$(COMPOSE) restart app
	@echo "✅ Application restarted!"

# ================================================
# Logs
# ================================================
logs: ## Exibe logs de todos os containers
	$(COMPOSE) logs -f

logs-app: ## Exibe logs da aplicação
	$(COMPOSE) logs -f app

logs-db: ## Exibe logs do MongoDB
	$(COMPOSE) logs -f mongodb

# ================================================
# Status e Info
# ================================================
status: ## Mostra status dos containers
	@echo "📊 Container Status:"
	@$(COMPOSE) ps

ps: status ## Alias para status

info: ## Mostra informações sobre os containers
	@echo "================================================"
	@echo "Portal PPSA - Container Information"
	@echo "================================================"
	@$(COMPOSE) ps
	@echo ""
	@echo "📊 Resource Usage:"
	@docker stats --no-stream $(APP_CONTAINER) $(DB_CONTAINER)

# ================================================
# Shell Access
# ================================================
shell: ## Acessa shell do container da aplicação
	@echo "🐚 Accessing application shell..."
	@docker exec -it $(APP_CONTAINER) /bin/bash

db-shell: ## Acessa MongoDB shell
	@echo "🗄️  Accessing MongoDB shell..."
	@docker exec -it $(DB_CONTAINER) mongosh -u admin -p changeme123 --authenticationDatabase admin

db-shell-app: ## Acessa MongoDB shell do banco da aplicação
	@echo "🗄️  Accessing MongoDB shell (sgppServices database)..."
	@docker exec -it $(DB_CONTAINER) mongosh -u admin -p changeme123 --authenticationDatabase admin sgppServices

# ================================================
# Database Operations
# ================================================
db-backup: ## Faz backup do MongoDB
	@echo "💾 Creating MongoDB backup..."
	@mkdir -p ./backups
	@docker exec $(DB_CONTAINER) mongodump --uri="mongodb://admin:changeme123@localhost:27017/sgppServices?authSource=admin" --out=/tmp/backup
	@docker cp $(DB_CONTAINER):/tmp/backup ./backups/backup-$(shell date +%Y%m%d-%H%M%S)
	@echo "✅ Backup created in ./backups/"

db-restore: ## Restaura backup do MongoDB (usage: make db-restore BACKUP=./backups/backup-20240101-120000)
	@if [ -z "$(BACKUP)" ]; then \
		echo "❌ Error: Specify backup directory with BACKUP=path"; \
		echo "Example: make db-restore BACKUP=./backups/backup-20240101-120000"; \
		exit 1; \
	fi
	@echo "♻️  Restoring MongoDB backup from $(BACKUP)..."
	@docker cp $(BACKUP) $(DB_CONTAINER):/tmp/restore
	@docker exec $(DB_CONTAINER) mongorestore --uri="mongodb://admin:changeme123@localhost:27017/?authSource=admin" /tmp/restore
	@echo "✅ Backup restored!"

db-init: ## Reinicializa o banco de dados (CUIDADO: apaga dados)
	@echo "⚠️  WARNING: This will delete all database data!"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker exec $(DB_CONTAINER) mongosh -u admin -p changeme123 --authenticationDatabase admin --eval "db.getSiblingDB('sgppServices').dropDatabase()"; \
		docker exec $(DB_CONTAINER) mongosh -u admin -p changeme123 --authenticationDatabase admin sgppServices < init-scripts/init-mongo.js; \
		echo "✅ Database reinitialized!"; \
	fi

# ================================================
# Clean
# ================================================
clean: ## Remove containers, volumes, imagens e arquivos temporários
	@echo "🧹 Cleaning up..."
	@$(COMPOSE) down -v --rmi all
	@rm -rf cache/ logs/ uploads/
	@echo "✅ Cleanup completed!"

clean-cache: ## Remove apenas cache da aplicação
	@echo "🧹 Cleaning cache..."
	@rm -rf cache/*
	@echo "✅ Cache cleaned!"

# ================================================
# Development
# ================================================
dev: ## Inicia em modo desenvolvimento
	@echo "🔧 Starting in development mode..."
	@FLASK_ENV=development FLASK_DEBUG=True $(COMPOSE) up

test: ## Executa testes (se disponível)
	@echo "🧪 Running tests..."
	@docker exec $(APP_CONTAINER) pytest -v

lint: ## Executa linter no código
	@echo "🔍 Running linter..."
	@docker exec $(APP_CONTAINER) flake8 app/

format: ## Formata código com black
	@echo "✨ Formatting code..."
	@docker exec $(APP_CONTAINER) black app/

# ================================================
# Production
# ================================================
deploy: build up ## Build e deploy em produção
	@echo "🚀 Deployed to production!"

health: ## Verifica saúde dos containers
	@echo "🏥 Checking container health..."
	@docker inspect --format='{{.State.Health.Status}}' $(APP_CONTAINER) || echo "App: No healthcheck"
	@docker inspect --format='{{.State.Health.Status}}' $(DB_CONTAINER) || echo "DB: No healthcheck"

# ================================================
# Monitoring
# ================================================
stats: ## Mostra estatísticas de uso em tempo real
	@docker stats $(APP_CONTAINER) $(DB_CONTAINER)

top: ## Mostra processos rodando nos containers
	@echo "📊 Application processes:"
	@docker top $(APP_CONTAINER)
	@echo ""
	@echo "📊 Database processes:"
	@docker top $(DB_CONTAINER)