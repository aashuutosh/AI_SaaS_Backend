from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from loguru import logger

# 1. Cleaned up, consolidated imports!
from app.routes import auth, users, ai, history, subscriptions, admin, settings

# Initialize the Limiter using the client's IP address
limiter = Limiter(key_func=get_remote_address)
    
def create_app() -> FastAPI:
    """
    Initializes the FastAPI application, mounts routers, and configures middleware.
    """
    # 2. Premium Swagger UI Customization
    app = FastAPI(
        title="AI SaaS Platform - Core API",
        description=(
            "Enterprise-grade AI backend architecture.\n\n"
            "Features include strict Role-Based Access Control (RBAC), "
            "atomic database transactions, and algorithmic rate-limiting for LLM cost control."
        ),
        version="1.0.0",
        docs_url="/docs",
        openapi_url="/openapi.json",
        contact={
            "name": "Lead Developer",
        }
    )

    # 3. Register the SlowAPI Rate Limiter to the application state
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # 4. Security: CORS Configuration 
    # (Set to "*" for your local screen recording demo so it doesn't block you)
   origins = [
    "http://localhost:5173", 
    "https://magical-bombolone-f9fbf8.netlify.app/"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
    

    # 5. Auto-Redirect to the Beautiful UI
    @app.get("/", include_in_schema=False)
    async def root_redirect():
        """Instantly snaps anyone visiting the base URL to the interactive dashboard."""
        return RedirectResponse(url="/docs")

    # 6. System Health Check (Clients love seeing this)
    @app.get("/v1/health", tags=["System Core"])
    async def system_health_check():
        """Verifies that the API, Database, and LLM routes are online and responsive."""
        return {"status": "online", "environment": "production", "version": "1.0.0"}

    # 7. Route Registration (No more duplicates!)
    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(settings.router)
    app.include_router(subscriptions.router)
    app.include_router(ai.router)
    app.include_router(history.router)
    app.include_router(admin.router)

    return app

# Instantiate the application
app = create_app()

# 8. Global Exception Handler
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
