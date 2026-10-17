.PHONY: help install dev docker-build docker-run tf-init tf-plan tf-apply tf-destroy

help:
	@echo "🛡️ Comandos disponibles para Armor Agent Demo:"
	@echo "  make install       - Instala dependencias de Python localmente"
	@echo "  make dev           - Inicia el servidor de desarrollo local (FastAPI)"
	@echo "  make docker-build  - Construye la imagen Docker local"
	@echo "  make docker-run    - Ejecuta el contenedor Docker en http://localhost:8080"
	@echo "  make tf-init       - Inicializa Terraform"
	@echo "  make tf-plan       - Ejecuta terraform plan"
	@echo "  make tf-apply      - Despliega toda la infraestructura en GCP"
	@echo "  make tf-destroy    - Destruye todos los recursos en GCP"

install:
	pip install -r app/requirements.txt

dev:
	uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

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
