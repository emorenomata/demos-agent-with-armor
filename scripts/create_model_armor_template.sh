#!/bin/bash
# Script para crear o verificar el Template oficial de Google Cloud Model Armor v1

set -e

PROJECT_ID=${1:-$PROJECT_ID}
LOCATION=${2:-"us-central1"}
TEMPLATE_ID=${3:-"armor-agent-template"}

if [ -z "$PROJECT_ID" ]; then
    echo "❌ Error: PROJECT_ID no está definido. Uso: ./scripts/create_model_armor_template.sh <PROJECT_ID> [LOCATION] [TEMPLATE_ID]"
    exit 1
fi

echo "🛡️ Obteniendo token de autenticación de GCP..."
ACCESS_TOKEN=$(gcloud auth print-access-token)

echo "🛡️ Creando Template de Model Armor: '$TEMPLATE_ID' en $LOCATION (Proyecto: $PROJECT_ID)..."

URL="https://modelarmor.${LOCATION}.rep.googleapis.com/v1/projects/${PROJECT_ID}/locations/${LOCATION}/templates?templateId=${TEMPLATE_ID}"

RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  "${URL}" \
  -d '{
    "filterConfig": {
      "raiSettings": {
        "raiFilters": [
          {"filterType": "HATE_SPEECH", "confidenceLevel": "MEDIUM_AND_ABOVE"},
          {"filterType": "HARASSMENT", "confidenceLevel": "MEDIUM_AND_ABOVE"},
          {"filterType": "DANGEROUS", "confidenceLevel": "MEDIUM_AND_ABOVE"},
          {"filterType": "SEXUALLY_EXPLICIT", "confidenceLevel": "MEDIUM_AND_ABOVE"}
        ]
      },
      "piAndJailbreakFilterSettings": {
        "filterEnforcement": "ENABLED",
        "confidenceLevel": "MEDIUM_AND_ABOVE"
      },
      "maliciousUriFilterSettings": {
        "filterEnforcement": "ENABLED"
      },
      "sdpSettings": {
        "basicConfig": {
          "filterEnforcement": "ENABLED"
        }
      }
    }
  }')

HTTP_STATUS=$(echo "$RESPONSE" | grep "HTTP_STATUS" | cut -d':' -f2)
BODY=$(echo "$RESPONSE" | sed '/HTTP_STATUS/d')

if [ "$HTTP_STATUS" -eq 200 ] || [ "$HTTP_STATUS" -eq 201 ]; then
    echo "✅ Template de Model Armor creado exitosamente en Google Cloud:"
    echo "$BODY"
elif [ "$HTTP_STATUS" -eq 409 ]; then
    echo "ℹ️ El Template '$TEMPLATE_ID' ya existe en Google Cloud Model Armor (listo para usarse)."
else
    echo "⚠️ Respuesta de la API (Status $HTTP_STATUS):"
    echo "$BODY"
fi
