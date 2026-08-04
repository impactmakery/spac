from fastapi import FastAPI

app = FastAPI(title="Tomorrow Agent Hub API")


@app.get("/health")
def health() -> dict:
    """Liveness probe. Extend with DB / R2 / OpenAI reachability per the scope appendix."""
    return {"status": "ok"}
