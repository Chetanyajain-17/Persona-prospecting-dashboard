import requests
import pandas as pd
import streamlit as st


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="Persona Prospecting Dashboard",
    page_icon="🎯",
    layout="wide"
)

LUSHA_URL = "https://api.lusha.com/v3/contacts/prospecting"


# =========================================================
# PERSONAS
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
# HELPERS
# =========================================================

def normalize(value):
    return " ".join(
        str(value).lower().strip().split()
    )


def persona_match(title):
    """
    Our own strict persona qualification.
    This prevents broad Lusha matches such as
    Account Manager from becoming IT leads.
    """

    title = normalize(title)

    for group, titles in PERSONA_GROUPS.items():

        for allowed in titles:

            if title == normalize(allowed):
                return True, group

    # Controlled partial matches
    patterns = {
        "IT Leadership": [
            "it manager",
            "it director",
            "director of it",
            "head of it",
            "head it",
            "head of information technology",
            "information technology manager",
            "information technology director",
            "technology director",
            "technology manager",
            "head of technology",
        ],

        "Infrastructure / Network": [
            "infrastructure manager",
            "infrastructure director",
            "head of infrastructure",
            "network manager",
            "network director",
            "network architect",
            "network security architect",
            "infrastructure architect",
            "systems administrator",
            "system administrator",
        ],

        "Cyber Security": [
            "security manager",
            "security director",
            "head of security",
            "information security manager",
            "information security director",
            "head of information security",
            "cyber security manager",
            "cybersecurity manager",
            "cyber security director",
            "cybersecurity director",
            "security architect",
            "cyber security architect",
            "cybersecurity architect",
        ],

        "Executive Technology": [
            "chief technology officer",
            "chief information officer",
            "chief information security officer",
        ]
    }

    # Explicit exclusions
    if any(x in title for x in [
        "account manager",
        "sales manager",
        "business development",
        "marketing manager",
        "hr manager",
        "human resources",
        "finance manager",
    ]):
        return False, None

    for group, patterns_list in patterns.items():

        for pattern in patterns_list:

            if pattern in title:
                return True, group

    return False, None


# =========================================================
# LUSHA SEARCH
# =========================================================

