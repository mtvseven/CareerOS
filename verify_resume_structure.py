
import sys
import os
import toml
import unittest
from unittest.mock import MagicMock

# Add project root to path
sys.path.append(os.getcwd())

# Mock Streamlit with print side-effects
sys.modules["streamlit"] = MagicMock()
import streamlit as st
st.error = lambda x: print(f"ST_ERROR: {x}")
st.write = lambda x: print(f"ST_WRITE: {x}")
st.code = lambda x: print(f"ST_CODE: {x}")


# Load secrets manually
try:
    secrets = toml.load(".streamlit/secrets.toml")
    st.secrets = secrets
except Exception as e:
    print(f"Warning: Could not load secrets: {e}")
    st.secrets = {}

# Now import the helper
from utils import llm_helper

class TestResumeStructure(unittest.TestCase):
    def test_generate_structured_content(self):
        print("\nTesting generate_structured_content...")
        
        # skip if no api key (e.g. in CI environment, but here we expect it)
        if "GEMINI_API_KEY" not in st.secrets:
            print("Skipping test: GEMINI_API_KEY not found in secrets.")
            return

        prompt = """
        Create a dummy response for a software engineer application.
        Result must be a JSON with these keys:
        - "Fit Score": "High",
        - "Company": "TechCorp",
        - "Job Title": "Senior Dev",
        - "Cover Letter": "...",
        - "Resume": { "Professional Summary": "...", "Experience": {}, "Education": { "Degree": {"School": "Uni"} } }
        Keep it very short.
        """
        
        # Test the function
        result = llm_helper.generate_structured_content(prompt, model_name="gemini-flash-latest")
        
        # Basic validation
        self.assertIsNotNone(result, "Result should not be None")
        self.assertIsInstance(result, dict, "Result should be a dictionary")
        
        print("\nGenerated Dictionary:")
        print(result)
        
        # Check for expected keys
        expected_keys = ["Fit Score", "Company", "Job Title", "Cover Letter", "Resume"]
        for key in expected_keys:
            self.assertIn(key, result, f"Result missing expected key: {key}")
            
        # Check Resume structure
        resume = result.get("Resume", {})
        self.assertIn("Professional Summary", resume)
        self.assertIn("Experience", resume)
        self.assertIn("Education", resume)
        
        # Check Education structure (if present in dummy)
        education = resume.get("Education", {})
        if education:
             # Just check first item structure if any exist
             first_degree = list(education.values())[0]
             self.assertIn("School", first_degree)
        
if __name__ == "__main__":
    unittest.main()
