import os
import time
import uuid
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="TorresMack Chatbot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────
# Configuración
# ──────────────────────────────────────────────

LLM_PROVIDER      = os.getenv("LLM_PROVIDER", "mock")
DEPLOYMENT        = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "DeepSeek-V4-Flash")
BASE_URL          = os.getenv("AZURE_OPENAI_BASE_URL", "")
API_KEY           = os.getenv("AZURE_OPENAI_API_KEY", "")
GROUP_ID          = os.getenv("GROUP_ID", "G5")
LOG_PATH          = "logs.jsonl"

SYSTEM_PROMPT = """Eres el asistente virtual de TorresMack Correduría de Seguros.
Ayudas a clientes con dudas sobre seguros de coche, hogar y artes escénicas.
Si la pregunta requiere un presupuesto personalizado o contratar una póliza,
deriva al cliente a info@torresmack.com.
Responde siempre en español, de forma clara y concisa."""

# ──────────────────────────────────────────────
# Modelos de entrada / salida
# ──────────────────────────────────────────────

class Options(BaseModel):
    temperature: Optional[float] = 0.2
    max_tokens: Optional[int] = 600

class PredictRequest(BaseModel):
    input: str
    history: Optional[list] = []
    options: Optional[Options] = Options()

class PredictResponse(BaseModel):
    ok: bool
    output: Optional[str] = None
    meta: Optional[dict] = None
    error: Optional[dict] = None


# ──────────────────────────────────────────────
# Logger
# ──────────────────────────────────────────────

def write_log(request_id: str, deployment: str, usage, latency_ms: int, exercise_id: str = "P12-S2"):
    event = {
        "ts":                time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "group_id":          GROUP_ID,
        "exercise_id":       exercise_id,
        "request_id":        request_id,
        "deployment":        deployment,
        "prompt_tokens":     usage.prompt_tokens if usage else 0,
        "completion_tokens": usage.completion_tokens if usage else 0,
        "total_tokens":      usage.total_tokens if usage else 0,
        "latency_ms":        latency_ms,
    }
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


# ──────────────────────────────────────────────
# Provider mock
# ──────────────────────────────────────────────

def mock_provider(user_input: str) -> dict:
    return {
        "ok": True,
        "output": f"[MOCK] He recibido: {user_input[:200]}",
        "meta": {
            "provider":           "mock",
            "deployment":         None,
            "latency_ms":         0,
            "prompt_tokens":      0,
            "completion_tokens":  0,
            "total_tokens":       0,
            "request_id":         None,
        }
    }


# ──────────────────────────────────────────────
# Provider Foundry (DeepSeek)
# ──────────────────────────────────────────────

def foundry_provider(user_input: str, history: list, options: Options) -> dict:
    client = OpenAI(
        base_url=BASE_URL,
        api_key=API_KEY,
        default_headers={"api-key": API_KEY},
    )

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history:
        messages.append(msg)
    messages.append({"role": "user", "content": user_input})

    request_id = str(uuid.uuid4())
    t0 = time.time()

    resp = client.chat.completions.create(
        model=DEPLOYMENT,
        messages=messages,
        max_tokens=min(options.max_tokens or 600, 600),
        temperature=options.temperature or 0.2,
    )

    latency_ms = int((time.time() - t0) * 1000)
    write_log(request_id, DEPLOYMENT, resp.usage, latency_ms)

    return {
        "ok": True,
        "output": resp.choices[0].message.content,
        "meta": {
            "provider":           "foundry",
            "deployment":         DEPLOYMENT,
            "latency_ms":         latency_ms,
            "prompt_tokens":      resp.usage.prompt_tokens,
            "completion_tokens":  resp.usage.completion_tokens,
            "total_tokens":       resp.usage.total_tokens,
            "request_id":         request_id,
        }
    }


# ──────────────────────────────────────────────
# Endpoint principal
# ──────────────────────────────────────────────

@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    if not req.input or not req.input.strip():
        return PredictResponse(
            ok=False,
            error={
                "code":    "INVALID_INPUT",
                "message": "El mensaje no puede estar vacío.",
                "details": {"field": "input"}
            }
        )

    try:
        if LLM_PROVIDER == "foundry":
            result = foundry_provider(req.input, req.history, req.options)
        else:
            result = mock_provider(req.input)

        return PredictResponse(ok=result["ok"], output=result["output"], meta=result["meta"])

    except Exception as e:
        return PredictResponse(
            ok=False,
            error={
                "code":    "INTERNAL_ERROR",
                "message": "Ha ocurrido un error procesando tu consulta. Inténtalo de nuevo.",
                "details": {"exception": str(e)}
            }
        )


@app.get("/health")
def health():
    return {"status": "ok", "provider": LLM_PROVIDER, "deployment": DEPLOYMENT}