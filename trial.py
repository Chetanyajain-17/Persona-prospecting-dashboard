import re
import io
import requests
import pandas as pd
import streamlit as st


# ============================================================
# CONFIG
# ============================================================

st.set_page_config(
    page_title="Company & Persona Intelligence",
    page_icon="🔎",
    layout="wide"
)

APOLLO_BASE = "https://api.apollo.io/api/v1"

# ============================================================
# PERSONA DEFINITIONS
# ============================================================

PERSONAS = {
    "Executive": [
        "CEO",
        "Chief Executive Officer",
        "CTO",
        "Chief Technology Officer",
        "CIO",
        "Chief Information Officer",
        "CISO",
        "Chief Information Security Officer",
    ],

    "IT Leadership": [
        "Head of IT",
        "Head IT",
        "Head of Information Technology",
        "IT Head",
        "IT Director",
        "Director IT",
        "Director of Information Technology",
        "IT Manager",
        "Information Technology Manager",
        "IT Operations Manager",
        "Technology Manager",
        "VP IT",
        "VP Technology",
        "Vice President IT",
        "Vice President Technology",
    ],

    "Infrastructure": [
        "Infrastructure Head",
        "Head of Infrastructure",
        "Infrastructure Director",
        "Infrastructure Manager",
        "IT Infrastructure Manager",
        "Infrastructure Architect",
        "Systems Architect",
        "Enterprise Architect",
        "Cloud Architect",
        "Solutions Architect",
    ],

    "Network": [
        "Network Administrator",
        "Network Admin",
        "Network Engineer",
        "Network Architect",
        "Network Security Architect",
        "Network Manager",
        "Head of Network",
        "Network Infrastructure Manager",
    ],

    "Security": [
        "Security Architect",
        "Cybersecurity Architect",
        "Cyber Security Architect",
        "Information Security Manager",
        "Information Security Director",
        "Information Security Head",
        "Security Manager",
        "Cybersecurity Manager",
        "Cyber Security Manager",
        "Security Engineer",
        "Cybersecurity Engineer",
        "Cyber Security Engineer",
    ],

    "Systems": [
        "System Administrator",
        "Systems Administrator",
        "System Admin",
        "Systems Admin",
        "Systems Manager",
        "System Engineer",
        "Systems Engineer",
        "IT Systems Manager",
    ]
}


ALL_TITLES = []

for group_titles in PERSONAS.values():
    for title in group_titles:
        if title not in ALL_TITLES:
            ALL_TITLES.append(title)


# ============================================================
# SESSION STATE
# ============================================================

if "company" not in st.session_state:
    st.session_state.company = None

if "people" not in st.session_state:
    st.session_state.people = []

if "search_complete" not in st.session_state:
    st.session_state.search_complete = False


# ============================================================
# HELPERS
# ============================================================

def normalize_domain(value):
    if not value:
        return ""

    value = str(value).strip().lower()

    value = re.sub(r"^https?://", "", value)
    value = re.sub(r"^www\.", "", value)

    value = value.split("/")[0]
    value = value.split("?")[0]

    return value.strip()


def clean_text(value):
    if value is None:
        return ""

    if isinstance(value, (dict, list)):
        return str(value)

    return str(value).strip()


def safe_get(data, *keys, default=""):
    current = data

    for key in keys:
        if not isinstance(current, dict):
            return default

        current = current.get(key)

        if current is None:
            return default

    return current


def apollo_request(endpoint, api_key, method="POST", params=None, json_data=None):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "x-api-key": api_key,
        "Cache-Control": "no-cache"
    }

    url = f"{APOLLO_BASE}/{endpoint}"

    try:
        if method.upper() == "GET":
            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=30
            )
        else:
            response = requests.post(
                url,
                headers=headers,
                params=params,
                json=json_data,
                timeout=30
            )

        if response.status_code == 401:
            return None, "Invalid Apollo API key."

        if response.status_code == 403:
            return None, (
                "Apollo rejected this request. "
                "Your API plan/account may not have access to this endpoint."
            )

        if response.status_code == 429:
            return None, "Apollo rate limit reached. Please wait and try again."

        if response.status_code >= 400:
            try:
                error_data = response.json()
            except Exception:
                error_data = response.text

            return None, f"Apollo API error ({response.status_code}): {error_data}"

        return response.json(), None

    except requests.exceptions.Timeout:
        return None, "Apollo request timed out."

    except requests.exceptions.RequestException as e:
        return None, f"Network error: {e}"

    except Exception as e:
        return None, f"Unexpected error: {e}"


