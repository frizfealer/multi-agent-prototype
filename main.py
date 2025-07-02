import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router
from src.api.session_routes import router as session_router
from src.core.config import settings
from src.core.session_manager import SessionManager
from src.db.base import DatabaseManager

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

# Database manager
db_manager = DatabaseManager(settings.database_url)


async def cleanup_expired_sessions():
    """Background task to clean up expired sessions every 5 minutes."""
    while True:
        try:
            async for session in db_manager.get_session():
                session_manager = SessionManager(session)
                count = await session_manager.cleanup_expired_sessions()
                if count > 0:
                    logger.info(f"Cleaned up {count} expired sessions")
        except Exception as e:
            logger.error(f"Error cleaning up sessions: {e}")
        
        await asyncio.sleep(300)  # 5 minutes


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing database...")
    await db_manager.init_db()
    logger.info("Database initialized successfully")
    
    # Start background tasks
    cleanup_task = asyncio.create_task(cleanup_expired_sessions())
    
    yield
    
    # Shutdown
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Triage Agent API", version="1.0.0", lifespan=lifespan)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(router, prefix="/api/v1")
app.include_router(session_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)