import os
import uuid
import logging
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime
from typing import List, Optional
from pybit.unified_trading import HTTP
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI(title="Crypto Exchange API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

BYBIT_API_KEY = os.getenv("BYBIT_API_KEY")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET")

if not BYBIT_API_KEY or not BYBIT_API_SECRET:
    raise ValueError("Добавь ключи в .env файл!")

DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'orders.db')}"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.now)
    amount_usdt = Column(Float)
    bank = Column(String)
    phone = Column(String)
    deposit_address = Column(String)
    status = Column(String, default="pending")

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

BYBIT_DEPOSIT_ADDRESS = os.getenv("BYBIT_DEPOSIT_ADDRESS", "")

def get_bybit_deposit_address():
    try:
        session = HTTP(
            testnet=False, 
            api_key=BYBIT_API_KEY, 
            api_secret=BYBIT_API_SECRET, 
            recv_window=30000
        )
        result = session.get_master_deposit_address(
            coin="USDT",
            chainType="TRX"
        )
        if result.get("retCode") == 0:
            chains = result.get("result", {}).get("chains", [])
            if chains:
                return chains[0].get("addressDeposit")
    except Exception as e:
        print(f"Error getting deposit address: {e}")
    
    if BYBIT_DEPOSIT_ADDRESS:
        return BYBIT_DEPOSIT_ADDRESS
    
    raise Exception("Не удалось получить адрес депозита. Добавь BYBIT_DEPOSIT_ADDRESS в .env")

class OrderCreate(BaseModel):
    amount_usdt: float
    bank: str
    phone: str

class OrderUpdate(BaseModel):
    status: str

@app.get("/", response_class=HTMLResponse)
async def payment_page(request: Request):
    template_path = os.path.join(BASE_DIR, "templates", "payment.html")
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    template_path = os.path.join(BASE_DIR, "templates", "admin.html")
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()

@app.post("/api/orders")
async def create_order(order: OrderCreate, db: Session = Depends(get_db)):
    logger.info(f"Creating order: {order}")
    deposit_address = get_bybit_deposit_address()
    logger.info(f"Deposit address: {deposit_address}")
    if not deposit_address:
        raise HTTPException(status_code=500, detail="Не удалось получить адрес депозита")
    
    order_id = str(uuid.uuid4())[:8].upper()
    new_order = Order(
        order_id=order_id,
        amount_usdt=order.amount_usdt,
        bank=order.bank,
        phone=order.phone,
        deposit_address=deposit_address,
        status="pending"
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order)
    
    return {
        "order_id": new_order.order_id,
        "deposit_address": new_order.deposit_address,
        "amount_usdt": new_order.amount_usdt,
        "status": new_order.status,
        "created_at": new_order.created_at.isoformat()
    }

@app.get("/api/orders", response_model=List[dict])
async def get_orders(db: Session = Depends(get_db)):
    orders = db.query(Order).order_by(Order.created_at.desc()).all()
    return [{
        "id": o.id,
        "order_id": o.order_id,
        "created_at": o.created_at.isoformat(),
        "amount_usdt": o.amount_usdt,
        "bank": o.bank,
        "phone": o.phone,
        "deposit_address": o.deposit_address,
        "status": o.status
    } for o in orders]

@app.patch("/api/orders/{order_id}")
async def update_order_status(order_id: str, update: OrderUpdate, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.order_id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    
    if update.status not in ["pending", "paid", "canceled"]:
        raise HTTPException(status_code=400, detail="Неверный статус")
    
    order.status = update.status
    db.commit()
    return {"status": "success", "new_status": order.status}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

