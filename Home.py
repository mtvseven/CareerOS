import streamlit as st
import pandas as pd
import datetime
from utils import db_manager
import utils.llm_helper as llm_helper
import utils.pdf_utils as pdf_utils

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
            
            # Reset index to ensure compatible behavior with hide_index=True and num_rows="dynamic"
            df_acc = df_acc.reset_index(drop=True)

            # Use data_editor to allow inline editing
            edited_df = st.data_editor(
                df_acc, 
                width="stretch", # Replaced use_container_width=True
                hide_index=True,
                disabled=["id"],  # Prevent editing IDs
                key="history_editor",
                num_rows="dynamic" # Allow adding/deleting rows
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
    st.subheader("Job Details")
    


    # Personal Details
    st.markdown("### Contact Information")
    pd_col1, pd_col2 = st.columns(2)
    with pd_col1:
        user_name = st.text_input("Full Name", placeholder="Jane Doe", key="user_name_input")
        user_email = st.text_input("Email", placeholder="jane@example.com", key="user_email_input")
    with pd_col2:
        user_phone = st.text_input("Phone", placeholder="(555) 123-4567", key="user_phone_input")
        user_linkedin = st.text_input("LinkedIn URL", placeholder="linkedin.com/in/...", key="user_linkedin_input")
    
    # Company Name Input (New)
    company_name = st.text_input("Company Name (Optional)", help="If provided, this will ensure the cover letter is addressed correctly.")

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
            
    # Text Area Fallback
    if not job_description:
        job_description = st.text_area("Or paste Job Description here", height=200)

    st.markdown("---")
    available_models = llm_helper.get_available_models()
    default_index = 0
    if available_models:
        try:
            default_index = available_models.index("gemini-flash-latest")
        except ValueError:
            default_index = 0
    model_name = st.selectbox("Select Model:", available_models, index=default_index if available_models else None, key="model_sel")
    
    # ----------------------------
    # GENERATION LOGIC
    # ----------------------------
    if st.button("Generate Assets", type="primary"):
        if not job_description:
            st.warning("Please provide a Job Description.")
        else:
            with st.spinner("Analyzing profile and generating content..."):
                try:
                    current_user = st.session_state.get("username", "default")
                    df = db_manager.get_accomplishments(user=current_user)
                    if df.empty:
                        st.error("No accomplishments found in database! Please log some achievements first.")
                    else:
                        # Filter relevant columns for context
                        context_cols = ['date', 'category', 'description', 'impact_metric', 'company', 'title']
                        subset_df = df[[c for c in context_cols if c in df.columns]]
                        context_data = subset_df.to_string(index=False)
                        
                        # Append Contact Info
                        contact_info = f"""
                        Name: {user_name}
                        Email: {user_email}
                        Phone: {user_phone}
                        LinkedIn: {user_linkedin}
                        """
                        
                        target_audience = company_name if company_name else "Hiring Manager"
                        
                        # Construct Prompt
                        # We inject company name explicitly if provided
                        company_context = f"COMPANY NAME: {company_name}" if company_name else "COMPANY NAME: Infer from Job Description"

                        prompt = f"""You are an expert Career Coach and Professional Resume Writer.

TASK: Create a tailored resume AND cover letter that ALIGN the provided career accomplishments with the requirements and responsibilities found in the Job Description below.

{company_context}

JOB DESCRIPTION:
{job_description}

TARGET AUDIENCE: {target_audience}

APPLICANT CONTACT INFO:
{contact_info}

INSTRUCTIONS:
1. Infer the Company Name and Job Title from the Job Description.
2. Estimate a "Fit Score" (Low/Medium/High) based on how well the experience aligns with the job.
3. Write a concise cover letter (3-4 paragraphs, max 300 words) referencing specific accomplishments.
4. Select and emphasize relevant accomplishments for the resume.
5. Quantify impact metrics where available.
6. Enforce character limits: Professional Summary (~500 chars), Job Summaries (~150 chars), Accomplishments (~150 chars).
7. Return the result strictly as a JSON object with the specified structure.
8. If Education is mentioned in accomplishments or context, populate the Education section; otherwise, leave it empty.

OUTPUT FORMAT (JSON):
{{
    "Fit Score": "Low/Medium/High",
    "Company": "Name of the company inferred from the job description",
    "Job Title": "Name of the job title inferred from the job description",
    "Cover Letter": "The main body of the generated cover letter...",
    "Resume": {{
        "Professional Summary": "A strong, tailored summary (Max 500 characters)...",
        "Experience": {{
             "Job Title, Company": {{
                   "Start Date": "YYYY-MM-DD",
                   "End Date": "YYYY-MM-DD or Present",
                   "Summary": "One sentence summary (Max 150 characters)...",
                   "Accomplishments": [
                        "Accomplishment 1 (Max 150 characters)...",
                        "Accomplishment 2 (Max 150 characters)...",
                        "Accomplishment 3 (Max 150 characters)..."
                   ]
             }}
             // Add more positions as relevant, in Reverse Chronological Order
        }},
        "Education": {{
             "Degree Name": {{
                 "Type of Degree": "BSc/MSc/PhD etc.",
                 "Major": "Major field of study",
                 "School": "University/School Name",
                 "Graduation Date": "YYYY-MM-DD or Year",
                 "Information of Note": "Honors, Thesis, etc."
             }}
             // Add more degrees if relevant
        }}
    }}
}}
"""
                        
                        # Call new structured generation function
                        response_dict = llm_helper.generate_structured_content(prompt, context_data=context_data, model_name=model_name)
                        
                        if response_dict:
                            st.session_state['generated_profile'] = response_dict
                            # Initialize edits state for this new profile
                            # We'll use a specific key structure in session_state, but we can also store a clean 'edit_model'
                            # For simplicity, we'll let the widgets initialize their own state based on the dict, 
                            # but we need to reset the PDF generation state.
                            st.session_state['generated_pdf_cl'] = None
                            st.session_state['generated_pdf_resume'] = None
                            st.session_state['profile_version'] = st.session_state.get('profile_version', 0) + 1
                            
                            st.success("Draft generated! Please review and edit below.")
                        else:
                            st.error("Failed to generate structured resume. Please try again.")

                except Exception as e:
                    st.error(f"Error: {e}")

    # with col2:
    st.subheader("Review & Finalize")
    
    if 'generated_profile' in st.session_state:
        content = st.session_state['generated_profile']
        version = st.session_state.get('profile_version', 0)
        
        if isinstance(content, dict):
            
            # --- Fit Score Display ---
            fit_score = content.get("Fit Score", "N/A")
            score_color = "green" if fit_score == "High" else "orange" if fit_score == "Medium" else "red"
            st.markdown(f"""
            <div style="padding: 10px; border-radius: 5px; background-color: #f0f2f6; margin-bottom: 20px; text-align: center;">
                <h3 style="margin: 0; color: {score_color};">Fit Score: {fit_score}</h3>
            </div>
            """, unsafe_allow_html=True)
            
            review_tab, finalize_tab = st.tabs(["✏️ Review & Edit", "💾 Generate & Download"])
            
            # --- Tab 1: Review & Edit ---
            with review_tab:
                st.markdown("### Cover Letter")
                # Editable Cover Letter
                cl_key = f"cl_edit_{version}"
                new_cl_text = st.text_area(
                    "Edit Cover Letter Content", 
                    value=content.get('Cover Letter', ''),
                    height=300,
                    key=cl_key
                )

                st.divider()
                st.markdown("### Professional Summary")
                # Editable Professional Summary
                prof_sum_key = f"prof_sum_edit_{version}"
                new_prof_sum = st.text_area(
                    "Edit Professional Summary", 
                    value=content.get('Resume', {}).get('Professional Summary', ''),
                    height=150,
                    key=prof_sum_key
                )
                
                st.divider()
                st.markdown("### Experience")
                
                # We need to capture the state of inclusions. 
                # We will use a dictionary to track the 'final' state locally for the Generate button to read.
                # However, since Streamlit re-runs, we rely on session_state values for the widgets.
                
                experience = content.get('Resume', {}).get('Experience', {})
                
                # Containers for layout
                for i, (job_title_key, job_details) in enumerate(experience.items()):
                    with st.expander(f"Job: {job_title_key}", expanded=True):
                        
                        # Checkbox to include the whole job
                        job_inc_key = f"job_{i}_include_{version}"
                        include_job = st.checkbox(
                            f"Include '{job_title_key}' in Resume", 
                            value=True, 
                            key=job_inc_key
                        )
                        

                        if include_job:
                            # Edited Summary
                            sum_key = f"job_{i}_summary_{version}"
                            st.text_input(
                                "Job Summary", 
                                value=job_details.get('Summary', ''), 
                                key=sum_key
                            )
                            
                            st.caption("Select & Edit Accomplishments:")
                            acc_list = job_details.get('Accomplishments', [])
                            for j, acc in enumerate(acc_list):
                                acc_inc_key = f"job_{i}_acc_{j}_include_{version}"
                                acc_text_key = f"job_{i}_acc_{j}_text_{version}"
                                
                                ac_col1, ac_col2 = st.columns([0.05, 0.95])
                                with ac_col1:
                                    st.checkbox("", value=True, key=acc_inc_key)
                                with ac_col2:
                                    st.text_area(
                                        "Accomplishment", 
                                        value=acc, 
                                        height=68, 
                                        key=acc_text_key, 
                                        label_visibility="collapsed"
                                    )

            # --- Tab 2: Generate & Download ---
            with finalize_tab:
                st.write("Once you are happy with your edits and selections, click the button below to generate your PDFs.")
                
                if st.button("✨ Apply Changes & Generate PDFs", type="primary"):
                    with st.spinner("Generating Custom PDFs..."):
                        # Reconstruct the data dictionary based on widget states
                        final_data = content.copy()
                        
                        # Update Cover Letter
                        final_data['Cover Letter'] = st.session_state.get(cl_key, "")
                        
                        # Rebuild Experience
                        final_resume = final_data.get('Resume', {}).copy()
                        
                        # Update Professional Summary
                        final_resume['Professional Summary'] = st.session_state.get(prof_sum_key, "")

                        original_experience = final_resume.get('Experience', {})
                        new_experience = {}
                        
                        for i, (job_title_key, job_details) in enumerate(original_experience.items()):
                            # Check if job is included
                            if st.session_state.get(f"job_{i}_include_{version}", True):
                                new_job_details = job_details.copy()
                                
                                # Update Summary
                                new_job_details['Summary'] = st.session_state.get(f"job_{i}_summary_{version}", job_details.get('Summary', ''))
                                
                                # Filter Accomplishments
                                original_accs = job_details.get('Accomplishments', [])
                                new_accs = []
                                for j, acc in enumerate(original_accs):
                                    # Check inclusion
                                    if st.session_state.get(f"job_{i}_acc_{j}_include_{version}", True):
                                        # Get edited text
                                        edited_acc_text = st.session_state.get(f"job_{i}_acc_{j}_text_{version}", acc)
                                        if edited_acc_text.strip(): # Only add if not empty
                                            new_accs.append(edited_acc_text)
                                new_job_details['Accomplishments'] = new_accs
                                
                                new_experience[job_title_key] = new_job_details
                        
                        final_resume['Experience'] = new_experience
                        final_data['Resume'] = final_resume
        
                        # Prepare Contact Info
                        contact_data = {
                            'name': user_name,
                            'email': user_email,
                            'phone': user_phone,
                            'linkedin': user_linkedin
                        }

                        # Generate PDFs
                        st.session_state['generated_pdf_cl'] = pdf_utils.create_cover_letter_pdf(final_data, contact_data)
                        st.session_state['generated_pdf_resume'] = pdf_utils.create_resume_pdf(final_data, contact_data)
                        st.success("PDFs Generated!")

                        
                        # Sanitize filenames
                        import re
                        def sanitize(s):
                            if not s: return "unknown"
                            return re.sub(r'[^a-zA-Z0-9_]', '', s.replace(' ', '_').lower())

                        s_user = sanitize(user_name or "applicant")
                        s_company = sanitize(company_name or "company")
                        
                        st.session_state['base_filename'] = f"{s_user}_{s_company}"
                        
                # Download Buttons
                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    if st.session_state.get('generated_pdf_cl'):
                        base_name = st.session_state.get('base_filename', 'document')
                        st.download_button(
                            label="📥 Download Cover Letter",
                            data=st.session_state['generated_pdf_cl'],
                            file_name=f"{base_name}_cover_letter.pdf",
                            mime="application/pdf"
                        )
                    else:
                        st.info("Click 'Generate PDFs' to create the file.")
                        
                with col_d2:
                    if st.session_state.get('generated_pdf_resume'):
                        base_name = st.session_state.get('base_filename', 'document')
                        st.download_button(
                            label="📥 Download Resume",
                            data=st.session_state['generated_pdf_resume'],
                            file_name=f"{base_name}_resume.pdf",
                            mime="application/pdf"
                        )
                    else:
                        st.info("Click 'Generate PDFs' to create the file.")
                
                st.divider()
                with st.expander("Debugger - View Structured Data"):
                     st.json(content)

        else:
            # Fallback for legacy state
            st.warning("Content format not recognized. Please regenerate.")
            st.write(content)
    else:
        st.info("Upload a JD and click Generate to see results.")
