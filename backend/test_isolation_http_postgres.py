"""Cross-user isolation over real HTTP against a migrated PostgreSQL database.

Two users register, verify (through the captured email link) and log in with
separate cookie jars. User A creates every kind of owned resource; each
resource-bearing route is then attacked by user B. Only the external services
(Anthropic, Groq, Chromium, SMTP) are mocked.
"""
import re
import uuid
from contextlib import ExitStack
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import text

import db
import main
from postgres_test_support import alembic_config, disposable_postgres_database
from routes import auth as auth_routes
from routes.test_generate import _tailored_resume
from services import auth_service
from services.build_resume_pdf import PdfBuildResult
from services.claude_service import ATSScoreResult, KeywordExtractionResult
from services.cover_letter_service import CoverLetterResult

PASSWORD = "valid-password-123"
JOB_DESCRIPTION = "Build reliable APIs with Python and FastAPI."

# Every route in the app must be listed in exactly one of these sets, so a new
# route cannot ship without isolation coverage or an explicit exemption.
ISOLATION_COVERED = {
    ("GET", "/api/master-resumes"),
    ("POST", "/api/master-resumes"),
    ("GET", "/api/master-resumes/{record_id}"),
    ("PUT", "/api/master-resumes/{record_id}"),
    ("DELETE", "/api/master-resumes/{record_id}"),
    ("POST", "/api/master-resumes/{record_id}/seed-dictionary"),
    ("POST", "/api/extract-keywords"),
    ("POST", "/api/generate-resume"),
    ("GET", "/api/history"),
    ("GET", "/api/history/{record_id}"),
    ("DELETE", "/api/history/{record_id}"),
    ("POST", "/api/history/{record_id}/restore"),
    ("GET", "/api/download-history/{record_id}"),
    ("GET", "/api/download-history-cover-letter/{record_id}"),
    ("GET", "/api/download/{filename}"),
    ("POST", "/api/preview-html"),
    ("POST", "/api/download-custom"),
    ("POST", "/api/regenerate-section"),
    ("POST", "/api/generate-cover-letter"),
    ("POST", "/api/download-cover-letter"),
    ("GET", "/api/resumes"),
}
# Authenticated, but they neither read nor write any stored user data.
STATELESS_AUTHENTICATED = {
    ("POST", "/api/resumes/parse"),  # parses an upload in memory, retains nothing
}
# Intentionally reachable without a session.
PUBLIC = {
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/logout"),
    ("POST", "/api/auth/password-reset"),
    ("POST", "/api/auth/password-reset/confirm"),
    ("POST", "/api/auth/register"),
    ("POST", "/api/auth/verify-email"),
    ("GET", "/health"),
    ("GET", "/health/ready"),
    ("GET", "/docs"),
    ("GET", "/docs/oauth2-redirect"),
    ("GET", "/openapi.json"),
    ("GET", "/redoc"),
    # Needs a session cookie but answers 401 itself rather than through the
    # /api/ middleware, so it is checked in the authentication tests instead.
    ("GET", "/api/auth/me"),
}


def _app_routes() -> set[tuple[str, str]]:
    """Every (method, path) registered on the app, including included routers."""
    found: set[tuple[str, str]] = set()

    def walk(routes, prefix=""):
        for route in routes:
            if type(route).__name__ == "_IncludedRouter":
                walk(
                    route.original_router.routes,
                    prefix + (getattr(route.include_context, "prefix", "") or ""),
                )
            elif getattr(route, "methods", None):
                for method in route.methods - {"HEAD", "OPTIONS"}:
                    found.add((method, prefix + route.path))

    walk(main.app.routes)
    return found


# ── Environment ───────────────────────────────────────────────────────────────

def _write_pdf(*args, **kwargs):
    output_path = kwargs.get("output_path") or args[1]
    output_path.write_bytes(b"%PDF-1.4 isolation test")
    return PdfBuildResult(output_path, 1, True)


def _write_letter_pdf(letter, output_path, *args, **kwargs):
    output_path.write_bytes(b"%PDF-1.4 isolation letter")


def _ats_result() -> ATSScoreResult:
    return ATSScoreResult(
        overall_score=80, keyword_coverage=0.5, matched_keywords=["Python"],
        missing_keywords=["Docker"], suggestions=[], raw_response="",
    )


