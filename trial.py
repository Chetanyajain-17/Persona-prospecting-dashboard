import os
import re
import requests
import pandas as pd
import streamlit as st


# ============================================================
# CONFIG
# ============================================================

st.set_page_config(
    page_title="IT Persona Prospecting Dashboard",
    layout="wide"
)

LUSHA_URL = "https://api.lusha.com/v3/contacts/prospecting"


# ============================================================
# PERSONA DEFINITIONS
# ============================================================

PERSONA_PATTERNS = {
    "CTO / Technology Executive": [
        r"\bcto\b",
        r"chief technology officer",
        r"chief technical officer",
        r"chief technology",
        r"chief digital officer",
        r"chief information officer",
        r"\bcio\b",
        r"chief information",
        r"chief information security officer",
        r"\bciso\b",
        r"chief security officer",
        r"chief technology &",
        r"chief technology and"
    ],

    "IT Leadership": [
        r"\bit manager\b",
        r"\bit director\b",
        r"\bit head\b",
        r"head of it",
        r"head - it",
        r"head, it",
        r"head information technology",
        r"information technology head",
        r"information technology director",
        r"information technology manager",
        r"information systems manager",
        r"information systems director",
        r"technology director",
        r"technology manager",
        r"technology head",
        r"head of technology",
        r"director of technology",
        r"manager of information technology",
        r"it operations manager",
        r"technology operations manager",
        r"it operations director",
        r"it service delivery manager",
        r"it service delivery director",
        r"it infrastructure manager",
        r"infrastructure manager",
        r"infrastructure director",
        r"it lead",
        r"technology lead",
        r"information technology lead"
    ],

    "Infrastructure / Network": [
        r"infrastructure manager",
        r"infrastructure director",
        r"infrastructure lead",
        r"it infrastructure",
        r"network manager",
        r"network director",
        r"network lead",
        r"network architect",
        r"network administrator",
        r"network engineer",
        r"systems administrator",
        r"system administrator",
        r"systems manager",
        r"systems engineer",
        r"system engineer",
        r"server administrator",
        r"cloud infrastructure",
        r"cloud architect",
        r"cloud engineer",
        r"it infrastructure architect",
        r"infrastructure architect"
    ],

    "Cyber Security": [
        r"\bciso\b",
        r"chief information security officer",
        r"information security manager",
        r"information security director",
        r"information security lead",
        r"information security architect",
        r"cyber security manager",
        r"cybersecurity manager",
        r"cyber security director",
        r"cybersecurity director",
        r"cyber security lead",
        r"cybersecurity lead",
        r"security manager",
        r"security director",
        r"security architect",
        r"security engineer",
        r"network security",
        r"information security",
        r"cyber security",
        r"cybersecurity",
        r"security operations",
        r"soc manager",
        r"soc lead"
    ],

    "IT Operations / Support": [
        r"it operations",
        r"it support manager",
        r"it support lead",
        r"it service manager",
        r"service desk manager",
        r"help desk manager",
        r"technical support manager",
        r"technical support lead",
        r"desktop support manager",
        r"desktop support lead",
        r"it administrator",
        r"it administration",
        r"it service"
    ],

    "IT Asset / Systems Management": [
        r"it asset",
        r"information technology asset",
        r"technology asset",
        r"asset management.*it",
        r"it.*asset management",
        r"software asset management",
        r"hardware asset management",
        r"configuration manager.*it",
        r"systems management",
        r"technology management"
    ]
}


# ============================================================
# EXCLUSIONS
# ============================================================

EXCLUDED_TITLE_PATTERNS = [
    r"\baccount manager\b",
    r"\bkey account\b",
    r"\baccount executive\b",
    r"\bsales\b",
    r"\bbusiness development\b",
    r"\bbd manager\b",
    r"\bmarketing\b",
    r"\bhuman resources\b",
    r"\bhr manager\b",
    r"\brecruiter\b",
    r"\brecruitment\b",
    r"\bfinance\b",
    r"\bfinancial\b",
    r"\baccountant\b",
    r"\baccounts manager\b",
    r"\blegal\b",
    r"\bprocurement\b",
    r"\bpurchase manager\b",
    r"\boperations manager\b"
]


# ============================================================
# PERSONA MATCHING
# ============================================================

