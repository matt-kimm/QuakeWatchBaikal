import os
import datetime
from fastapi import FastAPI, HTTPException, status, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import jwt
from passlib.context import CryptContext
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from typing import List, Optional

SECRET_KEY = os.getenv("JWT_SECRET", "super_secret_key_for_baikal_2026")
ALGORITHM = "HS256"
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:secret_password@db:5432/quakewatch")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# =====================================================================
# МОДЕЛИ БД
# =====================================================================
class UserDB(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)

class EarthquakeDB(Base):
    __tablename__ = "earthquakes"
    id = Column(Integer, primary_key=True, index=True)
    time = Column(DateTime, nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    depth = Column(Float, nullable=False)
    energy_class = Column(Float, nullable=False, index=True)
    magnitude = Column(Float, nullable=True)

class FaultDB(Base):
    __tablename__ = "faults"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    geometry = Column(String, nullable=False) # Храним как JSON-строку [[lat1, lon1], [lat2, lon2], ...]

Base.metadata.create_all(bind=engine)

app = FastAPI(title="QuakeWatchBaikal API - Phase 3")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_headers=["*"],
    allow_methods=["*"],
)

class UserAuth(BaseModel):
    username: str
    password: str

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Хеширование паролей
def get_password_hash(password):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.datetime.utcnow() + datetime.timedelta(hours=2)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# =====================================================================
# ЭНДПОИНТЫ АВТОРИЗАЦИИ
# =====================================================================
@app.post("/api/register")
def register(user: UserAuth, db: Session = Depends(get_db)):
    db_user = db.query(UserDB).filter(UserDB.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    hashed_password = get_password_hash(user.password)
    new_user = UserDB(username=user.username, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    return {"message": "User registered successfully"}

@app.post("/api/login")
def login(user: UserAuth, db: Session = Depends(get_db)):
    db_user = db.query(UserDB).filter(UserDB.username == user.username).first()
    if not db_user or not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    token = create_access_token(data={"sub": db_user.username})
    return {"access_token": token, "token_type": "bearer"}

# =====================================================================
# ФУНКЦИОНАЛЬНЫЕ ЭНДПОИНТЫ (FR-2, FR-3)
# =====================================================================

@app.get("/api/earthquakes")
def get_earthquakes(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    min_class: Optional[float] = Query(None),
    db: Session = Depends(get_db)
):
    """Получение землетрясений с фильтрацией (FR-2)"""
    query = db.query(EarthquakeDB)
    
    if start_date:
        query = query.filter(EarthquakeDB.time >= datetime.datetime.fromisoformat(start_date))
    if end_date:
        query = query.filter(EarthquakeDB.time <= datetime.datetime.fromisoformat(end_date))
    if min_class is not None:
        query = query.filter(EarthquakeDB.energy_class >= min_class)
        
    return query.all()

@app.get("/api/faults")
def get_faults(db: Session = Depends(get_db)):
    """Получение каталога разломов для отрисовки на карте (FR-3)"""
    return db.query(FaultDB).all()

@app.post("/api/debug/seed")
def seed_debug_data(db: Session = Depends(get_db)):
    """Наполнение базы реалистичными сейсмоданными Байкала"""
    db.query(EarthquakeDB).delete()
    db.query(FaultDB).delete()
    
    # 1. Добавляем землетрясения (Ким Матвей Сергеевич, данные для тестов)
    eqs = [
        EarthquakeDB(time=datetime.datetime(2026, 11, 1, 10, 30), latitude=51.85, longitude=104.90, depth=12.0, energy_class=12.5, magnitude=4.7),
        EarthquakeDB(time=datetime.datetime(2026, 11, 5, 0, 15), latitude=52.40, longitude=106.20, depth=18.0, energy_class=9.0, magnitude=3.1),
        EarthquakeDB(time=datetime.datetime(2026, 11, 8, 22, 10), latitude=55.70, longitude=109.80, depth=10.0, energy_class=14.0, magnitude=5.6),
        EarthquakeDB(time=datetime.datetime(2026, 10, 20, 14, 0), latitude=51.50, longitude=104.30, depth=15.0, energy_class=10.5, magnitude=3.8)
    ]
    
    # 2. Добавляем разломы (массивы координат линий геометрии)
    faults = [
        FaultDB(name="Обручевский сброс", geometry="[[51.5, 104.2], [51.9, 105.1], [52.3, 105.8]]"),
        FaultDB(name="Ангарский разлом", geometry="[[52.1, 104.0], [52.6, 104.8], [53.2, 105.5]]"),
        FaultDB(name="Главный Саянский разлом", geometry="[[51.2, 102.5], [51.6, 103.8], [51.9, 104.4]]")
    ]
    
    db.add_all(eqs)
    db.add_all(faults)
    db.commit()
    return {"message": "Каталоги землетрясений и разломов Байкала успешно загружены в БД!"}
