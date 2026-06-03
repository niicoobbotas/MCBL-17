import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.models.charger import Charger
from app.schemas.charger import ChargerCreate, ChargerUpdate, ChargerResponse
from app.utils.deps import get_current_user
from app.services.charger_interface import charger as charger_service

router = APIRouter(prefix="/api/chargers", tags=["chargers"])


@router.get("/", response_model=list[ChargerResponse])
async def list_chargers(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Charger).where(Charger.user_id == user.id))
    return result.scalars().all()


@router.post("/", response_model=ChargerResponse, status_code=status.HTTP_201_CREATED)
async def create_charger(
    req: ChargerCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    c = Charger(**req.model_dump(), user_id=user.id)
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


@router.put("/{charger_id}", response_model=ChargerResponse)
async def update_charger(
    charger_id: uuid.UUID,
    req: ChargerUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Charger).where(Charger.id == charger_id, Charger.user_id == user.id)
    )
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Charger not found")

    for field, value in req.model_dump(exclude_unset=True).items():
        setattr(c, field, value)

    await db.commit()
    await db.refresh(c)
    return c


@router.delete("/{charger_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_charger(
    charger_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Charger).where(Charger.id == charger_id, Charger.user_id == user.id)
    )
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Charger not found")

    await db.delete(c)
    await db.commit()


@router.get("/{charger_id}/status")
async def get_charger_status(
    charger_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Charger).where(Charger.id == charger_id, Charger.user_id == user.id)
    )
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Charger not found")

    status_info = await charger_service.get_status(str(charger_id))
    return {
        "charger_id": str(charger_id),
        "name": c.name,
        "status": status_info.status,
        "current_rate_kw": status_info.current_rate_kw,
        "session_kwh": status_info.session_kwh,
        "connected": status_info.connected,
    }
