from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from loguru import logger

# Import all functional routers
from app.routes import auth, ai, users, admin

# Initialize the Limiter using the client's IP address
limiter = Limiter(key_func=get_remote_address)

def create_app() -> FastAPI:
    """
    Initializes the FastAPI application, mounts routers, and configures middleware.
    """
    app = FastAPI(
        title="AIFlow SaaS Backend",
        version="1.0.0",
        docs_url="/v1/docs",
        openapi_url="/v1/openapi.json"
    )

    # 1. Register the SlowAPI Rate Limiter to the application state
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # 2. Security: Strict CORS Configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://app.aiflow-platform.com"], # Strict production domain
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    # 3. Route Registration
    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(ai.router)
    app.include_router(admin.router)

    return app

# Instantiate the application
app = create_app()

# 4. Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Catches all unhandled exceptions globally to prevent application crashes,
    logs the stack trace, and returns a standardized JSON error response.
    """
    logger.exception(f"Unhandled exception on {request.method} {request.url.path}: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred. Our engineers have been notified.",
            "path": request.url.path
        }
    )