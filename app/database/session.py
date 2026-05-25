from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config.settings import get_settings

settings = get_settings()

# Create the async engine. We disable echo in production to prevent log spam.
# Create the async engine. We disable echo in production to prevent log spam.
engine = create_async_engine(
    settings.DATABASE_URL, 
    echo=False,
    connect_args={"prepared_statement_cache_size": 0}  # Add this critical line
)

# Session factory for dependency injection
AsyncSessionLocal = async_sessionmaker(
    bind=engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

async def get_db() -> AsyncSession:
    """
    Dependency function that yields a database session for each request,
    ensuring it is safely closed after the request completes.
    """
    async with AsyncSessionLocal() as session:
        yield session