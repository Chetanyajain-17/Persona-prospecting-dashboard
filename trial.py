import os
import requests
import pandas as pd
import streamlit as st


# =========================================================
# CONFIG
# =========================================================

st.set_page_config(
    page_title="Persona Prospecting Dashboard",
    page_icon="🎯",
    layout="wide"
)

LUSHA_URL = "https://api.lusha.com/v3/contacts/prospecting"


# =========================================================
# PERSONA DEFINITIONS
# =========================================================

PERSONA_GROUPS = {
    "Executive Technology": [
        "CTO",
        "Chief Technology Officer",
        "CIO",
        "Chief Information Officer",
        "CISO",
        "Chief Information Security Officer",
        "Chief Technology & Information Officer",
        "Chief Information & Technology Officer",
    ],

    "IT Leadership": [
        "IT Manager",
        "IT Director",
        "Director of IT",
        "Head of IT",
        "Head IT",
        "Head of Information Technology",
        "Information Technology Manager",
        "Information Technology Director",
        "Technology Director",
        "Technology Manager",
        "Head of Technology",
        "VP IT",
        "VP of IT",
        "Vice President IT",
        "Vice President of IT",
    ],

    "Infrastructure / Network": [
        "Infrastructure Manager",
        "Infrastructure Director",
        "Head of Infrastructure",
        "Network Manager",
        "Network Director",
        "Network Administrator",
        "Network Architect",
        "Network Security Architect",
        "Infrastructure Architect",
        "Systems Administrator",
        "System Administrator",
        "Systems Manager",
        "System Manager",
    ],

    "Cyber Security": [
        "Security Manager",
        "Security Director",
        "Head of Security",
        "Information Security Manager",
        "Information Security Director",
        "Head of Information Security",
        "Cyber Security Manager",
        "Cybersecurity Manager",
        "Cyber Security Director",
        "Cybersecurity Director",
        "Security Architect",
        "Cyber Security Architect",
        "Cybersecurity Architect",
    ]
}


# =========================================================
# STRICT PERSONA CHECK
# =========================================================

def normalize(text):
    return " ".join(
        str(text).lower().strip().split()
    )


def is_valid_persona(title):
    """
    Our own qualification layer.
    Lusha may return broad matches, so we do NOT
    blindly trust every result.
    """

    title_normalized = normalize(title)

    for group, titles in PERSONA_GROUPS.items():

        for allowed_title in titles:

            allowed = normalize(allowed_title)

            if title_normalized == allowed:
                return True, group

    # Additional controlled patterns
    patterns = [
        "chief technology officer",
        "chief information officer",
        "chief information security officer",
        "information technology manager",
        "information technology director",
        "head of information technology",
        "head of it",
        "director of it",
        "it manager",
        "it director",
        "head of technology",
        "technology director",
        "technology manager",
        "infrastructure manager",
        "infrastructure director",
        "network manager",
        "network architect",
        "security architect",
        "information security manager",
        "information security director",
        "cyber security manager",
        "cybersecurity manager",
    ]

    for pattern in patterns:

        if pattern in title_normalized:

            # Don't accidentally classify unrelated titles
            if "account manager" in title_normalized:
                return False, None

            if "sales" in title_normalized:
                return False, None

            return True, "Technology / IT"

    return False, None


# =========================================================
# LUSHA SEARCH
# =========================================================

def search_lusha(api_key, company_name, job_titles, page_size=50):

    headers = {
        "api_key": api_key,
        "Content-Type": "application/json"
    }

    payload = {
        "pagination": {
            "page": 0,
            "size": page_size
        },

        "filters": {

            "contacts": {
                "include": {
                    "jobTitles": job_titles
                }
            },

            "companies": {
                "include": {
                    "names": [
                        company_name
                    ]
                }
            }
        }
    }

    try:

        response = requests.post(
            LUSHA_URL,
            headers=headers,
            json=payload,
            timeout=60
        )

    except requests.exceptions.RequestException as e:

        return None, f"Connection error: {e}"

    if response.status_code != 200:

        try:
            error = response.json()

        except Exception:
            error = response.text

        return None, (
            f"Lusha API error "
            f"{response.status_code}: {error}"
        )

    try:

        return response.json(), None

    except Exception:

        return None, "Lusha returned invalid JSON."


# =========================================================
# CONVERT RESULTS
# =========================================================

def process_results(data):

    rows = []

    results = data.get("results", [])

    for person in results:

        first_name = person.get("firstName", "")
        last_name = person.get("lastName", "")

        full_name = f"{first_name} {last_name}".strip()

        job = person.get("jobTitle", {}) or {}

        title = job.get("title", "")

        departments = job.get(
            "departments",
            []
        )

        seniority = job.get(
            "seniority",
            ""
        )

        company = person.get(
            "company",
            {}
        ) or {}

        company_name = company.get(
            "name",
            ""
        )

        company_domain = company.get(
            "domain",
            ""
        )

        location = person.get(
            "location",
            {}
        ) or {}

        city = location.get(
            "city",
            ""
        )

        state = location.get(
            "state",
            ""
        )

        country = location.get(
            "country",
            ""
        )

        linkedin = (
            person.get("socialLinks", {}) or {}
        ).get(
            "linkedin",
            ""
        )

        valid_persona, persona_group = is_valid_persona(
            title
        )

        if valid_persona:

            status = "QUALIFIED"

        else:

            status = "REJECTED"

        rows.append({

            "Name": full_name,

            "Current Title": title,

            "Persona": persona_group or "",

            "Department": ", ".join(departments),

            "Seniority": seniority,

            "Company": company_name,

            "Company Domain": company_domain,

            "City": city,

            "State": state,

            "Country": country,

            "LinkedIn": linkedin,

            "Status": status,

            "Lusha ID": person.get(
                "id",
                ""
            )

        })

    return pd.DataFrame(rows)