def persona_match(title):
    """
    Returns:
        (True/False, persona, reason)
    """

    if not title:
        return False, "Unknown", "No job title"

    title_clean = str(title).strip()
    title_lower = title_clean.lower()

    # --------------------------------------------------------
    # Exclude obvious non-IT functions
    # --------------------------------------------------------

    for pattern in EXCLUDED_TITLE_PATTERNS:

        # Don't blindly reject a title containing "operations".
        # We only reject the actual generic/non-IT patterns above.
        if re.search(pattern, title_lower):
            return False, "Excluded", f"Non-IT title matched: {pattern}"

    # --------------------------------------------------------
    # Look for IT persona
    # --------------------------------------------------------

    for persona, patterns in PERSONA_PATTERNS.items():

        for pattern in patterns:

            if re.search(pattern, title_lower):
                return True, persona, f"Matched: {pattern}"

    # --------------------------------------------------------
    # Additional intelligent IT detection
    # --------------------------------------------------------

    technology_words = [
        "information technology",
        "information systems",
        "it ",
        "technology",
        "infrastructure",
        "network",
        "cybersecurity",
        "cyber security",
        "information security",
        "systems administration",
        "system administration"
    ]

    management_words = [
        "manager",
        "director",
        "head",
        "lead",
        "chief",
        "vp",
        "vice president",
        "architect"
    ]

    has_technology = any(
        word in title_lower for word in technology_words
    )

    has_management = any(
        word in title_lower for word in management_words
    )

    if has_technology and has_management:

        return (
            True,
            "Technology / IT Management",
            "Technology keyword + management/senior keyword"
        )

    return False, "Not IT", "No IT persona pattern matched"


# ============================================================
# LOCATION HELPERS
# ============================================================

def build_location(country, state, city):

    location = {}

    if country.strip():
        location["country"] = country.strip()

    if state.strip():
        location["state"] = state.strip()

    if city.strip():
        location["city"] = city.strip()

    return location


# ============================================================
# LUSHA SEARCH
# ============================================================

