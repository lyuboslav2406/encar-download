import requests
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from .config import GENERATED_DIR, HEADERS
from .generator import process_encar
from .image_service import get_image_path
from .models import GenerateRequest
from .report_service import build_report_url, extract_report_carid

router = APIRouter()


@router.post("/generate")
def generate(request: GenerateRequest):
    try:
        result = process_encar(request.url)
        return result
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex))


@router.post("/report-url")
def report_url(request: GenerateRequest):
    try:
        if "md/sl/mdsl_regcar.do" in request.url:
            carid = None
            for part in request.url.split("?")[1].split("&") if "?" in request.url else []:
                if part.startswith("carid="):
                    carid = part.split("=", 1)[1]
                    break
            if not carid:
                raise ValueError("Не успях да намеря carid в URL на репорта.")
            return {"carid": carid, "report_url": request.url}

        detail_html = requests.get(request.url, headers=HEADERS, timeout=30).text
        carid = extract_report_carid(detail_html)
        report_url = build_report_url(carid)
        return {"carid": carid, "report_url": report_url}
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
