"""M9.1a — deny-by-default regression test (design §7.2).

The control that actually prevents a future accidental exposure: enumerate
every route the app exposes and assert that anything not on the explicit
``PUBLIC_ROUTES`` allowlist carries ``get_current_user`` somewhere in its
dependency tree. A new router or endpoint added later to ``api_router`` is
protected by construction (it inherits the mount-level dependency in
``app.main``); this test is what turns "someone forgot to protect it" into a
build failure instead of a silent gap.

No database is used — this only introspects the FastAPI ``Dependant`` tree.
"""
from __future__ import annotations

import importlib
from typing import Iterable

from fastapi.routing import APIRoute

from app.api.deps import get_current_user

# The only endpoints that must be reachable with no credential at all.
# GET /health: OD-S2 — the sole anonymous runtime endpoint.
# POST /api/auth/login: cannot itself require the token it hands out.
PUBLIC_ROUTES: set[tuple[str, str]] = {
    ("GET", "/health"),
    ("POST", "/api/auth/login"),
}

# FastAPI's own documentation routes are a separate concern (OD-S2: dev-only,
# disabled in production — see test_docs_disabled_in_production /
# test_docs_enabled_in_development below), not part of the application data
# surface this allowlist protects.
_DOC_ROUTE_PATHS = {"/docs", "/redoc", "/docs/oauth2-redirect", "/openapi.json"}


def _requires_current_user(route: APIRoute) -> bool:
    """True if ``get_current_user`` appears anywhere in the route's
    dependency tree (directly, or nested under e.g. ``require_role``)."""

    def _walk(dependant) -> bool:
        if dependant.call is get_current_user:
            return True
        return any(_walk(sub) for sub in dependant.dependencies)

    return _walk(route.dependant)


def _iter_routes(app) -> Iterable[APIRoute]:
    for route in app.routes:
        if isinstance(route, APIRoute):
            yield route


def test_every_non_public_api_route_requires_authentication():
    from app.main import app

    unprotected = []
    for route in _iter_routes(app):
        if route.path in _DOC_ROUTE_PATHS:
            continue
        for method in sorted(route.methods or ()):
            if method == "HEAD":
                continue  # mirrors GET; not an independent route
            if (method, route.path) in PUBLIC_ROUTES:
                continue
            if not _requires_current_user(route):
                unprotected.append((method, route.path))

    assert unprotected == [], (
        f"routes reachable without authentication and not on PUBLIC_ROUTES: {unprotected}"
    )


def test_public_routes_are_exactly_the_documented_allowlist():
    """The inverse check: every route actually in PUBLIC_ROUTES exists, is
    anonymously reachable, and nothing extra has silently become public."""
    from app.main import app

    anonymous_routes = set()
    for route in _iter_routes(app):
        if route.path in _DOC_ROUTE_PATHS:
            continue
        for method in sorted(route.methods or ()):
            if method == "HEAD":
                continue
            if not _requires_current_user(route):
                anonymous_routes.add((method, route.path))

    assert anonymous_routes == PUBLIC_ROUTES


def test_health_endpoint_is_public():
    from fastapi.testclient import TestClient
    from app.main import app

    response = TestClient(app).get("/health")
    assert response.status_code == 200


def test_results_endpoint_rejects_anonymous_request():
    from fastapi.testclient import TestClient
    from app.main import app

    response = TestClient(app).get("/api/results")
    assert response.status_code == 401


# --------------------------------------------------------------------------- #
# CORS (OD-S2 / design §9): explicit allowlist, no credentialed wildcard.
# --------------------------------------------------------------------------- #


def test_cors_allowed_origin_is_reflected():
    from fastapi.testclient import TestClient
    from app.core.config import settings
    from app.main import app

    allowed_origin = settings.cors_allow_origins[0]
    response = TestClient(app).get("/health", headers={"Origin": allowed_origin})
    assert response.headers.get("access-control-allow-origin") == allowed_origin


def test_cors_disallowed_origin_gets_no_allow_header():
    from fastapi.testclient import TestClient
    from app.main import app

    response = TestClient(app).get(
        "/health", headers={"Origin": "https://not-an-allowed-origin.example"}
    )
    assert "access-control-allow-origin" not in {
        k.lower() for k in response.headers.keys()
    }


def test_cors_never_allows_credentials():
    """No wildcard-plus-credentials trap (design §2.1): allow_credentials is
    False, so the header must never be emitted, even for an allowed origin."""
    from fastapi.testclient import TestClient
    from app.core.config import settings
    from app.main import app

    allowed_origin = settings.cors_allow_origins[0]
    response = TestClient(app).get("/health", headers={"Origin": allowed_origin})
    assert "access-control-allow-credentials" not in {
        k.lower() for k in response.headers.keys()
    }


def test_cors_wildcard_is_not_configured():
    from app.core.config import settings

    assert "*" not in settings.cors_allow_origins


# --------------------------------------------------------------------------- #
# FastAPI docs (OD-S2): development only, disabled in production.
# --------------------------------------------------------------------------- #


def test_docs_enabled_in_development():
    from app.main import app

    # This test suite runs with ENVIRONMENT=development (backend/.env).
    assert app.docs_url == "/docs"
    assert app.redoc_url == "/redoc"
    assert app.openapi_url == "/openapi.json"


def test_docs_disabled_in_production(monkeypatch):
    """Reload app.main with ENVIRONMENT=production and assert the doc routes
    do not exist on the resulting app — not merely "unauthenticated"."""
    from app.core.config import settings
    import app.main as main_module

    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    try:
        reloaded = importlib.reload(main_module)
        assert reloaded.app.docs_url is None
        assert reloaded.app.redoc_url is None
        assert reloaded.app.openapi_url is None
        paths = {route.path for route in reloaded.app.routes}
        assert not (paths & _DOC_ROUTE_PATHS)
    finally:
        # Restore the development app for every other test module — those
        # already bound `from app.main import app` before this ran, so this
        # reload only affects `app.main`'s own module-level name, but keep
        # the environment consistent for anything that reloads later too.
        monkeypatch.undo()
        importlib.reload(main_module)
