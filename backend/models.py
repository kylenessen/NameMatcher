from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from enum import Enum

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    
    swipes: List["Swipe"] = Relationship(back_populates="user")

class Name(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    gender: Optional[str] = None
    origin: Optional[str] = None
    meaning: Optional[str] = None
    
    swipes: List["Swipe"] = Relationship(back_populates="name_obj")

class SwipeDecision(str, Enum):
    like = "like"
    dislike = "dislike"
    superlike = "superlike"
    maybe = "maybe"

class Swipe(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    name_id: int = Field(foreign_key="name.id")
    decision: SwipeDecision
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    user: User = Relationship(back_populates="swipes")
    name_obj: Name = Relationship(back_populates="swipes")