def search_lusha(
    api_key,
    company_name,
    company_country="",
    company_state="",
    company_city="",
    employee_country="",
    employee_state="",
    employee_city="",
    page_size=50
):

    headers = {
        "api_key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    # --------------------------------------------------------
    # BROADER JOB TITLE SEARCH
    #
    # We intentionally include many variants so that
    # Lusha doesn't eliminate valid people before our
    # Python classifier gets a chance to evaluate them.
    # --------------------------------------------------------

    broad_job_titles = [
        "CTO",
        "Chief Technology Officer",
        "CIO",
        "Chief Information Officer",
        "CISO",
        "Chief Information Security Officer",
        "Chief Security Officer",

        "IT Manager",
        "IT Director",
        "IT Head",
        "Head of IT",
        "Head IT",

        "Technology Manager",
        "Technology Director",
        "Technology Head",
        "Head of Technology",
        "Director of Technology",

        "Information Technology Manager",
        "Information Technology Director",
        "Information Technology Head",
        "Information Technology Lead",

        "Information Systems Manager",
        "Information Systems Director",
        "Information Systems Head",

        "IT Operations Manager",
        "IT Operations Director",
        "Technology Operations Manager",

        "IT Infrastructure Manager",
        "Infrastructure Manager",
        "Infrastructure Director",
        "Infrastructure Lead",

        "Network Manager",
        "Network Director",
        "Network Lead",
        "Network Architect",
        "Network Engineer",
        "Network Administrator",

        "Systems Administrator",
        "System Administrator",
        "Systems Manager",
        "Systems Engineer",

        "Security Manager",
        "Security Director",
        "Security Architect",
        "Security Engineer",

        "Information Security Manager",
        "Information Security Director",
        "Information Security Lead",

        "Cybersecurity Manager",
        "Cybersecurity Director",
        "Cybersecurity Lead",

        "IT Asset Manager",
        "IT Asset Management",
        "Information Technology Asset Management",

        "IT Service Manager",
        "IT Service Delivery Manager",
        "IT Support Manager",
        "IT Support Lead",
        "Technical Support Manager"
    ]

    contact_include = {
        "jobTitles": broad_job_titles
    }

    # --------------------------------------------------------
    # Employee location
    # --------------------------------------------------------

    employee_location = build_location(
        employee_country,
        employee_state,
        employee_city
    )

    if employee_location:
        contact_include["locations"] = [
            employee_location
        ]

    # --------------------------------------------------------
    # Company filters
    # --------------------------------------------------------

    company_include = {}

    if company_name.strip():
        company_include["names"] = [
            company_name.strip()
        ]

    company_location = build_location(
        company_country,
        company_state,
        company_city
    )

    if company_location:
        company_include["locations"] = [
            company_location
        ]

    # --------------------------------------------------------
    # Payload
    # --------------------------------------------------------

    payload = {
        "pagination": {
            "page": 0,
            "size": page_size
        },

        "filters": {
            "contacts": {
                "include": contact_include
            },

            "companies": {
                "include": company_include
            }
        }
    }

    # --------------------------------------------------------
    # API CALL
    # --------------------------------------------------------

    response = requests.post(
        LUSHA_URL,
        headers=headers,
        json=payload,
        timeout=60
    )

    return response, payload


# ============================================================
# EXTRACT CONTACTS
# ============================================================

def extract_contacts(data):

    if not isinstance(data, dict):
        return []

    # Lusha responses can expose results in different structures.
    possible_keys = [
        "contacts",
        "results",
        "data"
    ]

    for key in possible_keys:

        value = data.get(key)

        if isinstance(value, list):
            return value

        if isinstance(value, dict):

            for nested_key in [
                "contacts",
                "results",
                "data"
            ]:

                nested_value = value.get(nested_key)

                if isinstance(nested_value, list):
                    return nested_value

    return []


# ============================================================
# NORMALIZE CONTACT
# ============================================================

def normalize_contact(contact):

    if not isinstance(contact, dict):
        return {}

    company = contact.get("company")

    if not isinstance(company, dict):
        company = {}

    location = contact.get("location")

    if not isinstance(location, dict):
        location = {}

    first_name = (
        contact.get("firstName")
        or contact.get("first_name")
        or ""
    )

    last_name = (
        contact.get("lastName")
        or contact.get("last_name")
        or ""
    )

    name = (
        contact.get("name")
        or f"{first_name} {last_name}".strip()
    )

    title = (
        contact.get("jobTitle")
        or contact.get("job_title")
        or contact.get("title")
        or ""
    )

    linkedin = (
        contact.get("linkedin")
        or contact.get("linkedinUrl")
        or contact.get("linkedin_url")
        or ""
    )

    company_name = (
        company.get("name")
        or contact.get("companyName")
        or ""
    )

    company_domain = (
        company.get("domain")
        or contact.get("companyDomain")
        or ""
    )

    city = (
        location.get("city")
        or contact.get("city")
        or ""
    )

    state = (
        location.get("state")
        or contact.get("state")
        or ""
    )

    country = (
        location.get("country")
        or contact.get("country")
        or ""
    )

    department = (
        contact.get("department")
        or ""
    )

    seniority = (
        contact.get("seniority")
        or ""
    )

    contact_id = (
        contact.get("id")
        or contact.get("contactId")
        or ""
    )

    qualified, persona, reason = persona_match(title)

    return {
        "Name": name,
        "Current Title": title,
        "Persona": persona,
        "Department": department,
        "Seniority": seniority,
        "Company": company_name,
        "Company Domain": company_domain,
        "Employee City": city,
        "Employee State": state,
        "Employee Country": country,
        "LinkedIn": linkedin,
        "Contact ID": contact_id,
        "Qualified": qualified,
        "Reason": reason
    }


# ============================================================
# UI
# ============================================================

st.title("🎯 IT Persona Prospecting Dashboard")

st.caption(
    "Find technology, IT, infrastructure, network and cybersecurity "
    "personas using Lusha."
)

st.warning(
    "Important: Lusha search results are not independent proof of "
    "current employment. This dashboard separates Lusha discovery "
    "from our persona qualification."
)


# ============================================================
# API KEY
# ============================================================

st.sidebar.header("Lusha")

api_key = st.sidebar.text_input(
    "Lusha API Key",
    type="password",
    value=os.getenv("LUSHA_API_KEY", "")
)

st.sidebar.markdown(
    "Your API key is used only for the API request."
)


# ============================================================
# COMPANY
# ============================================================

st.sidebar.header("Company")

company_name = st.sidebar.text_input(
    "Company Name",
    placeholder="e.g. Denave"
)

company_country = st.sidebar.text_input(
    "Company Country",
    value="India"
)

company_state = st.sidebar.text_input(
    "Company State",
    placeholder="e.g. Karnataka"
)

company_city = st.sidebar.text_input(
    "Company City",
    placeholder="e.g. Bangalore"
)


# ============================================================
# EMPLOYEE LOCATION
# ============================================================

st.sidebar.header("Employee Location")

employee_country = st.sidebar.text_input(
    "Employee Country",
    placeholder="Optional"
)

employee_state = st.sidebar.text_input(
    "Employee State",
    placeholder="Optional"
)

employee_city = st.sidebar.text_input(
    "Employee City",
    placeholder="Optional"
)


# ============================================================
# SEARCH
# ============================================================

search_button = st.sidebar.button(
    "🔎 Search Personas",
    type="primary",
    use_container_width=True
)


if search_button:

    if not api_key.strip():

        st.error("Please enter your Lusha API key.")

        st.stop()

    if not company_name.strip():

        st.error("Please enter a company name.")

        st.stop()

    with st.spinner("Searching Lusha..."):

        try:

            response, payload = search_lusha(
                api_key=api_key,
                company_name=company_name,
                company_country=company_country,
                company_state=company_state,
                company_city=company_city,
                employee_country=employee_country,
                employee_state=employee_state,
                employee_city=employee_city,
                page_size=50
            )

        except requests.RequestException as e:

            st.error(
                f"Network/API connection error: {e}"
            )

            st.stop()

    # ========================================================
    # API ERROR
    # ========================================================

    if response.status_code != 200:

        st.error(
            f"Lusha API returned HTTP {response.status_code}"
        )

        try:
            error_json = response.json()

            st.json(error_json)

        except Exception:

            st.code(response.text)

        st.subheader("Request Payload")

        st.json(payload)

        st.stop()

    # ========================================================
    # RESPONSE
    # ========================================================

    try:

        data = response.json()

    except Exception:

        st.error("Lusha returned an invalid JSON response.")

        st.code(response.text)

        st.stop()

    contacts = extract_contacts(data)

    # ========================================================
    # NORMALIZE
    # ========================================================

    normalized = []

    for contact in contacts:

        row = normalize_contact(contact)

        if row:
            normalized.append(row)

    df = pd.DataFrame(normalized)

    # ========================================================
    # METRICS
    # ========================================================

    returned_count = len(df)

    if returned_count:

        qualified_df = df[
            df["Qualified"] == True
        ].copy()

        rejected_df = df[
            df["Qualified"] == False
        ].copy()

    else:

        qualified_df = pd.DataFrame()
        rejected_df = pd.DataFrame()

    qualified_count = len(qualified_df)
    rejected_count = len(rejected_df)

    # ========================================================
    # HEADER
    # ========================================================

    st.subheader(
        f"Results for {company_name}"
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Lusha Contacts Returned",
        returned_count
    )

    col2.metric(
        "Qualified IT Personas",
        qualified_count
    )

    col3.metric(
        "Rejected",
        rejected_count
    )

    if returned_count:

        qualification_rate = (
            qualified_count / returned_count
        ) * 100

    else:

        qualification_rate = 0

    col4.metric(
        "Qualification Rate",
        f"{qualification_rate:.1f}%"
    )

    # ========================================================
    # ZERO RESULT EXPLANATION
    # ========================================================

    if returned_count == 0:

        st.error(
            "Lusha returned 0 contacts for this query."
        )

        st.info(
            "This does NOT prove that the company has no IT "
            "personas. It means Lusha returned no contacts "
            "matching the current search filters."
        )

        st.subheader("Search Used")

        st.json(payload)

    # ========================================================
    # QUALIFIED PERSONAS
    # ========================================================

    if qualified_count:

        st.subheader(
            f"✅ Qualified IT Personas ({qualified_count})"
        )

        display_columns = [
            "Name",
            "Current Title",
            "Persona",
            "Department",
            "Seniority",
            "Company",
            "Company Domain",
            "Employee City",
            "Employee State",
            "Employee Country",
            "LinkedIn",
            "Reason"
        ]

        st.dataframe(
            qualified_df[display_columns],
            use_container_width=True,
            hide_index=True
        )

        # ----------------------------------------------------
        # CSV
        # ----------------------------------------------------

        csv = qualified_df[
            display_columns
        ].to_csv(index=False).encode("utf-8")

        st.download_button(
            "⬇️ Download Qualified Personas CSV",
            data=csv,
            file_name=(
                f"{company_name}_qualified_personas.csv"
            ),
            mime="text/csv"
        )

    else:

        st.warning(
            "No returned contacts passed our IT-persona classifier."
        )

    # ========================================================
    # REJECTED
    # ========================================================

    if rejected_count:

        with st.expander(
            f"❌ Rejected Contacts ({rejected_count})"
        ):

            rejected_columns = [
                "Name",
                "Current Title",
                "Company",
                "Department",
                "Reason",
                "LinkedIn"
            ]

            st.dataframe(
                rejected_df[rejected_columns],
                use_container_width=True,
                hide_index=True
            )

    # ========================================================
    # PERSONA BREAKDOWN
    # ========================================================

    if qualified_count:

        st.subheader("Persona Breakdown")

        persona_counts = (
            qualified_df["Persona"]
            .value_counts()
            .rename_axis("Persona")
            .reset_index(name="Contacts")
        )

        st.dataframe(
            persona_counts,
            use_container_width=True,
            hide_index=True
        )

    # ========================================================
    # RAW DATA
    # ========================================================

    with st.expander("🔧 Debug / Raw Lusha Response"):

        st.subheader("Request Payload")

        st.json(payload)

        st.subheader("Raw Response")

        st.json(data)
