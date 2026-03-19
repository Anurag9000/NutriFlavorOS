"""
PostgreSQL Database Schema and Configuration
Uses SQLAlchemy ORM for production persistence
"""
import os
from sqlalchemy import create_engine, Column, Integer, String, Float, JSON, ForeignKey, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

# Database URL - fallback to SQLite for local development if PG is not available
DB_URL = os.getenv("DATABASE_URL", "sqlite:///nutriflavor.db")

engine = create_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class DBUser(Base):
    """User Profile and Biometrics"""
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, index=True)
    name = Column(String)
    age = Column(Integer)
    weight_kg = Column(Float)
    height_cm = Column(Float)
    gender = Column(String)
    activity_level = Column(Float)
    goal = Column(String)
    
    # Store preferences as JSON for flexibility
    liked_ingredients = Column(JSON)
    disliked_ingredients = Column(JSON)
    dietary_restrictions = Column(JSON)
    health_conditions = Column(JSON)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    plans = relationship("DBMealPlan", back_populates="user")

class DBRecipe(Base):
    """Recipe Database"""
    __tablename__ = "recipes"
    
    id = Column(String, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String)
    image_url = Column(String)
    ingredients = Column(JSON)
    calories = Column(Integer)
    macros = Column(JSON)
    flavor_profile = Column(JSON)
    tags = Column(JSON)
    cuisine = Column(String)
    instructions = Column(JSON)
    estimated_cost = Column(Float)

class DBMealPlan(Base):
    """Saved Meal Plans"""
    __tablename__ = "meal_plans"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id"))
    plan_data = Column(JSON) # Full PlanResponse dump
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("DBUser", back_populates="plans")

def init_db():
    """Create all tables"""
    Base.metadata.create_all(bind=engine)

def get_db():
    """Dependency for FastAPI routes"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
