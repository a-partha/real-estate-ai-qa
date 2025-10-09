#main_pinecone.py
import os
import time
import requests
from urllib.parse import urljoin
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import pathlib

DAG_ID = "pinecone_property_pipeline"

# ── Resolve Airflow base URL ────────────────────────────────────────────────────

def normalize_base(u: str) -> str:
    return u.rstrip("/")

def probe_base(base: str) -> bool:
    """Return True if this base looks like a valid Airflow API root."""
    try:
        # v1: /dags?limit=1, v2 (Airflow 3): same path exists as well
        r = requests.get(urljoin(base + "/", "dags?limit=1"), timeout=5, auth=(AIRFLOW_USER, AIRFLOW_PW))
        return r.status_code < 500
    except Exception:
        return False

AIRFLOW_USER = os.getenv("AIRFLOW_USER", "airflow")
AIRFLOW_PW = os.getenv("AIRFLOW_PW", "airflow")

_explicit = os.getenv("AIRFLOW_API_BASE_URL")
if _explicit:
    AIRFLOW_API_BASE_URL = normalize_base(_explicit)
else:
    host = os.getenv("AIRFLOW_API_HOST", "airflow-webserver")
    port = os.getenv("AIRFLOW_API_PORT", "8080")
    # Try v2, then v1
    candidates = [
        f"http://{host}:{port}/api/v2",
        f"http://{host}:{port}/api/v1",
    ]
    AIRFLOW_API_BASE_URL = None
    for c in candidates:
        c = normalize_base(c)
        if probe_base(c):
            AIRFLOW_API_BASE_URL = c
            break

if not AIRFLOW_API_BASE_URL:
    raise RuntimeError(
        "Could not reach Airflow API. Set AIRFLOW_API_BASE_URL or AIRFLOW_API_HOST/AIRFLOW_API_PORT."
    )

try:
    AIRFLOW_DAG_MAX_WAIT_SEC = int(os.getenv("AIRFLOW_DAG_MAX_WAIT_SEC", "600"))
except ValueError:
    raise RuntimeError("AIRFLOW_DAG_MAX_WAIT_SEC must be an integer")

# ── FastAPI app ────────────────────────────────────────────────────────────────

app = FastAPI(title="NYC ACRIS QA API")

class AskRequest(BaseModel):
    prompt: str
    top_k: Optional[int] = None  # Optional top_k

app.mount("/assets", StaticFiles(directory=os.path.join(os.getcwd(), "web/dist/assets")), name="assets")

@app.get("/", response_class=HTMLResponse)
async def read_index():
    index_path = pathlib.Path(os.path.join(os.getcwd(), "web/dist/index.html"))
    return index_path.read_text()

# ── Airflow helpers ────────────────────────────────────────────────────────────

def airflow_request(method: str, path: str, **kwargs):
    url = urljoin(AIRFLOW_API_BASE_URL + "/", path.lstrip("/"))
    resp = requests.request(
        method,
        url,
        auth=(AIRFLOW_USER, AIRFLOW_PW),
        timeout=15,
        **kwargs,
    )
    # For 4xx/5xx erros to map them to clear messages
    resp.raise_for_status()
    # Some Airflow endpoints return empty body
    return resp.json() if resp.content else {}

def ensure_dag_available(dag_id: str):
    try:
        airflow_request("GET", f"/dags/{dag_id}")
    except requests.HTTPError as e:
        code = e.response.status_code if e.response is not None else None
        if code == 404:
            raise HTTPException(
                status_code=404,
                detail=f"DAG '{dag_id}' not found. Ensure the file is in Airflow's dags folder and parsed.",
            )
        raise

# ── API: /ask ─────────────────────────────────────────────────────────────────

@app.post("/ask")
def ask(request: AskRequest):
    prompt = request.prompt
    top_k = request.top_k

    # Check DAG exists before triggering
    ensure_dag_available(DAG_ID)

    # Build conf without nulls
    conf = {"prompt": prompt}
    if top_k is not None:
        conf["top_k"] = top_k

    # 1) Trigger the DAG
    try:
        payload = airflow_request(
            "POST",
            f"/dags/{DAG_ID}/dagRuns",
            json={"conf": conf},
        )
    except requests.HTTPError as e:
        code = e.response.status_code if e.response is not None else None
        body = e.response.text if e.response is not None else str(e)
        raise HTTPException(
            status_code=500,
            detail=f"DAG trigger failed (HTTP {code}). {body}",
        )

    run_id = payload.get("dag_run_id")
    if not run_id:
        raise HTTPException(500, f"No dag_run_id returned: {payload}")

    # 2) Poll until success or failure
    elapsed = 0
    interval = 5
    while elapsed < AIRFLOW_DAG_MAX_WAIT_SEC:
        try:
            status = airflow_request("GET", f"/dags/{DAG_ID}/dagRuns/{run_id}").get("state")
        except requests.HTTPError as e:
            code = e.response.status_code if e.response is not None else None
            raise HTTPException(500, f"Error checking DAG status (HTTP {code}).")
        if status == "success":
            break
        if status in ("failed", "error"):
            raise HTTPException(500, f"DAG run ended with state: {status}")
        time.sleep(interval)
        elapsed += interval
    else:
        raise HTTPException(
            500,
            f"DAG run {run_id} did not complete within {AIRFLOW_DAG_MAX_WAIT_SEC}s",
        )

    # 3) Fetch XComs
    def get_xcom(key: str) -> Optional[str]:
        try:
            res = airflow_request(
                "GET",
                f"/dags/{DAG_ID}/dagRuns/{run_id}"
                + f"/taskInstances/ask_gemini_with_pinecone_context/xcomEntries/{key}",
            )
            return res.get("value")
        except Exception:
            return None

    answer = get_xcom("answer")
    context = get_xcom("context") or ""
    route = get_xcom("route")
    confidence = get_xcom("confidence")

    return {
        "answer": answer,
        "context": context,
        "run_id": run_id,
        "route": route,
        "confidence": confidence,
    }
