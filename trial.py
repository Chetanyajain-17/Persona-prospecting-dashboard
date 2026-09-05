import os
import re
import requests
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Universal IT Persona Finder",
    layout="wide"
)

LUSHA_URL = "https://api.lusha.com/v3/contacts/prospecting"


# ============================================================
# PERSONA CLASSIFIER
# ============================================================

PERSONA_RULES = {

    "CTO": [
        r"\bcto\b",
        r"chief technology officer",
        r"chief technical officer",
    ],

    "CIO": [
        r"\bcio\b",
        r"chief information officer",
    ],

    "CISO": [
        r"\bciso\b",
        r"chief information security officer",
        r"chief security officer",
    ],

    "IT Leadership": [
        r"\bit manager\b",
        r"\bit director\b",
        r"\bit head\b",
        r"head of it",
        r"head - it",
        r"head, it",
        r"head of information technology",
        r"information technology head",
        r"information technology manager",
        r"information technology director",
        r"information technology lead",
        r"manager of information technology",
        r"director of information technology",
        r"information systems manager",
        r"information systems director",
        r"information systems head",
        r"technology manager",
        r"technology director",
        r"technology head",
        r"head of technology",
        r"director of technology",
        r"technology lead",
        r"it operations manager",
        r"it operations director",
        r"technology operations manager",
        r"it service manager",
        r"it service delivery manager",
    ],

    "Infrastructure": [
        r"infrastructure manager",
        r"infrastructure director",
        r"infrastructure lead",
        r"it infrastructure manager",
        r"it infrastructure director",
        r"it infrastructure lead",
        r"infrastructure architect",
        r"cloud infrastructure",
        r"cloud architect",
        r"cloud engineer",
    ],

    "Network": [
        r"network manager",
        r"network director",
        r"network lead",
        r"network architect",
        r"network administrator",
        r"network engineer",
        r"network security",
    ],

    "Systems": [
        r"systems administrator",
        r"system administrator",
        r"systems manager",
        r"systems engineer",
        r"system engineer",
        r"systems architect",
        r"system architect",
        r"server administrator",
    ],

    "Cyber Security": [
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
        r"information security",
        r"cyber security",
        r"cybersecurity",
        r"security operations",
        r"soc manager",
        r"soc lead",
    ],

    "IT Operations": [
        r"it operations",
        r"it support manager",
        r"it support lead",
        r"it service manager",
        r"it service delivery",
        r"service desk manager",
        r"help desk manager",
        r"technical support manager",
        r"technical support lead",
        r"desktop support manager",
        r"desktop support lead",
        r"it administrator",
        r"it administration",
    ],

    "IT Asset Management": [
        r"it asset",
        r"information technology asset",
        r"technology asset",
        r"it.*asset management",
        r"asset management.*it",
        r"software asset management",
        r"hardware asset management",
    ],

    "Technology Management": [
        r"technology management",
        r"technology operations",
        r"information systems",
        r"information technology",
    ]
}


# ============================================================
# NON-IT EXCLUSIONS
# ============================================================

EXCLUDE = [
    r"\baccount manager\b",
    r"\baccount executive\b",
    r"\bkey account\b",
    r"\bsales\b",
    r"\bsales manager\b",
    r"\bbusiness development\b",
    r"\bmarketing\b",
    r"\bmarketing manager\b",
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
]


def classify_persona(title):

    if not title:
        return False, "Unknown", "No title"

    t = str(title).lower().strip()

    # --------------------------------------------------------
    # Exclude obvious false positives
    # --------------------------------------------------------

    for pattern in EXCLUDE:

        if re.search(pattern, t):

            return (
                False,
                "Excluded",
                pattern
            )

    # --------------------------------------------------------
    # Strong persona matches
    # --------------------------------------------------------

    for persona, patterns in PERSONA_RULES.items():

        for pattern in patterns:

            if re.search(pattern, t):

                return (
                    True,
                    persona,
                    f"Matched {pattern}"
                )

    # --------------------------------------------------------
    # Flexible detection
    # --------------------------------------------------------

    tech_words = [
        "information technology",
        "information systems",
        "technology",
        "infrastructure",
        "network",
        "cybersecurity",
        "cyber security",
        "information security",
        "systems",
        "it operations",
        "it services"
    ]

    senior_words = [
        "manager",
        "director",
        "head",
        "lead",
        "chief",
        "vp",
        "vice president",
        "architect",
        "administrator"
    ]

    has_tech = any(
        word in t
        for word in tech_words
    )

    has_senior = any(
        word in t
        for word in senior_words
    )

    if has_tech and has_senior:

        return (
            True,
            "Technology / IT",
            "Flexible technology match"
        )

    return (
        False,
        "Not IT",
        "No persona match"
    )


