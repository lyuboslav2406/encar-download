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
import threading
import uuid
import secrets
from enum import Enum
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Optional, Dict
from pathlib import Path

logger = logging.getLogger("encar.facebook")

router = APIRouter()

# ============================================================================
# Media token storage for Buffer public image URLs
# ============================================================================
# Maps token -> {job_id, image_names (list), expires_at}
_media_tokens_lock = threading.Lock()
_media_tokens: Dict[str, dict] = {}

# ============================================================================
# Background job processing for concurrent Encar generation
# ============================================================================

class JobStatus(str, Enum):
    """Job status enumeration"""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Job:
    """In-memory job record for background Encar processing"""
    job_id: str
    encar_url: str
    status: JobStatus
    result: Optional[dict] = None
    error: Optional[str] = None


# Global thread-safe job store and executor
_jobs_lock = threading.Lock()
_jobs: Dict[str, Job] = {}
_executor = ThreadPoolExecutor(max_workers=3)  # Max 3 concurrent vehicle jobs


def _process_job_background(job_id: str, url: str) -> None:
    """Process a single vehicle URL in the background (thread worker)"""
    try:
        # Mark as processing
        with _jobs_lock:
            if job_id in _jobs:
                _jobs[job_id].status = JobStatus.PROCESSING
        
        # Run existing single-vehicle generation
        result = process_encar(url)
        
        # Mark as completed with result
        with _jobs_lock:
            if job_id in _jobs:
                _jobs[job_id].result = result
                _jobs[job_id].status = JobStatus.COMPLETED
    except Exception as e:
        # Mark as failed with error
        with _jobs_lock:
            if job_id in _jobs:
                _jobs[job_id].error = str(e)
                _jobs[job_id].status = JobStatus.FAILED


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


@router.get("/buffer-media/{token}/{image_name}")
def get_buffer_media(token: str, image_name: str):
    """Public endpoint to serve images via Buffer media token.
    
    This endpoint is NOT protected by authentication and is used by Buffer
    to fetch images for posting. The token is cryptographically secure and
    server-side validated to prevent unauthorized access.
    """
    with _media_tokens_lock:
        if token not in _media_tokens:
            raise HTTPException(status_code=404, detail="Media token not found or expired.")
        
        token_data = _media_tokens[token]
        job_id = token_data["job_id"]
        allowed_images = token_data["image_names"]
    
    # Validate that the requested image is in the allowed list
    if image_name not in allowed_images:
        raise HTTPException(status_code=403, detail="Image not allowed for this token.")
    
    # Use the safe get_image_path to resolve and validate the path (prevents path traversal)
    image_path = get_image_path(job_id, image_name)

    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Снимката не е намерена.")

    return FileResponse(
        image_path,
        media_type="image/jpeg",
        filename=image_name
    )


# ============================================================================
# Helper functions for Buffer GraphQL integration
# ============================================================================

def generate_media_token(job_id: str, image_names: list) -> str:
    """Generate a cryptographically secure media token and store metadata server-side."""
    token = secrets.token_urlsafe(32)
    with _media_tokens_lock:
        _media_tokens[token] = {
            "job_id": job_id,
            "image_names": image_names,
        }
    return token


def build_buffer_media_url(request: Request, token: str, image_name: str) -> str:
    """Build the public URL for a Buffer media image using the media token."""
    base_url = str(request.base_url).rstrip("/")
    return f"{base_url}/buffer-media/{token}/{image_name}"


def validate_buffer_credentials() -> tuple:
    """Validate that Buffer API credentials are configured.
    
    Returns: (BUFFER_API_KEY, BUFFER_CHANNEL_ID)
    Raises: HTTPException if credentials missing
    """
    api_key = os.environ.get("BUFFER_API_KEY")
    channel_id = os.environ.get("BUFFER_CHANNEL_ID")
    
    if not api_key or not channel_id:
        raise HTTPException(
            status_code=500,
            detail="Buffer credentials not configured on server (BUFFER_API_KEY, BUFFER_CHANNEL_ID missing)."
        )
    
    return api_key, channel_id


def call_buffer_graphql(api_key: str, query: str, variables: dict = None) -> dict:
    """Call Buffer GraphQL API with a mutation and optional variables.
    
    Args:
        api_key: Buffer API key
        query: GraphQL query/mutation string
        variables: Optional dict of GraphQL variables
    
    Returns: GraphQL response dict with data or errors
    Raises: HTTPException on network or parsing errors
    """
    url = "https://api.buffer.com"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Buffer API connection failed: {str(e)}")
    
    try:
        data = resp.json()
    except Exception:
        raise HTTPException(status_code=502, detail=f"Buffer API response parse failed: {resp.text}")
    
    return data


