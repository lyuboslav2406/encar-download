import requests
import os
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, JSONResponse

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


@router.get("/login")
def login_page(request: Request):
        html = """
        <!doctype html>
        <html>
            <head><meta charset="utf-8"><title>StreamLine Auto - Login</title></head>
            <body style="background:#111;color:#fff;font-family:Arial,Helvetica,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;">
                <div style="width:320px;padding:24px;border-radius:12px;background:#1b1b1b;border:1px solid rgba(255,255,255,0.06);">
                    <h2 style="margin:0 0 12px">StreamLine Auto</h2>
                    <form method="post" action="/login">
                        <input name="password" type="password" placeholder="Password" style="width:100%;padding:10px;border-radius:8px;border:1px solid rgba(255,255,255,0.06);margin-bottom:12px;background:#111;color:#fff;" />
                        <button type="submit" style="width:100%;padding:10px;border-radius:8px;background:#d61c1c;color:#fff;border:none;font-weight:700">Login</button>
                    </form>
                </div>
            </body>
        </html>
        """
        return HTMLResponse(html)


@router.post("/login")
async def login(request: Request):
    # Read password from form or JSON body
    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            body = await request.json()
            password = body.get("password", "")
        else:
            form = await request.form()
            password = form.get("password", "")
    except Exception:
        password = ""

    app_password = os.environ.get("APP_PASSWORD")
    if not app_password:
        return JSONResponse({"detail": "Server not configured: APP_PASSWORD missing"}, status_code=500)

    if password != app_password:
        # For form submission, redirect back to login with an error query
        # Simpler: return a minimal HTML page with error
        return HTMLResponse("<p style='color:#faa'>Incorrect password.</p><p><a href='/login'>Back</a></p>", status_code=401)

    # successful login: mark session
    request.session["authenticated"] = True
    return RedirectResponse(url="/", status_code=302)


@router.get("/logout")
def logout(request: Request):
    try:
        request.session.pop("authenticated", None)
    except Exception:
        pass
    return RedirectResponse(url="/login")


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


@router.post("/schedule-facebook")
def schedule_facebook(request: Request, body: dict):
    """Schedule selected images and message to configured Facebook Page for future publishing.

    Expects JSON body: { "job_id": "...", "image_ids": ["img1.jpg", ...], "message": "...", "scheduled_publish_time": <Unix timestamp> }
    """
    import time
    
    try:
        page_id = os.environ.get("FACEBOOK_PAGE_ID")
        page_token = os.environ.get("FACEBOOK_PAGE_ACCESS_TOKEN")

        if not page_id or not page_token:
            raise HTTPException(status_code=500, detail="Facebook credentials not configured on server.")

        job_id = body.get("job_id")
        image_ids = body.get("image_ids") or []
        message = body.get("message") or ""
        scheduled_publish_time = body.get("scheduled_publish_time")

        # Validate scheduled_publish_time
        if scheduled_publish_time is None:
            raise HTTPException(status_code=400, detail="scheduled_publish_time is required.")

        try:
            scheduled_timestamp = int(scheduled_publish_time)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="scheduled_publish_time must be a valid Unix timestamp.")

        # Validate: at least 10 minutes in future, no more than 30 days in future
        current_timestamp = int(time.time())
        min_timestamp = current_timestamp + (10 * 60)  # 10 minutes
        max_timestamp = current_timestamp + (30 * 24 * 60 * 60)  # 30 days

        if scheduled_timestamp < min_timestamp:
            raise HTTPException(status_code=400, detail="Scheduled time must be at least 10 minutes in the future.")

        if scheduled_timestamp > max_timestamp:
            raise HTTPException(status_code=400, detail="Scheduled time must be no more than 30 days in the future.")

        # Upload each photo by uploading the local file (multipart/form-data)
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

            # Debug: print photo upload outcome
            try:
                print(f"facebook.photo_upload filename={image_name} status={resp.status_code} response={resp_json}", flush=True)
            except Exception:
                pass

            if resp.status_code != 200 or "id" not in resp_json:
                raise HTTPException(status_code=502, detail=f"Facebook photo upload failed for {image_name}: {resp_json}")

            photo_fb_ids.append(resp_json["id"])

        # Create feed post with attached_media if any, and scheduled_publish_time
        feed_endpoint = f"https://graph.facebook.com/v16.0/{page_id}/feed"
        data = {"message": message, "access_token": page_token, "published": "false", "scheduled_publish_time": scheduled_timestamp}

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
            raise HTTPException(status_code=502, detail=f"Facebook feed scheduling failed: {resp.text}")

        # Debug: print feed response (status and JSON)
        try:
            print(f"facebook.feed_schedule status={resp.status_code} response={resp_json}", flush=True)
        except Exception:
            pass

        if resp.status_code != 200 or "id" not in resp_json:
            raise HTTPException(status_code=502, detail=f"Facebook feed scheduling failed: {resp_json}")

        # Return success with scheduled post ID (no URL for scheduled posts)
        post_full_id = resp_json.get("id")

        return {"success": True, "scheduled_post_id": post_full_id}

    except HTTPException:
        raise
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex))
