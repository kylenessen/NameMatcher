import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from datetime import datetime, timedelta
from unittest.mock import patch

# Import backend modules
# We need to make sure we're importing from the same file
from main import app, get_session
from models import User, Name, Swipe, SwipeDecision

from sqlmodel.pool import StaticPool

# Setup in-memory DB
# Use StaticPool to share the same in-memory database across the same process
engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_test_session():
    with Session(engine) as session:
        yield session

# Override dependency
app.dependency_overrides[get_session] = get_test_session
client = TestClient(app)

@pytest.fixture(name="session")
def session_fixture():
    create_db_and_tables()
    with Session(engine) as session:
        # Seed basic data
        user = User(name="TestUser")
        session.add(user)
        
        # Add a few names
        names_list = ["Alice", "Bob", "Charlie", "David", "Eve", "Frank", "Grace"]
        for n in names_list:
            session.add(Name(name=n))
            
        session.commit()
        yield session
    SQLModel.metadata.drop_all(engine)

def test_fresh_user_sees_names(session):
    user = session.exec(select(User).where(User.name == "TestUser")).first()
    response = client.get(f"/recommendations/{user.id}")
    assert response.status_code == 200
    names = response.json()
    # Since we have 7 names and default limit is 10, we should see all of them.
    assert len(names) == 7
    assert any(n['name'] == "Alice" for n in names)

def test_like_cooldown_manual_timestamps(session):
    """
    Test that a 'like' hides the name for 24h.
    """
    user = session.exec(select(User).where(User.name == "TestUser")).first()
    name = session.exec(select(Name).where(Name.name == "Alice")).first()
    
    # 1. Swipe Like NOW
    client.post("/swipe", json={
        "user_id": user.id,
        "name_id": name.id,
        "decision": "like"
    })
    
    # 2. Should be hidden immediately
    response = client.get(f"/recommendations/{user.id}")
    names = response.json()
    assert not any(n['id'] == name.id for n in names), "Liked name appeared immediately (should be hidden for 24h)"

    # 3. Simulate time passing > 24h
    # We update the existing swipe to be from 25 hours ago
    swipe = session.exec(select(Swipe).where(Swipe.name_id == name.id, Swipe.user_id == user.id)).one()
    swipe.timestamp = datetime.utcnow() - timedelta(hours=25)
    session.add(swipe)
    session.commit()

    # 4. Should be visible again
    response = client.get(f"/recommendations/{user.id}")
    names = response.json()
    assert any(n['id'] == name.id for n in names), "Liked name from 25h ago should reappear"
    
def test_cooldown_logic_via_db(session):
    user = session.exec(select(User).where(User.name == "TestUser")).first()
    name = session.exec(select(Name).where(Name.name == "Bob")).first()
    
    # Add swipe 23 hours ago
    ts_recent = datetime.utcnow() - timedelta(hours=23)
    session.add(Swipe(user_id=user.id, name_id=name.id, decision="like", timestamp=ts_recent))
    session.commit()
    
    # Should be HIDDEN
    response = client.get(f"/recommendations/{user.id}")
    assert not any(n['id'] == name.id for n in response.json()), "Name swiped 23h ago should be hidden"
    
    # Update timestamp to 25 hours ago
    swipe = session.exec(select(Swipe).where(Swipe.name_id == name.id)).first()
    swipe.timestamp = datetime.utcnow() - timedelta(hours=25)
    session.add(swipe) # update
    session.commit()
    
    # Should be VISIBLE
    response = client.get(f"/recommendations/{user.id}")
    assert any(n['id'] == name.id for n in response.json()), "Name swiped 25h ago should be visible"

def test_3_strike_dislike(session):
    user = session.exec(select(User).where(User.name == "TestUser")).first()
    name = session.exec(select(Name).where(Name.name == "Charlie")).first()
    
    def add_past_dislike(hours_ago):
        ts = datetime.utcnow() - timedelta(hours=hours_ago)
        session.add(Swipe(user_id=user.id, name_id=name.id, decision="dislike", timestamp=ts))
        session.commit()
        
    # Strike 1 (25h ago) -> Visible
    add_past_dislike(25)
    response = client.get(f"/recommendations/{user.id}")
    assert any(n['id'] == name.id for n in response.json())
    
    # Strike 2 (25h ago) -> Visible
    add_past_dislike(25)
    response = client.get(f"/recommendations/{user.id}")
    assert any(n['id'] == name.id for n in response.json())
    
    # Strike 3 (25h ago) -> BANNED
    add_past_dislike(25)
    response = client.get(f"/recommendations/{user.id}")
    assert not any(n['id'] == name.id for n in response.json()), "Name should be banned after 3 dislikes"

def test_3_strike_mastery(session):
    user = session.exec(select(User).where(User.name == "TestUser")).first()
    name = session.exec(select(Name).where(Name.name == "David")).first()
    
    def add_past_like(hours_ago):
        ts = datetime.utcnow() - timedelta(hours=hours_ago)
        session.add(Swipe(user_id=user.id, name_id=name.id, decision="like", timestamp=ts))
        session.commit()
        
    # Like 1 (48h ago) -> Visible
    add_past_like(48)
    response = client.get(f"/recommendations/{user.id}")
    assert any(n['id'] == name.id for n in response.json())
    
    # Like 2 (48h ago) -> Visible
    add_past_like(48)
    response = client.get(f"/recommendations/{user.id}")
    assert any(n['id'] == name.id for n in response.json())
    
    # Like 3 (48h ago) -> MASTERED (Hidden from swipe deck)
    add_past_like(48)
    response = client.get(f"/recommendations/{user.id}")
    assert not any(n['id'] == name.id for n in response.json()), "Name should be graduated after 3 likes"
