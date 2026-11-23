from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from app.core.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    dashboards = relationship("Dashboard", back_populates="user", cascade="all, delete-orphan")

class Earthquake(Base):
    __tablename__ = "earthquakes"
    id = Column(Integer, primary_key=True, index=True)
    datetime_utc = Column(DateTime, nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    depth = Column(Float, nullable=False)
    energy_class = Column(Float, nullable=False, index=True)
    region = Column(String, default="Байкальская рифтовая зона")

    records = relationship("SeismicRecord", back_populates="earthquake", cascade="all, delete-orphan")

class Fault(Base):
    __tablename__ = "faults"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    geom = Column(Geometry(geometry_type="LINESTRING", srid=4326), nullable=False)
    fault_type = Column(String, default="active")

class SeismicRecord(Base):
    __tablename__ = "seismic_records"
    id = Column(Integer, primary_key=True, index=True)
    earthquake_id = Column(Integer, ForeignKey("earthquakes.id"), nullable=False)
    station_code = Column(String, nullable=False)
    channel = Column(String, nullable=False)  # BHE, BHN, BHZ
    sampling_rate = Column(Float, default=100.0)
    file_path = Column(String, nullable=False)

    earthquake = relationship("Earthquake", back_populates="records")

class WeatherStation(Base):
    __tablename__ = "weather_stations"
    id = Column(Integer, primary_key=True, index=True)
    station_name = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    measurements = relationship("WeatherMeasurement", back_populates="station", cascade="all, delete-orphan")

class WeatherMeasurement(Base):
    __tablename__ = "weather_measurements"
    id = Column(Integer, primary_key=True, index=True)
    station_id = Column(Integer, ForeignKey("weather_stations.id"), nullable=False)
    datetime_utc = Column(DateTime, nullable=False, index=True)
    wind_speed = Column(Float, nullable=False)
    wind_direction = Column(Float, nullable=False)

    station = relationship("WeatherStation", back_populates="measurements")

class Dashboard(Base):
    __tablename__ = "dashboards"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    configuration = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="dashboards")
