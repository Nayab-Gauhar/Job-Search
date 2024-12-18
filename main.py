import streamlit as st
import requests
import json
import re
import os
import PyPDF2
import google.generativeai as genai
import tempfile

# Access API keys from Streamlit secrets
APIJOBS_API_KEY = st.secrets["APIJOBS_API_KEY"]
GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]

# Configure Google Gemini API
genai.configure(api_key=GOOGLE_API_KEY)

def extract_text_from_pdf(uploaded_file):
    """Extract text content from uploaded PDF resume"""
    text = ""
    try:
        # Create a temporary file to store the uploaded PDF
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_file_path = tmp_file.name

        # Read the PDF from the temporary file
        with open(tmp_file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text()

        # Clean up the temporary file
        os.unlink(tmp_file_path)
        return text
    except Exception as e:
        st.error(f"Error extracting text from PDF: {e}")
        return None

def analyze_resume_with_gemini(resume_text):
    """Analyze resume content using Google Gemini API"""
    try:
        model = genai.GenerativeModel('gemini-pro')
        prompt = f"""
        Analyze the following resume and extract key information:
        - Skills (technical and soft skills)
        - Experience level (junior, mid-level, senior)
        - Job titles (current and past positions)
        - Industry
        - Preferred job location (if mentioned, otherwise leave blank)

        Resume text:
        {resume_text}

        Provide the response in JSON format with these fields. If any field is not found in the resume, leave it as an empty list or string as appropriate.
        {{
          "skills": [],
          "experience_level": "",
          "job_titles": [],
          "industry": "",
          "preferred_location": ""
        }}
        """

        response = model.generate_content(prompt)

        # Use regex to find content within curly braces, handling variations
        match = re.search(r"\{.*\}", response.text, re.DOTALL)
        if match:
            extracted_json_string = match.group(0)
            try:
                return json.loads(extracted_json_string)
            except json.JSONDecodeError:
                st.error("Error parsing Gemini response. The response might not be in valid JSON format.")
                st.write("Raw response:", response.text)
                return None
        else:
            st.error("Could not extract JSON-like structure from Gemini response.")
            st.write("Raw response:", response.text)
            return None

    except Exception as e:
        st.error(f"Error analyzing resume with Gemini: {e}")
        return None
        
def search_jobs(api_key, search_params):
    """Search jobs using the APIJobs.dev API."""
    try:
        headers = {
            'apikey': api_key,
            'Content-Type': 'application/json'
        }

        # Construct the data payload for the POST request
        search_query = ','.join(search_params.get('skills', []))
        if 'job_titles' in search_params and search_params['job_titles']:
            search_query += ',' + ','.join(search_params['job_titles'])

        data = {
            "q": search_query
            # Add other parameters here based on API documentation
        }

        response = requests.post('https://api.apijobs.dev/v1/job/search', headers=headers, json=data)

        # Check for HTTP errors
        response.raise_for_status()

        # Parse the JSON response
        try:
            jobs_data = response.json()
        except json.JSONDecodeError as e:
            st.error(f"JSON decoding error: {e}")
            st.write("Response content:", response.text)
            return None

        # Check if the expected data is in the response
        if 'hits' in jobs_data:
            return jobs_data
        else:
            st.error("Unexpected response format from APIJobs.dev.")
            st.write("Response content:", response.text)
            return None

    except requests.exceptions.RequestException as e:
        st.error(f"Error searching jobs: {e}")
        if 'response' in locals():
            st.write(f"API Response Status: {response.status_code}")
            st.write(f"API Response Body: {response.text}")
        return None

    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
        return None

def main():
    st.set_page_config(
        page_title="Resume Analyzer & Job Matcher",
        page_icon="📄",
        layout="wide"
    )

    st.title("📄 Resume Analyzer & Job Matcher")
    st.write("Upload your resume and let AI find the best matching jobs for you!")

    # File uploader for resume
    uploaded_file = st.file_uploader("Upload your resume (PDF format)", type="pdf")

    if uploaded_file:
        with st.spinner("Processing your resume..."):
            resume_text = extract_text_from_pdf(uploaded_file)

            if resume_text:
                col1, col2 = st.columns([1, 1], gap="large")  # Add gap="large" for more spacing

                with col1:
                    st.subheader("📋 Resume Analysis")
                    resume_analysis = analyze_resume_with_gemini(resume_text)

                    if resume_analysis:
                        st.write("**Skills:**")
                        for skill in resume_analysis['skills']:
                            st.write(f"- {skill}")

                        st.write(f"**Experience Level:** {resume_analysis['experience_level']}")

                        st.write("**Job Titles:**")
                        for title in resume_analysis['job_titles']:
                            st.write(f"- {title}")

                        st.write(f"**Industry:** {resume_analysis['industry']}")

                        if 'preferred_location' in resume_analysis:
                            st.write(f"**Preferred Location:** {resume_analysis['preferred_location']}")

                with col2:
                    st.subheader("🔍 Job Search Filters")

                    search_params = resume_analysis.copy() if resume_analysis else {}

                    # Use resume analysis (if available) to set default search filters
                    default_skills = search_params.get('skills', [])[:3] if 'skills' in search_params else []
                    default_experience = search_params.get('experience_level', '').lower() if 'experience_level' in search_params else 'junior'
                    default_job_titles = search_params.get('job_titles', []) if 'job_titles' in search_params else []

                    # Allow users to modify search parameters
                    selected_skills = st.multiselect(
                        "Skills to focus on:",
                        options=search_params.get('skills', []),
                        default=default_skills
                    )

                    experience_level = st.selectbox(
                        "Experience Level:",
                        options=['junior', 'mid-level', 'senior'],
                        index=['junior', 'mid-level', 'senior'].index(default_experience)
                    )

                    selected_job_titles = st.multiselect(
                        "Job Titles to search for:",
                        options=search_params.get('job_titles', []),
                        default=default_job_titles
                    )

                    # Update search parameters based on user selections
                    search_params['skills'] = selected_skills
                    search_params['experience_level'] = experience_level
                    search_params['job_titles'] = selected_job_titles

                    # Search button
                    if st.button("🔎 Search Matching Jobs"):
                        with st.spinner("Searching for matching jobs..."):
                            jobs = search_jobs(APIJOBS_API_KEY, search_params)

                            if jobs and 'hits' in jobs:
                                st.subheader("🎯 Matching Jobs")
                                for job in jobs['hits']:
                                    with st.expander(f"{job['title']} at {job.get('websiteName', 'N/A')}"):
                                        st.write(f"**Company:** {job.get('websiteName', 'N/A')}")
                                        st.write(f"**Location:** {job.get('locationName', 'N/A')}")
                                        st.write("**Description:**")
                                        st.write(job['description'])
                                        st.write(f"**Created at:** {job.get('created_at', 'Not specified')}")
                                        if 'url' in job:
                                            st.markdown(f"[Apply Now]({job['url']})")
                            else:
                                st.warning("No matching jobs found. Try adjusting your search filters.")

    else:
        st.info("👆 Please upload your resume in PDF format to get started!")

    # Informational expanders
    with st.expander("ℹ️ How it works"):
        st.write("""
        1. Upload your resume in PDF format.
        2. Our AI will analyze your resume to extract key information.
        3. Review the analysis and adjust search filters if needed.
        4. Get matched with relevant job opportunities.
        5. Apply directly to positions that interest you.
        """)

    with st.expander("📝 Resume Tips"):
        st.write("""
        To get the best results:
        - Ensure your PDF is text-searchable (not scanned).
        - Include clear sections for skills, experience, and education.
        - List relevant technical skills and tools.
        - Provide detailed work experience with measurable achievements.
        - Keep formatting simple and professional.
        """)

    with st.expander("🔒 Privacy Information"):
        st.write("""
        We take your privacy seriously:
        - Your resume data is processed securely.
        - We don't store your resume or personal information.
        - All analysis is done in real-time.
        - Data is encrypted during transmission.
        - You have full control over what information to include in job searches.
        """)

    # Add custom CSS to improve the UI
    st.markdown("""
        <style>
        .stButton>button {
            width: 100%;
            background-color: #ff4b4b;
            color: white;
        }
        .stButton>button:hover {
            background-color: #ff3333;
            color: white;
        }
        .streamlit-expanderHeader {
            background-color: #f0f2f6;
            border-radius: 5px;
        }
        .css-1d391kg {
            padding: 1rem;
        }
        .stProgress .st-bo {
            background-color: #ff4b4b;
        }
        </style>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()