def _patch_external_services(stack: ExitStack) -> dict[str, MagicMock]:
    """Mock every paid or browser-backed boundary; return the mocks by name."""
    mocks = {
        "extract_keywords": MagicMock(return_value=KeywordExtractionResult(
            hard_skills=["Python"], soft_skills=[], tools_and_technologies=[],
            job_titles=[], certifications=[], priority_keywords=[], raw_response="",
        )),
        "tailor_resume": MagicMock(side_effect=lambda **kwargs: _tailored_resume()),
        "score_resume": MagicMock(return_value=_ats_result()),
        "build_pdf": MagicMock(side_effect=_write_pdf),
        "regenerate_summary": MagicMock(return_value="Alternative summary"),
        "regenerate_bullets": MagicMock(return_value=[]),
        "regenerate_score": MagicMock(return_value=_ats_result()),
        "generate_cover_letter": MagicMock(return_value=CoverLetterResult(
            letter="Dear Hiring Manager, A's private letter.", word_count=6,
            company="Acme", job_title="Engineer",
        )),
        "cover_letter_pdf": MagicMock(side_effect=_write_letter_pdf),
        "history_letter_pdf": MagicMock(side_effect=_write_letter_pdf),
        "preview_pdf": MagicMock(side_effect=_write_pdf),
        "seed_skill_dictionary": MagicMock(return_value={"status": "seeded", "term_count": 1}),
    }
    targets = {
        "extract_keywords": "routes.extract.claude_extract_keywords",
        "tailor_resume": "routes.generate.tailor_resume",
        "score_resume": "routes.generate.score_resume",
        "build_pdf": "routes.generate.build_pdf",
        "regenerate_summary": "routes.regenerate.regenerate_summary",
        "regenerate_bullets": "routes.regenerate.regenerate_bullets",
        "regenerate_score": "routes.regenerate.score_resume",
        "generate_cover_letter": "routes.cover_letter.generate_cover_letter",
        "cover_letter_pdf": "routes.cover_letter.build_cover_letter_pdf",
        "history_letter_pdf": "routes.history.build_cover_letter_pdf",
        "preview_pdf": "routes.preview.build_pdf_with_overrides",
        "seed_skill_dictionary": "routes.master_resumes.seed_skill_dictionary",
    }
    for name, target in targets.items():
        stack.enter_context(patch(target, mocks[name]))
    return mocks


def _apply_http_patches(monkeypatch, database_url: str) -> None:
    """Point the real middleware at the migrated database with real auth."""
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("DATABASE_PASSWORD_FILE", "")
    monkeypatch.setenv("AUTH_TOKEN_PEPPER", "isolation-test-pepper")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "false")
    monkeypatch.setenv("STATIC_PROFILES_ENABLED", "false")
    main.app.dependency_overrides.clear()
    monkeypatch.setattr(main, "get_session", db.get_session)
    monkeypatch.setattr(main, "get_current_user", auth_service.get_current_user)


def _master_payload(name: str = "Jamie Rivera") -> dict:
    return {
        "resume": {
            "contact": {
                "name": name, "email": "jamie@example.com", "phone": "",
                "location": "Chicago, IL", "linkedin": "", "portfolio": "",
            },
            "targetRole": "Platform Engineer",
            "targetJobTitle": "Software Engineer",
            "summary": "Platform engineer.",
            "experience": [{
                "company": "Example Co", "title": "Engineer", "location": "",
                "startDate": "2020-01", "endDate": "2024-01",
                "highlights": "Built an API.",
            }],
            "education": [],
            "skills": [{"key": "backend", "category": "Backend", "items": ["Python", "FastAPI"]}],
            "projects": [],
            "certifications": [],
        }
    }


# ── World: two real users and user A's resources ─────────────────────────────

@dataclass
class Ids:
    master: str
    history: str
    session: str
    filename: str


@dataclass
class World:
    a: TestClient
    b: TestClient
    anon: TestClient
    engine: object
    sent_urls: list[str]
    a_ids: Ids
    b_ids: Ids
    a_snapshot: dict


def _register_verify_login(client: TestClient, sent_urls: list[str], email: str) -> None:
    credentials = {"email": email, "password": PASSWORD}
    assert client.post("/api/auth/register", json=credentials).status_code == 202
    token = sent_urls.pop().split("token=")[1]
    assert client.post("/api/auth/verify-email", json={"token": token}).status_code == 200
    assert client.post("/api/auth/login", json=credentials).status_code == 200


