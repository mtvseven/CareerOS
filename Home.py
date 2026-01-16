import streamlit as st
import pandas as pd
import datetime
from utils import db_manager
import utils.llm_helper as llm_helper

# Verify the function exists (Streamlit hot-reload debug)
if not hasattr(llm_helper, 'process_audio_to_form'):
    st.error("llm_helper missing 'process_audio_to_form'. Attempting to force reload.")
    import importlib
    importlib.reload(llm_helper)

# Constants
DEFAULT_TARGET_AUDIENCE = "Recruiters"
JOB_DESC_FILE_TYPES = ["txt"]

# Page Configuration
st.set_page_config(
    page_title="CareerOS - Managed",
    page_icon="📄",
    layout="wide"
)

# Initialize DB
db_manager.init_db()

# --- Authentication Logic ---
def check_password():
    """Returns `True` if the user had a correct password."""
    def login_form():
        """Form with widgets to collect user information"""
        with st.form("Credentials"):
            st.markdown("### 🔐 Login Required")
            # Changed key to avoid collision with session_state["username"]
            input_username = st.text_input("Username", key="login_username")
            input_password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Log In", type="primary")
            
            if submitted:
                # Check against secrets
                if "credentials" in st.secrets:
                    known_users = st.secrets["credentials"]
                    if input_username in known_users and known_users[input_username] == input_password:
                        st.session_state["authentication_status"] = True
                        st.session_state["username"] = input_username # Store username
                        st.rerun()
                    else:
                        st.error("😕 User not known or password incorrect")
                else:
                    st.error("No credentials configuration found in secrets.toml")

    if "authentication_status" not in st.session_state:
        st.session_state["authentication_status"] = False

    if not st.session_state["authentication_status"]:
        login_form()
        return False
    else:
        # Logout button in sidebar
        with st.sidebar:
            st.write(f"Logged in as: **{st.session_state.get('username', 'User')}**")
            if st.button("Log Out"):
                st.session_state["authentication_status"] = False
                st.session_state["username"] = None
                st.rerun()
        return True

# Check authentication before showing the app
if not check_password():
    st.stop()  # Stop execution if not logged in

st.title("CareerOS")

# Create Tabs
tab1, tab2, tab3 = st.tabs(["📂 Log Accomplishment", "📜 Achievement History", "🎯 Tailored Resume Generator"])

# --- Tab 1: Log Accomplishment ---
with tab1:
    st.header("Log New Accomplishment")
    
    # Initialize session state for fields if not present
    if 'acc_date' not in st.session_state:
        st.session_state['acc_date'] = datetime.date.today()
    if 'acc_category' not in st.session_state:
        st.session_state['acc_category'] = ""
    if 'acc_company' not in st.session_state:
        st.session_state['acc_company'] = ""
    if 'acc_title' not in st.session_state:
        st.session_state['acc_title'] = ""
    if 'acc_description' not in st.session_state:
        st.session_state['acc_description'] = ""
    if 'acc_impact' not in st.session_state:
        st.session_state['acc_impact'] = ""
    
    # Voice Input Section (Must be outside form to trigger reruns)
    audio_file = st.audio_input("Voice Input Option", width="stretch")

    if audio_file:
        with st.spinner("Gemini is analyzing your recording..."):
            audio_bytes = audio_file.read()
            # Process audio to JSON
            parsed_data = llm_helper.process_audio_to_form(audio_bytes, audio_file.type)
            
            if parsed_data:
                # Update session state with parsed values
                try:
                    st.session_state['acc_date'] = datetime.datetime.strptime(parsed_data.get('date', ''), '%Y-%m-%d').date()
                except:
                    st.session_state['acc_date'] = datetime.date.today()
        
                st.session_state['acc_category'] = parsed_data.get('category', '')
                st.session_state['acc_company'] = parsed_data.get('company', '')
                st.session_state['acc_title'] = parsed_data.get('title', '')
                st.session_state['acc_description'] = parsed_data.get('description', '')
                st.session_state['acc_impact'] = parsed_data.get('impact_metric', '')
                st.toast("Transcribed and parsed! Review the form below.")
            else:
                st.warning("Could not parse audio. Please try again or type manually.")

    # Manual Entry Form
    with st.form("accomplishment_form", clear_on_submit=False):
        
        date = st.date_input("Date", value=st.session_state['acc_date'])
        category = st.text_input("Category (e.g., Leadership, Tech, Sales)", value=st.session_state['acc_category'], placeholder="Comma separated tags...")
        company = st.text_input("Company", value=st.session_state['acc_company'], placeholder="Where did this happen?")
        title = st.text_input("Title", value=st.session_state['acc_title'], placeholder="Your role at the time...")
        description = st.text_area("Description", value=st.session_state['acc_description'], placeholder="Describe what you did and how it helped...")
        impact_metric = st.text_input("Impact Metric", value=st.session_state['acc_impact'], placeholder="e.g., Increased revenue by 20%")
        
        submit_button = st.form_submit_button("Save Accomplishment")

        if submit_button:
            if not description:
                st.error("Please provide a description.")
            else:
                try:
                    db_manager.add_accomplishment(
                        date=date.strftime("%Y-%m-%d"),
                        category=category,
                        description=description,
                        impact_metric=impact_metric,
                        company=company,
                        title=title,
                        user=st.session_state.get("username", "default")
                    )
                    st.success("Accomplishment saved successfully!")
                    # Clear session state after successful save
                    st.session_state['acc_category'] = ""
                    st.session_state['acc_company'] = ""
                    st.session_state['acc_title'] = ""
                    st.session_state['acc_description'] = ""
                    st.session_state['acc_impact'] = ""
                    st.rerun()
                except Exception as e:
                    st.error(f"Error saving accomplishment: {e}")        