# ============================================================
# COMPANY SEARCH
# ============================================================

def search_company(company_name, location, api_key):

    payload = {
        "q_organization_name": company_name,
        "organization_locations": [location],
        "page": 1,
        "per_page": 10
    }

    data, error = apollo_request(
        "mixed_companies/search",
        api_key,
        method="POST",
        json_data=payload
    )

    if error:
        return [], error

    organizations = (
        data.get("organizations")
        or data.get("accounts")
        or data.get("companies")
        or []
    )

    return organizations, None


# ============================================================
# COMPANY ENRICHMENT
# ============================================================

def enrich_company(company, api_key):

    company_id = (
        company.get("id")
        or company.get("organization_id")
    )

    domain = normalize_domain(
        company.get("primary_domain")
        or company.get("domain")
        or company.get("website_url")
    )

    name = company.get("name", "")

    payload = {}

    if domain:
        payload["domain"] = domain

    if name:
        payload["name"] = name

    if not payload:
        return company, "Could not identify company for enrichment."

    data, error = apollo_request(
        "organizations/enrich",
        api_key,
        method="GET",
        params=payload
    )

    if error:
        # If enrichment fails, retain search result.
        return company, error

    enriched = (
        data.get("organization")
        or data.get("company")
        or data
    )

    if isinstance(enriched, dict):
        return enriched, None

    return company, None


# ============================================================
# PEOPLE SEARCH
# ============================================================

def search_people(
    organization_id,
    organization_domain,
    selected_titles,
    api_key
):

    payload = {
        "person_titles": selected_titles,

        # VERY IMPORTANT:
        # We don't want similar titles accidentally expanding
        # the search into unrelated positions.
        "include_similar_titles": False,

        "page": 1,
        "per_page": 100
    }

    if organization_id:
        payload["organization_ids"] = [organization_id]

    elif organization_domain:
        payload["q_organization_domains_list"] = [
            organization_domain
        ]

    else:
        return [], "No company ID or domain available."

    data, error = apollo_request(
        "mixed_people/api_search",
        api_key,
        method="POST",
        json_data=payload
    )

    if error:
        return [], error

    people = (
        data.get("people")
        or data.get("contacts")
        or []
    )

    return people, None


# ============================================================
# PERSON ENRICHMENT
# ============================================================

def enrich_person(person, api_key):

    person_id = person.get("id") or person.get("person_id")

    linkedin_url = (
        person.get("linkedin_url")
        or person.get("linkedin")
    )

    payload = {}

    if person_id:
        payload["id"] = person_id

    elif linkedin_url:
        payload["linkedin_url"] = linkedin_url

    else:
        first_name = person.get("first_name", "")
        last_name = person.get("last_name", "")

        if first_name or last_name:
            payload["name"] = f"{first_name} {last_name}".strip()

        organization = person.get("organization") or {}

        domain = normalize_domain(
            organization.get("primary_domain")
            or organization.get("domain")
        )

        if domain:
            payload["domain"] = domain

    if not payload:
        return person, "No usable person identifier."

    data, error = apollo_request(
        "people/match",
        api_key,
        method="POST",
        json_data=payload
    )

    if error:
        return person, error

    enriched = (
        data.get("person")
        or data.get("contact")
        or data
    )

    if isinstance(enriched, dict):
        return enriched, None

    return person, None


# ============================================================
# EMPLOYMENT VERIFICATION
# ============================================================

