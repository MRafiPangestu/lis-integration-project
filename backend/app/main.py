from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.deps import get_current_user
from app.api.main_router import api_router
from app.api.routers import auth as auth_router_module
from app.core.config import settings

# FastAPI's own /docs, /redoc, /openapi.json are development-only (OD-S2):
# disabled entirely when ENVIRONMENT=production, so they can never be part of
# the production anonymous surface. Not related to authentication of /api.
_is_production = settings.ENVIRONMENT.lower() == "production"

app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    docs_url=None if _is_production else "/docs",
    redoc_url=None if _is_production else "/redoc",
    openapi_url=None if _is_production else "/openapi.json",
)

# Explicit allowlist, fail closed (OD-S2 / design §9): an empty
# CORS_ALLOW_ORIGINS means no cross-origin access, never "*". Bearer tokens
# travel in a header, so allow_credentials=False removes the reflected-origin
# hazard a credentialed wildcard config would create (design §2.1).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# --- Deny-by-default mount (design §7.1) -------------------------------------
# Everything under /api requires authentication by default. A new router
# added to api_router is protected by construction; making something public
# requires deliberately mounting it outside this dependency, as auth_router is
# below — that is visible in review, which is the point.
app.include_router(api_router, prefix="/api", dependencies=[Depends(get_current_user)])

# The one explicit exception: login itself cannot require a token to obtain one.
app.include_router(auth_router_module.router, prefix="/api")


@app.get("/health")
def health_check():
    """The only anonymous runtime endpoint (OD-S2)."""
    return {"status": "ok", "message": "LIS API is running."}
