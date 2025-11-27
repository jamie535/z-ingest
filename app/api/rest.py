"""REST API endpoints (health checks, buffer queries, stats)."""

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import text

router = APIRouter()


@router.get("/health")
async def health():
    """Health check endpoint (liveness probe)."""
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(request: Request):
    """Readiness check endpoint (includes dependency checks)."""
    app = request.app
    try:
        # Check Redis
        await app.state.redis.ping()

        # Check database
        async with app.state.db.get_session() as session:
            await session.execute(text("SELECT 1"))

        return {
            "status": "ready",
            "redis": "connected",
            "database": "connected"
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unavailable: {e}")


@router.get("/buffer/{user_id}/latest")
async def get_latest(user_id: str, request: Request, sample_type: str = "features"):
    """Get latest sample from buffer.

    Args:
        user_id: User identifier
        sample_type: Type of sample ("features" or "raw")
    """
    app = request.app
    if user_id not in app.state.buffers:
        raise HTTPException(404, "User buffer not found")

    # Get all samples, filter by type
    samples = await app.state.buffers[user_id].get_last_n(1, user_id, sample_type)
    if not samples:
        raise HTTPException(404, "No data in buffer")

    return samples[0]


@router.get("/buffer/{user_id}/last/{n}")
async def get_last_n(user_id: str, n: int, request: Request, sample_type: str = "features"):
    """Get last N samples from buffer.

    Args:
        user_id: User identifier
        n: Number of samples
        sample_type: Type of sample ("features" or "raw")
    """
    app = request.app
    if user_id not in app.state.buffers:
        raise HTTPException(404, "User buffer not found")

    return await app.state.buffers[user_id].get_last_n(n, user_id, sample_type)


@router.get("/buffer/{user_id}/stats")
async def get_buffer_stats(user_id: str, request: Request):
    """Get buffer statistics for a user."""
    app = request.app
    if user_id not in app.state.buffers:
        raise HTTPException(404, "User buffer not found")

    return await app.state.buffers[user_id].get_stats()


@router.get("/stats")
async def get_stats(request: Request):
    """Get server statistics."""
    app = request.app
    return {
        "connections": app.state.connections.get_stats(),
        "persistence": app.state.persistence.get_stats(),
        "buffers": {
            user_id: await buffer.get_stats()
            for user_id, buffer in app.state.buffers.items()
        }
    }
