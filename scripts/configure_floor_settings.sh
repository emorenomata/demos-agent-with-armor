#!/bin/bash
# Script para configurar el Floor Setting de Google Cloud Model Armor a nivel de Proyecto
# e integrarlo nativamente con Vertex AI (AI_PLATFORM) en modo INSPECT_AND_BLOCK o INSPECT_ONLY.

set -e

PROJECT_ID=${1:-${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}}
MODE=${2:-"BLOCK"} # "BLOCK" (inspectAndBlock: true) o "INSPECT" (inspectOnly: true)

if [ -z "$PROJECT_ID" ]; then
  echo "❌ Error: PROJECT_ID no especificado. Uso: ./scripts/configure_floor_settings.sh <PROJECT_ID> [BLOCK|INSPECT]"
  exit 1
fi

echo "🛡️ Obteniendo token de autenticación y Project Number para '$PROJECT_ID'..."
ACCESS_TOKEN=$(gcloud auth application-default print-access-token 2>/dev/null || gcloud auth print-access-token)
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")

echo "🔑 Asegurando permisos IAM para el Service Agent de Vertex AI (service-${PROJECT_NUMBER}@gcp-sa-aiplatform.iam.gserviceaccount.com)..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-aiplatform.iam.gserviceaccount.com" \
  --role="roles/modelarmor.user" \
  --condition=None >/dev/null

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-aiplatform.iam.gserviceaccount.com" \
  --role="roles/dlp.user" \
  --condition=None >/dev/null

if [ "$MODE" = "INSPECT" ]; then
  AI_PLATFORM_SETTING='"inspectOnly": true, "enableCloudLogging": true'
  echo "⚠️ Configurando Floor Setting en modo AUDITORÍA (INSPECT_ONLY) para Vertex AI..."
else
  AI_PLATFORM_SETTING='"inspectAndBlock": true, "enableCloudLogging": true'
  echo "🛡️ Configurando Floor Setting en modo PROTECCIÓN ACTIVA (INSPECT_AND_BLOCK) para Vertex AI..."
fi

URL="https://modelarmor.googleapis.com/v1/projects/${PROJECT_ID}/locations/global/floorSetting"

RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X PATCH \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  "${URL}" \
  -d "{
    \"enableFloorSettingEnforcement\": true,
    \"integratedServices\": [
      \"AI_PLATFORM\"
    ],
    \"aiPlatformFloorSetting\": {
      ${AI_PLATFORM_SETTING}
    },
    \"floorSettingMetadata\": {
      \"multiLanguageDetection\": {
        \"enableMultiLanguageDetection\": true
      }
    },
    \"filterConfig\": {
      \"raiSettings\": {
        \"raiFilters\": [
          {\"filterType\": \"HATE_SPEECH\", \"confidenceLevel\": \"MEDIUM_AND_ABOVE\"},
          {\"filterType\": \"HARASSMENT\", \"confidenceLevel\": \"MEDIUM_AND_ABOVE\"},
          {\"filterType\": \"DANGEROUS\", \"confidenceLevel\": \"MEDIUM_AND_ABOVE\"},
          {\"filterType\": \"SEXUALLY_EXPLICIT\", \"confidenceLevel\": \"MEDIUM_AND_ABOVE\"}
        ]
      },
      \"piAndJailbreakFilterSettings\": {
        \"filterEnforcement\": \"ENABLED\",
        \"confidenceLevel\": \"LOW_AND_ABOVE\"
      },
      \"maliciousUriFilterSettings\": {
        \"filterEnforcement\": \"ENABLED\"
      },
      \"sdpSettings\": {
        \"basicConfig\": {
          \"filterEnforcement\": \"ENABLED\"
        }
      }
    }
  }")

HTTP_STATUS=$(echo "$RESPONSE" | grep "HTTP_STATUS" | cut -d':' -f2)
BODY=$(echo "$RESPONSE" | sed '/HTTP_STATUS/d')

if [ "$HTTP_STATUS" -eq 200 ]; then
  echo "✅ Floor Setting de Model Armor configurado exitosamente en el proyecto '$PROJECT_ID':"
  echo "$BODY"
else
  echo "❌ Error al configurar Floor Setting (HTTP $HTTP_STATUS):"
  echo "$BODY"
  exit 1
fi
