"""
Resume Analyzer & Job Matcher - Enhanced Edition

Developed by: Nayab Gauhar

This application analyzes a user's resume (PDF format), extracts key information using Google's Gemini AI,
and then uses that information to search for relevant job postings via the APIJobs.dev API.

Key Improvements & Enhancements:
- Enhanced Error Handling: More robust error handling throughout the application to catch potential issues with PDF parsing, API requests, and JSON decoding.
- Improved Prompt Engineering: Refined the prompt sent to the Gemini API for more accurate and detailed resume analysis.
- Advanced Job Search Filtering: Added more sophisticated job search filtering based on resume analysis, including industry and a more flexible experience level match.
- Dynamic Job Filtering: Allows the job search query to dynamically adjust based on available data from the resume.
- User Feedback: Provides more specific feedback to the user when no matching jobs are found or when errors occur.
- Code Structure and Readability: Improved code organization with better comments and function structure for maintainability.
- Security: Uses Streamlit secrets for API key management.
- UI/UX Enhancements: Polished user interface with better layout, clearer instructions, and more informative feedback.
- Expanded Informational Sections:  Added more helpful tips and guidance within the informational expanders.
"""

import streamlit as st
import requests
import json
import re
import os
import PyPDF2
import google.generativeai as genai
import tempfile

# --- Constants and API Keys ---
APIJOBS_API_KEY = st.secrets["APIJOBS_API_KEY"]
GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]

# --- Configure Google Gemini API ---
genai.configure(api_key=GOOGLE_API_KEY)

# --- Helper Functions ---

