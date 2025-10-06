# FastAPI Integration

Integrate KnowledgeBeast with your FastAPI application.

## Basic Integration

```python
from fastapi import FastAPI, HTTPException
from knowledgebeast import KnowledgeBeast, KnowledgeBeastConfig

app = FastAPI()
kb = KnowledgeBeast()

@app.get("/search")
async def search(q: str, n: int = 5):
    try:
        results = kb.query(q, n_results=n)
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.on_event("shutdown")
async def shutdown():
    kb.shutdown()
```

## Using Dependency Injection

```python
from fastapi import Depends, FastAPI

app = FastAPI()

def get_kb():
    kb = KnowledgeBeast()
    try:
        yield kb
    finally:
        kb.shutdown()

@app.get("/search")
async def search(q: str, kb: KnowledgeBeast = Depends(get_kb)):
    results = kb.query(q)
    return {"results": results}
```

## Full Integration Example

See `knowledgebeast/api/` for full production-ready FastAPI integration.

## Next Steps

- [REST API Guide](../guides/rest-api.md)
- [Python API Guide](../guides/python-api.md)
