from fastapi import APIRouter

api_router = APIRouter()

@api_router.get("/status")
async def status():
    """
    Simple status endpoint.
    """
    return {"status": "ok"}
