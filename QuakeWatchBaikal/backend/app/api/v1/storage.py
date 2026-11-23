import os
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from app.core.config import settings
from app.core.s3 import upload_bytes_to_s3, upload_file_to_s3, list_s3_keys
from app.api.deps import get_current_user

router = APIRouter(prefix="/storage", tags=["S3 Storage"])


@router.get("/stats")
async def get_s3_stats(_user=Depends(get_current_user)):
    ss_keys = list_s3_keys("SS/")
    mt_keys = list_s3_keys("MT/")
    return {
        "bucket": settings.S3_BUCKET,
        "seed_files_count": len(ss_keys),
        "meteo_files_count": len(mt_keys),
        "total_objects": len(ss_keys) + len(mt_keys),
    }


@router.post("/upload")
async def upload_to_s3(
    category: str = Form(..., description="SS или MT"),
    year: str = Form(...),
    month: str = Form(...),
    day: str = Form(""),
    file: UploadFile = File(...),
    _user=Depends(get_current_user),
):
    cat = category.upper()
    if cat not in ("SS", "MT"):
        raise HTTPException(status_code=400, detail="Категория должна быть SS или MT")

    month_pad = month.zfill(2)
    if cat == "SS":
        if not day:
            raise HTTPException(status_code=400, detail="Для SS необходимо указать день (day)")
        s3_key = f"SS/{year}/{month_pad}/{day.zfill(2)}/{file.filename}"
    else:
        s3_key = f"MT/{year}/{month_pad}/{file.filename}"

    upload_bytes_to_s3(file.file, s3_key)
    return {"message": f"Файл загружен в S3: {s3_key}", "s3_key": s3_key}


@router.post("/sync-local")
async def sync_local_data_to_s3(
    limit: int = 500,
    _user=Depends(get_current_user),
):
    """Переносит существующие файлы из D:/data (SS и MT) в бакет MinIO S3."""
    existing_keys = set(list_s3_keys(""))
    uploaded = 0

    for sub in ("SS", "MT"):
        base_path = os.path.join(settings.DATA_DIR, sub)
        if not os.path.exists(base_path):
            continue
        for root, _, files in os.walk(base_path):
            for fname in files:
                if not (fname.endswith(".seed") or fname.endswith(".csv")):
                    continue
                full_path = os.path.join(root, fname)
                rel_path = os.path.relpath(full_path, settings.DATA_DIR).replace("\\", "/")
                if rel_path not in existing_keys:
                    upload_file_to_s3(full_path, rel_path)
                    uploaded += 1
                    if uploaded >= limit:
                        return {
                            "message": f"Загружена партия из {uploaded} файлов в S3 (вызовите повторно для продолжения)",
                            "uploaded": uploaded,
                        }

    return {"message": f"Синхронизация завершена. Новых файлов загружено в S3: {uploaded}", "uploaded": uploaded}
