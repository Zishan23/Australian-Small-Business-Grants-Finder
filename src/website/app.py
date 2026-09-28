"""Local demo website for the AU small business grants finder.

Serves a single chat-style page (src/website/static/index.html) and a
/api/query endpoint backed by src/rag/interface.py's
build_default_orchestrator(). Today that returns MockQueryOrchestrator,
so every answer is clearly labeled as a demo (see QueryResult.is_mock)
until the real Bedrock-backed pipeline in src/rag/orchestrator.py is
wired in here (swap the orchestrator this module builds, at startup,
to RagQueryOrchestrator with real records + a BedrockClient - nothing
else in this file needs to change, since it only depends on the
QueryOrchestrator interface).

Run locally:
    pip install -r requirements.txt
    uvicorn src.website.app:app --reload
Then open http://127.0.0.1:8000
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.rag.interface import Citation, QueryOrchestrator, QueryResult, build_default_orchestrator

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="AU Small Business Grants Finder (demo)")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Built once at startup. See module docstring for how this becomes the
# real pipeline later without changing anything else in this file.
_orchestrator: QueryOrchestrator = build_default_orchestrator()


class QueryRequest(BaseModel):
    question: str


class CitationOut(BaseModel):
    record_id: str
    title: str
    url: str
    source: str
    snippet: str | None = None

    @classmethod
    def from_citation(cls, c: Citation) -> "CitationOut":
        return cls(
            record_id=c.record_id, title=c.title, url=c.url, source=c.source, snippet=c.snippet
        )


class QueryResponse(BaseModel):
    answer: str
    citations: list[CitationOut]
    agents_used: list[str]
    is_mock: bool

    @classmethod
    def from_result(cls, r: QueryResult) -> "QueryResponse":
        return cls(
            answer=r.answer,
            citations=[CitationOut.from_citation(c) for c in r.citations],
            agents_used=r.agents_used,
            is_mock=r.is_mock,
        )


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse:
    result = _orchestrator.query(request.question)
    return QueryResponse.from_result(result)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "orchestrator": type(_orchestrator).__name__}
