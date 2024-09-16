import os
import psycopg2
from psycopg2 import sql
from datetime import date
from typing import Any, Optional
import random

db_params: dict[str, Any] = {
    "dbname": os.environ.get("PGDATABASE"),
    "user": os.environ.get("PGUSER"),
    "password": os.environ.get("PGPASSWORD"),
    "host": os.environ.get("PGHOST"),
    "port": os.environ.get("PGPORT")
}

def get_db_connection():
    return psycopg2.connect(**db_params)

def create_tables():
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS gifts (
            id SERIAL PRIMARY KEY,
            giver TEXT NOT NULL,
            gift_details TEXT NOT NULL,
            date_received DATE NOT NULL,
            cost NUMERIC(10, 2),
            category TEXT,
            thank_you_sent BOOLEAN DEFAULT FALSE
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS gift_suggestions (
            id SERIAL PRIMARY KEY,
            gift_id INTEGER REFERENCES gifts(id),
            suggested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            accepted BOOLEAN
        )
    """)
    
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name='gifts' AND column_name='category'
    """)
    if cur.fetchone() is None:
        cur.execute("ALTER TABLE gifts ADD COLUMN category TEXT")
    
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name='gifts' AND column_name='thank_you_sent'
    """)
    if cur.fetchone() is None:
        cur.execute("ALTER TABLE gifts ADD COLUMN thank_you_sent BOOLEAN DEFAULT FALSE")
    
    conn.commit()
    cur.close()
    conn.close()

def add_gift(giver: str, gift_details: str, date_received: date, cost: Optional[float] = None, category: Optional[str] = None):
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute(
        sql.SQL("INSERT INTO gifts (giver, gift_details, date_received, cost, category) VALUES (%s, %s, %s, %s, %s)"),
        (giver, gift_details, date_received, cost, category)
    )
    
    conn.commit()
    cur.close()
    conn.close()

def get_all_gifts():
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT * FROM gifts ORDER BY date_received DESC")
    gifts = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return gifts

def get_gift_categories():
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT DISTINCT category FROM gifts WHERE category IS NOT NULL AND category != ''")
    categories = [row[0] for row in cur.fetchall()]
    
    cur.close()
    conn.close()
    
    return categories

def get_filtered_gifts(category: Optional[str] = None, start_date: Optional[date] = None, end_date: Optional[date] = None):
    conn = get_db_connection()
    cur = conn.cursor()
    
    query = "SELECT * FROM gifts WHERE 1=1"
    params = []
    
    if category:
        query += " AND category = %s"
        params.append(category)
    
    if start_date:
        query += " AND date_received >= %s"
        params.append(start_date)
    
    if end_date:
        query += " AND date_received <= %s"
        params.append(end_date)
    
    query += " ORDER BY date_received DESC"
    
    cur.execute(query, params)
    gifts = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return gifts

def send_thank_you_note(gift_id: int, note: str) -> bool:
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute(
            "UPDATE gifts SET thank_you_sent = TRUE WHERE id = %s",
            (gift_id,)
        )
        conn.commit()
        success = True
    except Exception as e:
        print(f"Error sending thank you note: {e}")
        conn.rollback()
        success = False
    
    cur.close()
    conn.close()
    
    return success

def get_gift_suggestions(giver: Optional[str] = None, category: Optional[str] = None, num_suggestions: int = 3):
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        query = """
        WITH ranked_gifts AS (
            SELECT 
                g.id,
                g.gift_details,
                g.category,
                g.cost,
                COUNT(*) OVER (PARTITION BY g.giver) as giver_frequency,
                ROW_NUMBER() OVER (PARTITION BY g.category ORDER BY g.cost DESC) as rank_in_category
            FROM gifts g
            LEFT JOIN gift_suggestions gs ON g.id = gs.gift_id
            WHERE gs.id IS NULL OR gs.accepted IS NULL OR gs.accepted = FALSE
        """
        params = []
        
        if giver:
            query += " AND g.giver = %s"
            params.append(giver)
        
        if category:
            query += " AND g.category = %s"
            params.append(category)
        
        query += """
        )
        SELECT id, gift_details, category, cost
        FROM ranked_gifts
        WHERE rank_in_category <= 3
        ORDER BY giver_frequency DESC, cost DESC
        LIMIT %s
        """
        params.append(num_suggestions)
        
        cur.execute(query, params)
        suggestions = cur.fetchall()
        
        if not suggestions:
            return {"status": "no_suggestions", "message": "No suitable gift suggestions found based on the criteria.", "suggestions": []}
        
        for suggestion in suggestions:
            cur.execute("INSERT INTO gift_suggestions (gift_id) VALUES (%s)", (suggestion[0],))
        
        conn.commit()
        
        return {
            "status": "success",
            "message": f"Found {len(suggestions)} suggestion(s) based on the criteria.",
            "suggestions": [{"id": s[0], "gift": s[1], "category": s[2], "cost": s[3]} for s in suggestions]
        }
    except Exception as e:
        conn.rollback()
        return {"status": "error", "message": f"An error occurred while fetching gift suggestions: {str(e)}", "suggestions": []}
    finally:
        cur.close()
        conn.close()

def clear_all_gifts():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM gift_suggestions")
        cur.execute("DELETE FROM gifts")
        conn.commit()
    except Exception as e:
        print(f"Error clearing gifts: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

def update_suggestion_feedback(suggestion_id: int, accepted: bool):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE gift_suggestions SET accepted = %s WHERE id = %s", (accepted, suggestion_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating suggestion feedback: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()
