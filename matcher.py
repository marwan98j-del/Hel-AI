# =========================================================
# OPPORTUNITY AI MATCHING ENGINE
# =========================================================


EDUCATION_LEVELS = {
    "High School": 1,
    "Diploma": 2,
    "Bachelor's Degree": 3,
    "Master's Degree": 4,
    "PhD": 5
}


KURDISTAN_REGION_CITIES = {
    "Sulaymaniyah",
    "Erbil",
    "Duhok",
    "Halabja"
}


# =========================================================
# LOCATION HELPERS
# =========================================================

def is_kurdistan_region_city(city):
    return city in KURDISTAN_REGION_CITIES


def check_residency(profile, opportunity):

    requirement = opportunity.get(
        "residency_requirement",
        ""
    )

    if not requirement:
        return True, None

    city = profile.get(
        "city",
        ""
    )

    if requirement == "Iraq":

        if city:
            return (
                True,
                "You meet the Iraq residency requirement"
            )

    if requirement == "Kurdistan Region":

        if is_kurdistan_region_city(city):

            return (
                True,
                "You meet the Kurdistan Region residency requirement"
            )

        return (
            False,
            "Applicants must live in the Kurdistan Region"
        )

    if requirement in KURDISTAN_REGION_CITIES:

        if city == requirement:

            return (
                True,
                f"You meet the {requirement} residency requirement"
            )

        return (
            False,
            f"Applicants must live in {requirement}"
        )

    return True, None


def calculate_location_relevance(profile, opportunity):

    user_city = profile.get(
        "city",
        ""
    )

    location = opportunity.get(
        "location",
        ""
    )

    if not user_city or not location:

        return (
            10,
            "Location compatibility is neutral"
        )

    location_lower = location.lower()
    city_lower = user_city.lower()

    if city_lower in location_lower:

        return (
            20,
            f"The opportunity is located in {user_city}"
        )

    if (
        "kurdistan region" in location_lower
        and is_kurdistan_region_city(user_city)
    ):

        return (
            18,
            "The opportunity is available across the Kurdistan Region"
        )

    if (
        location_lower == "iraq"
        or "across iraq" in location_lower
    ):

        return (
            15,
            "The opportunity is available in Iraq"
        )

    if (
        "international" in location_lower
        or "united kingdom" in location_lower
        or "abroad" in location_lower
    ):

        return (
            14,
            "This is an international opportunity"
        )

    return (
        8,
        f"The opportunity is outside your selected city ({user_city})"
    )


# =========================================================
# MAIN MATCH FUNCTION
# =========================================================

