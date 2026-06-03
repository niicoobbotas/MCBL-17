from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import auth, vehicles, chargers, prices, schedules, dashboard
from app.ws.price_stream import router as ws_router

app = FastAPI(
    title="EV Charger Optimizer",
    description="Smart EV charging optimization based on electricity spot prices",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST routers
app.include_router(auth.router)
app.include_router(vehicles.router)
app.include_router(chargers.router)
app.include_router(prices.router)
app.include_router(schedules.router)
app.include_router(dashboard.router)

# WebSocket
app.include_router(ws_router)


@app.get("/")
async def root():
    return {"message": "EV Charger Optimizer API", "docs": "/docs"}
