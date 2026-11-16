import io
import csv
import json
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import LineString
from app.core.database import get_db
from app.core.redis import redis_client
from app.models.domain import Earthquake, Fault
from app.api.deps import get_current_user

router = APIRouter(tags=["Seismic"])


def _decode_text(raw_bytes: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            return raw_bytes.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ValueError("Не удалось определить кодировку файла (ожидается UTF-8 или Windows-1251)")


@router.get("/earthquakes")
async def get_earthquakes(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    min_energy_class: Optional[float] = Query(None),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    stmt = select(Earthquake)
    if start_date:
        stmt = stmt.where(Earthquake.datetime_utc >= datetime.fromisoformat(start_date.replace("Z", "")))
    if end_date:
        stmt = stmt.where(Earthquake.datetime_utc <= datetime.fromisoformat(end_date.replace("Z", "")))
    if min_energy_class is not None:
        stmt = stmt.where(Earthquake.energy_class >= min_energy_class)

    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/faults")
async def get_faults(db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    result = await db.execute(select(Fault))
    faults = result.scalars().all()
    response = []
    for f in faults:
        line = to_shape(f.geom)
        # Переворачиваем (lon, lat) из PostGIS в [lat, lon] для Leaflet
        coords = [[lat, lon] for lon, lat in line.coords]
        response.append({
            "id": f.id,
            "name": f.name,
            "fault_type": f.fault_type,
            "coordinates": coords,
        })
    return response


@router.post("/catalogs/upload")
async def upload_catalogs(
    earthquakes_file: Optional[UploadFile] = File(None),
    faults_file: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    if not earthquakes_file and not faults_file:
        raise HTTPException(status_code=400, detail="Выберите хотя бы один файл для загрузки")

    eq_count = 0
    fault_count = 0

    try:
        # 1. Парсинг каталога землетрясений (;lat;lon;K)
        if earthquakes_file:
            text = _decode_text(await earthquakes_file.read())
            delimiter = ";" if text[:1024].count(";") >= text[:1024].count(",") else ","
            reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
            if reader.fieldnames:
                reader.fieldnames = [name.strip().lower() for name in reader.fieldnames]

            await db.execute(delete(Earthquake))

            for idx, row in enumerate(reader, start=1):
                # В вашем файле первая колонка без имени ('') содержит дату '2020-01-09 19:58:57.0'
                time_raw = row.get("") or row.get("time") or row.get("datetime") or row.get("date")
                lat_raw = row.get("lat") or row.get("latitude")
                lon_raw = row.get("lon") or row.get("longitude")
                k_raw = row.get("k") or row.get("energy_class") or row.get("class") or "8.0"

                if not (time_raw and lat_raw and lon_raw):
                    continue

                dt_clean = datetime.fromisoformat(time_raw.strip().replace("Z", "").replace(" ", "T")).replace(tzinfo=None)
                depth = float(str(row.get("depth") or "10.0").replace(",", "."))

                db.add(Earthquake(
                    id=idx,
                    datetime_utc=dt_clean,
                    latitude=float(lat_raw.strip().replace(",", ".")),
                    longitude=float(lon_raw.strip().replace(",", ".")),
                    depth=depth,
                    energy_class=float(k_raw.strip().replace(",", ".")),
                    region=row.get("region") or "Байкальская рифтовая зона",
                ))
                eq_count += 1

        # 2. Парсинг каталога разломов (GeoJSON FeatureCollection)
        if faults_file:
            text = _decode_text(await faults_file.read())
            geojson = json.loads(text)
            features = geojson.get("features", [])
            await db.execute(delete(Fault))

            for idx, feat in enumerate(features, start=1):
                geom = feat.get("geometry") or {}
                props = feat.get("properties") or {}
                g_type = geom.get("type")
                coords = geom.get("coordinates") or []

                if g_type == "LineString" and len(coords) >= 2:
                    # В GeoJSON координаты уже идут в порядке [lon, lat] — идеально для PostGIS
                    line = LineString([(float(c[0]), float(c[1])) for c in coords])
                    name = props.get("Name") or props.get("ID") or f"Разлом #{idx}"
                    slip = props.get("Slip_sense") or "Не указан"
                    activity = props.get("Activity_degree") or "Не указана"
                    length_km = props.get("Length_km") or "?"
                    fault_info = f"{slip} | Активность: {activity} | L={length_km} км"

                    db.add(Fault(
                        id=idx,
                        name=str(name),
                        geom=from_shape(line, srid=4326),
                        fault_type=fault_info,
                    ))
                    fault_count += 1

        await db.commit()
        await redis_client.flushdb()
        return {
            "message": f"Успешно загружено: землетрясений — {eq_count}, разломов — {fault_count}",
            "earthquakes_count": eq_count,
            "faults_count": fault_count,
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"Ошибка разбора файла: {str(e)}")
