from fastapi import FastAPI, Depends, HTTPException, Query
from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime, timedelta
import random

from fastapi.middleware.cors import CORSMiddleware
from database import create_db_and_tables, get_session
from models import User, Name, Swipe, SwipeDecision

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    create_db_and_tables()
    # Seed users if they don't exist
    with Session(get_session().__next__().bind) as session:
        if not session.exec(select(User).where(User.name == "Kyle")).first():
            session.add(User(name="Kyle"))
        if not session.exec(select(User).where(User.name == "Emily")).first():
            session.add(User(name="Emily"))
        session.commit()

@app.get("/")
def read_root():
    return {"message": "NameMatch API is running"}

@app.get("/users", response_model=List[User])
def get_users(session: Session = Depends(get_session)):
    return session.exec(select(User)).all()

@app.get("/recommendations/{user_id}", response_model=List[Name])
def get_recommendations(user_id: int, limit: int = 10, session: Session = Depends(get_session)):
    """
    Get names to swipe on.
    Logic (SRS):
    1. EXCLUDE if swiped 'dislike'.
    2. EXCLUDE if swiped 'like' RECENTLY (< 24 hours).
    3. EXCLUDE if swiped 'like' TOO MANY TIMES (>= 3).
    4. INCLUDE otherwise (never swiped, or swiped 'like' > 24h ago).
    """
    # Fetch all swipes for this user
    user_swipes = session.exec(select(Swipe).where(Swipe.user_id == user_id).order_by(Swipe.timestamp.desc())).all()
    
    # Process swipe history
    excluded_name_ids = set()
    name_like_counts = {} # name_id -> count
    dislike_counts = {} # name_id -> count
    
    now = datetime.utcnow()
    
    for s in user_swipes:
        # If we already decided to exclude this name, skip
        if s.name_id in excluded_name_ids:
            continue
            
        if s.decision == SwipeDecision.dislike:
            # Track dislike counts
            dislike_counts[s.name_id] = dislike_counts.get(s.name_id, 0) + 1
            
            # Recency check: If disliked recently (< 24h), exclude temporarily
            if (now - s.timestamp) < timedelta(hours=24):
                excluded_name_ids.add(s.name_id)

            # 3-Strike Rule: If disliked 3 times, exclude PERMANENTLY
            if dislike_counts[s.name_id] >= 3:
                excluded_name_ids.add(s.name_id)

        elif s.decision in [SwipeDecision.like, SwipeDecision.superlike]:
            # Check recurrence
            name_like_counts[s.name_id] = name_like_counts.get(s.name_id, 0) + 1
            
            # If recently swiped (< 24h), exclude
            if (now - s.timestamp) < timedelta(hours=24):
                excluded_name_ids.add(s.name_id)
            
            # If confirmed enough times, exclude (mastered)
            if name_like_counts[s.name_id] >= 3:
                excluded_name_ids.add(s.name_id)
    
    # Select names NOT in excluded list
    # Use limits cautiously with ID filtering if set is huge, but for names it's fine.
    # To handle "random" with exclusions, we fetch a batch.
    
    query = select(Name).where(Name.id.not_in(excluded_name_ids))
    # Optimize: If we just want random 10, better to fetch IDs or use random order in DB side if possible.
    # SQLite random: func.random()
    from sqlalchemy import func
    query = query.order_by(func.random()).limit(limit)
    
    results = session.exec(query).all()
    return results

@app.get("/dashboard")
def get_dashboard(session: Session = Depends(get_session)):
    """
    Return lists of names for dashboard buckets.
    """
    # Fetch all swipes
    # Join with User and Name
    results = session.exec(select(Swipe, User, Name).join(User).join(Name)).all()
    
    # Organize by name
    # name_id -> { 'name': str, 'Kyle': 'like', 'Emily': 'dislike' }
    from collections import defaultdict
    data = defaultdict(dict)
    name_objs = {}
    
    users = session.exec(select(User)).all()
    user_names = [u.name for u in users] # ["Kyle", "Emily"]
    
    for swipe, user, name in results:
        data[name.id][user.name] = swipe.decision
        name_objs[name.id] = name
        
    dashboard = {
        "matches": [],
        "kyle_likes": [],
        "emily_likes": [],
        "rejected": []
    }
    
    for nid, decisions in data.items():
        name = name_objs[nid]
        
        kyle_dec = decisions.get("Kyle")
        emily_dec = decisions.get("Emily")
        
        is_kyle_like = kyle_dec in [SwipeDecision.like, SwipeDecision.superlike]
        is_emily_like = emily_dec in [SwipeDecision.like, SwipeDecision.superlike]
        is_kyle_dislike = kyle_dec == SwipeDecision.dislike
        is_emily_dislike = emily_dec == SwipeDecision.dislike
        
        if is_kyle_like and is_emily_like:
            dashboard["matches"].append(name)
        elif is_kyle_like:
            # Kyle liked it (and it's not a match, so Emily either Pending or Dislike)
            dashboard["kyle_likes"].append(name)
        elif is_emily_like:
            # Emily liked it (and it's not a match, so Kyle either Pending or Dislike)
            dashboard["emily_likes"].append(name)
        elif is_kyle_dislike and is_emily_dislike:
            # Both explicitly disliked
            dashboard["rejected"].append(name)
            
    return dashboard

@app.get("/matches", response_model=List[Name])
def get_matches(session: Session = Depends(get_session)):
    """
    Get names that have been liked by at least 2 users (representing a match).
    """
    from sqlalchemy import func
    # Select names where the count of 'like' swipes is >= 2
    # Assuming we only have 2 users for now.
    statement = (
        select(Name)
        .join(Swipe)
        .where(Swipe.decision == "like")
        .group_by(Name.id)
        .having(func.count(Swipe.user_id.distinct()) >= 2)
    )
    return session.exec(statement).all()