def _create_resources(client: TestClient, name: str = "Jamie Rivera") -> Ids:
    """Create a master resume, a generated history record, and a cover letter."""
    created = client.post("/api/master-resumes", json=_master_payload(name))
    assert created.status_code == 201, created.text
    master_id = created.json()["id"]

    generated = client.post("/api/generate-resume", json={
        "job_description": JOB_DESCRIPTION, "selected_keywords": ["Python"],
        "company": "Acme", "job_title": "Engineer", "master_resume_id": master_id,
    })
    assert generated.status_code == 200, generated.text
    body = generated.json()
    assert body["pdf_url"], body

    letter = client.post("/api/generate-cover-letter", json={
        "session_id": body["session_id"], "history_id": body["history_id"],
        "job_description": JOB_DESCRIPTION, "company": "Acme", "job_title": "Engineer",
    })
    assert letter.status_code == 200, letter.text
    return Ids(
        master=master_id, history=body["history_id"], session=body["session_id"],
        filename=body["pdf_url"].rsplit("/", 1)[1],
    )


def _snapshot(client: TestClient, ids: Ids) -> dict:
    """Everything observable about one user's resources, for before/after checks."""
    def get(path):
        response = client.get(path)
        return response.status_code, response.content
    preview = client.post("/api/preview-html", json={"session_id": ids.session})
    return {
        "master": get(f"/api/master-resumes/{ids.master}"),
        "master_list": get("/api/master-resumes"),
        "history": get(f"/api/history/{ids.history}"),
        "history_list": get("/api/history"),
        "pdf": get(f"/api/download/{ids.filename}"),
        "history_pdf": get(f"/api/download-history/{ids.history}"),
        "preview": (preview.status_code, preview.content),
    }


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    module_patch = pytest.MonkeyPatch()
    with disposable_postgres_database() as database_url:
        command.upgrade(alembic_config(database_url), "head")
        db.get_engine.cache_clear()
        _apply_http_patches(module_patch, database_url.render_as_string(hide_password=False))
        engine = db.get_engine()

        # Rate limits are not under test here; keep them out of the way.
        for name in (
            "API_RATE_LIMIT_MAX_REQUESTS", "READ_RATE_LIMIT_MAX_REQUESTS",
            "AUTH_LOGIN_RATE_LIMIT_MAX_REQUESTS", "AUTH_REGISTER_RATE_LIMIT_MAX_REQUESTS",
            "RATE_LIMIT_MAX_REQUESTS", "AI_USER_RATE_LIMIT_MAX_REQUESTS",
        ):
            module_patch.setattr(main, name, 10**9)

        outputs = tmp_path_factory.mktemp("outputs")
        for module in ("generate", "history", "cover_letter", "preview"):
            module_patch.setattr(f"routes.{module}.OUTPUTS_DIR", outputs)
        sent_urls: list[str] = []
        module_patch.setattr(
            auth_routes, "send_email", lambda recipient, subject, url: sent_urls.append(url)
        )

        with ExitStack() as stack:
            _patch_external_services(stack)
            a = stack.enter_context(TestClient(main.app))
            b = stack.enter_context(TestClient(main.app))
            anon = stack.enter_context(TestClient(main.app))
            _register_verify_login(a, sent_urls, "user-a@example.com")
            _register_verify_login(b, sent_urls, "user-b@example.com")
            a_ids = _create_resources(a, "Alice Anderson")
            b_ids = _create_resources(b, "Bob Brown")
            yield World(a, b, anon, engine, sent_urls, a_ids, b_ids, _snapshot(a, a_ids))

        engine.dispose()
        db.get_engine.cache_clear()
    # The process-wide limiter buckets outlive this module; leave them empty so
    # the rate-limit tests in test_main.py start from a clean window.
    for buckets in (
        main._api_rate_limit_hits, main._read_rate_limit_hits, main._auth_rate_limit_hits,
        main._ai_user_rate_limit_hits, main._rate_limit_hits,
    ):
        buckets.clear()
    module_patch.undo()