def calculate_match(profile, opportunity):

    reasons = []

    eligibility_gaps = []
    readiness_gaps = []

    eligible = True

    # -----------------------------------------------------
    # CLOSED
    # -----------------------------------------------------

    if opportunity.get("status") == "Closed":

        return {
            "score": 0,
            "eligible": False,
            "readiness": 0,
            "reasons": [],
            "missing": [
                "This opportunity is closed"
            ],
            "eligibility_gaps": [
                "This opportunity is closed"
            ],
            "readiness_gaps": []
        }

    # -----------------------------------------------------
    # AGE
    # -----------------------------------------------------

    age = profile.get(
        "age",
        0
    )

    minimum_age = opportunity.get(
        "minimum_age"
    )

    maximum_age = opportunity.get(
        "maximum_age"
    )

    if (
        minimum_age is not None
        and age < minimum_age
    ):

        eligible = False

        eligibility_gaps.append(
            f"Minimum age is {minimum_age}"
        )

    elif (
        maximum_age is not None
        and age > maximum_age
    ):

        eligible = False

        eligibility_gaps.append(
            f"Maximum age is {maximum_age}"
        )

    else:

        reasons.append(
            "You meet the age requirement"
        )

    # -----------------------------------------------------
    # EDUCATION
    # -----------------------------------------------------

    required_education = opportunity.get(
        "education",
        "Any"
    )

    education_rule = opportunity.get(
        "education_rule",
        "minimum"
    )

    user_education = profile.get(
        "education",
        ""
    )

    if required_education == "Any":

        reasons.append(
            "No specific education level is required"
        )

    else:

        user_level = EDUCATION_LEVELS.get(
            user_education,
            0
        )

        required_level = EDUCATION_LEVELS.get(
            required_education,
            0
        )

        if education_rule == "exact":

            if user_education == required_education:

                reasons.append(
                    f"Your education matches the required "
                    f"{required_education} level"
                )

            else:

                eligible = False

                eligibility_gaps.append(
                    f"This opportunity specifically targets "
                    f"{required_education} applicants"
                )

        else:

            if user_level >= required_level:

                reasons.append(
                    f"Your education meets the "
                    f"{required_education} requirement"
                )

            else:

                eligible = False

                eligibility_gaps.append(
                    f"Requires at least {required_education}"
                )

    # -----------------------------------------------------
    # GRADE
    # -----------------------------------------------------

    minimum_grade = opportunity.get(
        "minimum_grade",
        0
    )

    user_grade = profile.get(
        "grade",
        0
    )

    if minimum_grade > 0:

        if user_grade >= minimum_grade:

            reasons.append(
                f"Your grade meets the minimum "
                f"{minimum_grade}% requirement"
            )

        else:

            eligible = False

            eligibility_gaps.append(
                f"Requires a minimum academic average "
                f"of {minimum_grade}%"
            )

    # -----------------------------------------------------
    # WORK EXPERIENCE
    # -----------------------------------------------------

    required_work = opportunity.get(
        "minimum_work_experience_years",
        0
    )

    user_work = profile.get(
        "work_experience_years",
        0
    )

    if required_work > 0:

        if user_work >= required_work:

            reasons.append(
                f"You meet the {required_work}-year "
                f"work experience requirement"
            )

        else:

            eligible = False

            eligibility_gaps.append(
                f"Requires {required_work} years "
                f"of work experience"
            )

    # -----------------------------------------------------
    # LANGUAGES
    # -----------------------------------------------------

    required_languages = opportunity.get(
        "languages",
        []
    )

    user_languages = profile.get(
        "languages",
        []
    )

    missing_languages = [
        language
        for language in required_languages
        if language not in user_languages
    ]

    if required_languages:

        if not missing_languages:

            reasons.append(
                "You meet the language requirements"
            )

        else:

            eligible = False

            eligibility_gaps.append(
                "Missing required language: "
                + ", ".join(missing_languages)
            )

    # -----------------------------------------------------
    # RESIDENCY
    # -----------------------------------------------------

    residency_ok, residency_reason = check_residency(
        profile,
        opportunity
    )

    if residency_ok:

        if residency_reason:

            reasons.append(
                residency_reason
            )

    else:

        eligible = False

        eligibility_gaps.append(
            residency_reason
        )

    # =====================================================
    # READINESS
    # =====================================================

    document_requirements = [
        (
            "requires_passport",
            "has_passport",
            "Valid passport"
        ),
        (
            "requires_ielts",
            "has_ielts",
            "IELTS / English certificate"
        ),
        (
            "requires_portfolio",
            "has_portfolio",
            "Portfolio"
        ),
        (
            "requires_cv",
            "has_cv",
            "CV"
        )
    ]

    required_documents = 0
    available_documents = 0

    for (
        opportunity_key,
        profile_key,
        label
    ) in document_requirements:

        if opportunity.get(
            opportunity_key,
            False
        ):

            required_documents += 1

            if profile.get(
                profile_key,
                False
            ):

                available_documents += 1

                reasons.append(
                    f"You already have the required {label}"
                )

            else:

                readiness_gaps.append(
                    f"Missing document: {label}"
                )

    if required_documents == 0:

        readiness = 100

    else:

        readiness = round(
            (
                available_documents
                / required_documents
            )
            * 100
        )

    # =====================================================
    # MATCH / RELEVANCE SCORE
    # =====================================================

    relevance_points = 0
    relevance_possible = 0

    # -----------------------------------------------------
    # OPPORTUNITY TYPE
    # -----------------------------------------------------

    user_types = profile.get(
        "opportunity_types",
        []
    )

    opportunity_type = opportunity.get(
        "type",
        ""
    )

    relevance_possible += 25

    if opportunity_type in user_types:

        relevance_points += 25

        reasons.append(
            f"You are looking for "
            f"{opportunity_type} opportunities"
        )

    # -----------------------------------------------------
    # LOCATION
    # -----------------------------------------------------

    relevance_possible += 20

    location_points, location_reason = (
        calculate_location_relevance(
            profile,
            opportunity
        )
    )

    relevance_points += location_points

    if location_reason:

        reasons.append(
            location_reason
        )

    # -----------------------------------------------------
    # INTERESTS
    # -----------------------------------------------------

    opportunity_interests = opportunity.get(
        "interests",
        []
    )

    user_interests = profile.get(
        "interests",
        []
    )

    relevance_possible += 30

    if opportunity_interests:

        interest_matches = (
            set(opportunity_interests)
            & set(user_interests)
        )

        interest_ratio = (
            len(interest_matches)
            / len(opportunity_interests)
        )

        relevance_points += (
            30 * interest_ratio
        )

        if interest_matches:

            reasons.append(
                "Matching interests: "
                + ", ".join(
                    sorted(
                        interest_matches
                    )
                )
            )

    else:

        relevance_points += 15

    # -----------------------------------------------------
    # SKILLS
    # -----------------------------------------------------

    opportunity_skills = opportunity.get(
        "skills",
        []
    )

    user_skills = profile.get(
        "skills",
        []
    )

    relevance_possible += 25

    if opportunity_skills:

        skill_matches = (
            set(opportunity_skills)
            & set(user_skills)
        )

        skill_ratio = (
            len(skill_matches)
            / len(opportunity_skills)
        )

        relevance_points += (
            25 * skill_ratio
        )

        if skill_matches:

            reasons.append(
                "Matching skills: "
                + ", ".join(
                    sorted(
                        skill_matches
                    )
                )
            )

    else:

        relevance_points += 12.5

    # -----------------------------------------------------
    # FINAL SCORE
    # -----------------------------------------------------

    if relevance_possible > 0:

        score = round(
            (
                relevance_points
                / relevance_possible
            )
            * 100
        )

    else:

        score = 0

    score = max(
        0,
        min(
            score,
            100
        )
    )

    missing = (
        eligibility_gaps
        + readiness_gaps
    )

    return {
        "score": score,
        "eligible": eligible,
        "readiness": readiness,
        "reasons": reasons,
        "missing": missing,
        "eligibility_gaps": eligibility_gaps,
        "readiness_gaps": readiness_gaps
    }