# =========================================================
# UI
# =========================================================

st.title("🎯 Persona Prospecting Dashboard")

st.caption(
    "Find technology / IT decision-makers using Lusha Prospecting API"
)

st.divider()


# ---------------------------------------------------------
# API KEY
# ---------------------------------------------------------

with st.sidebar:

    st.header("⚙️ Configuration")

    api_key = st.text_input(
        "Lusha API Key",
        type="password",
        help="Your Lusha API key. It is used only for this session."
    )

    st.divider()

    st.subheader("Persona Groups")

    selected_groups = []

    for group in PERSONA_GROUPS:

        if st.checkbox(
            group,
            value=True
        ):

            selected_groups.append(group)


# ---------------------------------------------------------
# COMPANY INPUT
# ---------------------------------------------------------

st.subheader("Company")

company_name = st.text_input(
    "Company Name",
    value="Denave",
    placeholder="e.g. Denave"
)


# ---------------------------------------------------------
# PERSONA SELECTION
# ---------------------------------------------------------

st.subheader("Personas")

selected_titles = []

for group in selected_groups:

    selected_titles.extend(
        PERSONA_GROUPS[group]
    )

selected_titles = list(
    dict.fromkeys(selected_titles)
)

st.write(
    f"Searching for **{len(selected_titles)} persona titles**"
)


# ---------------------------------------------------------
# SEARCH
# ---------------------------------------------------------

search_button = st.button(
    "🔎 Find Current IT Employees",
    type="primary",
    use_container_width=True
)


if search_button:

    if not api_key:

        st.error(
            "Please enter your Lusha API key."
        )

        st.stop()

    if not company_name.strip():

        st.error(
            "Please enter a company name."
        )

        st.stop()

    if not selected_titles:

        st.error(
            "Select at least one persona group."
        )

        st.stop()

    with st.spinner(
        f"Searching Lusha for IT personas at {company_name}..."
    ):

        data, error = search_lusha(
            api_key=api_key,
            company_name=company_name.strip(),
            job_titles=selected_titles,
            page_size=50
        )

    if error:

        st.error(error)

        st.stop()

    # -----------------------------------------------------
    # RAW RESULT INFO
    # -----------------------------------------------------

    total = data.get(
        "pagination",
        {}
    ).get(
        "total",
        0
    )

    returned = len(
        data.get(
            "results",
            []
        )
    )

    st.success(
        f"Lusha returned {returned} records "
        f"out of {total} matching records."
    )

    # -----------------------------------------------------
    # PROCESS
    # -----------------------------------------------------

    df = process_results(data)

    if df.empty:

        st.warning(
            "No contacts were returned."
        )

        st.stop()

    # -----------------------------------------------------
    # STRICT QUALIFICATION
    # -----------------------------------------------------

    qualified_df = df[
        df["Status"] == "QUALIFIED"
    ].copy()

    rejected_df = df[
        df["Status"] == "REJECTED"
    ].copy()

    # -----------------------------------------------------
    # METRICS
    # -----------------------------------------------------

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Returned",
            len(df)
        )

    with col2:
        st.metric(
            "Qualified",
            len(qualified_df)
        )

    with col3:
        st.metric(
            "Rejected",
            len(rejected_df)
        )

    with col4:
        st.metric(
            "IT Match Rate",
            f"{(len(qualified_df) / len(df) * 100):.0f}%"
            if len(df) else "0%"
        )

    st.divider()

    # -----------------------------------------------------
    # QUALIFIED RESULTS
    # -----------------------------------------------------

    st.subheader(
        "✅ Qualified Technology / IT Employees"
    )

    if qualified_df.empty:

        st.warning(
            "No strict IT persona matched the returned contacts."
        )

    else:

        display_columns = [
            "Name",
            "Current Title",
            "Persona",
            "Department",
            "Seniority",
            "Company",
            "City",
            "State",
            "Country",
            "LinkedIn",
            "Status"
        ]

        st.dataframe(
            qualified_df[display_columns],
            use_container_width=True,
            hide_index=True,
            column_config={
                "LinkedIn": st.column_config.LinkColumn(
                    "LinkedIn",
                    display_text="Open LinkedIn"
                )
            }
        )

        csv = qualified_df.to_csv(
            index=False
        ).encode("utf-8")

        st.download_button(
            "⬇️ Download Qualified Contacts CSV",
            csv,
            file_name=f"{company_name}_IT_personas.csv",
            mime="text/csv"
        )

    # -----------------------------------------------------
    # REJECTED
    # -----------------------------------------------------

    with st.expander(
        f"Show rejected records ({len(rejected_df)})"
    ):

        if rejected_df.empty:

            st.write(
                "No rejected records."
            )

        else:

            st.dataframe(
                rejected_df[
                    [
                        "Name",
                        "Current Title",
                        "Department",
                        "Company",
                        "City",
                        "Country",
                        "LinkedIn",
                        "Status"
                    ]
                ],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "LinkedIn": st.column_config.LinkColumn(
                        "LinkedIn",
                        display_text="Open LinkedIn"
                    )
                }
            )

    # -----------------------------------------------------
    # RAW DATA
    # -----------------------------------------------------

    with st.expander(
        "Debug: Raw Lusha response"
    ):

        st.json(data)