@pytest.fixture(autouse=True)
def http_environment(request, isolate_http_app, monkeypatch):
    """Undo the root conftest's per-test SQLite and auth stubs, then mock services.

    Only tests that use the `world` fixture need this; the route-coverage guard
    runs without a database.
    """
    if "world" not in request.node.fixturenames:
        yield {}
        return
    world = request.getfixturevalue("world")
    _apply_http_patches(
        monkeypatch, world.engine.url.render_as_string(hide_password=False)
    )
    with ExitStack() as stack:
        mocks = _patch_external_services(stack)
        mocks["allow_calls"] = False
        yield mocks
        # A denied request must never reach a paid API or a browser.
        if not mocks["allow_calls"]:
            reached = [name for name, mock in mocks.items()
                       if isinstance(mock, MagicMock) and mock.called]
            assert not reached, f"Denied request reached external services: {reached}"


@pytest.fixture
def ai(http_environment):
    """Opt a test out of the no-external-calls check (positive controls)."""
    http_environment["allow_calls"] = True
    return http_environment


# ── Operations: one callable per resource-bearing route ──────────────────────

def _letter_resume(name: str) -> dict:
    return {"contact": {"name": name}, "summary": "Own supplied resume."}


OPERATIONS = {
    "GET master": lambda c, i: c.get(f"/api/master-resumes/{i.master}"),
    "PUT master": lambda c, i: c.put(
        f"/api/master-resumes/{i.master}", json=_master_payload("Hijacked Name")),
    "DELETE master": lambda c, i: c.delete(f"/api/master-resumes/{i.master}"),
    "POST seed-dictionary": lambda c, i: c.post(
        f"/api/master-resumes/{i.master}/seed-dictionary"),
    "POST extract-keywords (master)": lambda c, i: c.post(
        "/api/extract-keywords",
        json={"job_description": JOB_DESCRIPTION, "master_resume_id": i.master}),
    "POST generate-resume (master)": lambda c, i: c.post(
        "/api/generate-resume",
        json={"job_description": JOB_DESCRIPTION, "master_resume_id": i.master}),
    "GET history": lambda c, i: c.get(f"/api/history/{i.history}"),
    "DELETE history": lambda c, i: c.delete(f"/api/history/{i.history}"),
    "POST history restore": lambda c, i: c.post(f"/api/history/{i.history}/restore"),
    "GET download-history": lambda c, i: c.get(f"/api/download-history/{i.history}"),
    "GET download-history-cover-letter": lambda c, i: c.get(
        f"/api/download-history-cover-letter/{i.history}"),
    "GET download (A's PDF filename)": lambda c, i: c.get(f"/api/download/{i.filename}"),
    "POST preview-html": lambda c, i: c.post(
        "/api/preview-html", json={"session_id": i.session}),
    "POST download-custom": lambda c, i: c.post(
        "/api/download-custom", json={"session_id": i.session}),
    "POST regenerate-section": lambda c, i: c.post("/api/regenerate-section", json={
        "session_id": i.session, "section": "summary", "job_description": JOB_DESCRIPTION}),
    "POST generate-cover-letter (session)": lambda c, i: c.post(
        "/api/generate-cover-letter",
        json={"session_id": i.session, "job_description": JOB_DESCRIPTION}),
    "POST generate-cover-letter (history)": lambda c, i: c.post(
        "/api/generate-cover-letter", json={
            "history_id": i.history, "tailored_resume": _letter_resume("Bob Brown"),
            "job_description": JOB_DESCRIPTION}),
    "POST download-cover-letter (history)": lambda c, i: c.post(
        "/api/download-cover-letter",
        json={"letter": "Dear Hiring Manager, overwritten by B.", "history_id": i.history}),
}


