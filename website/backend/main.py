"""
SmartEV — CACCS Backend API
FastAPI application serving the dashboard and CACCS scheduling API.
"""
import os, json, datetime
from typing import List, Optional
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, status, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

import models, schemas, auth, caccs
from database import engine, get_db

# ── Bootstrap ──────────────────────────────────────────────────────────────────
models.Base.metadata.create_all(bind=engine)


def _migrate_db():
    """Add any missing columns to existing tables without dropping data."""
    from sqlalchemy import inspect, text
    inspector = inspect(engine)

    new_user_cols = {
        "charging_profile":  "VARCHAR DEFAULT 'balance'",
        "gdpr_consent":      "BOOLEAN DEFAULT 0",
        "gdpr_consent_date": "DATETIME",
        "address":           "VARCHAR",
    }
    new_vehicle_cols = {
        "brand": "VARCHAR",
        "year":  "INTEGER",
    }
    try:
        existing_u = {c["name"] for c in inspector.get_columns("users")}
        existing_v = {c["name"] for c in inspector.get_columns("vehicles")}
        with engine.connect() as conn:
            for col, defn in new_user_cols.items():
                if col not in existing_u:
                    conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {defn}"))
                    conn.commit()
            for col, defn in new_vehicle_cols.items():
                if col not in existing_v:
                    conn.execute(text(f"ALTER TABLE vehicles ADD COLUMN {col} {defn}"))
                    conn.commit()
    except Exception:
        pass  # table may not exist yet on first run; create_all handles it


_migrate_db()

