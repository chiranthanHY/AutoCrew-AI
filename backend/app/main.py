import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    
    app = FastAPI(
        title="AutoCrew AI",
        description="A multi-agent automation platform.",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    # Configure CORS middleware
    # For production, update this to your specific frontend domains
    origins = [
        "http://localhost",
        "http://localhost:3000",
        "http://localhost:5173",  # Vite default
        "http://localhost:8000",
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health check endpoint
    @app.get("/health", tags=["System"])
    async def health_check():
        """
        Health check endpoint to verify that the API is running.
        """
        return {"status": "ok", "service": "AutoCrew AI Backend"}

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    # This block allows running the file directly via `python main.py`
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
