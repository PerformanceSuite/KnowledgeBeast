"""FastAPI integration example.

This example demonstrates:
- Integrating KnowledgeBeast with FastAPI
- Dependency injection
- Error handling
- Custom endpoints
"""

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Any

from knowledgebeast import KnowledgeBeast, KnowledgeBeastConfig


# Pydantic models
class QueryRequest(BaseModel):
    """Query request model."""
    query: str
    n_results: int = 5


class QueryResponse(BaseModel):
    """Query response model."""
    results: List[Dict[str, Any]]
    count: int


# Initialize FastAPI app
app = FastAPI(
    title="KnowledgeBeast Integration",
    description="Example FastAPI integration with KnowledgeBeast",
    version="1.0.0"
)


# Dependency injection for KnowledgeBeast
def get_kb() -> KnowledgeBeast:
    """Get KnowledgeBeast instance (singleton pattern)."""
    if not hasattr(get_kb, "_instance"):
        config = KnowledgeBeastConfig()
        get_kb._instance = KnowledgeBeast(config)
    return get_kb._instance


# Endpoints
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "KnowledgeBeast FastAPI Integration",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health")
async def health(kb: KnowledgeBeast = Depends(get_kb)):
    """Health check endpoint."""
    stats = kb.get_stats()
    return {
        "status": "healthy",
        "documents": stats["total_documents"],
        "cache_size": stats["cache_stats"]["size"]
    }


@app.post("/search", response_model=QueryResponse)
async def search(
    request: QueryRequest,
    kb: KnowledgeBeast = Depends(get_kb)
) -> QueryResponse:
    """Search endpoint."""
    try:
        results = kb.query(
            request.query,
            n_results=request.n_results
        )
        return QueryResponse(
            results=results,
            count=len(results)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        )


@app.get("/stats")
async def stats(kb: KnowledgeBeast = Depends(get_kb)):
    """Statistics endpoint."""
    return kb.get_stats()


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    if hasattr(get_kb, "_instance"):
        get_kb._instance.shutdown()


# Run with: uvicorn fastapi_integration:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