# --- Tab 2: Achievement History ---
with tab2:
    st.header("Your Achievement History")
    
    # Session state for delete selection
    if "delete_selected" not in st.session_state:
        st.session_state["delete_selected"] = []

    try:
        current_user = st.session_state.get("username", "default")
        df_acc = db_manager.get_accomplishments(user=current_user)
        if not df_acc.empty:
            
            # --- Editing Interface ---
            st.caption("Double-click any cell to edit. Changes are saved when you click the button below.")
            
            # Use data_editor to allow inline editing
            edited_df = st.data_editor(
                df_acc, 
                use_container_width=True, 
                hide_index=True,
                disabled=["id"],  # Prevent editing IDs
                key="history_editor",
                num_rows="dynamic" # Allow adding/deleting rows (Deletion handles strictly via UI is complex with GSheets, sticking to explicit delete for now)
            )
            
            # Compare original vs edited to detect changes
            # We use a simple button to commit changes to avoid "save on every keystroke" API churn
            if st.button("💾 Save Changes"):
                with st.spinner("Syncing changes to Google Sheets..."):
                    # Detect differences
                    # Iterate through rows and check for changes
                    # (Simple approach: Updates each row that differs. 
                    # For optimization, we could filter, but for <100 rows, iteration is fast enough logic-wise)
                    
                    changes_count = 0
                    for index, row in edited_df.iterrows():
                        original_row = df_acc.iloc[index]
                        
                        # Check if ANY field changed
                        has_changes = False
                        for col in df_acc.columns:
                            if str(row[col]) != str(original_row[col]):
                                has_changes = True
                                break
                        
                        if has_changes:
                            db_manager.update_accomplishment(
                                id_val=row['id'],
                                date=str(row['date']),
                                category=row['category'],
                                description=row['description'],
                                impact_metric=row['impact_metric'],
                                company=row['company'],
                                title=row['title']
                            )
                            changes_count += 1
                    
                    if changes_count > 0:
                        st.success(f"Successfully updated {changes_count} entries!")
                        st.rerun()
                    else:
                        st.info("No changes detected.")

            st.divider()

            # --- Deletion Interface ---
            with st.expander("🗑️ Delete Entries"):
                st.warning("Deletion is permanent.")
                id_to_delete = st.text_input("Paste ID (UUID) to delete", help="Copy the ID from the table above")
                if st.button("Permanently Delete"):
                    if id_to_delete:
                        with st.spinner("Deleting..."):
                            db_manager.delete_accomplishment(id_to_delete)
                            st.rerun()

        else:
            st.info("No accomplishments logged yet. Use the Log tab to get started!")
    except Exception as e:
        st.error(f"Error loading history: {e}")

