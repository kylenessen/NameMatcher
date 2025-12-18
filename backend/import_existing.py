import csv
import sys
from sqlmodel import Session, select
from database import engine, create_db_and_tables
from models import User, Name, Swipe, SwipeDecision

def get_decision(val):
    val = val.strip().upper()
    if 'Y' in val: return SwipeDecision.like
    if 'N' in val: return SwipeDecision.dislike
    if 'M' in val: return SwipeDecision.maybe
    return None

def main():
    create_db_and_tables()
    
    with Session(engine) as session:
        # Ensure users exist
        kyle = session.exec(select(User).where(User.name == "Kyle")).first()
        if not kyle:
            kyle = User(name="Kyle")
            session.add(kyle)
        
        emily = session.exec(select(User).where(User.name == "Emily")).first()
        if not emily:
            emily = User(name="Emily")
            session.add(emily)
        
        session.commit()
        session.refresh(kyle)
        session.refresh(emily)
        
        # Read file
        filepath = "../existing_names.md"
        with open(filepath, 'r') as f:
            lines = f.readlines()
        
        # Parse (skip header)
        # Format: Name \t Emily \t Kyle
        # But looking at file content, it might be TABS or SPACES.
        # Line 1: Name	Emily	Kyle
        # Line 2: Patrick	Y	N
        
        for line in lines[1:]: # Skip header
            parts = line.strip().split('\t')
            if len(parts) < 3:
                # Try splitting by multiple spaces if tabs fail? 
                # Or maybe it's mixed.
                # Let's try simple split() which handles all whitespace
                parts = line.strip().split()
                # But names might have spaces? "Noah "
                # The file view showed tabs likely, or fixed width.
                # Let's assume the first token is name, next is Emily, next is Kyle?
                # Line 49: Mayer 	M	N  <- Name has space? Or just tab?
                # Line 51: Lennon	M	N
                
            # Re-evaluating split strategy based on file view:
            # "Name	Emily	Kyle"
            # It looks like tab separated.
            parts = [p.strip() for p in line.split('\t') if p.strip()]
            
            if len(parts) < 3:
                print(f"Skipping ambiguous line: {line.strip()}")
                continue
                
            name_str = parts[0]
            emily_val = parts[1]
            kyle_val = parts[2]
            
            # Create Name
            name_obj = session.exec(select(Name).where(Name.name == name_str)).first()
            if not name_obj:
                name_obj = Name(name=name_str)
                session.add(name_obj)
                session.commit()
                session.refresh(name_obj)
            
            # Create Swipes
            e_dec = get_decision(emily_val)
            if e_dec:
                # Check if exists
                existing_swipe = session.exec(select(Swipe).where(Swipe.user_id == emily.id, Swipe.name_id == name_obj.id)).first()
                if not existing_swipe:
                    session.add(Swipe(user_id=emily.id, name_id=name_obj.id, decision=e_dec))
            
            k_dec = get_decision(kyle_val)
            if k_dec:
                 existing_swipe = session.exec(select(Swipe).where(Swipe.user_id == kyle.id, Swipe.name_id == name_obj.id)).first()
                 if not existing_swipe:
                    session.add(Swipe(user_id=kyle.id, name_id=name_obj.id, decision=k_dec))
        
        session.commit()
        print("Import complete!")

if __name__ == "__main__":
    main()
