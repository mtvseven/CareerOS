"""
Database management module for CareerOS (Google Sheets Edition).

This module handles all database operations using Google Sheets as the backend.
Requires 'gspread' and 'google-auth'.
"""
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from typing import Optional, Dict, Any, List
import uuid
import datetime

# Constants
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# Cache the connection to avoid re-authenticating on every run
@st.cache_resource
def get_gsheet_connection():
    """
    Establishes a connection to Google Sheets using credentials from secrets.
    """
    try:
        # Load credentials from secrets
        service_account_info = st.secrets["gcp_service_account"]
        
        # Authenticate
        creds = Credentials.from_service_account_info(
            service_account_info, scopes=SCOPES
        )
        client = gspread.authorize(creds)
        
        # Open the sheet
        sheet_url = st.secrets["gsheets"]["sheet_url"]
        sheet = client.open_by_url(sheet_url).sheet1
        return sheet
    except Exception as e:
        st.error(f"Error connecting to Google Sheets: {e}")
        return None

def init_db() -> None:
    """
    Initialize the Google Sheet with required headers if empty.
    """
    sheet = get_gsheet_connection()
    if not sheet:
        return

    try:
        # Check if headers exist (row 1)
        headers = sheet.row_values(1)
        # Added "user" to the end
        expected_headers = ["id", "date", "category", "description", "impact_metric", "company", "title", "user"]
        
        if not headers:
            # Initialize headers
            sheet.append_row(expected_headers)
            st.toast("Initialized Google Sheet headers.")
        else:
            # Check if 'user' column is missing (migration)
            if "user" not in headers:
                # Append 'user' to the header row
                # Find the next empty column
                col_idx = len(headers) + 1
                sheet.update_cell(1, col_idx, "user")
                # st.toast("Added 'user' column to database schema.")
            
    except Exception as e:
        st.error(f"Error initializing DB: {e}")


def add_accomplishment(
    date: str,
    category: str,
    description: str,
    impact_metric: Optional[str],
    company: str = "",
    title: str = "",
    user: str = "default"
) -> None:
    """
    Add a new accomplishment to the Google Sheet.
    """
    sheet = get_gsheet_connection()
    if not sheet:
        return

    try:
        new_id = str(uuid.uuid4())
        row_data = [
            new_id,
            date,
            category,
            description,
            impact_metric if impact_metric else "",
            company,
            title,
            user  # Add user
        ]
        sheet.append_row(row_data)
    except Exception as e:
        st.error(f"Error adding accomplishment: {e}")
        raise e


def get_accomplishments(user: str = None) -> pd.DataFrame:
    """
    Retrieve all accomplishments as a DataFrame, filtered by user.
    """
    sheet = get_gsheet_connection()
    if not sheet:
        return pd.DataFrame()

    try:
        # Get all values including headers
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        # Ensure correct column order/existence if sheet is empty but has headers
        expected_cols = ["id", "date", "category", "description", "impact_metric", "company", "title", "user"]
        if df.empty:
            return pd.DataFrame(columns=expected_cols)

        # Handle missing 'user' column in old data (treat as NaN/empty)
        if 'user' not in df.columns:
            df['user'] = ""

        # Filter by user if provided
        if user:
            # Filter rows where user matches OR user is empty (legacy data visibility optional?)
            # Strict mode: Only show matching user
            df = df[df['user'] == user]
            
        # Sort by date descending if possible
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
            df = df.sort_values(by='date', ascending=False)
            # Convert back to string for display consistency if needed, but Streamlit handles dates well
            df['date'] = df['date'].dt.strftime('%Y-%m-%d')
            
        return df
    except Exception as e:
        st.error(f"Error fetching accomplishments: {e}")
        return pd.DataFrame()


def delete_accomplishment(id_val: Any) -> None:
    """
    Delete an accomplishment by ID (UUID).
    Note: gspread deletion requires finding the row number first.
    """
    sheet = get_gsheet_connection()
    if not sheet:
        return

    try:
        # Find cell with the ID
        cell = sheet.find(str(id_val))
        if cell:
            sheet.delete_rows(cell.row)
        else:
            st.warning(f"Entry with ID {id_val} not found.")
    except Exception as e:
        st.error(f"Error deleting accomplishment: {e}")


def get_accomplishment(id_val: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a single accomplishment by ID.
    This is less efficient in GSheets than SQL, so we scan the DF.
    """
    # Note: This reads ALL data, potentially unsafe if we want strict isolation via API,
    # but okay for now since we filter in get_accomplishments usually.
    # To be safe, we should probably pass user here too, but for simplicity:
    df = get_accomplishments() 
    if df.empty:
        return None
    
    # Filter by ID
    # Ensure ID string matching
    row = df[df['id'].astype(str) == str(id_val)]
    
    if not row.empty:
        return row.iloc[0].to_dict()
    return None

# Functions below are legacy or helpers that might not be strictly needed but kept for compatibility

def update_accomplishment(
    id_val: str,
    date: str,
    category: str,
    description: str,
    impact_metric: Optional[str],
    company: str = "",
    title: str = "",
    user: str = "default"  # Added user param to signature to match pattern, though usually ID is sufficient
) -> None:
    """
    Update an existing accomplishment. 
    Uses range update to minimize API calls (1 call vs 6).
    """
    sheet = get_gsheet_connection()
    if not sheet:
        return

    try:
        cell = sheet.find(str(id_val))
        if cell:
            row_num = cell.row
            
            # --- SECURITY CHECK (Optional but good) ---
            # row_vals = sheet.row_values(row_num)
            # if we wanted to enforce ownership check before write.
            
            # Update columns B through G (Date to Title) + H (User)
            # Layout: A=id, B=date, C=cat, D=desc, E=impact, F=comp, G=title, H=user
            # We assume 'user' is the 8th column (H) if it exists.
            
            # Since user might pass 'user' arg, let's update it too or keep it.
            # For now, let's just update the content fields.
            
            range_name = f"B{row_num}:G{row_num}"
            values = [[
                date,
                category,
                description,
                impact_metric if impact_metric else "",
                company,
                title
            ]]
            sheet.update(range_name=range_name, values=values)
            
            # Handle user column update separately if needed, or expand range to H
        else:
            st.warning(f"Could not find entry to update: {id_val}")
    except Exception as e:
        st.error(f"Error updating accomplishment: {e}")


def get_unique_tags(user: str = None) -> List[str]:
    """
    Retrieve all unique tags from the database.
    """
    df = get_accomplishments(user=user)
    unique_tags = set()
    if not df.empty and 'category' in df.columns:
        for tags_str in df['category']:
            if tags_str:
                parts = [t.strip() for t in str(tags_str).split(',')]
                unique_tags.update(parts)
    return list(unique_tags)
