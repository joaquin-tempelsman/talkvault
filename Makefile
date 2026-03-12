.PHONY: help dev prod build up down logs test deploy clean

DC = docker compose --env-file .env -f infrastructure/docker-compose.yml

help:
	@echo "TalkVault"
	@echo ""
	@echo "  make dev      Start development environment"
	@echo "  make prod     Start production environment"
	@echo "  make build    Build Docker image"
	@echo "  make up       Start bot"
	@echo "  make down     Stop bot"
	@echo "  make logs     View logs"
	@echo "  make test     Run tests"
	@echo "  make deploy   Deploy to production"
	@echo "  make clean    Stop and remove containers"

dev: build up

build:
	$(DC) build

up:
	$(DC) up -d
	@echo "Bot started. Check logs with: make logs"

down:
	$(DC) down

logs:
	$(DC) logs -f

prod:
	docker compose -f infrastructure/docker-compose.yml -f infrastructure/docker-compose.prod.yml --env-file .env up -d --build

test:
	pytest -v

deploy:
	chmod +x deploy/deploy-prod.sh && ./deploy/deploy-prod.sh

clean:
	$(DC) down -v
	docker system prune -f
