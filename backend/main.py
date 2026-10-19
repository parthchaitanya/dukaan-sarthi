"""Dukaan Sarthi API (FastAPI). Serves the JSON API under /api and the built PWA at /.

Run:  uvicorn backend.main:app --reload     (after `python -m backend.seed`)
"""
from __future__ import annotations

import warnings

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, db, llm, metrics, tts
from .features import ask as ask_mod
from .features import brief as brief_mod
from .features import cashflow, festival, nudges, recon, winback

warnings.filterwarnings("ignore")

app = FastAPI(title="Dukaan Sarthi", version="1.0.0",
              description="Voice-first AI business copilot for Paytm merchants (hackathon MVP).")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def _check(mid: str, lang: str = "hinglish"):
    try:
        db.merchant(mid)
    except KeyError:
        raise HTTPException(404, f"Unknown merchant {mid}")
    if lang not in config.LANGS:
        raise HTTPException(400, f"lang must be one of {config.LANGS}")


class AskBody(BaseModel):
    merchant_id: str = "m1"
    question: str
    lang: str = "hinglish"


class PaymentBody(BaseModel):
    merchant_id: str = "m1"
    amount: float = 120
    lang: str = "hinglish"


class TTSBody(BaseModel):
    text: str
    lang: str = "hi"


class CampaignBody(BaseModel):
    merchant_id: str = "m1"
    lang: str = "hinglish"
    segment: str = "lapsing"
    message: str
    n_customers: int


@app.get("/api/health")
def health():
    return {"ok": True, "demo_today": config.DEMO_TODAY.isoformat(),
            "llm": llm.provider() or "rules (offline)", "model": llm.model_name(), "tts": tts.provider()}


@app.get("/api/merchants")
def merchants():
    return db.merchants()


@app.get("/api/brief")
def get_brief(merchant_id: str = "m1", lang: str = "hinglish"):
    _check(merchant_id, lang)
    return brief_mod.brief(merchant_id, lang)


@app.post("/api/ask")
def post_ask(body: AskBody):
    _check(body.merchant_id, body.lang)
    if not body.question.strip():
        raise HTTPException(400, "Empty question")
    return ask_mod.ask(body.merchant_id, body.question[:300], body.lang)


@app.get("/api/winback")
def get_winback(merchant_id: str = "m1", lang: str = "hinglish"):
    _check(merchant_id, lang)
    return winback.winback(merchant_id, lang)


@app.post("/api/campaigns")
def post_campaign(body: CampaignBody):
    _check(body.merchant_id, body.lang)
    with db.connect() as con:
        cur = con.execute("INSERT INTO campaigns(merchant_id, created_at, segment, lang, message, n_customers, status) "
                          "VALUES (?, datetime('now'), ?, ?, ?, ?, 'queued')",
                          (body.merchant_id, body.segment, body.lang, body.message[:500], body.n_customers))
        con.commit()
        cid = cur.lastrowid
    return {"id": cid, "status": "queued",
            "note": "In production Paytm delivers the offer to these customers on its own channel, so the merchant "
                    "never sees their phone numbers."}


@app.get("/api/campaigns")
def get_campaigns(merchant_id: str = "m1"):
    _check(merchant_id)
    return db.df("SELECT * FROM campaigns WHERE merchant_id=? ORDER BY id DESC", (merchant_id,)).to_dict("records")


@app.get("/api/cashflow")
def get_cashflow(merchant_id: str = "m1"):
    _check(merchant_id)
    return cashflow.cashflow(merchant_id)


@app.get("/api/credit")
def get_credit(merchant_id: str = "m1"):
    _check(merchant_id)
    return cashflow.credit_readiness(merchant_id)


@app.get("/api/festival")
def get_festival(merchant_id: str = "m1", lang: str = "hinglish"):
    _check(merchant_id, lang)
    return festival.plan(merchant_id, lang)


@app.get("/api/recon")
def get_recon(merchant_id: str = "m1", days: int = 30):
    _check(merchant_id)
    return recon.reconcile(merchant_id, days=max(1, min(days, 180)))


@app.post("/api/soundbox/pay")
def soundbox_pay(body: PaymentBody):
    _check(body.merchant_id, body.lang)
    return nudges.record_payment(body.merchant_id, body.amount, body.lang)


@app.get("/api/soundbox/status")
def soundbox_status(merchant_id: str = "m1"):
    _check(merchant_id)
    return nudges.status(merchant_id)


@app.post("/api/soundbox/reset")
def soundbox_reset(merchant_id: str = "m1"):
    _check(merchant_id)
    nudges.reset_live(merchant_id)
    return {"ok": True}


@app.post("/api/tts")
def post_tts(body: TTSBody):
    """Neural voice (Sarvam Bulbul) as MP3. 204 = server voice is off; the app then uses the browser's voice."""
    try:
        data = tts.audio(body.text, body.lang)
    except llm.LLMError as e:
        raise HTTPException(502, f"Voice service failed: {e}")
    if data is None:
        return Response(status_code=204)
    return Response(content=data, media_type="audio/mpeg", headers={"Cache-Control": "public, max-age=86400"})


@app.get("/api/metrics")
def get_metrics(refresh: bool = False):
    return metrics.load(refresh=refresh)


# ---- frontend (built PWA). /metrics and other client routes fall back to index.html
if config.FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=config.FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str = ""):
        f = config.FRONTEND_DIST / path
        if path and f.is_file() and config.FRONTEND_DIST in f.resolve().parents:
            return FileResponse(f)
        return FileResponse(config.FRONTEND_DIST / "index.html")
else:
    @app.get("/")
    def no_frontend():
        return JSONResponse({"message": "API is running. Build the frontend (cd frontend && npm run build) for the UI.",
                             "docs": "/docs"})
