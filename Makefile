.PHONY: help install dev docker-build docker-run configure-floor deploy-agent deploy-all tf-init tf-plan tf-apply tf-destroy

help:
	@echo "🛡️ Comandos disponibles para Armor Agent Demo:"
	@echo "  make install          - Instala dependencias de Python localmente"
	@echo "  make dev              - Inicia el servidor de desarrollo local (FastAPI)"
	@echo "  make configure-floor  - Activa Model Armor Floor Settings (AI_PLATFORM + INSPECT_AND_BLOCK)"
	@echo "  make deploy-agent     - Despliega el Agente ADK puro en Vertex AI Agent Engine"
	@echo "  make deploy-all       - Despliegue End-to-End automatizado (Agent Engine + Cloud Build + Terraform)"
	@echo "  make tf-init          - Inicializa Terraform"
	@echo "  make tf-plan          - Ejecuta terraform plan"
	@echo "  make tf-apply         - Despliega toda la infraestructura en GCP con Terraform"
	@echo "  make tf-destroy       - Destruye todos los recursos en GCP"

install:
	pip install -r app/requirements.txt

dev:
	uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

configure-floor:
	./scripts/configure_floor_settings.sh

deploy-agent:
	python3 scripts/deploy_agent_engine.py

deploy-all:
	./scripts/deploy_all.sh

docker-build:
	docker build -t armor-agent:latest .

docker-run:
	docker run -p 8080:8080 --env-file .env armor-agent:latest

tf-init:
	cd terraform && terraform init

tf-plan:
	cd terraform && terraform plan

tf-apply:
	cd terraform && terraform apply -auto-approve

tf-destroy:
	cd terraform && terraform destroy -auto-approve