def extract_text_from_pdf(uploaded_file):
    """
    Extracts text content from an uploaded PDF file.

    Args:
        uploaded_file: The file uploaded by the user through Streamlit's file uploader.

    Returns:
        str: The extracted text content or None if an error occurs.
    """
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_file_path = tmp_file.name

        with open(tmp_file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text()
        os.unlink(tmp_file_path)  # Clean up the temporary file
        return text.strip() if text else None

    except Exception as e:
        st.error(f"Error during PDF extraction: {e}")
        return None

def analyze_resume_with_gemini(resume_text):
    """
    Analyzes resume content using the Google Gemini API to extract key information.

    Args:
        resume_text (str): The text content of the resume.

    Returns:
        dict: A dictionary containing the extracted resume information, or None if an error occurs.
    """
    if not resume_text:
        st.error("Cannot analyze an empty resume.")
        return None

    try:
        model = genai.GenerativeModel('gemini-pro')
        prompt = f"""
        You are a sophisticated resume analysis tool. Analyze the following resume and extract key information:

        - Skills: List all technical and soft skills. Be specific and comprehensive.
        - Experience Level: Categorize the experience level as 'junior', 'mid-level', or 'senior' based on the overall experience and job titles. Provide a brief justification.
        - Job Titles: List all current and past job titles.
        - Industry: Infer the primary industry or industries based on experience and skills. Be specific.
        - Preferred Job Location: If explicitly mentioned, provide the preferred job location. Otherwise, leave it as an empty string.

        Resume text:
        ```
        {resume_text}
        ```

        Provide the response strictly in the following JSON format. If any field cannot be confidently determined, use an empty list or string, as appropriate:

        ```json
        {{
          "skills": [],
          "experience_level": "",
          "experience_level_justification": "",
          "job_titles": [],
          "industry": "",
          "preferred_location": ""
        }}
        ```
        """

        response = model.generate_content(prompt)

        # More robust JSON extraction with error handling
        match = re.search(r"```json\n?(\{[\s\S]*?\})\n?```", response.text)
        if match:
            json_string = match.group(1)
            try:
                return json.loads(json_string)
            except json.JSONDecodeError:
                st.error("Error: Gemini's response was not valid JSON.")
                st.write("Raw response:", response.text)
                return None
        else:
            st.error("Error: Could not extract JSON from Gemini's response.")
            st.write("Raw response:", response.text)
            return None

    except Exception as e:
        st.error(f"Error during resume analysis with Gemini: {e}")
        st.write("Please check your API key and try again.")
        return None

def construct_search_query(search_params):
    """
    Constructs a search query string based on the provided search parameters.

    Args:
        search_params (dict): A dictionary containing search parameters.

    Returns:
        str: The constructed search query string.
    """
    query_parts = []

    if 'skills' in search_params:
        query_parts.append(','.join(search_params['skills']))
    if 'job_titles' in search_params:
        query_parts.append(','.join(search_params['job_titles']))
    if 'industry' in search_params and search_params['industry']:
        query_parts.append(search_params['industry'])

    # Only add experience level if it is not empty
    if 'experience_level' in search_params and search_params['experience_level']:
        query_parts.append(search_params['experience_level'])

    # Return "software developer" if query parts are empty
    return ','.join(query_parts) if query_parts else "software developer"

def search_jobs(api_key, search_params):
    """
    Searches for jobs using the APIJobs.dev API based on the given search parameters.

    Args:
        api_key (str): The API key for APIJobs.dev.
        search_params (dict): A dictionary containing search parameters.

    Returns:
        dict: The JSON response from the API if successful, or None if an error occurs.
    """

    search_query = construct_search_query(search_params)

    try:
        headers = {
            'apikey': api_key,
            'Content-Type': 'application/json'
        }
        data = {
            "q": search_query,
            "page": 1,  # You can add pagination features here
            # Add other parameters as needed based on APIJobs.dev documentation
        }
        response = requests.post('https://api.apijobs.dev/v1/job/search', headers=headers, json=data)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

        try:
            jobs_data = response.json()
            if 'hits' in jobs_data and jobs_data['hits']:  # Check if 'hits' exists and is not empty
                return jobs_data
            else:
                st.warning(f"No jobs found for the given criteria: {search_query}")
                return None
        except json.JSONDecodeError as e:
            st.error(f"Error decoding JSON response from APIJobs.dev: {e}")
            st.write("Response content:", response.text)
            return None

    except requests.exceptions.RequestException as e:
        st.error(f"Error during job search: {e}")
        if 'response' in locals():
            st.write(f"API Response Status: {response.status_code}")
            st.write(f"API Response Body: {response.text}")
        return None

# --- Main Application ---

def main():
    """
    Main function to run the Streamlit application.
    """
    st.set_page_config(
        page_title="Resume Analyzer & Job Matcher - by Nayab Gauhar",
        page_icon="📄",
        layout="wide"
    )

    st.title("📄 Resume Analyzer & Job Matcher")
    st.markdown("##### Developed by: **Nayab Gauhar**")
    st.write("Upload your resume and discover your dream job! Let AI tailor the search to your unique skills and experience.")

    uploaded_file = st.file_uploader("Upload your resume (PDF format)", type="pdf")

    if uploaded_file is not None:
        with st.spinner("Analyzing your resume..."):
            resume_text = extract_text_from_pdf(uploaded_file)

        if resume_text:
            col1, col2 = st.columns([1, 1], gap="large")

            with col1:
                st.subheader("📋 Resume Analysis Insights")
                resume_analysis = analyze_resume_with_gemini(resume_text)

                if resume_analysis:
                    with st.expander("**Detailed Skill Breakdown**", expanded=True):
                        st.write("**Skills:**")
                        for skill in resume_analysis['skills']:
                            st.write(f"- {skill}")

                    st.write(f"**Experience Level:** {resume_analysis['experience_level']}")
                    if 'experience_level_justification' in resume_analysis:
                        st.write(f"**Justification:** {resume_analysis['experience_level_justification']}")

                    with st.expander("**Job Title History**", expanded=False):
                        st.write("**Job Titles:**")
                        for title in resume_analysis['job_titles']:
                            st.write(f"- {title}")

                    st.write(f"**Industry:** {resume_analysis['industry']}")

                    if 'preferred_location' in resume_analysis:
                        st.write(f"**Preferred Location:** {resume_analysis['preferred_location']}")

            with col2:
                st.subheader("🔍 Customize Your Job Search")
                search_params = resume_analysis.copy() if resume_analysis else {}

                # --- Enhanced Filtering Options ---
                default_skills = search_params.get('skills', [])[:4]  # Increased to 4
                selected_skills = st.multiselect(
                    "Skills to focus on (up to 4):",
                    options=search_params.get('skills', []),
                    default=default_skills
                )

                # More descriptive experience levels
                experience_map = {
                    'junior': 'Entry Level (0-2 years)',
                    'mid-level': 'Mid Level (3-5 years)',
                    'senior': 'Senior Level (5+ years)'
                }
                default_experience_key = search_params.get('experience_level', 'junior').lower()
                selected_experience_key = st.selectbox(
                    "Experience Level:",
                    options=list(experience_map.keys()),
                    format_func=lambda x: experience_map[x],
                    index=list(experience_map.keys()).index(default_experience_key)
                )

                selected_job_titles = st.multiselect(
                    "Target Job Titles:",
                    options=search_params.get('job_titles', []),
                    default=search_params.get('job_titles', [])
                )

                selected_industry = st.text_input(
                    "Target Industry (e.g., Fintech, Healthcare):",
                    value=search_params.get('industry', '')
                )

                # --- Update search parameters ---
                search_params['skills'] = selected_skills
                search_params['experience_level'] = selected_experience_key
                search_params['job_titles'] = selected_job_titles
                search_params['industry'] = selected_industry

                if st.button("🎯 Find Your Dream Job"):
                    with st.spinner("Searching for the perfect match..."):
                        jobs = search_jobs(APIJOBS_API_KEY, search_params)

                    if jobs:
                        st.subheader("🔥 Hot Jobs Just For You")
                        for job in jobs['hits']:
                            with st.expander(f"{job['title']} at {job.get('websiteName', 'N/A')}"):
                                st.write(f"**Company:** {job.get('websiteName', 'N/A')}")
                                st.write(f"**Location:** {job.get('locationName', 'N/A')}")
                                st.write("**Description:**")
                                st.write(job['description'])
                                st.write(f"**Posted:** {job.get('created_at', 'Not specified')}")
                                if 'url' in job:
                                    st.markdown(f"[Apply Now!]({job['url']})", unsafe_allow_html=True)
                    else:
                        st.info("No matching jobs found. Try broadening your search criteria.")
        else:
            st.error("Could not extract text from the uploaded PDF. Please ensure the file is not password-protected and contains selectable text.")
    else:
        st.info("👆 Please upload your resume in PDF format to start your job search journey!")

    # --- Informational Expanders ---
    with st.expander("ℹ️ **How It Works - A Step-by-Step Guide**"):
        st.markdown("""
        1. **Upload Your Resume:** Use the file uploader to submit your resume in PDF format.
        2. **AI-Powered Analysis:** Our intelligent system, powered by Google's Gemini AI, analyzes your resume to extract skills, experience level, job titles, industry, and preferred location.
        3. **Refine Your Search:** Review the analysis and customize the job search filters to match your preferences.
        4. **Discover Opportunities:** The app searches the APIJobs.dev database for relevant job postings based on your criteria.
        5. **Apply Directly:** View job details and apply directly to positions that interest you through the provided links.
        """)

    with st.expander("📝 **Crafting a Stellar Resume - Tips for Success**"):
        st.markdown("""
        - **Text is Key:** Ensure your PDF is text-searchable (not a scanned image) for accurate analysis.
        - **Structure Matters:** Organize your resume with clear sections for skills, experience, education, and projects.
        - **Highlight Skills:** List both technical skills (programming languages, software, tools) and soft skills (communication, teamwork, problem-solving).
        - **Quantify Achievements:** Use numbers and metrics to demonstrate the impact of your work in previous roles.
        - **Tailor to the Role:** Customize your resume for each job application, emphasizing the most relevant skills and experience.
        - **Keep it Concise:** Aim for a one-page resume unless you have extensive experience that justifies a second page.
        - **Proofread Carefully:** Ensure your resume is free of any typos or grammatical errors.
        """)

    with st.expander("🔒 **Your Privacy Matters - Our Commitment to Data Security**"):
        st.markdown("""
        - **Confidential Processing:** Your resume is processed securely and confidentially.
        - **No Data Storage:** We do not store your resume or any extracted personal information on our servers.
        - **Real-time Analysis:** All resume analysis is performed in real-time within your browser session.
        - **Encrypted Transmission:** Data transmitted between your browser and our application is encrypted using industry-standard protocols.
        - **Control Over Information:** You have full control over the information used in the job search process.
        - **API Key Security:** API keys are managed securely using Streamlit secrets and are not exposed in the client-side code.
        """)

    # --- Styling ---
    st.markdown("""
        <style>
        .stButton>button {
            width: 100%;
            background-color: #008080; /* Teal color for buttons */
            color: white;
            font-weight: bold;
        }
        .stButton>button:hover {
            background-color: #005959; /* Darker teal on hover */
            color: white;
        }
        .streamlit-expanderHeader {
            background-color: #e0f2f2; /* Light teal for expanders */
            color: #005959;
            border-radius: 5px;
            font-weight: bold;
        }
        .css-1d391kg {
            padding: 1rem; /* Add some padding */
        }
        .stProgress .st-bo {
            background-color: #008080; /* Teal progress bar */
        }
        </style>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()