import streamlit as st
import requests
import json
import re
import os
import PyPDF2
import google.generativeai as genai
import tempfile

# API Keys from Streamlit Secrets
APIJOBS_API_KEY = st.secrets["APIJOBS_API_KEY"]
GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]

# Configure Google Gemini
genai.configure(api_key=GOOGLE_API_KEY)

# --- Helper Functions ---

def extract_text_from_pdf(uploaded_file):
    """Extract text from PDF."""
    text = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_file_path = tmp_file.name

        with open(tmp_file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text()

        os.unlink(tmp_file_path)
        return text
    except Exception as e:
        st.error(f"Error extracting text: {e}")
        return None

def analyze_resume_with_gemini(resume_text):
    """Analyze resume with Google Gemini."""
    try:
        model = genai.GenerativeModel('gemini-pro')
        prompt = f"""
        Analyze the resume and extract:
        - Skills (technical and soft skills)
        - Experience level (junior, mid-level, senior)
        - Job titles (current and past)
        - Industry
        - Preferred job location (if mentioned, else blank)

        Resume:
        {resume_text}

        Provide response in JSON:
        {{
          "skills": [],
          "experience_level": "",
          "job_titles": [],
          "industry": "",
          "preferred_location": ""
        }}
        """
        response = model.generate_content(prompt)

        match = re.search(r"\{.*\}", response.text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                st.error("Error parsing Gemini response. Not valid JSON.")
                return None
        else:
            st.error("Could not extract JSON from Gemini response.")
            return None
    except Exception as e:
        st.error(f"Error analyzing with Gemini: {e}")
        return None

def search_jobs(api_key, search_params):
    """Search jobs using APIJobs.dev."""
    try:
        headers = {'apikey': api_key, 'Content-Type': 'application/json'}
        search_query = ','.join(search_params.get('skills', []))
        if 'job_titles' in search_params and search_params['job_titles']:
            search_query += ',' + ','.join(search_params['job_titles'])

        data = {"q": search_query}
        response = requests.post('https://api.apijobs.dev/v1/job/search', headers=headers, json=data)
        response.raise_for_status()

        jobs_data = response.json()
        if 'hits' in jobs_data:
            return jobs_data
        else:
            st.error("Unexpected response from APIJobs.dev.")
            return None
    except requests.exceptions.RequestException as e:
        st.error(f"Error searching jobs: {e}")
        return None

# --- Main Streamlit App ---

def main():
    st.set_page_config(page_title="Resume Analyzer & Job Matcher", page_icon="📄", layout="wide")
    st.title("📄 Resume Analyzer & Job Matcher")
    st.write("Upload resume, AI finds matching jobs!")

    uploaded_file = st.file_uploader("Upload resume (PDF)", type="pdf")

    if uploaded_file:
        with st.spinner("Processing resume..."):
            resume_text = extract_text_from_pdf(uploaded_file)
            if resume_text:
                col1, col2 = st.columns([1, 1], gap="large")
                with col1:
                    st.subheader("📋 Resume Analysis")
                    resume_analysis = analyze_resume_with_gemini(resume_text)
                    if resume_analysis:
                        st.write("**Skills:**", ", ".join(resume_analysis['skills']))
                        st.write(f"**Experience:** {resume_analysis['experience_level']}")
                        st.write("**Titles:**", ", ".join(resume_analysis['job_titles']))
                        st.write(f"**Industry:** {resume_analysis['industry']}")
                        if 'preferred_location' in resume_analysis:
                            st.write(f"**Location:** {resume_analysis['preferred_location']}")

                with col2:
                    st.subheader("🔍 Job Search")
                    search_params = resume_analysis.copy() if resume_analysis else {}
                    default_skills = search_params.get('skills', [])[:3]
                    default_experience = search_params.get('experience_level', '').lower() or 'junior'
                    default_job_titles = search_params.get('job_titles', [])

                    selected_skills = st.multiselect("Skills:", options=search_params.get('skills', []), default=default_skills)
                    experience_level = st.selectbox("Experience:", options=['junior', 'mid-level', 'senior'], index=['junior', 'mid-level', 'senior'].index(default_experience))
                    selected_job_titles = st.multiselect("Job Titles:", options=search_params.get('job_titles', []), default=default_job_titles)

                    search_params['skills'] = selected_skills
                    search_params['experience_level'] = experience_level
                    search_params['job_titles'] = selected_job_titles

                    if st.button("🔎 Search Jobs"):
                        with st.spinner("Searching..."):
                            jobs = search_jobs(APIJOBS_API_KEY, search_params)
                            if jobs and 'hits' in jobs:
                                st.subheader("🎯 Matching Jobs")
                                for job in jobs['hits']:
                                    with st.expander(f"{job['title']} at {job.get('websiteName', 'N/A')}"):
                                        st.write(f"**Company:** {job.get('websiteName', 'N/A')}")
                                        st.write(f"**Location:** {job.get('locationName', 'N/A')}")
                                        st.write("**Description:**", job['description'])
                                        st.write(f"**Created:** {job.get('created_at', 'N/A')}")
                                        if 'url' in job:
                                            st.markdown(f"[Apply]({job['url']})")
                            else:
                                st.warning("No matches. Try adjusting filters.")
    else:
        st.info("👆 Upload resume to start!")

    # Info Expanders
    with st.expander("ℹ️ How it works"):
        st.write("1. Upload PDF. 2. AI analyzes. 3. Adjust filters. 4. Get job matches. 5. Apply.")
    with st.expander("📝 Resume Tips"):
        st.write("Text-searchable PDF. Clear skills, experience, education. Relevant technical skills. Detailed work experience, measurable achievements. Simple formatting.")
    with st.expander("🔒 Privacy"):
        st.write("Secure processing. No resume/personal info stored. Real-time analysis. Encrypted data. You control search info.")

    # Custom CSS
    st.markdown("""
        <style>
        .stButton>button {width: 100%; background-color: #ff4b4b; color: white;}
        .stButton>button:hover {background-color: #ff3333;}
        .streamlit-expanderHeader {background-color: #f0f2f6; border-radius: 5px;}
        .css-1d391kg {padding: 1rem;}
        .stProgress .st-bo {background-color: #ff4b4b;}
        </style>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()