def verify_current_employee(
    person,
    target_company,
    target_org_id,
    target_domain
):

    reasons = []
    score = 0

    target_name = clean_text(
        target_company.get("name")
    ).lower()

    target_domain = normalize_domain(
        target_domain
    )

    person_org = person.get("organization") or {}

    current_org_id = clean_text(
        person_org.get("id")
        or person.get("organization_id")
    )

    current_org_name = clean_text(
        person_org.get("name")
        or person.get("organization_name")
    )

    current_domain = normalize_domain(
        person_org.get("primary_domain")
        or person_org.get("domain")
        or person.get("primary_domain")
    )

    # --------------------------------------------------------
    # Organization ID check
    # --------------------------------------------------------

    if target_org_id and current_org_id:
        if str(target_org_id) == str(current_org_id):
            score += 45
            reasons.append("Current Apollo organization ID matches.")
        else:
            return False, 0, [
                "Current Apollo organization ID does NOT match target company."
            ]

    # --------------------------------------------------------
    # Domain check
    # --------------------------------------------------------

    if target_domain and current_domain:

        if current_domain == target_domain:
            score += 30
            reasons.append("Current employer domain matches.")

        elif current_domain.endswith("." + target_domain):
            score += 25
            reasons.append("Current employer domain is a subdomain match.")

        else:
            return False, 0, [
                "Current employer domain does NOT match target company."
            ]

    # --------------------------------------------------------
    # Company name check
    # --------------------------------------------------------

    if target_name and current_org_name:

        normalized_target = re.sub(
            r"[^a-z0-9]",
            "",
            target_name
        )

        normalized_current = re.sub(
            r"[^a-z0-9]",
            "",
            current_org_name.lower()
        )

        if (
            normalized_target == normalized_current
            or normalized_target in normalized_current
            or normalized_current in normalized_target
        ):
            score += 15
            reasons.append("Current employer name matches.")
        else:

            # If ID/domain already matched, don't reject.
            if score < 40:
                return False, 0, [
                    "Current employer name does NOT match target company."
                ]

    # --------------------------------------------------------
    # Employment history
    # --------------------------------------------------------

    employment_history = person.get(
        "employment_history"
    ) or []

    if isinstance(employment_history, list):

        current_entries = []

        for job in employment_history:

            if not isinstance(job, dict):
                continue

            if job.get("current") is True:
                current_entries.append(job)

        if current_entries:

            history_match = False

            for job in current_entries:

                job_org_id = clean_text(
                    job.get("organization_id")
                )

                job_org_name = clean_text(
                    job.get("organization_name")
                    or job.get("organization")
                ).lower()

                job_domain = normalize_domain(
                    job.get("domain")
                )

                if (
                    target_org_id
                    and job_org_id
                    and str(target_org_id) == str(job_org_id)
                ):
                    history_match = True

                if (
                    target_domain
                    and job_domain
                    and target_domain == job_domain
                ):
                    history_match = True

                if (
                    target_name
                    and job_org_name
                    and (
                        target_name in job_org_name
                        or job_org_name in target_name
                    )
                ):
                    history_match = True

            if history_match:
                score += 10
                reasons.append(
                    "Employment history confirms current employment."
                )

            else:
                # Current organization is already strongly matched,
                # so don't automatically reject due to incomplete history.
                reasons.append(
                    "Employment history is available but not fully matched."
                )

    # --------------------------------------------------------
    # Current title
    # --------------------------------------------------------

    title = clean_text(
        person.get("title")
    )

    if title:
        score += 10
        reasons.append(
            f"Current title returned by Apollo: {title}"
        )

    # --------------------------------------------------------
    # Final decision
    # --------------------------------------------------------

    if score >= 70:
        return True, min(score, 100), reasons

    if score >= 45:
        return True, score, reasons

    return False, score, reasons


# ============================================================
# TITLE CATEGORY
# ============================================================

def get_persona_category(title):

    title_lower = title.lower()

    for category, titles in PERSONAS.items():

        for allowed_title in titles:

            allowed_lower = allowed_title.lower()

            if allowed_lower in title_lower:
                return category

    return "Other"


# ============================================================
# COMPANY DISPLAY DATA
# ============================================================

def extract_company_data(company):

    locations = company.get("locations") or []

    location_strings = []

    if isinstance(locations, list):

        for loc in locations:

            if isinstance(loc, dict):

                parts = [
                    loc.get("city"),
                    loc.get("state"),
                    loc.get("country")
                ]

                parts = [
                    clean_text(x)
                    for x in parts
                    if clean_text(x)
                ]

                if parts:
                    location_strings.append(
                        ", ".join(parts)
                    )

    hq = company.get("primary_location") or {}

    return {
        "name": company.get("name", ""),
        "website": (
            company.get("website_url")
            or company.get("website")
            or (
                "https://" + company.get("primary_domain")
                if company.get("primary_domain")
                else ""
            )
        ),
        "linkedin": (
            company.get("linkedin_url")
            or company.get("linkedin")
            or ""
        ),
        "description": (
            company.get("short_description")
            or company.get("description")
            or ""
        ),
        "industry": (
            company.get("industry")
            or ""
        ),
        "employees": (
            company.get("estimated_num_employees")
            or company.get("num_employees")
            or ""
        ),
        "revenue": (
            company.get("annual_revenue_printed")
            or company.get("annual_revenue")
            or ""
        ),
        "founded": (
            company.get("founded_year")
            or ""
        ),
        "city": (
            hq.get("city")
            or company.get("city")
            or ""
        ),
        "state": (
            hq.get("state")
            or company.get("state")
            or ""
        ),
        "country": (
            hq.get("country")
            or company.get("country")
            or ""
        ),
        "locations": location_strings
    }