# (method, path) each operation exercises, checked against ISOLATION_COVERED below.
OPERATION_ROUTES = {'GET master': ('GET', '/api/master-resumes/{record_id}'),
    'PUT master': ('PUT', '/api/master-resumes/{record_id}'),
    'DELETE master': ('DELETE', '/api/master-resumes/{record_id}'),
    'POST seed-dictionary': ('POST', '/api/master-resumes/{record_id}/seed-dictionary'),
    'POST extract-keywords (master)': ('POST', '/api/extract-keywords'),
    'POST generate-resume (master)': ('POST', '/api/generate-resume'),
    'GET history': ('GET', '/api/history/{record_id}'),
    'DELETE history': ('DELETE', '/api/history/{record_id}'),
    'POST history restore': ('POST', '/api/history/{record_id}/restore'),
    'GET download-history': ('GET', '/api/download-history/{record_id}'),
    'GET download-history-cover-letter': ('GET', '/api/download-history-cover-letter/{record_id}'),
    "GET download (A's PDF filename)": ('GET', '/api/download/{filename}'),
    'POST preview-html': ('POST', '/api/preview-html'),
    'POST download-custom': ('POST', '/api/download-custom'),
    'POST regenerate-section': ('POST', '/api/regenerate-section'),
    'POST generate-cover-letter (session)': ('POST', '/api/generate-cover-letter'),
    'POST generate-cover-letter (history)': ('POST', '/api/generate-cover-letter'),
    'POST download-cover-letter (history)': ('POST', '/api/download-cover-letter')}


def _ghost_ids() -> Ids:
    """Well-formed identifiers that exist for nobody."""
    return Ids(
        master=uuid.uuid4().hex, history=uuid.uuid4().hex, session=uuid.uuid4().hex,
        filename="Ghost-Co-Role_Resume_deadbeef.pdf",
    )


def _outcome(response):
    return response.status_code, response.json()


@pytest.mark.parametrize("operation", OPERATIONS)
def test_owner_can_use_the_route_so_a_denial_is_meaningful(world, ai, operation):
    """Control: a user acting on their own fresh resources succeeds on every route.

    A throwaway user is used so A's lists and snapshot stay untouched.
    """
    owner = TestClient(main.app)
    _register_verify_login(owner, world.sent_urls, f"control-{uuid.uuid4().hex[:8]}@example.com")
    ids = _create_resources(owner)

    response = OPERATIONS[operation](owner, ids)

    assert response.status_code == 200, f"{operation}: {response.status_code} {response.text}"


@pytest.mark.parametrize("operation", OPERATIONS)
def test_other_user_gets_404_identical_to_a_nonexistent_id(world, operation):
    attempt = OPERATIONS[operation](world.b, world.a_ids)
    ghost = OPERATIONS[operation](world.b, _ghost_ids())

    assert attempt.status_code == 404, f"{operation}: {attempt.status_code} {attempt.text}"
    assert _outcome(attempt) == _outcome(ghost), "response differs from a nonexistent ID"
    assert _snapshot(world.a, world.a_ids) == world.a_snapshot, "A's data changed"


def test_denied_cover_letter_attempts_leave_the_stored_letter_untouched(world):
    OPERATIONS["POST download-cover-letter (history)"](world.b, world.a_ids)

    record = world.a.get(f"/api/history/{world.a_ids.history}").json()

    assert record["cover_letter"] == "Dear Hiring Manager, A's private letter."


# ── Lists and static profiles ─────────────────────────────────────────────────

def test_lists_contain_only_the_callers_own_items(world):
    a_history = {r["id"] for r in world.a.get("/api/history").json()["records"]}
    b_history = {r["id"] for r in world.b.get("/api/history").json()["records"]}
    a_masters = {r["id"] for r in world.a.get("/api/master-resumes").json()["resumes"]}
    b_masters = {r["id"] for r in world.b.get("/api/master-resumes").json()["resumes"]}

    assert world.a_ids.history in a_history and world.a_ids.master in a_masters
    assert world.b_ids.history in b_history and world.b_ids.master in b_masters
    assert not a_history & b_history
    assert not a_masters & b_masters
    assert world.a_ids.history not in b_history and world.a_ids.master not in b_masters


def test_static_profiles_are_hidden_from_everyone_when_disabled(world):
    assert world.a.get("/api/resumes").json() == {"resumes": []}
    assert world.b.get("/api/resumes").json() == {"resumes": []}


def test_users_cannot_see_each_others_data_after_everything_ran(world):
    assert _snapshot(world.a, world.a_ids) == world.a_snapshot


# ── Authentication boundary ───────────────────────────────────────────────────

def _fill_path(path: str) -> str:
    return path.replace("{record_id}", uuid.uuid4().hex).replace("{filename}", "x.pdf")


