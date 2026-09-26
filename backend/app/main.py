from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.data.db_schema import init_db
from backend.app.routers import core, audit, actions

# Auto-initialize database tables on server startup
init_db()

app = FastAPI(
    title="AltoMare Non-Revenue Water Platform API",
    description="Backend API for water balance audits, MNF estimation, billing fraud, and payback ROI.",
    version="2.0.0"
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routers
app.include_router(core.router)
app.include_router(audit.router)
app.include_router(actions.router)

@app.get("/")
def root():
    return {
        "platform": "AltoMare NRW Platform",
        "status": "online",
        "version": "2.0.0",
        "docs": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=True)