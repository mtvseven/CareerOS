"""
Migration script to move data from local SQLite to Google Sheets.
Run this script ONCE to transfer your data.
"""
import sqlite3
import pandas as pd
import uuid
from utils import db_manager

DB_FILE = "career_os.db"

def migrate_data():
    print(f"Reading from {DB_FILE}...")
    try:
        conn = sqlite3.connect(DB_FILE)
        query = "SELECT * FROM accomplishments"
        df = pd.read_sql_query(query, conn)
        conn.close()
    except Exception as e:
        print(f"Error reading SQLite DB: {e}")
        return

    if df.empty:
        print("No data found in SQLite database to migrate.")
        return

    print(f"Found {len(df)} records. Connecting to Google Sheets...")
    
    # Get the sheet using the existing db_manager helper
    # Note: This relies on db_manager looking at secrets.toml
    sheet = db_manager.get_gsheet_connection()
    if not sheet:
        print("Failed to connect to Google Sheet. Check secrets.toml.")
        return

    # Prepare data for sheets
    # Expected headers: ["id", "date", "category", "description", "impact_metric", "company", "title"]
    
    rows_to_add = []
    for _, row in df.iterrows():
        # Generate new UUID for the sheet
        new_id = str(uuid.uuid4())
        
        # Extract values, handling potential missing columns safely
        date = row['date'] if 'date' in df.columns else ""
        category = row['category'] if 'category' in df.columns else ""
        description = row['description'] if 'description' in df.columns else ""
        impact = row['impact_metric'] if 'impact_metric' in df.columns else ""
        company = row['company'] if 'company' in df.columns else ""
        title = row['title'] if 'title' in df.columns else ""
        
        # Append to our list
        rows_to_add.append([
            new_id,
            date,
            category,
            description,
            impact,
            company,
            title
        ])

    print(f"Writing {len(rows_to_add)} rows to Google Sheet...")
    try:
        sheet.append_rows(rows_to_add)
        print("Migration successful!")
    except Exception as e:
        print(f"Error appending rows to sheet: {e}")

if __name__ == "__main__":
    migrate_data()
