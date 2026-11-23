import os
import glob
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.redis import redis_client
from app.core.config import settings
from app.models.domain import Earthquake
from app.services.science import compute_polarization, compute_weather_spectrum, STATIONS
from app.api.deps import get_current_user
from datetime import datetime
from app.services.science import compute_polarization, compute_meteo_seismic_analysis, STATIONS


router = APIRouter(prefix="/analysis", tags=["Analysis"])


@router.get("/stations")
async def get_stations(_user=Depends(get_current_user)):
    return [{"code": code, **info} for code, info in STATIONS.items()]


@router.get("/polarization")
async def get_polarization(
    earthquake_id: int,
    station: str = Query("KYD"),
    days_before: int = Query(10, ge=1, le=60),
    days_after: int = Query(10, ge=0, le=60),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    cache_key = f"pol:v2:{earthquake_id}:{station}:{days_before}:{days_after}"
    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    result = await db.execute(select(Earthquake).where(Earthquake.id == earthquake_id))
    eq = result.scalar_one_or_none()
    if not eq:
        raise HTTPException(status_code=404, detail="Землетрясение не найдено")

    try:
        data = compute_polarization(
        eq_dt=eq.datetime_utc,
        energy_class=eq.energy_class,
        station_code=station.upper(),
        days_before=days_before,
        days_after=days_after,
    )
    except FileNotFoundError as e: 
        raise HTTPException(status_code=404, detail=str(e))

    await redis_client.setex(cache_key, 3600, json.dumps(data))
    return data


@router.get("/weather")
async def get_weather(
    earthquake_id: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    cache_key = f"weather:{earthquake_id}"
    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    result = await db.execute(select(Earthquake).where(Earthquake.id == earthquake_id))
    eq = result.scalar_one_or_none()
    if not eq:
        raise HTTPException(status_code=404, detail="Землетрясение не найдено")

    year = eq.datetime_utc.strftime("%Y")
    month = eq.datetime_utc.strftime("%m")
    mt_files = glob.glob(os.path.join(settings.DATA_DIR, "MT", year, month, "*.csv"))
    mt_file = mt_files[0] if mt_files else None

    data = compute_weather_spectrum(mt_file)
    await redis_client.setex(cache_key, 3600, json.dumps(data))
    return data

from datetime import datetime
from app.services.science import compute_polarization, compute_meteo_seismic_analysis, STATIONS


@router.get("/meteo-seismic")
async def get_meteo_seismic(
    start_time: str = Query(..., description="Формат YYYY-MM-DDTHH:MM:SS"),
    end_time: str = Query(..., description="Формат YYYY-MM-DDTHH:MM:SS"),
    station: str = Query("KYD"),
    channel: int = Query(2, ge=0, le=2),
    mt_station: str = Query("bugd"),
    f1: float = Query(1.0, gt=0),
    f2: float = Query(5.0, gt=0),
    _user=Depends(get_current_user),
):
    cache_key = f"mt_ss:{station}:{channel}:{mt_station}:{start_time}:{end_time}:{f1}:{f2}"
    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    try:
        dt1 = datetime.fromisoformat(start_time.replace("Z", ""))
        dt2 = datetime.fromisoformat(end_time.replace("Z", ""))
        if dt2 <= dt1:
            raise HTTPException(status_code=400, detail="Конец интервала должен быть позже начала")

        data = compute_meteo_seismic_analysis(
            dt1=dt1,
            dt2=dt2,
            ss_name=station.upper(),
            channel=channel,
            mt_station=mt_station,
            f1=f1,
            f2=f2,
        )
        await redis_client.setex(cache_key, 3600, json.dumps(data))
        return data
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=404, detail=str(e))