@app.post("/swipe")
def create_swipe(swipe: Swipe, session: Session = Depends(get_session)):
    session.add(swipe)
    session.commit()
    session.refresh(swipe)
    return swipe

@app.post("/generate")
def generate_names(session: Session = Depends(get_session)):
    import pandas as pd
    import os
    from openai import OpenAI
    
    # 1. Fetch data
    query = select(Swipe.name_id, Swipe.user_id, Swipe.decision, Name.name)\
        .join(Name, Swipe.name_id == Name.id)
    results = session.exec(query).all()
    
    if not results:
        return {"message": "No data to analyze yet."}
        
    df = pd.DataFrame(results, columns=["name_id", "user_id", "decision", "name_str"])
    
    # 2. Pivot
    # Map user_id to names (1=Kyle, 2=Emily - hardcoded for MVP or fetch user mapping)
    # Ideally fetch user map
    user_map = {u.id: u.name for u in session.exec(select(User)).all()}
    df['user_name'] = df['user_id'].map(user_map)
    
    pivot = df.pivot_table(index='name_str', columns='user_name', values='decision', aggfunc='first', fill_value='unknown')
    
    # 3. Summarize
    # Ensure columns exist
    if 'Kyle' not in pivot.columns: pivot['Kyle'] = 'unknown'
    if 'Emily' not in pivot.columns: pivot['Emily'] = 'unknown'
    
    both_like = pivot[(pivot['Kyle'] == 'like') & (pivot['Emily'] == 'like')].index.tolist()
    kyle_likes = pivot[(pivot['Kyle'] == 'like') & (pivot['Emily'] != 'like')].index.tolist()
    emily_likes = pivot[(pivot['Emily'] == 'like') & (pivot['Kyle'] != 'like')].index.tolist()
    disliked = pivot[(pivot['Kyle'] == 'dislike') | (pivot['Emily'] == 'dislike')].index.tolist()
    
    summary = f"""
    We are looking for baby names. Here is our feedback so far:
    
    Names we BOTH like: {', '.join(both_like)}
    Names Kyle likes (but Emily hasn't said yes to): {', '.join(kyle_likes)}
    Names Emily likes (but Kyle hasn't said yes to): {', '.join(emily_likes)}
    Names we disliked: {', '.join(disliked[:50])} (truncated)
    
    Based on this style, please generate 20 NEW, unique baby names we might both like.
    Return ONLY a JSON list of strings, e.g. ["Name1", "Name2"].
    """
    
    # 4. Call AI
    from dotenv import load_dotenv
    load_dotenv(override=True)
    
    api_key = os.environ.get("OPENROUTER_API_KEY")
    # Fallback to OPENAI_API_KEY
    if not api_key:
        api_key = os.environ.get("OPENAI_API_KEY")

    # DEBUG: Check if key is loaded and valid format
    print(f"DEBUG: Current Working Directory: {os.getcwd()}")
    from pathlib import Path
    env_path = Path('.') / '.env'
    print(f"DEBUG: .env exists at {env_path.absolute()}? {env_path.exists()}")
    
    if api_key:
        masked = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 10 else "SHORT_KEY"
        print(f"DEBUG: Using API Key: {masked} (Length: {len(api_key)})")
        # Check for common issues like quotes remaining
        if api_key.startswith('"') or api_key.startswith("'"):
            print("WARNING: API Key starts with quote! Check .env file.")
    else:
        print("DEBUG: No API Key found after load_dotenv()")

    if not api_key:
        print("Summary for manual review:\n" + summary)
        return {"message": "OPENROUTER_API_KEY not set. Check server logs for summary.", "summary": summary}
        
    client = OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
    )
    
    try:
        model = os.environ.get("OPENROUTER_MODEL", "google/gemini-2.0-flash-exp:free")
        response = client.chat.completions.create(
            # Using a model available on OpenRouter (GPT-4o is available via openai/gpt-4o, or others)
            # Defaulting to Gemini 2.0 Flash (free and fast) or user preference
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful baby name consultant. Return only JSON."},
                {"role": "user", "content": summary}
            ],
            # OpenRouter supports response_format but sometimes it varies by provider.
            # GPT-4o usually supports json_object.
            response_format={"type": "json_object"},
            extra_headers={
                "HTTP-Referer": "http://localhost:5173", # Optional, for OpenRouter rankings
                "X-Title": "NameMatch",
            },
        )
        content = response.choices[0].message.content
        import json
        try:
            new_names_dict = json.loads(content)
        except json.JSONDecodeError:
            print(f"RAW CONTENT ERROR: {content}")
            raise HTTPException(status_code=500, detail=f"Failed to parse JSON from AI: {content}")

        if isinstance(new_names_dict, list):
            new_names = new_names_dict
        else:
            new_names = new_names_dict.get("names", [])
            
        print(f"AI SUGGESTED: {new_names}")
            
        # Add to DB
        count = 0
        skipped = 0
        for n in new_names:
            # Check if name exists
            existing_name = session.exec(select(Name).where(Name.name == n)).first()
            if not existing_name:
                session.add(Name(name=n))
                count += 1
            else:
                skipped += 1
                # Check if THIS user has swiped it? 
                # If name exists but user has NOT swiped it, it should show up.
                # If name exists AND user swiped it, it won't show up.
                # If duplicates are high, we need to loop again?
        
        session.commit()
        msg = f"Generated {len(new_names)} suggestions. Added {count} new names to DB. Skipped {skipped} as duplicates."
        print(msg)
        return {"message": msg, "names": new_names, "added": count, "skipped": skipped}
        
    except Exception as e:
        print(f"GENERATION ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))

