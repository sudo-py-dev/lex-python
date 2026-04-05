from .session import AsyncSessionLocal, engine

async_session_local = AsyncSessionLocal


async def disconnect_db() -> None:
    """
    Disconnects the application from the database.
    Should be called during application shutdown.
    """
    await engine.dispose()
