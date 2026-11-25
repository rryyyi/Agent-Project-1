"""Local-first HTTP boundary; one application instance owns session serialization."""

from importlib.resources import files

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from jewelmentor import __version__
from jewelmentor.catalog import Catalog
from jewelmentor.config import Settings
from jewelmentor.harness import Harness
from jewelmentor.models import ChatRequest, TurnResult
from jewelmentor.providers import DemoProvider, OpenAIProvider
from jewelmentor.store import Conflict, Store


def create_app(settings: Settings | None = None, provider=None) -> FastAPI:
    settings = settings or Settings.from_env()
    store, catalog = Store(settings.db_path), Catalog()
    provider = provider or (
        DemoProvider() if settings.provider == "demo" else OpenAIProvider(settings)
    )
    harness = Harness(store, catalog, provider, settings)
    app = FastAPI(
        title="JewelMentor",
        version=__version__,
        description="珠宝销售培训 · 可审计的三层 Agent Harness。仅用于本地单进程演示。",
    )
    app.state.store, app.state.harness = store, harness
    assets = files("jewelmentor").joinpath("static")
    app.mount("/static", StaticFiles(directory=str(assets)), name="static")

    @app.middleware("http")
    async def browser_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        # Swagger manages its own CDN assets; the workbench has no third-party scripts.
        if not request.url.path.startswith(("/docs", "/redoc")):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
            )
        return response

    def error(status, code, message):
        return JSONResponse(
            status_code=status, content={"error": {"code": code, "message": message}}
        )

    @app.exception_handler(KeyError)
    async def missing(request: Request, exc: KeyError):
        return error(404, "not_found", "会话、回合或知识记录不存在")

    @app.exception_handler(Conflict)
    async def conflict(request: Request, exc: Conflict):
        return error(409, "conflict", str(exc))

    @app.exception_handler(RequestValidationError)
    async def invalid(request: Request, exc: RequestValidationError):
        return error(
            422, "validation", "输入无效：消息限 1–2000 字符；需合法 request_id；不接受额外字段"
        )

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return error(exc.status_code, "http_error", "请求路径或方法无效")

    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse(str(assets.joinpath("index.html")))

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "version": __version__,
            "provider": provider.name,
            "mode": "offline-demo" if provider.name == "demo" else "live-model",
            "deployment": "local-single-process",
        }

    @app.get("/api/experts")
    async def experts():
        return [expert.model_dump() for expert in catalog.experts]

    @app.get("/api/knowledge/{evidence_id}")
    async def knowledge(evidence_id: str):
        try:
            return catalog.evidence(evidence_id).model_dump()
        except StopIteration as exc:
            raise KeyError(evidence_id) from exc

    @app.post("/api/sessions", status_code=201)
    async def create_session():
        return store.create_session()

    @app.get("/api/sessions/{sid}")
    async def session(sid: str):
        return store.session(sid)

    @app.delete("/api/sessions/{sid}", status_code=204)
    async def delete(sid: str):
        await harness.delete(sid)
        return Response(status_code=204)

    @app.get("/api/sessions/{sid}/traces")
    async def traces(sid: str):
        store.session(sid)
        return store.trace(sid)

    @app.post("/api/sessions/{sid}/messages", response_model=TurnResult)
    async def chat(sid: str, body: ChatRequest):
        return await harness.chat(sid, body)

    @app.post("/api/sessions/{sid}/turns/{tid}/resume", response_model=TurnResult)
    async def resume(sid: str, tid: str):
        return await harness.resume(sid, tid)

    return app
