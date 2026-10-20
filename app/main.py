import os
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.routes import router as api_router
from app.core.agent import armor_agent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("armor-agent")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-calentar en background clientes de Vertex AI Agent Engine y caché de Floor Settings
    asyncio.create_task(asyncio.to_thread(armor_agent.warmup))
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Demo de IA Chat con Google Cloud Armor + Model Armor + Gemini",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Router
app.include_router(api_router)

# Mount Static Files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", include_in_schema=False)
async def serve_index():
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(
            index_file,
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )
    return {"message": "Armor Agent Backend Running. Static UI not found."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
