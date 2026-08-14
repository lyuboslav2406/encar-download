from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import os
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, RedirectResponse

# Paths that should be protected for unauthenticated users (API or actions)
PROTECTED_PREFIXES = [
    "/generate",
    "/publish-facebook",
    "/image",
    "/download",
    "/report-url",
    "/insurance-url",
    "/price-summary",
    "/photos",
]

# Public paths that do not require authentication
PUBLIC_PATHS = ["/login", "/logout"]

from .config import STATIC_DIR
from .routes import router


def create_app() -> FastAPI:
    app = FastAPI()
    # Session secret is required for signed session cookies
    session_secret = os.environ.get("SESSION_SECRET")
    if not session_secret:
        raise RuntimeError("SESSION_SECRET environment variable must be set for session signing")

    # Use secure cookies by default (suitable for Render HTTPS). For local dev, set SESSION_COOKIE_SECURE=0 to disable.
    https_only = os.environ.get("SESSION_COOKIE_SECURE", "1") != "0"


    class AuthMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            path = request.url.path

            # Allow static assets needed for the login page and explicit public paths
            if path in PUBLIC_PATHS or path.startswith("/static") or path.startswith("/favicon") or path.startswith("/site.webmanifest"):
                return await call_next(request)

            # If session indicates authenticated, allow
            sess = request.session
            if sess and sess.get("authenticated"):
                return await call_next(request)

            # Unauthenticated: protect known API/action prefixes with JSON 401
            for p in PROTECTED_PREFIXES:
                if path.startswith(p):
                    return JSONResponse({"detail": "Authentication required"}, status_code=401)

            # Otherwise redirect browser requests to /login
            return RedirectResponse(url="/login")

    # Register the auth middleware first, then install SessionMiddleware last
    # so that SessionMiddleware runs earlier in the ASGI chain and
    # `request.session` is available to AuthMiddleware.
    app.add_middleware(AuthMiddleware)

    app.add_middleware(
        SessionMiddleware,
        secret_key=session_secret,
        session_cookie="session",
        https_only=https_only,
        same_site="lax",
    )
    app.include_router(router)
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
    return app
