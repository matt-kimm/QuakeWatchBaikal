from fastapi import APIRouter
from app.api.v1 import auth, seismic, analysis, storage

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(seismic.router)
api_router.include_router(analysis.router)
api_router.include_router(storage.router)