# ============================================================
# PAGE HEADER
# ============================================================

st.title("🔎 Company & Persona Intelligence Dashboard")

st.caption(
    "Find company intelligence and verify current technology / IT decision-makers."
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("⚙️ Configuration")

    api_key = st.text_input(
        "Apollo API Key",
        type="password",
        help="Enter your Apollo API key."
    )

    st.divider()

    st.subheader("Persona Groups")

    selected_groups = []

    for group in PERSONAS.keys():

        if st.checkbox(
            group,
            value=True
        ):
            selected_groups.append(group)

    selected_titles = []

    for group in selected_groups:
        selected_titles.extend(
            PERSONAS[group]
        )

    st.divider()

    st.info(
        "The application uses strict current-employment "
        "verification before showing a person as a valid result."
    )


# ============================================================
# SEARCH INPUT
# ============================================================

st.subheader("🏢 Search Company")

col1, col2 = st.columns([2, 1])

with col1:

    company_name = st.text_input(
        "Company Name",
        placeholder="Example: Denave"
    )

with col2:

    company_location = st.text_input(
        "Company Location",
        placeholder="Example: Noida"
    )


search_button = st.button(
    "🔍 Search Company & Current Personas",
    type="primary",
    use_container_width=True
)


# ============================================================
# MAIN SEARCH
# ============================================================

if search_button:

    if not api_key:

        st.error(
            "Please enter your Apollo API key."
        )
        st.stop()

    if not company_name.strip():

        st.error(
            "Please enter a company name."
        )
        st.stop()

    if not company_location.strip():

        st.error(
            "Please enter the company location."
        )
        st.stop()

    if not selected_titles:

        st.error(
            "Please select at least one persona group."
        )
        st.stop()

    # --------------------------------------------------------
    # COMPANY SEARCH
    # --------------------------------------------------------

    with st.spinner(
        "Finding the correct company..."
    ):

        organizations, error = search_company(
            company_name.strip(),
            company_location.strip(),
            api_key
        )

    if error:

        st.error(error)
        st.stop()

    if not organizations:

        st.warning(
            "No company found for the supplied name/location."
        )
        st.stop()

    # --------------------------------------------------------
    # COMPANY SELECTION
    # --------------------------------------------------------

    # Prefer exact-ish company name matches.

    requested_name = company_name.strip().lower()

    def company_match_score(org):

        name = clean_text(
            org.get("name")
        ).lower()

        if name == requested_name:
            return 100

        if requested_name in name:
            return 80

        if name in requested_name:
            return 70

        return 50

    organizations = sorted(
        organizations,
        key=company_match_score,
        reverse=True
    )

    best_company = organizations[0]

    # --------------------------------------------------------
    # ENRICH COMPANY
    # --------------------------------------------------------

    with st.spinner(
        "Enriching company information..."
    ):

        enriched_company, company_error = enrich_company(
            best_company,
            api_key
        )

    if company_error:

        st.warning(
            f"Company enrichment warning: {company_error}"
        )

    st.session_state.company = enriched_company

    # --------------------------------------------------------
    # IDENTIFIERS
    # --------------------------------------------------------

    organization_id = (
        enriched_company.get("id")
        or enriched_company.get("organization_id")
        or best_company.get("id")
        or best_company.get("organization_id")
    )

    organization_domain = normalize_domain(
        enriched_company.get("primary_domain")
        or enriched_company.get("domain")
        or best_company.get("primary_domain")
        or best_company.get("domain")
        or enriched_company.get("website_url")
    )

    # --------------------------------------------------------
    # PEOPLE SEARCH
    # --------------------------------------------------------

    with st.spinner(
        "Searching for current people..."
    ):

        raw_people, people_error = search_people(
            organization_id,
            organization_domain,
            selected_titles,
            api_key
        )

    if people_error:

        st.error(people_error)
        st.stop()

    verified_people = []

    progress = st.progress(0)

    total = len(raw_people)

    # --------------------------------------------------------
    # ENRICH + VERIFY EACH PERSON
    # --------------------------------------------------------

    for index, raw_person in enumerate(raw_people):

        try:

            person, enrichment_error = enrich_person(
                raw_person,
                api_key
            )

            # If enrichment fails, we can still use the search
            # result, but verification will be conservative.

            if not person:
                continue

            is_current, score, reasons = verify_current_employee(
                person,
                enriched_company,
                organization_id,
                organization_domain
            )

            if not is_current:
                continue

            title = clean_text(
                person.get("title")
            )

            if not title:
                continue

            first_name = clean_text(
                person.get("first_name")
            )

            last_name = clean_text(
                person.get("last_name")
                or person.get("last_name_obfuscated")
            )

            full_name = clean_text(
                person.get("name")
            )

            if not full_name:

                full_name = (
                    f"{first_name} {last_name}"
                ).strip()

            person_org = person.get(
                "organization"
            ) or {}

            current_company = clean_text(
                person_org.get("name")
                or person.get("organization_name")
            )

            linkedin = (
                person.get("linkedin_url")
                or person.get("linkedin")
                or ""
            )

            city = clean_text(
                person.get("city")
            )

            state = clean_text(
                person.get("state")
            )

            country = clean_text(
                person.get("country")
            )

            location_parts = [
                city,
                state,
                country
            ]

            location_parts = [
                x for x in location_parts
                if x
            ]

            person_location = ", ".join(
                location_parts
            )

            verified_people.append({
                "Name": full_name,
                "Current Title": title,
                "Persona": get_persona_category(title),
                "Current Company": current_company,
                "Location": person_location,
                "LinkedIn": linkedin,
                "Confidence": score,
                "Verification": "CURRENT EMPLOYEE",
                "Evidence": " | ".join(reasons),
                "Apollo Person ID": (
                    person.get("id")
                    or person.get("person_id")
                    or ""
                )
            })

        except Exception:
            continue

        if total:
            progress.progress(
                (index + 1) / total
            )

    progress.empty()

    # --------------------------------------------------------
    # DEDUPLICATE
    # --------------------------------------------------------

    if verified_people:

        people_df = pd.DataFrame(
            verified_people
        )

        people_df = people_df.drop_duplicates(
            subset=[
                "Name",
                "Current Title",
                "LinkedIn"
            ]
        )

        people_df = people_df.sort_values(
            by=[
                "Confidence",
                "Persona"
            ],
            ascending=[
                False,
                True
            ]
        )

        st.session_state.people = (
            people_df.to_dict("records")
        )

    else:

        st.session_state.people = []

    st.session_state.search_complete = True


# ============================================================
# RESULTS
# ============================================================

if st.session_state.search_complete:

    company = st.session_state.company

    if not company:
        st.stop()

    company_data = extract_company_data(
        company
    )

    st.divider()

    # ========================================================
    # COMPANY OVERVIEW
    # ========================================================

    st.header(
        f"🏢 {company_data['name']}"
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "Employees",
            company_data["employees"]
            or "N/A"
        )

    with col2:

        st.metric(
            "Industry",
            company_data["industry"]
            or "N/A"
        )

    with col3:

        st.metric(
            "Founded",
            company_data["founded"]
            or "N/A"
        )

    with col4:

        st.metric(
            "Revenue",
            company_data["revenue"]
            or "N/A"
        )

    st.subheader(
        "Company Information"
    )

    info_col1, info_col2 = st.columns(2)

    with info_col1:

        st.markdown(
            f"**Website:** "
            f"{company_data['website'] or 'N/A'}"
        )

        st.markdown(
            f"**LinkedIn:** "
            f"{company_data['linkedin'] or 'N/A'}"
        )

        st.markdown(
            f"**Industry:** "
            f"{company_data['industry'] or 'N/A'}"
        )

    with info_col2:

        headquarters = ", ".join(
            [
                x
                for x in [
                    company_data["city"],
                    company_data["state"],
                    company_data["country"]
                ]
                if x
            ]
        )

        st.markdown(
            f"**Headquarters:** "
            f"{headquarters or 'N/A'}"
        )

        if company_data["locations"]:

            st.markdown(
                "**Known Locations:**"
            )

            for location in company_data[
                "locations"
            ]:

                st.write(
                    f"• {location}"
                )

    if company_data["description"]:

        st.subheader(
            "What does this company do?"
        )

        st.write(
            company_data["description"]
        )

    # ========================================================
    # PERSON RESULTS
    # ========================================================

    st.divider()

    st.header(
        "👥 Current Technology / IT People"
    )

    people = st.session_state.people

    if not people:

        st.warning(
            "No verified current persona was found "
            "for the selected persona groups."
        )

        st.info(
            "This does NOT mean the company has no such "
            "employee. It means the current data source "
            "did not provide a sufficiently verified match."
        )

    else:

        people_df = pd.DataFrame(
            people
        )

        # Summary
        c1, c2, c3 = st.columns(3)

        with c1:

            st.metric(
                "Verified People",
                len(people_df)
            )

        with c2:

            high_confidence = len(
                people_df[
                    people_df["Confidence"] >= 80
                ]
            )

            st.metric(
                "High Confidence",
                high_confidence
            )

        with c3:

            linkedin_count = len(
                people_df[
                    people_df["LinkedIn"].astype(str).str.len() > 0
                ]
            )

            st.metric(
                "LinkedIn Profiles",
                linkedin_count
            )

        st.divider()

        # ====================================================
        # PERSON CARDS
        # ====================================================

        for _, row in people_df.iterrows():

            confidence = int(
                row["Confidence"]
            )

            if confidence >= 85:
                badge = "🟢 HIGH"
            elif confidence >= 70:
                badge = "🟡 MEDIUM"
            else:
                badge = "🟠 REVIEW"

            with st.container(
                border=True
            ):

                left, middle, right = st.columns(
                    [2, 3, 1]
                )

                with left:

                    st.subheader(
                        row["Name"]
                    )

                    st.write(
                        f"**{row['Current Title']}**"
                    )

                    st.caption(
                        row["Persona"]
                    )

                with middle:

                    st.write(
                        f"**Current Company:** "
                        f"{row['Current Company']}"
                    )

                    st.write(
                        f"**Location:** "
                        f"{row['Location'] or 'N/A'}"
                    )

                    if row["LinkedIn"]:

                        st.markdown(
                            f"[🔗 LinkedIn Profile]"
                            f"({row['LinkedIn']})"
                        )

                    else:

                        st.write(
                            "LinkedIn: Not available"
                        )

                with right:

                    st.metric(
                        "Confidence",
                        f"{confidence}%"
                    )

                    st.write(
                        badge
                    )

                with st.expander(
                    "🔍 Verification Evidence"
                ):

                    st.write(
                        row["Evidence"]
                    )

                    st.success(
                        "CURRENT EMPLOYEE"
                    )

        # ====================================================
        # TABLE
        # ====================================================

        st.subheader(
            "📋 All Verified Results"
        )

        display_columns = [
            "Name",
            "Current Title",
            "Persona",
            "Current Company",
            "Location",
            "LinkedIn",
            "Confidence",
            "Verification"
        ]

        display_df = people_df[
            display_columns
        ].copy()

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "LinkedIn": st.column_config.LinkColumn(
                    "LinkedIn",
                    display_text="Open LinkedIn"
                ),
                "Confidence": st.column_config.ProgressColumn(
                    "Confidence",
                    min_value=0,
                    max_value=100,
                    format="%d%%"
                )
            }
        )

        # ====================================================
        # CSV DOWNLOAD
        # ====================================================

        csv_data = people_df.to_csv(
            index=False
        ).encode("utf-8")

        st.download_button(
            "⬇️ Download People CSV",
            data=csv_data,
            file_name="verified_current_people.csv",
            mime="text/csv",
            use_container_width=True
        )

    # ========================================================
    # DEBUG / RAW COMPANY
    # ========================================================

    with st.expander(
        "Developer Information"
    ):

        st.write(
            "Apollo Organization ID:"
        )

        st.code(
            company.get("id")
            or company.get("organization_id")
            or "N/A"
        )

        st.write(
            "Primary Domain:"
        )

        st.code(
            normalize_domain(
                company.get("primary_domain")
                or company.get("domain")
                or ""
            )
            or "N/A"
        )
