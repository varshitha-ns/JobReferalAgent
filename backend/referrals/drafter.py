from __future__ import annotations

import re

from candidate.candidate_data import candidate_profile


def _matching_skills(job_text: str) -> list[str]:
    profile = candidate_profile
    available = (
        profile.programming_languages
        + profile.web_backend
        + profile.machine_learning
        + profile.deep_learning
        + profile.generative_ai
        + profile.databases_tools_cloud
        + profile.cloud_devops
    )
    normalized = job_text.casefold()
    matches = []
    for skill in sorted(set(available), key=len, reverse=True):
        key = skill.casefold().strip()
        if len(key) < 3 or key in {item.casefold() for item in matches}:
            continue
        if re.search(rf"(?<![a-z0-9]){re.escape(key)}(?![a-z0-9])", normalized):
            matches.append(skill)
    return matches[:4]


def create_referral_draft(
    *,
    company: str,
    job_title: str,
    job_description: str,
    job_url: str,
    contact_name: str,
    contact_role: str | None = None,
) -> dict[str, str | None]:
    candidate = candidate_profile
    education = candidate.education[0]
    skills = _matching_skills(f"{job_title}\n{job_description}")

    opening = (
        f"Dear {contact_name},\n\n"
        f"I hope you are doing well. I am writing to express my interest in the "
        f"{job_title} position at {company}."
    )
    background = (
        f" I am a {education.graduation_year} {education.degree} graduate "
        f"specializing in {education.specialization} from {education.institution}."
    )
    requirements = (
        f" My background aligns with the role requirements in {', '.join(skills)}."
        if skills
        else " My background is in software development and artificial intelligence."
    )
    role_note = (
        f" I saw that you work as {contact_role} at {company} and hoped you might "
        "be able to advise me."
        if contact_role
        else " I hoped you might be able to advise me."
    )
    request = (
        " If you believe my qualifications could be a match, would you be willing "
        "to refer me for consideration? I would be glad to share my resume and "
        "any additional information."
    )
    job_link = f"\n\nJob posting: {job_url}" if job_url else ""
    signature = (
        f"\n\nThank you for your time and consideration.\n\nSincerely,\n"
        f"{candidate.name}\nEmail: {candidate.email}\nLinkedIn: {candidate.linkedin}"
    )
    message = opening + background + requirements + role_note + request + job_link + signature

    return {
        "message": message,
        "subject": f"Referral request: {job_title} at {company}",
        "candidate_name": candidate.name,
        "candidate_email": candidate.email,
        "candidate_linkedin": candidate.linkedin,
    }