# ============================================================
# LOCATION
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
# UNIVERSAL SEARCH
# ============================================================

def search_company(
    api_key,
    company_name,
    company_country="",
    company_state="",
    company_city="",
    employee_country="",
    employee_state="",
    employee_city=""
):

    headers = {
        "api_key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    # ========================================================
    # IMPORTANT:
    #
    # ONE broad searchText instead of dozens of job titles.
    # ========================================================

    search_text = (
        "IT technology information technology "
        "information systems infrastructure network "
        "cybersecurity information security systems "
        "technology operations IT operations"
    )

    contact_include = {
        "searchText": search_text
    }

    # --------------------------------------------------------
    # Optional employee location
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
    # Company filter
    # --------------------------------------------------------

    company_include = {
        "names": [
            company_name.strip()
        ]
    }

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
    # SINGLE REQUEST
    # --------------------------------------------------------

    payload = {

        "pagination": {
            "page": 0,
            "size": 10
        },

        "filters": {

            "contacts": {
                "include": contact_include
            },

            "companies": {
                "include": company_include
            }
        },

        # Keep the number of returned contacts controlled.
        "options": {
            "maxContactsPerCompany": 10
        }
    }

    response = requests.post(
        LUSHA_URL,
        headers=headers,
        json=payload,
        timeout=60
    )

    return response, payload


# ============================================================
# CONTACT EXTRACTION
# ============================================================

def extract_contacts(data):

    if not isinstance(data, dict):
        return []

    for key in [
        "contacts",
        "results",
        "data"
    ]:

        value = data.get(key)

        if isinstance(value, list):
            return value

        if isinstance(value, dict):

            for nested in [
                "contacts",
                "results",
                "data"
            ]:

                result = value.get(nested)

                if isinstance(result, list):
                    return result

    return []


# ============================================================
# NORMALIZE
# ============================================================

def normalize(contact):

    if not isinstance(contact, dict):
        return None

    company = contact.get(
        "company",
        {}
    )

    if not isinstance(company, dict):
        company = {}

    location = contact.get(
        "location",
        {}
    )

    if not isinstance(location, dict):
        location = {}

    first = contact.get(
        "firstName",
        ""
    )

    last = contact.get(
        "lastName",
        ""
    )

    name = (
        contact.get("name")
        or f"{first} {last}".strip()
    )

    title = (
        contact.get("jobTitle")
        or contact.get("title")
        or ""
    )

    linkedin = (
        contact.get("linkedin")
        or contact.get("linkedinUrl")
        or contact.get("linkedin_url")
        or ""
    )

    qualified, persona, reason = classify_persona(
        title
    )

    return {
        "Name": name,
        "Current Title": title,
        "Persona": persona,
        "Department": contact.get(
            "department",
            ""
        ),
        "Seniority": contact.get(
            "seniority",
            ""
        ),
        "Company": (
            company.get("name")
            or contact.get("companyName")
            or ""
        ),
        "Company Domain": (
            company.get("domain")
            or contact.get("companyDomain")
            or ""
        ),
        "Employee City": (
            location.get("city")
            or ""
        ),
        "Employee State": (
            location.get("state")
            or ""
        ),
        "Employee Country": (
            location.get("country")
            or ""
        ),
        "LinkedIn": linkedin,
        "Contact ID": (
            contact.get("id")
            or contact.get("contactId")
            or ""
        ),
        "Qualified": qualified,
        "Reason": reason
    }


# ============================================================
# UI
# ============================================================

st.title(
    "🎯 Universal IT Persona Finder"
)

st.caption(
    "One broad Lusha discovery request → "
    "Python persona qualification"
)

st.warning(
    "This version intentionally performs ONE Lusha search "
    "per company. Do not enable multiple fallback searches."
)


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.header(
    "Lusha API"
)

api_key = st.sidebar.text_input(
    "API Key",
    value=os.getenv(
        "LUSHA_API_KEY",
        ""
    ),
    type="password"
)


st.sidebar.header(
    "Company"
)

company_name = st.sidebar.text_input(
    "Company Name",
    placeholder="Denave"
)

company_country = st.sidebar.text_input(
    "Company Country",
    value="India"
)

company_state = st.sidebar.text_input(
    "Company State",
    placeholder="Uttar Pradesh"
)

company_city = st.sidebar.text_input(
    "Company City",
    placeholder="Noida"
)


st.sidebar.header(
    "Employee Location (optional)"
)

employee_country = st.sidebar.text_input(
    "Employee Country"
)

employee_state = st.sidebar.text_input(
    "Employee State"
)

employee_city = st.sidebar.text_input(
    "Employee City"
)


search = st.sidebar.button(
    "🔎 Find IT Personas",
    type="primary",
    use_container_width=True
)


# ============================================================
# RUN
# ============================================================

if search:

    if not api_key.strip():

        st.error(
            "Enter your Lusha API key."
        )

        st.stop()

    if not company_name.strip():

        st.error(
            "Enter a company name."
        )

        st.stop()

    with st.spinner(
        "Running one Lusha discovery search..."
    ):

        try:

            response, payload = search_company(
                api_key,
                company_name,
                company_country,
                company_state,
                company_city,
                employee_country,
                employee_state,
                employee_city
            )

        except requests.RequestException as e:

            st.error(
                f"API connection error: {e}"
            )

            st.stop()

    # ========================================================
    # API ERROR
    # ========================================================

    if response.status_code != 200:

        st.error(
            f"Lusha returned HTTP "
            f"{response.status_code}"
        )

        try:
            st.json(
                response.json()
            )

        except Exception:
            st.code(
                response.text
            )

        st.subheader(
            "Request Payload"
        )

        st.json(payload)

        st.stop()

    # ========================================================
    # JSON
    # ========================================================

    data = response.json()

    contacts = extract_contacts(
        data
    )

    rows = []

    for contact in contacts:

        row = normalize(
            contact
        )

        if row:
            rows.append(row)

    df = pd.DataFrame(
        rows
    )

    # ========================================================
    # BILLING
    # ========================================================

    billing = data.get(
        "billing",
        {}
    )

    credits = billing.get(
        "creditsCharged",
        "Not reported"
    )

    # ========================================================
    # METRICS
    # ========================================================

    if len(df):

        qualified = df[
            df["Qualified"] == True
        ]

        rejected = df[
            df["Qualified"] == False
        ]

    else:

        qualified = pd.DataFrame()
        rejected = pd.DataFrame()

    # ========================================================
    # DISPLAY
    # ========================================================

    st.subheader(
        f"Results — {company_name}"
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Lusha Contacts",
        len(df)
    )

    c2.metric(
        "Qualified IT",
        len(qualified)
    )

    c3.metric(
        "Rejected",
        len(rejected)
    )

    c4.metric(
        "Credits Charged",
        credits
    )

    # ========================================================
    # ZERO RESULT
    # ========================================================

    if len(df) == 0:

        st.error(
            "Lusha returned 0 contacts for this query."
        )

        st.info(
            "This does NOT mean the company has no IT "
            "employees. It means this single Lusha "
            "discovery query returned no contacts."
        )

    # ========================================================
    # QUALIFIED
    # ========================================================

    if len(qualified):

        st.subheader(
            f"✅ IT Personas ({len(qualified)})"
        )

        columns = [
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
            qualified[columns],
            use_container_width=True,
            hide_index=True
        )

        csv = qualified[
            columns
        ].to_csv(
            index=False
        ).encode(
            "utf-8"
        )

        st.download_button(
            "⬇️ Download CSV",
            csv,
            f"{company_name}_personas.csv",
            "text/csv"
        )

    # ========================================================
    # REJECTED
    # ========================================================

    if len(rejected):

        with st.expander(
            f"Rejected ({len(rejected)})"
        ):

            st.dataframe(
                rejected[
                    [
                        "Name",
                        "Current Title",
                        "Company",
                        "Department",
                        "Reason"
                    ]
                ],
                use_container_width=True,
                hide_index=True
            )

    # ========================================================
    # RAW RESPONSE
    # ========================================================

    with st.expander(
        "🔧 Raw Lusha Response"
    ):

        st.json(
            data
        )
