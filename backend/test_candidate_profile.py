from candidate.candidate_data import candidate_profile


print("========================================")
print("CANDIDATE PROFILE")
print("========================================")

print("Name:", candidate_profile.name)
print("Email:", candidate_profile.email)
print("Education:", candidate_profile.education[0].institution)
print("CGPA:", candidate_profile.education[0].cgpa)

print("\nExperience:")
for experience in candidate_profile.experience:
    print("-", experience.company, "|", experience.role)

print("\nProjects:")
for project in candidate_profile.projects:
    print("-", project.name)

print("\nSkills:")
print("Programming:", candidate_profile.programming_languages)
print("Web/Backend:", candidate_profile.web_backend)
print("ML:", candidate_profile.machine_learning)
print("GenAI:", candidate_profile.generative_ai)

print("\nCoding Problems:", candidate_profile.coding_problems_solved)