# =========================================================
# PROFILE COMPARISON
# =========================================================

def compare_profiles(
    original_profile,
    simulated_profile,
    opportunities
):

    unlocked = 0
    improved = 0

    score_gain = 0
    readiness_gain = 0

    for opportunity in opportunities:

        if opportunity.get(
            "status"
        ) != "Open":

            continue

        original = calculate_match(
            original_profile,
            opportunity
        )

        simulated = calculate_match(
            simulated_profile,
            opportunity
        )

        if (
            not original["eligible"]
            and simulated["eligible"]
        ):

            unlocked += 1

        score_difference = (
            simulated["score"]
            - original["score"]
        )

        readiness_difference = (
            simulated["readiness"]
            - original["readiness"]
        )

        if (
            score_difference > 0
            or readiness_difference > 0
        ):

            improved += 1

        if score_difference > 0:

            score_gain += score_difference

        if readiness_difference > 0:

            readiness_gain += readiness_difference

    return {
        "unlocked": unlocked,
        "improved": improved,
        "score_gain": score_gain,
        "readiness_gain": readiness_gain
    }


# =========================================================
# OPPORTUNITY BOOSTER
# =========================================================

def analyze_improvements(
    profile,
    opportunities
):

    improvements = {}

    open_opportunities = [
        opportunity
        for opportunity in opportunities
        if opportunity.get(
            "status"
        ) == "Open"
    ]

    # -----------------------------------------------------
    # DOCUMENTS / LANGUAGES / SKILLS
    # -----------------------------------------------------

    simulations = [
        (
            "Get a valid passport",
            "has_passport",
            True
        ),
        (
            "Get an IELTS / English certificate",
            "has_ielts",
            True
        ),
        (
            "Create a portfolio",
            "has_portfolio",
            True
        ),
        (
            "Prepare a professional CV",
            "has_cv",
            True
        ),
        (
            "Add English language",
            "languages",
            "English"
        ),
        (
            "Learn Artificial Intelligence",
            "skills",
            "Artificial Intelligence"
        ),
        (
            "Learn Programming",
            "skills",
            "Programming"
        ),
        (
            "Learn Data Analysis",
            "skills",
            "Data Analysis"
        ),
        (
            "Learn Project Management",
            "skills",
            "Project Management"
        )
    ]

    for (
        label,
        key,
        value
    ) in simulations:

        simulated_profile = profile.copy()

        current_value = profile.get(
            key
        )

        if isinstance(
            current_value,
            list
        ):

            simulated_profile[key] = list(
                current_value
            )

            if value in simulated_profile[key]:
                continue

            simulated_profile[key].append(
                value
            )

        else:

            if current_value == value:
                continue

            simulated_profile[key] = value

        result = compare_profiles(
            profile,
            simulated_profile,
            open_opportunities
        )

        if (
            result["unlocked"] > 0
            or result["improved"] > 0
        ):

            improvements[label] = result

    # -----------------------------------------------------
    # EDUCATION
    #
    # Only recommend education levels actually required
    # by currently open opportunities.
    # -----------------------------------------------------

    current_education = profile.get(
        "education",
        "High School"
    )

    current_level = EDUCATION_LEVELS.get(
        current_education,
        0
    )

    required_education_targets = set()

    for opportunity in open_opportunities:

        required = opportunity.get(
            "education",
            "Any"
        )

        if required == "Any":
            continue

        required_level = EDUCATION_LEVELS.get(
            required,
            0
        )

        if required_level > current_level:

            required_education_targets.add(
                required
            )

    sorted_targets = sorted(
        required_education_targets,
        key=lambda education: EDUCATION_LEVELS.get(
            education,
            0
        )
    )

    for education in sorted_targets:

        simulated_profile = profile.copy()

        simulated_profile[
            "education"
        ] = education

        result = compare_profiles(
            profile,
            simulated_profile,
            open_opportunities
        )

        if (
            result["unlocked"] > 0
            or result["improved"] > 0
        ):

            improvements[
                f"Reach {education} level"
            ] = result

    # -----------------------------------------------------
    # GRADE
    # -----------------------------------------------------

    current_grade = profile.get(
        "grade",
        0
    )

    grade_targets = sorted(
        {
            opportunity.get(
                "minimum_grade",
                0
            )
            for opportunity in open_opportunities
            if opportunity.get(
                "minimum_grade",
                0
            ) > current_grade
        }
    )

    for target in grade_targets:

        simulated_profile = profile.copy()

        simulated_profile[
            "grade"
        ] = target

        result = compare_profiles(
            profile,
            simulated_profile,
            open_opportunities
        )

        if (
            result["unlocked"] > 0
            or result["improved"] > 0
        ):

            improvements[
                f"Reach a {target}% academic average"
            ] = result

    # -----------------------------------------------------
    # WORK EXPERIENCE
    # -----------------------------------------------------

    current_work = profile.get(
        "work_experience_years",
        0
    )

    work_targets = sorted(
        {
            opportunity.get(
                "minimum_work_experience_years",
                0
            )
            for opportunity in open_opportunities
            if opportunity.get(
                "minimum_work_experience_years",
                0
            ) > current_work
        }
    )

    for target in work_targets:

        simulated_profile = profile.copy()

        simulated_profile[
            "work_experience_years"
        ] = target

        result = compare_profiles(
            profile,
            simulated_profile,
            open_opportunities
        )

        if (
            result["unlocked"] > 0
            or result["improved"] > 0
        ):

            improvements[
                f"Build {target} years of work experience"
            ] = result

    # -----------------------------------------------------
    # RANK RESULTS
    # -----------------------------------------------------

    ranked = sorted(
        improvements.items(),
        key=lambda item: (
            item[1]["unlocked"],
            item[1]["readiness_gain"],
            item[1]["score_gain"],
            item[1]["improved"]
        ),
        reverse=True
    )

    return ranked