# --- Tab 3: Tailored Resume Generator ---
with tab3:
    st.header("Generate Tailored Assets")
    st.markdown("Match your history against a specific job description.")
    
    # col1, col2 = st.columns([1, 2])

    # with col1:
    st.subheader("Details")
    
    # Job Description Input
    job_description = ""
    uploaded_file = st.file_uploader(
        "Upload Job Description (.txt)",
        type=JOB_DESC_FILE_TYPES,
        key="jd_uploader"
    )
    if uploaded_file is not None:
        try:
            job_description = uploaded_file.read().decode("utf-8")
            st.info("Job description loaded from file.")
        except Exception as e:
            st.error(f"Error reading file: {e}")
    
    # Text area for pasting or editing
    pasted_text = st.text_area(
        "Or Paste Job Description", 
        height=50, 
        placeholder="Paste the job requirements here...",
        value=job_description if job_description else "",
        key="jd_pasted"
    )
    if pasted_text:
        job_description = pasted_text
        
    target_audience = st.text_input(
        "Target Audience",
        placeholder="Recruiters, Hiring Manager...",
        value=DEFAULT_TARGET_AUDIENCE,
        key="target_aud"
    )
    
    st.markdown("---")
    available_models = llm_helper.get_available_models()
    default_index = 0
    if available_models:
        try:
            default_index = available_models.index("gemini-flash-latest")
        except ValueError:
            default_index = 0
    model_name = st.selectbox("Select Model:", available_models, index=default_index if available_models else None, key="model_sel")
    
    if st.button("Generate Assets", type="primary", key="gen_assets"):
        if not job_description:
            st.warning("Please provide a Job Description to tailor your resume and cover letter.")
        else:
            with st.spinner("Analyzing your career history and tailoring resume and cover letter..."):
                try:
                    # Get all accomplishments
                    current_user = st.session_state.get("username", "default")
                    df = db_manager.get_accomplishments(user=current_user)
                    if df.empty:
                        st.error("No accomplishments found in database! Please log some achievements first.")
                    else:
                        # Filter relevant columns for context
                        context_cols = ['date', 'category', 'description', 'impact_metric', 'company', 'title']
                        subset_df = df[[c for c in context_cols if c in df.columns]]
                        context_data = subset_df.to_string(index=False)
                        
                        prompt = f"""You are an expert Career Coach and Professional Resume Writer.

TASK: Create both a tailored resume and a tailored cover letter that align the provided career accomplishments with the requirements and responsibilities found in the Job Description below.

JOB DESCRIPTION:
{job_description}

TARGET AUDIENCE: {target_audience}

INSTRUCTIONS FOR RESUME:
1. Select and emphasize the most relevant accomplishments from the context.
2. Use industry keywords from the job description.
3. Focus on quantifiable impact metrics where available.
4. Maintain a professional, high-impact tone.
5. Structure the resume clearly with headers (e.g., Professional Summary, Experience, Skills).

INSTRUCTIONS FOR COVER LETTER:
1. Write a compelling cover letter that demonstrates how your experience matches the job requirements.
2. Reference specific accomplishments from your career history that align with the job description.
3. Show enthusiasm for the role and company.
4. Keep it concise (3-4 paragraphs) and professional.
5. Include a clear call to action.

OUTPUT FORMAT:
Please structure your response with two clear sections:
1. "## Tailored Resume" - followed by the resume content
2. "## Tailored Cover Letter" - followed by the cover letter content"""
                        
                        response = llm_helper.generate_content(prompt, context_data=context_data, model_name=model_name)
                        st.session_state['generated_profile'] = response
                
                except Exception as e:
                    st.error(f"Error: {e}")

    # with col2:
    st.subheader("Result")
    if 'generated_profile' in st.session_state:
        st.markdown(st.session_state['generated_profile'])
        
        st.download_button(
            label="Download as Markdown",
            data=st.session_state['generated_profile'],
            file_name="tailored_resume_and_cover_letter.md",
            mime="text/markdown"
        )
    else:
        st.info("Upload a JD and click Generate to see results.")