def test_every_api_route_requires_a_session(world):
    protected = sorted(
        (method, path) for method, path in _app_routes()
        if path.startswith("/api/") and not path.startswith("/api/auth/")
    )
    assert protected, "route discovery found nothing"

    for method, path in protected:
        body = {"json": {}} if method in {"POST", "PUT", "PATCH"} else {}
        response = world.anon.request(method, _fill_path(path), **body)
        assert response.status_code == 401, f"{method} {path} -> {response.status_code}"
        assert response.json() == {"detail": "Authentication required."}, f"{method} {path}"


def test_auth_me_requires_a_session(world):
    assert world.anon.get("/api/auth/me").status_code == 401


def test_logout_revokes_the_session_even_for_a_replayed_cookie(world):
    client = TestClient(main.app)
    _register_verify_login(client, world.sent_urls, "logout@example.com")
    raw_cookie = client.cookies.get(auth_service.SESSION_COOKIE)
    assert client.get("/api/history").status_code == 200

    assert client.post("/api/auth/logout").status_code == 200

    assert client.get("/api/history").status_code == 401
    replay = TestClient(main.app)
    replay.cookies.set(auth_service.SESSION_COOKIE, raw_cookie)
    assert replay.get("/api/history").status_code == 401
    assert replay.get("/api/master-resumes").status_code == 401


def test_unverified_user_cannot_sign_in_or_reach_the_api(world):
    client = TestClient(main.app)
    credentials = {"email": "unverified@example.com", "password": PASSWORD}
    assert client.post("/api/auth/register", json=credentials).status_code == 202

    login = client.post("/api/auth/login", json=credentials)

    assert login.status_code == 403
    assert auth_service.SESSION_COOKIE not in client.cookies
    assert client.get("/api/history").status_code == 401


def test_session_of_a_user_who_loses_verification_gets_403(world):
    client = TestClient(main.app)
    _register_verify_login(client, world.sent_urls, "unverified-later@example.com")
    assert client.get("/api/history").status_code == 200
    with world.engine.begin() as connection:
        connection.execute(text(
            "UPDATE users SET email_verified_at = NULL WHERE email = :email"
        ), {"email": "unverified-later@example.com"})

    assert client.get("/api/history").status_code == 403
    assert client.get("/api/master-resumes").status_code == 403


# ── Directly supplied resume ──────────────────────────────────────────────────

def test_generate_cover_letter_with_a_supplied_resume_uses_only_that_resume(world, ai):
    """Audit item: a resume sent in the body is not checked for ownership.

    There is nothing to check: the body is the caller's own data, and no stored
    record is read when neither session_id nor history_id is given. This test
    pins that the letter is built from the supplied resume alone and that none
    of A's data reaches the model call or the response.
    """
    response = world.b.post("/api/generate-cover-letter", json={
        "tailored_resume": _letter_resume("Bob Brown"),
        "job_description": JOB_DESCRIPTION,
    })

    assert response.status_code == 200
    call = ai["generate_cover_letter"].call_args.kwargs
    assert call["tailored_resume"] == _letter_resume("Bob Brown")
    assert call["applicant_contact"] == {"name": "Bob Brown"}
    assert "Alice" not in str(call)


# ── Route coverage guard ──────────────────────────────────────────────────────

def test_every_route_is_covered_or_explicitly_exempt():
    registered = _app_routes()
    accounted = ISOLATION_COVERED | STATELESS_AUTHENTICATED | PUBLIC

    assert not registered - accounted, (
        "Routes with no isolation coverage or exemption (add them to "
        f"ISOLATION_COVERED, STATELESS_AUTHENTICATED or PUBLIC): {sorted(registered - accounted)}"
    )
    assert not accounted - registered, (
        f"Coverage lists name routes that no longer exist: {sorted(accounted - registered)}"
    )
    assert not (ISOLATION_COVERED & PUBLIC) and not (ISOLATION_COVERED & STATELESS_AUTHENTICATED)


def test_operations_exercise_every_covered_resource_route():
    """Routes that take IDs or session data must each have an attack operation.

    The list endpoints and POST /api/master-resumes are covered by the list and
    control tests instead of an ID-based attack.
    """
    listed_elsewhere = {
        ("GET", "/api/master-resumes"), ("POST", "/api/master-resumes"),
        ("GET", "/api/history"), ("GET", "/api/resumes"),
    }
    assert set(OPERATIONS) == set(OPERATION_ROUTES)
    assert set(OPERATION_ROUTES.values()) == ISOLATION_COVERED - listed_elsewhere
