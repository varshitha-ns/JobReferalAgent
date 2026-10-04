from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes.jobs import router as jobs_router
from routes.contacts import router as contacts_router


app = FastAPI(
    title="Job Referral Agent",
    version="0.1.0"
)


# Allow Chrome extension and local development requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Routes
app.include_router(jobs_router)
app.include_router(contacts_router)


@app.get("/")
def root():
    return {
        "message": "Job Referral Agent backend is running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }
