# Lightweight Python Base
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

WORKDIR /workspace

# Install dependencies
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code and Agent Engine IDs mapping
COPY app/ /workspace/app/
COPY .agent_engine_ids.json .agent_engine_id* /workspace/

# Expose port (Cloud Run default: 8080)
EXPOSE 8080

# Run FastAPI app with Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
