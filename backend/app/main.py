import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .config import get_settings
from .db import Base, engine
from .limits import limiter
from .routes_admin import router as admin_router
from .routes_auth import router as auth_router
from .routes_submissions import router as submissions_router

settings = get_settings()
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    if settings.seed_demo:
        from .seed import seed_if_empty

        seed_if_empty()
    yield


app = FastAPI(
    title="VendorGuard API",
    lifespan=lifespan,
    docs_url=None if settings.is_prod else "/docs",
    redoc_url=None,
    openapi_url=None if settings.is_prod else "/openapi.json",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.middleware("http")
async def csrf_and_headers(request: Request, call_next):
    # CSRF defence: browsers cannot add a custom header on a cross-site form post, so requiring one
    # (together with SameSite=Lax cookies and no CORS) blocks forged state-changing requests.
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.headers.get("x-requested-with") != "fetch":
        return JSONResponse({"detail": "Missing required request header"}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Cache-Control"] = "no-store"
    return response


app.include_router(auth_router)
app.include_router(submissions_router)
app.include_router(admin_router)


@app.get("/health")
def health():
    return {"ok": True}
