#!/bin/bash
# ==============================================================================
# Armor Agent - End-to-End Automated Deployment Script (Agent Engine + Terraform)
# Uso:
#   ./scripts/deploy_all.sh <PROJECT_ID> [REGION]
# ==============================================================================

set -e

PROJECT_ID=${1:-${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}}
REGION=${2:-${GCP_LOCATION:-"us-central1"}}
APP_NAME="armor-agent"
REPO_NAME="${APP_NAME}-repo"

if [ -z "$PROJECT_ID" ]; then
  echo "❌ Error: Debes indicar el PROJECT_ID. Uso: ./scripts/deploy_all.sh <PROJECT_ID> [REGION]"
  exit 1
fi

echo "=============================================================================="
echo "🛡️  Desplegando Armor Agent (Cloud Armor + Model Armor Floor Settings + ADK)"
echo "📍 Proyecto : $PROJECT_ID"
echo "🌎 Región   : $REGION"
echo "=============================================================================="

# 1. Habilitar APIs base necesarias para el build y el agente
echo "1️⃣ Habilitando APIs de Google Cloud..."
gcloud services enable \
  run.googleapis.com \
  compute.googleapis.com \
  aiplatform.googleapis.com \
  modelarmor.googleapis.com \
  dlp.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  iam.googleapis.com \
  storage.googleapis.com \
  --project="$PROJECT_ID"

# 2. Configurar Model Armor Floor Settings + Template Regional
echo "2️⃣ Configurando Model Armor Floor Settings (Zero-Code Security para Vertex AI)..."
./scripts/configure_floor_settings.sh "$PROJECT_ID" "BLOCK"
./scripts/create_model_armor_template.sh "$PROJECT_ID" "$REGION" "${APP_NAME}-template"

# 3. Desplegar (o reutilizar) el Agente ADK puro en Vertex AI Agent Engine
echo "3️⃣ Desplegando Agente ADK puro en Vertex AI Agent Engine (Reasoning Engine)..."
PYTHON_BIN="python3"
if [ -x ".venv/bin/python" ]; then
  PYTHON_BIN=".venv/bin/python"
fi
$PYTHON_BIN scripts/deploy_agent_engine.py --project-id "$PROJECT_ID" --location "$REGION"
AGENT_ENGINE_ID=$(cat .agent_engine_id | tr -d '[:space:]')
echo "✅ Agent Engine Resource Name: $AGENT_ENGINE_ID"

# 4. Crear repositorio en Artifact Registry y construir imagen Docker con Cloud Build
echo "4️⃣ Construyendo imagen del contenedor Web UI / BFF en Artifact Registry..."
gcloud artifacts repositories describe "$REPO_NAME" \
  --location="$REGION" \
  --project="$PROJECT_ID" >/dev/null 2>&1 || \
gcloud artifacts repositories create "$REPO_NAME" \
  --repository-format=docker \
  --location="$REGION" \
  --description="Repositorio Docker para Armor Agent Demo" \
  --project="$PROJECT_ID"

IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${APP_NAME}:latest"
gcloud builds submit --tag "$IMAGE_URI" --project="$PROJECT_ID" .

# 5. Generar terraform.tfvars y aplicar infraestructura con Terraform
echo "5️⃣ Ejecutando Terraform (Cloud Armor + Load Balancer + Cloud Run + Model Armor)..."
cat > terraform/terraform.tfvars <<EOF
project_id                 = "${PROJECT_ID}"
region                     = "${REGION}"
app_name                   = "${APP_NAME}"
container_image            = "${IMAGE_URI}"
agent_engine_resource_name = "${AGENT_ENGINE_ID}"
model_armor_template_id    = "${APP_NAME}-template"
allowed_ips                = ["0.0.0.0/0"]
allowed_regions            = []
rate_limit_count           = 120
rate_limit_interval_sec    = 60
EOF

terraform -chdir=terraform init
terraform -chdir=terraform apply -auto-approve

echo "=============================================================================="
echo "🎉 ¡Despliegue completado exitosamente!"
terraform -chdir=terraform output
echo "=============================================================================="