app = FastAPI(
    title="SmartEV API",
    description="CACCS smart charging scheduler — Team 12",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


# ── Pi script download ─────────────────────────────────────────────────────────
@app.get("/download/charger_sim.py")
def download_charger_sim():
    p = Path(__file__).parent.parent.parent / "raspberry_pi" / "charger_sim.py"
    return FileResponse(p, filename="charger_sim.py", media_type="text/plain")

# ── Auth Routes ────────────────────────────────────────────────────────────────

@app.post("/api/auth/register", response_model=schemas.Token)
def register(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.email == user_in.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    now = datetime.datetime.utcnow()
    user = models.User(
        email=user_in.email,
        name=user_in.name,
        hashed_password=auth.hash_password(user_in.password),
        supplier=user_in.supplier,
        charging_profile=user_in.charging_profile,
        gdpr_consent=user_in.gdpr_consent,
        gdpr_consent_date=now if user_in.gdpr_consent else None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = auth.create_access_token(data={"sub": user.email})
    return {"access_token": token, "token_type": "bearer", "user": user}


@app.post("/api/auth/login", response_model=schemas.Token)
def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    client_ip = request.client.host if request.client else "unknown"
    user = auth.login_with_rate_limit(form.username, form.password, client_ip, db)
    token = auth.create_access_token(data={"sub": user.email})
    return {"access_token": token, "token_type": "bearer", "user": user}


@app.get("/api/auth/me", response_model=schemas.UserOut)
def me(current_user: models.User = Depends(auth.get_current_user)):
    return current_user


@app.put("/api/auth/me", response_model=schemas.UserOut)
def update_me(
    data: schemas.UserUpdate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    for field, value in data.dict(exclude_none=True).items():
        setattr(current_user, field, value)
    db.commit()
    db.refresh(current_user)
    return current_user


@app.get("/api/auth/me/data")
def export_my_data(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """GDPR Article 20 — data portability export."""
    sessions = db.query(models.ChargingSession).filter(
        models.ChargingSession.user_id == current_user.id
    ).all()
    vehicles = db.query(models.Vehicle).filter(
        models.Vehicle.user_id == current_user.id
    ).all()
    return {
        "export_date": datetime.datetime.utcnow().isoformat(),
        "gdpr_article": "20 — Right to data portability",
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "name": current_user.name,
            "supplier": current_user.supplier,
            "charging_profile": current_user.charging_profile,
            "plugin_time": current_user.plugin_time,
            "deadline": current_user.deadline,
            "ere_enabled": current_user.ere_enabled,
            "solar_enabled": current_user.solar_enabled,
            "solar_kwp": current_user.solar_kwp,
            "gdpr_consent": current_user.gdpr_consent,
            "gdpr_consent_date": current_user.gdpr_consent_date.isoformat() if current_user.gdpr_consent_date else None,
            "created_at": current_user.created_at.isoformat(),
        },
        "vehicles": [
            {
                "model_name": v.model_name,
                "battery_kwh": v.battery_kwh,
                "wltp_km": v.wltp_km,
                "ac_power_kw": v.ac_power_kw,
                "efficiency_kwh_100km": v.efficiency_kwh_100km,
                "is_default": v.is_default,
                "added_at": v.created_at.isoformat(),
            }
            for v in vehicles
        ],
        "charging_sessions": [
            {
                "date": s.session_date.isoformat(),
                "kwh_delivered": s.kwh_delivered,
                "cost_eur": s.cost_eur,
                "savings_vs_fixed": s.savings_vs_fixed,
                "plugin_hour": s.plugin_hour,
                "deadline_hour": s.deadline_hour,
                "supplier": s.supplier,
                "policy": s.policy,
            }
            for s in sessions
        ],
    }


@app.post("/api/auth/change-password", status_code=204)
def change_password(
    data: schemas.PasswordChange,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    if not auth.verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if len(data.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")
    current_user.hashed_password = auth.hash_password(data.new_password)
    db.commit()


@app.delete("/api/auth/me", status_code=204)
def delete_my_account(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """GDPR Article 17 — right to erasure."""
    db.delete(current_user)
    db.commit()


# ── Price Routes ────────────────────────────────────────────────────────────────

@app.get("/api/prices/current")
def current_price(
    supplier: str = "eneco",
    current_user: models.User = Depends(auth.get_current_user),
):
    return caccs.get_current_price(supplier)


@app.get("/api/prices/today")
def today_prices(
    supplier: str = "eneco",
    current_user: models.User = Depends(auth.get_current_user),
):
    return {"prices": caccs.get_today_hourly(supplier)}


@app.get("/api/prices/public")
def public_prices(supplier: str = "eneco"):
    """No auth — used by landing page calculator."""
    return {"prices": caccs.get_today_hourly(supplier)}


@app.get("/api/prices/forecast")
def prices_forecast(days: int = 3, supplier: str = "eneco"):
    """Return live_prices/*.json data for today + next N days."""
    import datetime, json
    from pathlib import Path
    live_dir = Path(__file__).parent / "live_prices"
    margin = caccs.SUPPLIERS[supplier]["dyn_margin"]
    today = datetime.date.today()
    result = []
    for offset in range(days + 1):
        date = today + datetime.timedelta(days=offset)
        data = None
        for suffix in ("", "_forecast"):
            p = live_dir / f"{date.isoformat()}{suffix}.json"
            if p.exists():
                try:
                    data = json.loads(p.read_text())
                    break
                except Exception:
                    pass
        if data:
            wholesale = data["prices_eur_mwh"]
            retail = [round(caccs.retail(w, margin), 4) for w in wholesale]
            result.append({
                "date": date.isoformat(),
                "is_forecast": data.get("is_forecast", False),
                "source": data.get("source", "unknown"),
                "prices_eur_mwh": wholesale,
                "prices_eur_kwh": retail,
            })
    return {"days": result}


# ── CACCS Algorithm Routes ─────────────────────────────────────────────────────

# Charging profile → β mapping
PROFILE_BETA = {"saver": 0.0, "balance": 0.5, "eco": 1.0}


@app.post("/api/caccs/compute", response_model=schemas.CACCSResult)
def compute_schedule(
    req: schemas.CACCSRequest,
    current_user: models.User = Depends(auth.get_current_user),
):
    if req.energy_kwh <= 0 or req.pmax_kw <= 0:
        raise HTTPException(status_code=422, detail="Energy and power must be positive")
    if req.plugin_hour == req.deadline_hour:
        raise HTTPException(status_code=422, detail="Plugin and deadline cannot be the same hour")
    result = caccs.run_caccs(
        energy_kwh=req.energy_kwh,
        pmax_kw=req.pmax_kw,
        plugin_hour=req.plugin_hour,
        deadline_hour=req.deadline_hour,
        supplier=req.supplier,
        beta=req.beta,
        eta=req.eta,
    )
    return result


@app.post("/api/caccs/public")
def compute_public(req: schemas.CACCSRequest):
    """No auth — landing page live demo."""
    result = caccs.run_caccs(
        energy_kwh=req.energy_kwh,
        pmax_kw=req.pmax_kw,
        plugin_hour=req.plugin_hour,
        deadline_hour=req.deadline_hour,
        supplier=req.supplier,
        beta=req.beta,
        eta=req.eta,
    )
    return result


@app.get("/api/caccs/annual-value")
def annual_value(
    annual_km: float = 12000,
    efficiency: float = 14.0,
    supplier: str = "eneco",
    plugin_hour: int = 18,
    deadline_hour: int = 7,
    pmax_kw: float = 11.0,
    ere_enabled: bool = True,
    solar_enabled: bool = False,
    solar_kwp: float = 4.0,
    current_user: models.User = Depends(auth.get_current_user),
):
    return caccs.compute_annual_value(
        annual_km, efficiency, supplier, plugin_hour, deadline_hour,
        pmax_kw, ere_enabled, solar_enabled, solar_kwp,
    )


# ── Vehicle Routes ─────────────────────────────────────────────────────────────

EV_CATALOG = [
    # Tesla
    {"id": 1,  "brand": "Tesla",      "model_name": "Tesla Model Y",               "year": 2025, "battery_kwh": 75,  "wltp_km": 600, "ac_power_kw": 11.0, "efficiency_kwh_100km": 14.5, "price_eur": 44990},
    {"id": 2,  "brand": "Tesla",      "model_name": "Tesla Model Y Long Range AWD","year": 2025, "battery_kwh": 82,  "wltp_km": 719, "ac_power_kw": 11.0, "efficiency_kwh_100km": 14.2, "price_eur": 54990},
    {"id": 3,  "brand": "Tesla",      "model_name": "Tesla Model 3",               "year": 2025, "battery_kwh": 60,  "wltp_km": 702, "ac_power_kw": 11.0, "efficiency_kwh_100km": 10.8, "price_eur": 42990},
    # Volkswagen Group
    {"id": 4,  "brand": "Volkswagen", "model_name": "Volkswagen ID.4",             "year": 2025, "battery_kwh": 77,  "wltp_km": 541, "ac_power_kw": 11.0, "efficiency_kwh_100km": 14.2, "price_eur": 41990},
    {"id": 5,  "brand": "Volkswagen", "model_name": "Volkswagen ID.3",             "year": 2025, "battery_kwh": 58,  "wltp_km": 563, "ac_power_kw": 11.0, "efficiency_kwh_100km": 14.0, "price_eur": 35990},
    {"id": 6,  "brand": "Skoda",      "model_name": "Skoda Enyaq",                 "year": 2025, "battery_kwh": 77,  "wltp_km": 570, "ac_power_kw": 11.0, "efficiency_kwh_100km": 14.0, "price_eur": 40490},
    {"id": 7,  "brand": "Audi",       "model_name": "Audi Q4 e-tron",              "year": 2025, "battery_kwh": 82,  "wltp_km": 599, "ac_power_kw": 11.0, "efficiency_kwh_100km": 14.5, "price_eur": 51990},
    {"id": 8,  "brand": "Cupra",      "model_name": "Cupra Born",                  "year": 2025, "battery_kwh": 77,  "wltp_km": 570, "ac_power_kw": 11.0, "efficiency_kwh_100km": 13.5, "price_eur": 38490},
    # Hyundai-Kia
    {"id": 9,  "brand": "Hyundai",    "model_name": "Hyundai Kona Electric",       "year": 2025, "battery_kwh": 65,  "wltp_km": 514, "ac_power_kw": 11.0, "efficiency_kwh_100km": 12.8, "price_eur": 39990},
    {"id": 10, "brand": "Kia",        "model_name": "Kia EV3",                     "year": 2025, "battery_kwh": 81,  "wltp_km": 605, "ac_power_kw": 11.0, "efficiency_kwh_100km": 13.6, "price_eur": 38990},
    {"id": 11, "brand": "Kia",        "model_name": "Kia EV6",                     "year": 2025, "battery_kwh": 77,  "wltp_km": 528, "ac_power_kw": 11.0, "efficiency_kwh_100km": 16.0, "price_eur": 46990},
    # Volvo
    {"id": 12, "brand": "Volvo",      "model_name": "Volvo EX30",                  "year": 2025, "battery_kwh": 69,  "wltp_km": 480, "ac_power_kw": 11.0, "efficiency_kwh_100km": 14.4, "price_eur": 35990},
    {"id": 13, "brand": "Volvo",      "model_name": "Volvo EX40",                  "year": 2025, "battery_kwh": 82,  "wltp_km": 573, "ac_power_kw": 11.0, "efficiency_kwh_100km": 16.4, "price_eur": 49990},
    # Renault
    {"id": 14, "brand": "Renault",    "model_name": "Renault Megane E-Tech",       "year": 2025, "battery_kwh": 60,  "wltp_km": 450, "ac_power_kw": 22.0, "efficiency_kwh_100km": 13.3, "price_eur": 34990},
    {"id": 15, "brand": "Renault",    "model_name": "Renault 5 E-Tech",            "year": 2025, "battery_kwh": 52,  "wltp_km": 400, "ac_power_kw": 11.0, "efficiency_kwh_100km": 13.0, "price_eur": 27990},
    # BMW
    {"id": 16, "brand": "BMW",        "model_name": "BMW iX1",                     "year": 2025, "battery_kwh": 66,  "wltp_km": 474, "ac_power_kw": 11.0, "efficiency_kwh_100km": 13.9, "price_eur": 55990},
    # Ford & Peugeot
    {"id": 17, "brand": "Ford",       "model_name": "Ford Mustang Mach-E",         "year": 2025, "battery_kwh": 91,  "wltp_km": 600, "ac_power_kw": 11.0, "efficiency_kwh_100km": 15.2, "price_eur": 47990},
    {"id": 18, "brand": "Peugeot",    "model_name": "Peugeot e-208",               "year": 2025, "battery_kwh": 54,  "wltp_km": 400, "ac_power_kw": 11.0, "efficiency_kwh_100km": 13.5, "price_eur": 31990},
    # MG & BYD
    {"id": 19, "brand": "MG",         "model_name": "MG4 Electric",                "year": 2025, "battery_kwh": 64,  "wltp_km": 450, "ac_power_kw": 11.0, "efficiency_kwh_100km": 14.2, "price_eur": 28990},
    {"id": 20, "brand": "BYD",        "model_name": "BYD Atto 3",                  "year": 2025, "battery_kwh": 60,  "wltp_km": 420, "ac_power_kw":  7.0, "efficiency_kwh_100km": 16.0, "price_eur": 32990},
]


@app.get("/api/vehicles/catalog")
def get_catalog():
    return {"vehicles": EV_CATALOG}


@app.get("/api/vehicles", response_model=List[schemas.VehicleOut])
def get_vehicles(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    return current_user.vehicles


@app.post("/api/vehicles", response_model=schemas.VehicleOut)
def add_vehicle(
    v: schemas.VehicleCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    if v.is_default:
        for existing in current_user.vehicles:
            existing.is_default = False
    vehicle = models.Vehicle(user_id=current_user.id, **v.dict())
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle


@app.put("/api/vehicles/{vehicle_id}", response_model=schemas.VehicleOut)
def update_vehicle(
    vehicle_id: int,
    v: schemas.VehicleUpdate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    vehicle = db.query(models.Vehicle).filter(
        models.Vehicle.id == vehicle_id,
        models.Vehicle.user_id == current_user.id,
    ).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    if v.is_default:
        for other in current_user.vehicles:
            other.is_default = False
    for field, value in v.dict(exclude_none=True).items():
        setattr(vehicle, field, value)
    db.commit()
    db.refresh(vehicle)
    return vehicle


@app.delete("/api/vehicles/{vehicle_id}", status_code=204)
def delete_vehicle(
    vehicle_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    v = db.query(models.Vehicle).filter(
        models.Vehicle.id == vehicle_id,
        models.Vehicle.user_id == current_user.id,
    ).first()
    if not v:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    db.delete(v)
    db.commit()


# ── Sessions & Bill Routes ─────────────────────────────────────────────────────

@app.get("/api/sessions", response_model=List[schemas.SessionOut])
def get_sessions(
    limit: int = 20,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(models.ChargingSession)
        .filter(models.ChargingSession.user_id == current_user.id)
        .order_by(models.ChargingSession.session_date.desc())
        .limit(limit)
        .all()
    )


@app.post("/api/sessions", response_model=schemas.SessionOut)
def log_session(
    s: schemas.SessionCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    session = models.ChargingSession(user_id=current_user.id, **s.dict())
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@app.get("/api/bill/monthly")
def monthly_bill(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    sessions = (
        db.query(models.ChargingSession)
        .filter(models.ChargingSession.user_id == current_user.id)
        .all()
    )
    monthly = {}
    for s in sessions:
        key = s.session_date.strftime("%Y-%m")
        if key not in monthly:
            monthly[key] = {"total_kwh": 0, "total_cost": 0, "total_savings": 0, "count": 0}
        monthly[key]["total_kwh"] += s.kwh_delivered
        monthly[key]["total_cost"] += s.cost_eur
        monthly[key]["total_savings"] += s.savings_vs_fixed
        monthly[key]["count"] += 1

    return {
        "months": [
            {
                "month": k,
                "total_kwh": round(v["total_kwh"], 2),
                "total_cost": round(v["total_cost"], 2),
                "total_savings_vs_fixed": round(v["total_savings"], 2),
                "session_count": v["count"],
            }
            for k, v in sorted(monthly.items(), reverse=True)
        ]
    }


@app.get("/api/dashboard/stats")
def dashboard_stats(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    sessions = (
        db.query(models.ChargingSession)
        .filter(models.ChargingSession.user_id == current_user.id)
        .all()
    )
    total_savings = sum(s.savings_vs_fixed for s in sessions)
    total_kwh = sum(s.kwh_delivered for s in sessions)
    total_cost = sum(s.cost_eur for s in sessions)
    session_count = len(sessions)

    now = datetime.datetime.now()
    this_month = [
        s for s in sessions
        if s.session_date.year == now.year and s.session_date.month == now.month
    ]
    month_cost = sum(s.cost_eur for s in this_month)
    month_savings = sum(s.savings_vs_fixed for s in this_month)

    current_price_data = caccs.get_current_price(current_user.supplier)

    return {
        "total_savings_eur": round(total_savings, 2),
        "total_kwh": round(total_kwh, 2),
        "total_cost_eur": round(total_cost, 2),
        "session_count": session_count,
        "month_cost_eur": round(month_cost, 2),
        "month_savings_eur": round(month_savings, 2),
        "current_price": current_price_data,
        "charging_profile": current_user.charging_profile,
    }


# ── Frontend Routing ───────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def serve_landing():
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return HTMLResponse("<h1>SmartEV API running. Frontend not found.</h1>")


@app.get("/login", response_class=HTMLResponse)
def serve_login():
    return FileResponse(str(FRONTEND_DIR / "login.html"))


@app.get("/register", response_class=HTMLResponse)
def serve_register():
    return FileResponse(str(FRONTEND_DIR / "register.html"))


@app.get("/dashboard", response_class=HTMLResponse)
def serve_dashboard():
    return FileResponse(str(FRONTEND_DIR / "dashboard.html"))


@app.get("/app", response_class=HTMLResponse)
def serve_app():
    return FileResponse(str(FRONTEND_DIR / "app.html"))


@app.get("/technology", response_class=HTMLResponse)
def serve_technology():
    return FileResponse(str(FRONTEND_DIR / "technology.html"))


@app.get("/catalog", response_class=HTMLResponse)
def serve_catalog():
    return FileResponse(str(FRONTEND_DIR / "catalog.html"))


@app.get("/privacy", response_class=HTMLResponse)
def serve_privacy():
    return FileResponse(str(FRONTEND_DIR / "privacy.html"))


@app.get("/terms", response_class=HTMLResponse)
def serve_terms():
    return FileResponse(str(FRONTEND_DIR / "terms.html"))


# ── Raspberry Pi PoC WebSocket relay ─────────────────────────────────────────
# One Pi connects to /ws/pi; dashboard browsers connect to /ws/dashboard.
# The backend relays messages both ways so the Pi and dashboard talk to each
# other without needing to be on the same network segment.

_pi_ws: Optional[WebSocket] = None
_dash_sockets: list[WebSocket] = []


async def _broadcast_dash(msg: dict) -> None:
    dead = []
    for ws in list(_dash_sockets):
        try:
            await ws.send_json(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in _dash_sockets:
            _dash_sockets.remove(ws)


@app.websocket("/ws/pi")
async def ws_pi(ws: WebSocket):
    global _pi_ws
    await ws.accept()
    _pi_ws = ws
    await _broadcast_dash({"type": "pi_connected"})
    print("RPi connected")
    try:
        async for msg in ws.iter_json():
            await _broadcast_dash(msg)
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        print(f"Pi WS error: {exc}")
    finally:
        if _pi_ws is ws:
            _pi_ws = None
        await _broadcast_dash({"type": "pi_disconnected"})
        print("RPi disconnected")


@app.websocket("/ws/dashboard")
async def ws_dashboard(ws: WebSocket):
    await ws.accept()
    _dash_sockets.append(ws)
    # Tell the new browser tab the current Pi connection status
    await ws.send_json({"type": "pi_status", "connected": _pi_ws is not None})
    try:
        async for msg in ws.iter_json():
            # Relay any command to the Pi
            if _pi_ws:
                try:
                    await _pi_ws.send_json(msg)
                except Exception:
                    pass
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        print(f"Dashboard WS error: {exc}")
    finally:
        if ws in _dash_sockets:
            _dash_sockets.remove(ws)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
