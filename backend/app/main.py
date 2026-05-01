from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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


@app.exception_handler(404)
async def not_found_handler(request: Request, _exc):
    if "invoice" in request.url.path:
        return JSONResponse(
            status_code=404,
            content={
                "detail": "Route not found. Available invoice routes: POST /upload-invoice, GET /invoices, DELETE /invoice/{id}",
                "available_invoice_routes": [
                    "POST /upload-invoice",
                    "GET /invoices",
                    "DELETE /invoice/{id}",
                ],
            },
        )
    return JSONResponse(status_code=404, content={"detail": "Not Found"})
