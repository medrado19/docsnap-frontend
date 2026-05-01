from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.database import Base, engine

app = FastAPI(title="Revnio API", version="0.1.0")

# Keep simple for now so frontend fetch can connect during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://medrado19.github.io"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

app.include_router(router)


@app.get("/")
def root_status():
    return {"status": "ok", "service": "revnio-backend"}


@app.get("/health")
def health_check():
    return {"status": "ok"}
