import markdown
from xhtml2pdf import pisa
from io import BytesIO
import datetime

# Shared CSS for consistent styling
BASE_CSS = """
<style>
    @page {
        size: letter;
        margin: 2.0cm;

    }
    body {
        font-family: Helvetica, sans-serif;
        font-size: 11pt;
        line-height: 1.4;
        color: #333;
    }
    .header {
        text-align: center;
        margin-bottom: 20px;
    }
    .name {
        font-size: 24pt;
        font-weight: bold;
        color: #2c3e50;
        margin-bottom: 5px;
    }
    .contact-info {
        font-size: 10pt;
        color: #666;
    }
    h1 {
        font-size: 18pt;
        color: #2c3e50;
        border-bottom: 2px solid #2c3e50;
        padding-bottom: 5px;
        margin-top: 20px;
        margin-bottom: 15px;
    }
    h2 {
        font-size: 14pt;
        color: #2c3e50;
        margin-top: 15px;
        margin-bottom: 5px;
        font-weight: bold;
    }
    .job-meta {
        font-size: 10pt;
        color: #555;
        font-style: italic;
        margin-bottom: 5px;
    }
    ul {
        margin-top: 5px;
        padding-left: 20px;
    }
    li {
        margin-bottom: 3px;
    }
    .section-content {
        margin-bottom: 15px;
    }

</style>
"""

# Compact CSS for Cover Letter to ensure single-page fit
CL_CSS = """
<style>
    @page {
        size: letter;
        margin: 1.5cm; /* Reduced margins */

    }
    body {
        font-family: Helvetica, sans-serif;
        font-size: 10.5pt; /* Slightly smaller font */
        line-height: 1.3;  /* Tighter line height */
        color: #333;
    }
    .header {
        text-align: center;
        margin-bottom: 15px;
    }
    .name {
        font-size: 20pt;
        font-weight: bold;
        color: #2c3e50;
        margin-bottom: 5px;
    }
    .contact-info {
        font-size: 9pt;
        color: #666;
    }
    strong {
        font-weight: bold;
    }
    .section-content {
        margin-bottom: 15px;
    }

</style>
"""

def _generate_pdf_from_html(html_content, css=BASE_CSS):
    """
    Helper to convert HTML string to PDF bytes.
    """
    full_html = f"""
    <html>
    <head>
        {css}
    </head>
    <body>
        {html_content}

    </body>
    </html>
    """
    
    result_file = BytesIO()
    pisa_status = pisa.CreatePDF(
        src=full_html,
        dest=result_file
    )
    
    if pisa_status.err:
        return None
    
    return result_file.getvalue()

def _format_contact_header(contact_info):
    """
    Helper to create the standard contact header.
    """
    parts = []
    # Order: Email | Phone | LinkedIn
    if contact_info.get('email'): parts.append(contact_info['email'])
    if contact_info.get('phone'): parts.append(contact_info['phone'])
    if contact_info.get('linkedin'): parts.append(contact_info['linkedin'])
    
    contact_line = " | ".join(parts)
    
    return f"""
    <div class="header">
        <div class="name">{contact_info.get('name', '')}</div>
        <div class="contact-info">{contact_line}</div>
    </div>
    """

def create_cover_letter_pdf(data, contact_info):
    """
    Generates a Cover Letter PDF from structured data.
    """
    header = _format_contact_header(contact_info)
    
    today = datetime.date.today().strftime("%B %d, %Y")
    company = data.get('Company', 'Hiring Manager')
    
    # Simple formatting for the body: convert newlines to <br/> or paragraphs
    # Assuming text comes as a big string block from LLM
    body_text = data.get('Cover Letter', '')
    # Convert markdown bold to html bold if present
    body_html = markdown.markdown(body_text)

    content = f"""
    {header}
    <div style="margin-top: 20px; margin-bottom: 15px;">
        {today}
    </div>
    <div style="margin-bottom: 15px;">
        <strong>Hiring Team</strong><br/>
        {company}
    </div>
    
    <div class="section-content">
        {body_html}
    </div>
    
    <div style="margin-top: 30px;">
        Sincerely,<br/>
        <br/>
        {contact_info.get('name', '')}
    </div>
    """
    
    # Use CL_CSS specifically
    return _generate_pdf_from_html(content, css=CL_CSS)

def create_resume_pdf(data, contact_info):
    """
    Generates a Resume PDF from structured data.
    """
    header = _format_contact_header(contact_info)
    
    resume_data = data.get('Resume', {})
    summary = resume_data.get('Professional Summary', '')
    experience = resume_data.get('Experience', {})
    
    # Build Experience HTML
    experience_html = ""
    
    # Iterate through experience. 
    # Note: The dictionary keys are "Job Title, Company". 
    # We might want to parse that or just display it.
    # The structure implies keys are unique identifiers.
    for job_key, job_details in experience.items():
        title_company = job_key
        start = job_details.get('Start Date', '')
        end = job_details.get('End Date', '')
        job_summary = job_details.get('Summary', '')
        accomplishments = job_details.get('Accomplishments', [])
        
        acc_bullets = ""
        for acc in accomplishments:
            acc_bullets += f"<li>{acc}</li>"
            
        experience_html += f"""
        <div class="job-entry">
            <h2>{title_company}</h2>
            <div class="job-meta">
                {start} - {end}
            </div>
            <p>{job_summary}</p>
            <ul>
                {acc_bullets}
            </ul>
        </div>
        """
        
    content = f"""
    {header}
    
    <h1>Professional Summary</h1>
    <div class="section-content">
        {summary}
    </div>
    
    <h1>Professional Experience</h1>
    <div class="section-content">
        {experience_html}
    </div>
    """
    
    # Build Education HTML
    education = resume_data.get('Education', {})
    if education:
        education_html = ""
        for degree_key, edu_details in education.items():
            degree_type = edu_details.get('Type of Degree', '')
            major = edu_details.get('Major', '')
            school = edu_details.get('School', '')
            grad_date = edu_details.get('Graduation Date', '')
            info = edu_details.get('Information of Note', '')
            
            # Formatting line: "BSc in Computer Science" or just "Computer Science"
            degree_line = f"{degree_type} in {major}" if degree_type and major else (degree_type or major or degree_key)
            
            info_html = f"<p><em>{info}</em></p>" if info else ""
            
            education_html += f"""
            <div class="edu-entry" style="margin-bottom: 10px;">
                <div style="font-weight: bold; font-size: 12pt;">{school}</div>
                <div>{degree_line} &mdash; {grad_date}</div>
                {info_html}
            </div>
            """
            
        content += f"""
        <h1>Education</h1>
        <div class="section-content">
            {education_html}
        </div>
        """
    
    return _generate_pdf_from_html(content)