@router.post("/publish-facebook")
def publish_facebook(request: Request, body: dict):
    """Publish selected images and message to Buffer (now, via shareNow mode).

    Expects JSON body: { "job_id": "...", "image_ids": ["img1.jpg", ...], "message": "..." }
    
    Uses Buffer GraphQL API with createPost mutation. Images are served publicly via
    cryptographically secure media tokens.
    """
    try:
        # Validate Buffer credentials are configured
        api_key, channel_id = validate_buffer_credentials()

        job_id = body.get("job_id")
        image_ids = body.get("image_ids") or []
        message = body.get("message") or ""

        # Validate job_id and that the job directory exists
        if not job_id:
            raise HTTPException(status_code=400, detail="job_id is required.")

        job_dir = GENERATED_DIR / job_id
        if not job_dir.exists():
            raise HTTPException(status_code=400, detail=f"Job directory not found: {job_id}")

        # Validate that all selected images exist
        for image_name in image_ids:
            image_path = get_image_path(job_id, image_name)
            if not image_path.exists() or not image_path.is_file():
                raise HTTPException(status_code=400, detail=f"Image file not found or invalid: {image_name}")

        # Generate a cryptographically secure media token for this job's images
        media_token = generate_media_token(job_id, image_ids)

        # Build Buffer asset URLs and structure with correct image nesting
        assets = []
        if image_ids:
            for image_name in image_ids:
                url = build_buffer_media_url(request, media_token, image_name)
                assets.append({"image": {"url": url}})

        # Build variables for GraphQL mutation (safe transport of arbitrary text)
        variables = {
            "input": {
                "text": message,
                "channelId": channel_id,
                "schedulingType": "automatic",
                "mode": "shareNow",
                "metadata": {
                    "facebook": {
                        "type": "post"
                    }
                }
            }
        }
        
        # Only include assets if there are images
        if assets:
            variables["input"]["assets"] = assets

        # GraphQL mutation with parameterized input and union response fragments
        mutation = '''
        mutation CreatePost($input: CreatePostInput!) {
            createPost(input: $input) {
                ... on PostActionSuccess {
                    post {
                        id
                        text
                        dueAt
                    }
                }
                ... on MutationError {
                    message
                }
            }
        }
        '''

        # Call Buffer GraphQL API with variables
        gql_response = call_buffer_graphql(api_key, mutation, variables)

        # Check for GraphQL parsing/execution errors
        if "errors" in gql_response and gql_response["errors"]:
            errors = gql_response["errors"]
            error_msg = "; ".join([str(e.get("message", str(e))) for e in errors])
            raise HTTPException(status_code=502, detail=f"Buffer GraphQL error: {error_msg}")

        # Extract response data
        if "data" not in gql_response or not gql_response["data"]:
            raise HTTPException(status_code=502, detail="Buffer API returned no data.")

        create_post_result = gql_response["data"].get("createPost")
        if not create_post_result:
            raise HTTPException(status_code=502, detail="Buffer API response missing createPost field.")

        # Handle MutationError fragment
        if "message" in create_post_result:
            error_message = create_post_result.get("message", "Unknown error")
            raise HTTPException(status_code=502, detail=f"Buffer API error: {error_message}")

        # Extract post ID from PostActionSuccess fragment
        post = create_post_result.get("post")
        if not post:
            raise HTTPException(status_code=502, detail="Buffer API response missing post object.")

        post_id = post.get("id")
        if not post_id:
            raise HTTPException(status_code=502, detail="Buffer API response missing post ID.")

        # Return response compatible with frontend (success, post_id, post_url as null)
        return {"success": True, "post_id": post_id, "post_url": None}

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


@router.post("/batch-generate")
def batch_generate(request: Request, body: dict):
    """Submit multiple Encar URLs for concurrent background processing.
    
    Request body: { "urls": ["url1", "url2", ...] }
    Response: { "job_ids": ["uuid1", "uuid2", ...] }
    """
    try:
        urls = body.get("urls", [])
        
        if not urls or not isinstance(urls, list):
            raise HTTPException(status_code=400, detail="At least one URL is required in 'urls' list")
        
        job_ids = []
        for url in urls:
            if not url or not isinstance(url, str):
                raise HTTPException(status_code=400, detail="All URLs must be non-empty strings")
            
            # Create job record
            job_id = str(uuid.uuid4())
            job = Job(
                job_id=job_id,
                encar_url=url,
                status=JobStatus.QUEUED
            )
            
            # Store job
            with _jobs_lock:
                _jobs[job_id] = job
            
            # Submit to executor (max 3 concurrent jobs enforced by ThreadPoolExecutor)
            _executor.submit(_process_job_background, job_id, url)
            job_ids.append(job_id)
        
        return {"job_ids": job_ids}
    
    except HTTPException:
        raise
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex))


@router.get("/batch-status")
def batch_status(request: Request):
    """Get status of all background jobs.
    
    Response: {
      "jobs": [
        { "job_id": "...", "status": "processing", "encar_url": "..." },
        { "job_id": "...", "status": "completed", "encar_url": "...", "result": {...} },
        { "job_id": "...", "status": "failed", "encar_url": "...", "error": "..." }
      ]
    }
    """
    try:
        jobs_data = []
        with _jobs_lock:
            for job in _jobs.values():
                job_data = {
                    "job_id": job.job_id,
                    "status": job.status.value,
                    "encar_url": job.encar_url
                }
                if job.result is not None:
                    job_data["result"] = job.result
                if job.error is not None:
                    job_data["error"] = job.error
                jobs_data.append(job_data)
        
        return {"jobs": jobs_data}
    
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex))
