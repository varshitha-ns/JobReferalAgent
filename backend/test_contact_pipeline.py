import asyncio

from people.contact_pipeline import ContactPipeline


async def main():

    pipeline = ContactPipeline(
        target_contacts=5,
        max_candidates=40,
    )

    contacts = await pipeline.find_contacts(
        company="Microsoft",
        job_title="Software Engineer",
        location="Bangalore",
    )

    print()
    print("=" * 70)
    print("REFERRAL CONTACTS AND PUBLIC EMAIL LEADS")
    print("=" * 70)

    email_count = sum(bool(contact.public_email) for contact in contacts)
    print(f"\nRelevant contacts found: {len(contacts)} / 5")
    print(f"Public email leads found: {email_count} / 5")

    for index, contact in enumerate(
        contacts,
        start=1,
    ):

        print()
        print("-" * 70)

        print(f"CONTACT #{index}")
        print("Name:", contact.name)
        print("Role:", contact.current_role)
        print(
            "Contact type:",
            contact.contact_type.value,
        )
        print(
            "LinkedIn:",
            contact.linkedin_url,
        )
        print(
            "Email:",
            contact.public_email,
        )
        print("Email type:", contact.email_type or "none")
        print(
            "Status:",
            contact.verification_status.value,
        )

        print("\nReasons:")

        for reason in contact.relevance_reasons:
            print(" -", reason)

        print("\nEvidence:")

        for evidence in contact.contact_evidence:
            print(
                f" - [{evidence.source_type}] "
                f"{evidence.source_url}"
            )


if __name__ == "__main__":
    asyncio.run(main())
