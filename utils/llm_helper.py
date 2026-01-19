import streamlit as st
import datetime
import json
import re
from typing import List, Optional
import google.generativeai as genai

# Constants
DEFAULT_MODEL = "gemini-flash-latest"
FALLBACK_MODELS = ["gemini-1.5-flash", "gemini-flash-latest", "gemini-1.5-pro"]
_API_INITIALIZED = False


def init_gemini() -> bool:
    """
    Initialize the Gemini client with the API key from secrets.
    """
    global _API_INITIALIZED
    
    if _API_INITIALIZED:
        return True
    
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=api_key)
        _API_INITIALIZED = True
        return True
    except KeyError:
        st.error("GEMINI_API_KEY not found in secrets. Please configure it in your Streamlit secrets.")
        return False
    except Exception as e:
        st.error(f"Error configuring Gemini API: {e}")
        return False


def get_available_models() -> List[str]:
    """
    Fetch a list of available models that support generateContent.
    """
    if not init_gemini():
        return FALLBACK_MODELS
    
    try:
        models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                models.append(m.name.replace('models/', ''))
        return sorted(models) if models else FALLBACK_MODELS
    except Exception as e:
        st.error(f"Error fetching models: {e}")
        return FALLBACK_MODELS


def generate_content(
    prompt: str,
    context_data: Optional[str] = None,
    model_name: str = DEFAULT_MODEL,
    attachments: Optional[List[dict]] = None
) -> str:
    """
    Generate content using Gemini.
    """
    if not init_gemini():
        return "Error: Gemini API not configured. Please check your API key."
    
    try:
        model = genai.GenerativeModel(model_name)
        
        if context_data:
            full_prompt = f"Context Data:\n{context_data}\n\nTask:\n{prompt}"
        else:
            full_prompt = prompt
            
        content = [full_prompt]
        if attachments:
            content.extend(attachments)
            
        response = model.generate_content(content)
        
        # Robust error handling
        if not response.candidates:
            return "Error: No candidates returned from Gemini."
            
        candidate = response.candidates[0]
        if candidate.finish_reason != 1: # 1 = STOP
            return f"Error: Model stopped unexpectedly. Reason: {candidate.finish_reason}. Safety Ratings: {candidate.safety_ratings}"
            
        if not candidate.content.parts:
            return "Error: Model returned no content parts. The input might have been blocked or interpreted as empty."
            
        return response.text
    except Exception as e:
        return f"Error generating content: {e}"


def process_audio_to_form(
    audio_bytes: bytes,
    mime_type: str,
    model_name: str = DEFAULT_MODEL
) -> Optional[dict]:
    """
    Process audio recording and extract structured completion data.
    """
    if not init_gemini():
        return None
    
    try:
        model = genai.GenerativeModel(model_name)
        
        prompt = f"""
        Analyze this audio recording of someone describing a professional accomplishment.
        Extract the following information and return it ONLY as a valid JSON object:
        {{
            "date": "YYYY-MM-DD (use today's date if not specified)",
            "category": "Comma-separated tags/categories",
            "description": "Standardized, professional description of what was done",
            "impact_metric": "Specific quantifiable impact mentioned",
            "company": "Company name if mentioned",
            "title": "Job title if mentioned"
        }}
        
        Today's date is: {datetime.date.today()}
        
        If a field is not mentioned, provide an empty string or logical default.
        Result must be ONLY the JSON block.
        """
        
        # Audio input for Gemini
        audio_part = {
            "mime_type": mime_type,
            "data": audio_bytes
        }
        
        response = model.generate_content([prompt, audio_part])
        
        # Extract JSON from response
        text = response.text
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return None
        
    except Exception as e:
        st.error(f"Error processing audio: {e}")
        return None


def generate_structured_content(
    prompt: str,
    context_data: Optional[str] = None,
    model_name: str = DEFAULT_MODEL
) -> Optional[dict]:
    """
    Generate structured JSON content using Gemini.
    """
    if not init_gemini():
        return None
    
    try:
        model = genai.GenerativeModel(model_name)
        
        # Enforce JSON instruction
        structure_instruction = "\n\nCRITICAL: Return your response ONLY as valid JSON. Do not include markdown formatting like ```json ... ```. Just the raw JSON string."
        
        if context_data:
            full_prompt = f"Context Data:\n{context_data}\n\nTask:\n{prompt}{structure_instruction}"
        else:
            full_prompt = f"{prompt}{structure_instruction}"
            
        response = model.generate_content(full_prompt)
        
        # Robust error handling
        if not response.candidates:
            st.error("Error: No candidates returned from Gemini.")
            return None
            
        candidate = response.candidates[0]
        if candidate.finish_reason != 1: # 1 = STOP
            st.error(f"Error: Model stopped unexpectedly. Reason: {candidate.finish_reason}.")
            return None
            
        text_content = response.text
        
        # Clean up potential markdown code blocks if the model ignores the "raw JSON" instruction
        text_content = re.sub(r'^```json\s*', '', text_content)
        text_content = re.sub(r'^```\s*', '', text_content)
        text_content = re.sub(r'\s*```$', '', text_content)
        
        try:
            return json.loads(text_content)
        except json.JSONDecodeError as e:
            st.error(f"Error decoding JSON from model output: {e}")
            st.text("Raw output:")
            st.code(text_content)
            return None
            
    except Exception as e:
        st.error(f"Error generating structured content: {e}")
        return None


def check_api_status() -> dict:
    """
    Check Gemini API status and usage limits.
    """
    if not init_gemini():
        return {
            'status': 'not_configured',
            'message': 'API not configured',
            'quota_info': {}
        }
    
    try:
        # Make a minimal test call to check API status
        model = genai.GenerativeModel(DEFAULT_MODEL)
        response = model.generate_content("test", generation_config={"max_output_tokens": 1})
        
        return {
            'status': 'ok',
            'message': 'API is operational',
            'quota_info': {
                'note': 'Quota limits vary by tier. Check Google AI Studio for your specific limits.',
                'common_limits': {
                    'free_tier': '15 requests per minute (RPM)',
                    'paid_tier': 'Higher limits based on your plan'
                }
            }
        }
    except Exception as e:
        error_str = str(e).lower()
        if 'quota' in error_str or 'rate limit' in error_str or '429' in error_str:
            return {
                'status': 'rate_limited',
                'message': 'Rate limit or quota exceeded',
                'quota_info': {
                    'error': str(e),
                    'suggestion': 'Wait a moment and try again, or check your quota limits in Google AI Studio'
                }
            }
        else:
            return {
                'status': 'error',
                'message': f'API error: {str(e)[:100]}',
                'quota_info': {}
            }
