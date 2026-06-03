import asyncio
import json
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy import select, and_

from app.database import async_session
from app.models.price import Price
from app.config import settings

router = APIRouter()


@router.websocket("/ws/prices")
async def price_stream(websocket: WebSocket, area: str = Query(default=None)):
    await websocket.accept()
    price_area = area or settings.nordpool_price_area

    try:
        while True:
            now = datetime.utcnow()
            current_hour = now.replace(minute=0, second=0, microsecond=0)

            async with async_session() as db:
                result = await db.execute(
                    select(Price).where(
                        and_(
                            Price.price_area == price_area,
                            Price.timestamp == current_hour,
                        )
                    )
                )
                price = result.scalar_one_or_none()

            if price:
                await websocket.send_text(json.dumps({
                    "timestamp": price.timestamp.isoformat(),
                    "price_area": price.price_area,
                    "price_eur_per_mwh": price.price_eur_per_mwh,
                }))

            # Send update every 60 seconds
            await asyncio.sleep(60)
    except WebSocketDisconnect:
        pass
