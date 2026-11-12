from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from .api import files, claims, reports, imports
from .core.config import settings
from .db import init_db

app = FastAPI(title="CogniTrace Backend")

# CORS for frontend dev server and configured production origins
cors_origins = [
    origin.strip()
    for origin in settings.CORS_ORIGINS.split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(files.router, prefix="/api/files", tags=["files"])
app.include_router(claims.router, prefix="/api/claims", tags=["claims"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
app.include_router(imports.router, prefix="/api/imports", tags=["imports"])

@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok"}

# Startup event to init DB
@app.on_event("startup")
def on_startup():
    init_db()
