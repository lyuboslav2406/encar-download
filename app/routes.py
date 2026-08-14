import requests
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from .config import GENERATED_DIR, HEADERS
from .generator import process_encar, process_price_summary
from .image_service import get_image_path
from .models import GenerateRequest
from .report_service import build_insurance_url, build_report_url, extract_carid_from_url, extract_report_carid
import os
import json
import logging

logger = logging.getLogger("encar.facebook")

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
            carid = extract_carid_from_url(request.url)
            if not carid:
                raise ValueError("Не успях да намеря carid в URL на репорта.")
            return {"carid": carid, "report_url": request.url}

        carid = extract_carid_from_url(request.url)
        if not carid:
            detail_html = requests.get(request.url, headers=HEADERS, timeout=30).text
            carid = extract_report_carid(detail_html)

        report_url = build_report_url(carid)
        return {"carid": carid, "report_url": report_url}
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex))


@router.post("/insurance-url")
def insurance_url(request: GenerateRequest):
    try:
        carid = extract_carid_from_url(request.url)
        if not carid:
            detail_html = requests.get(request.url, headers=HEADERS, timeout=30).text
            carid = extract_report_carid(detail_html)

        report_url = build_insurance_url(carid)
        return {"carid": carid, "report_url": report_url}
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex))


@router.post("/price-summary")
def price_summary(request: GenerateRequest):
    try:
        return process_price_summary(request.url)
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


@router.post("/publish-facebook")
def publish_facebook(request: Request, body: dict):
    """Publish selected images and message to configured Facebook Page.

    Expects JSON body: { "job_id": "...", "image_ids": ["img1.jpg", ...], "message": "..." }
    """
    try:
        page_id = os.environ.get("FACEBOOK_PAGE_ID")
        page_token = os.environ.get("FACEBOOK_PAGE_ACCESS_TOKEN")

        if not page_id or not page_token:
            raise HTTPException(status_code=500, detail="Facebook credentials not configured on server.")

        job_id = body.get("job_id")
        image_ids = body.get("image_ids") or []
        message = body.get("message") or ""

        # Publish each photo by uploading the local file (multipart/form-data)
        photo_fb_ids = []

        for image_name in image_ids:
            # resolve local image path (must already be downloaded into GENERATED_DIR/job_id)
            image_path = get_image_path(job_id, image_name)
            if not image_path.exists() or not image_path.is_file():
                raise HTTPException(status_code=400, detail=f"Image file not found or invalid: {image_name}")

            photo_endpoint = f"https://graph.facebook.com/v16.0/{page_id}/photos"

            with open(image_path, "rb") as fh:
                files = {"source": (image_name, fh, "image/jpeg")}
                data = {"published": "false", "access_token": page_token}
                resp = requests.post(photo_endpoint, files=files, data=data, timeout=60)

            try:
                resp_json = resp.json()
            except Exception:
                raise HTTPException(status_code=502, detail=f"Facebook photo upload failed for {image_name}: {resp.text}")

            # Debug: print photo upload outcome (filename, HTTP status, JSON response)
            try:
                print(f"facebook.photo_upload filename={image_name} status={resp.status_code} response={resp_json}", flush=True)
            except Exception:
                pass

            if resp.status_code != 200 or "id" not in resp_json:
                raise HTTPException(status_code=502, detail=f"Facebook photo upload failed for {image_name}: {resp_json}")

            photo_fb_ids.append(resp_json["id"])

        # Create feed post with attached_media if any
        feed_endpoint = f"https://graph.facebook.com/v16.0/{page_id}/feed"
        data = {"message": message, "access_token": page_token}

        if photo_fb_ids:
            attached = [{"media_fbid": fid} for fid in photo_fb_ids]
            # Debug: print attached_media structure (do not include tokens)
            try:
                print(f"facebook.attached_media {attached}", flush=True)
            except Exception:
                pass
            data["attached_media"] = json.dumps(attached)

        resp = requests.post(feed_endpoint, data=data, timeout=30)
        try:
            resp_json = resp.json()
        except Exception:
            raise HTTPException(status_code=502, detail=f"Facebook feed creation failed: {resp.text}")

        # Debug: print feed response (status and JSON)
        try:
            print(f"facebook.feed_create status={resp.status_code} response={resp_json}", flush=True)
        except Exception:
            pass

        if resp.status_code != 200 or "id" not in resp_json:
            raise HTTPException(status_code=502, detail=f"Facebook feed creation failed: {resp_json}")

        # Construct a readable post URL from the returned id (expected format: PAGEID_POSTID)
        post_full_id = resp_json.get("id")
        post_url = None
        if post_full_id:
            parts = str(post_full_id).split("_", 1)
            if len(parts) == 2:
                page_part, post_part = parts[0], parts[1]
            else:
                page_part = page_id
                post_part = parts[0]

            post_url = f"https://www.facebook.com/{page_part}/posts/{post_part}"

        return {"success": True, "post_id": post_full_id, "post_url": post_url}

    except HTTPException:
        raise
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex))
