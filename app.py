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

@app.get("/favicon.ico")
async def favicon():
    return {"status": "ok"}

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if os.getenv("RENDER"):
    try:
        DB_PATH = "/var/data/orders.db"
        os.makedirs("/var/data", exist_ok=True)
    except:
        DB_PATH = os.path.join(BASE_DIR, "orders.db")
else:
    DB_PATH = os.path.join(BASE_DIR, "orders.db")

DATABASE_URL = f"sqlite:///{DB_PATH}"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.now)
    amount_usdt = Column(Float)
    receive_amount = Column(Float)
    payment_method = Column(String)  # card or spb
    card_number = Column(String, nullable=True)
    spb_bank = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    deposit_address = Column(String)
    status = Column(String, default="accepted")  # accepted -> pending -> paid/canceled

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class OrderCreate(BaseModel):
    amount_usdt: float
    receive_amount: float
    method: str
    card_number: Optional[str] = None
    spb_bank: Optional[str] = None
    phone: Optional[str] = None

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
    
    order_id = str(uuid.uuid4())[:8].upper()
    
    order_count = db.query(Order).count()
    address_index = order_count
    
    try:
        from tron_wallet import create_trc20_address
        deposit_address = create_trc20_address(address_index)
    except Exception as e:
        logger.error(f"Error creating address: {e}")
        raise HTTPException(status_code=500, detail="Не удалось создать адрес депозита")
    
    logger.info(f"Deposit address: {deposit_address}")
    if not deposit_address:
        raise HTTPException(status_code=500, detail="Не удалось получить адрес депозита")
    
    new_order = Order(
        order_id=order_id,
        amount_usdt=order.amount_usdt,
        receive_amount=order.receive_amount,
        payment_method=order.method,
        card_number=order.card_number,
        spb_bank=order.spb_bank,
        phone=order.phone,
        deposit_address=deposit_address,
        status="accepted"
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order)
    
    import threading
    
    def run_withdrawal():
        from deposit_from_funpay import deposit_from_funpay
        try:
            result = deposit_from_funpay(
                order_id,
                order.method,
                order.card_number,
                order.spb_bank,
                order.phone,
                order.receive_amount
            )
            logger.info(f"FunPay result: {result}")
        except Exception as e:
            logger.error(f"FunPay withdrawal error: {e}")
    
    withdrawal_thread = threading.Thread(target=run_withdrawal)
    withdrawal_thread.start()
    
    new_order.status = "pending"
    db.commit()
    
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
        "receive_amount": o.receive_amount,
        "payment_method": o.payment_method,
        "card_number": o.card_number,
        "spb_bank": o.spb_bank,
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

rate_cache = {"rate": None, "time": 0}

@app.get("/api/rate")
async def get_usdt_rate():
    import time
    
    if rate_cache["rate"] and (time.time() - rate_cache["time"]) < 60:
        return {"rate": rate_cache["rate"], "source": "Rapira (cached)"}
    
    try:
        import requests
        from xml.etree import ElementTree as ET
        
        url = 'https://api.rapira.net/open/market/rates_xml'
        headers = {'Accept': 'application/xml'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        root = ET.fromstring(response.content)
        for item in root.findall('item'):
            fr = item.find('from').text
            to = item.find('to').text
            out = item.find('out').text
            if fr == 'USDT' and to == 'RUB':
                rate_cache["rate"] = float(out)
                rate_cache["time"] = time.time()
                return {"rate": float(out), "source": "Rapira"}
        
        return {"error": "Пара USDT/RUB не найдена"}
    except Exception as e:
        logger.error(f"Rate fetch error: {e}")
        if rate_cache["rate"]:
            return {"rate": rate_cache["rate"], "source": "Rapira (cached)"}
        return {"error": str(e)}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

