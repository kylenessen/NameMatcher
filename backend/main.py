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
    return {"message": "Baby Name Tinder API is running"}

@app.get("/users", response_model=List[User])
def get_users(session: Session = Depends(get_session)):
    return session.exec(select(User)).all()

@app.get("/recommendations/{user_id}", response_model=List[Name])
def get_recommendations(user_id: int, limit: int = 10, session: Session = Depends(get_session)):
    """
    Get names to swipe on.
    Logic:
    1. Exclude names already swiped by this user RECENTLY (e.g., last 30 days).
    (For now, strict exclusion of ANY swipe to keep it simple, later add spaced repetition).
    """
    # Get IDs of names already swiped by user
    subquery = select(Swipe.name_id).where(Swipe.user_id == user_id)
    swiped_name_ids = session.exec(subquery).all()
    
    # Select names NOT in swiped_name_ids
    # Using simple random sample for now
    query = select(Name).where(Name.id.not_in(swiped_name_ids)).limit(limit)
    results = session.exec(query).all()
    
    # If we run out of names, maybe show old ones? For now, just return what we have.
    # Ideally shuffle them
    results = list(results)
    random.shuffle(results)
    return results

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
                "X-Title": "Baby Name Tinder",
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