def search_lusha(
    api_key,
    company_name,
    company_country,
    company_state,
    company_city,
    selected_titles,
    person_country=None,
    person_state=None,
    person_city=None,
):

    headers = {
        "api_key": api_key,
        "Content-Type": "application/json"
    }

    # -----------------------------------------------------
    # CONTACT FILTER
    # -----------------------------------------------------

    contact_include = {
        "jobTitles": selected_titles
    }

    # Optional PERSON LOCATION
    if person_country or person_state or person_city:

        person_location = {}

        if person_country:
            person_location["country"] = person_country

        if person_state:
            person_location["state"] = person_state

        if person_city:
            person_location["city"] = person_city

        contact_include["locations"] = [
            person_location
        ]

    # -----------------------------------------------------
    # COMPANY FILTER
    # -----------------------------------------------------

    company_include = {
        "names": [
            company_name
        ]
    }

    # Company location is deliberately separate
    # from employee location.
    if company_country or company_state or company_city:

        company_location = {}

        if company_country:
            company_location["country"] = company_country

        if company_state:
            company_location["state"] = company_state

        if company_city:
            company_location["city"] = company_city

        company_include["locations"] = [
            company_location
        ]

    # -----------------------------------------------------
    # FINAL PAYLOAD
    # -----------------------------------------------------

    payload = {
        "pagination": {
            "page": 0,
            "size": 50
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

    try:

        response = requests.post(
            LUSHA_URL,
            headers=headers,
            json=payload,
            timeout=60
        )

    except requests.exceptions.RequestException as e:

        return None, f"Connection error: {e}"

    # -----------------------------------------------------
    # ERROR HANDLING
    # -----------------------------------------------------

    if response.status_code != 200:

        try:
            error_data = response.json()

        except Exception:
            error_data = response.text

        return None, (
            f"Lusha API returned "
            f"{response.status_code}\n\n"
            f"{error_data}"
        )

    try:

        return response.json(), None

    except Exception:

        return None, "Lusha returned invalid JSON."


# =========================================================
# PROCESS RESULTS
# =========================================================

def process_results(data):

    rows = []

    for person in data.get("results", []):

        first_name = person.get(
            "firstName",
            ""
        )

        last_name = person.get(
            "lastName",
            ""
        )

        name = (
            f"{first_name} {last_name}"
        ).strip()

        job = person.get(
            "jobTitle",
            {}
        ) or {}

        title = job.get(
            "title",
            ""
        )

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

        social = person.get(
            "socialLinks",
            {}
        ) or {}

        linkedin = social.get(
            "linkedin",
            ""
        )

        valid, persona = persona_match(
            title
        )

        if valid:
            status = "QUALIFIED"
        else:
            status = "REJECTED"

        rows.append({

            "Name": name,

            "Current Title": title,

            "Persona": persona or "",

            "Department": ", ".join(
                departments
            ),

            "Seniority": seniority,

            "Company": company_name,

            "Company Domain": company_domain,

            "Employee City": city,

            "Employee State": state,

            "Employee Country": country,

            "LinkedIn": linkedin,

            "Status": status,

            "Lusha ID": person.get(
                "id",
                ""
            )
        })

    return pd.DataFrame(rows)


# =========================================================
# SIDEBAR
# =========================================================

st.title("🎯 Persona Prospecting Dashboard")

st.write(
    "Find IT, Technology, Infrastructure and Cybersecurity "
    "employees at a specific company and company location."
)

st.divider()


with st.sidebar:

    st.header("⚙️ Configuration")

    api_key = st.text_input(
        "Lusha API Key",
        type="password"
    )

    st.divider()

    st.subheader("Persona Groups")

    selected_groups = []

    for group in PERSONA_GROUPS:

        checked = st.checkbox(
            group,
            value=True
        )

        if checked:
            selected_groups.append(group)


# =========================================================
# COMPANY FILTERS
# =========================================================

st.subheader("🏢 Company")

col1, col2 = st.columns(2)

with col1:

    company_name = st.text_input(
        "Company Name *",
        value="Denave",
        placeholder="e.g. Denave"
    )

    company_country = st.text_input(
        "Company Country",
        value="India",
        placeholder="e.g. India"
    )

with col2:

    company_state = st.text_input(
        "Company State",
        value="Uttar Pradesh",
        placeholder="e.g. Uttar Pradesh"
    )

    company_city = st.text_input(
        "Company City",
        value="Noida",
        placeholder="e.g. Noida"
    )


st.caption(
    "🏢 Company location filters the company's HQ/site location. "
    "It is separate from the employee's personal location."
)


# =========================================================
# PERSON LOCATION
# =========================================================

st.subheader("👤 Employee Location")

use_person_location = st.checkbox(
    "Also filter employees by their location"
)

person_country = ""
person_state = ""
person_city = ""

if use_person_location:

    p1, p2, p3 = st.columns(3)

    with p1:

        person_country = st.text_input(
            "Employee Country",
            placeholder="India"
        )

    with p2:

        person_state = st.text_input(
            "Employee State",
            placeholder="Uttar Pradesh"
        )

    with p3:

        person_city = st.text_input(
            "Employee City",
            placeholder="Noida"
        )

else:

    st.info(
        "Employee location filtering is OFF. "
        "This means a relevant employee can be returned "
        "even if their personal location differs from the "
        "company's location."
    )


# =========================================================
# PERSONAS
# =========================================================

selected_titles = []

for group in selected_groups:

    selected_titles.extend(
        PERSONA_GROUPS[group]
    )

selected_titles = list(
    dict.fromkeys(selected_titles)
)

st.subheader("🎯 Search Criteria")

st.write(
    f"**{len(selected_titles)} persona titles selected**"
)

with st.expander("Show persona titles"):

    for title in selected_titles:

        st.write(
            f"• {title}"
        )


# =========================================================
# SEARCH BUTTON
# =========================================================

search = st.button(
    "🔎 FIND CURRENT IT EMPLOYEES",
    type="primary",
    use_container_width=True
)


# =========================================================
# EXECUTE
# =========================================================

if search:

    if not api_key:

        st.error(
            "Enter your Lusha API key first."
        )

        st.stop()

    if not company_name.strip():

        st.error(
            "Company name is required."
        )

        st.stop()

    if not selected_titles:

        st.error(
            "Select at least one persona group."
        )

        st.stop()

    with st.spinner(
        "Searching Lusha..."
    ):

        data, error = search_lusha(

            api_key=api_key,

            company_name=company_name.strip(),

            company_country=company_country.strip(),

            company_state=company_state.strip(),

            company_city=company_city.strip(),

            selected_titles=selected_titles,

            person_country=person_country.strip()
            if use_person_location
            else None,

            person_state=person_state.strip()
            if use_person_location
            else None,

            person_city=person_city.strip()
            if use_person_location
            else None,
        )

    if error:

        st.error(error)

        st.stop()

    # -----------------------------------------------------
    # RESPONSE INFO
    # -----------------------------------------------------

    pagination = data.get(
        "pagination",
        {}
    )

    total = pagination.get(
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
        f"Search successful — "
        f"{returned} contacts returned."
    )

    # -----------------------------------------------------
    # PROCESS
    # -----------------------------------------------------

    df = process_results(
        data
    )

    if df.empty:

        st.warning(
            "No contacts found."
        )

        st.stop()

    qualified = df[
        df["Status"] == "QUALIFIED"
    ].copy()

    rejected = df[
        df["Status"] == "REJECTED"
    ].copy()

    # -----------------------------------------------------
    # METRICS
    # -----------------------------------------------------

    a, b, c, d = st.columns(4)

    with a:

        st.metric(
            "Lusha Matches",
            total
        )

    with b:

        st.metric(
            "Returned",
            returned
        )

    with c:

        st.metric(
            "Qualified IT",
            len(qualified)
        )

    with d:

        match_rate = (
            len(qualified) /
            len(df) *
            100
        ) if len(df) else 0

        st.metric(
            "Qualification Rate",
            f"{match_rate:.0f}%"
        )

    st.divider()

    # =====================================================
    # QUALIFIED
    # =====================================================

    st.subheader(
        "✅ Qualified IT / Technology Employees"
    )

    if qualified.empty:

        st.warning(
            "No returned contacts passed our strict "
            "IT persona qualification."
        )

    else:

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

            "Status"
        ]

        st.dataframe(

            qualified[columns],

            use_container_width=True,

            hide_index=True,

            column_config={

                "LinkedIn":
                    st.column_config.LinkColumn(
                        "LinkedIn",
                        display_text="Open LinkedIn"
                    )
            }
        )

        csv = qualified.to_csv(
            index=False
        ).encode(
            "utf-8"
        )

        st.download_button(

            "⬇️ Download Qualified CSV",

            data=csv,

            file_name=(
                f"{company_name}_"
                f"IT_personas.csv"
            ),

            mime="text/csv"
        )


    # =====================================================
    # REJECTED
    # =====================================================

    with st.expander(
        f"❌ Rejected contacts ({len(rejected)})"
    ):

        if rejected.empty:

            st.write(
                "No rejected contacts."
            )

        else:

            rejected_columns = [

                "Name",

                "Current Title",

                "Department",

                "Company",

                "Employee City",

                "Employee State",

                "Employee Country",

                "LinkedIn",

                "Status"
            ]

            st.dataframe(

                rejected[rejected_columns],

                use_container_width=True,

                hide_index=True,

                column_config={

                    "LinkedIn":
                        st.column_config.LinkColumn(
                            "LinkedIn",
                            display_text="Open LinkedIn"
                        )
                }
            )


    # =====================================================
    # RAW API RESPONSE
    # =====================================================

    with st.expander(
        "🔧 Debug — Raw Lusha Response"
    ):

        st.json(data)
