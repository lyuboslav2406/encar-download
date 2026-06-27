from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from .config import GENERATED_DIR
from .generator import process_encar
from .image_service import get_image_path
from .models import GenerateRequest

router = APIRouter()


@router.post("/generate")
def generate(request: GenerateRequest):
    try:
        result = process_encar(request.url)
        return result
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex))


@router.get("/download/{job_id}")
def download_zip(job_id: str):
    zip_path = GENERATED_DIR / job_id / "encar_images.zip"

    if not zip_path.exists():
        raise HTTPException(status_code=404, detail="ZIP файлът не е намерен.")

    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename="encar_images.zip"
    )


@router.get("/image/{job_id}/{image_name}")
def get_image(job_id: str, image_name: str):
    image_path = get_image_path(job_id, image_name)

    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Снимката не е намерена.")

    return FileResponse(
        image_path,
        media_type="image/jpeg",
        filename=image_name
    )


@router.get("/photos/{job_id}")
def get_photos(job_id: str, request: Request):
    job_dir = GENERATED_DIR / job_id

    if not job_dir.exists():
        raise HTTPException(status_code=404, detail="Папката със снимки не е намерена.")

    image_files = sorted(job_dir.glob("*.jpg"))
    base_url = str(request.base_url).rstrip("/")
    image_urls = [
        f"{base_url}/image/{job_id}/{image.name}"
        for image in image_files
    ]

    return {
        "job_id": job_id,
        "image_urls": image_urls,
        "images_count": len(image_urls)
    }
