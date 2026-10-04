"""Manual live-source contact-pipeline run (uses real SearXNG/GitHub sources)."""

import asyncio

from people.contact_pipeline import ContactPipeline


async def main():
    pipeline = ContactPipeline(target_contacts=5, max_candidates=40)
    contacts = await pipeline.find_contacts(
        company="Microsoft",
        job_title="Software Engineer",
        location="Bangalore",
    )

    print("\nPUBLICLY EVIDENCED REFERRAL CONTACTS")
    print(f"Found {len(contacts)} contact(s).")
    for contact in contacts:
        print("\nName:", contact.name)
        print("Role:", contact.current_role)
        print("Company:", contact.current_company)
        print("Public work email:", contact.public_email)
        print("Mailbox verified:", contact.email_verified)
        print("LinkedIn:", contact.linkedin_url)
        for evidence in contact.contact_evidence:
            print("Evidence source:", evidence.source_url)


if __name__ == "__main__":
    asyncio.run(main())
