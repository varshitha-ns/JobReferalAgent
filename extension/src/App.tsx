

import { useState } from "react";
import "./popup.css";

// Job information extracted from the active Chrome tab
interface JobData {
  url: string;
  title: string;
  description: string;
  hostname: string;
  company?: string;
  location?: string;
}

// Response received from the content script
interface ContentResponse {
  success: boolean;
  data?: JobData;
  error?: string;
}

interface ContactEvidence {
  source_url: string;
  source_type: string;
  evidence: string;
}

interface ReferralContact {
  name: string;
  current_company?: string | null;
  current_role?: string | null;
  location?: string | null;
  location_verified?: boolean | null;
  contact_type: string;
  linkedin_url?: string | null;
  github_url?: string | null;
  public_email?: string | null;
  email_type?: "work" | "personal_candidate" | null;
  email_verified: boolean;
  email_domain_has_mx?: boolean | null;
  email_verification_method?: string | null;
  contact_evidence: ContactEvidence[];
  relevance_reasons: string[];
}

interface ReferralDraft {
  message: string;
  subject: string;
  candidate_name: string;
  candidate_email: string;
  candidate_linkedin: string;
}

function App() {
  const [job, setJob] = useState<JobData | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [stage, setStage] = useState<string>("idle");
  const [message, setMessage] = useState<string>("");
  const [error, setError] = useState<boolean>(false);
  const [contacts, setContacts] = useState<ReferralContact[]>([]);
  const [analysis, setAnalysis] = useState<Record<string, unknown> | null>(null);
  const [drafts, setDrafts] = useState<Record<string, ReferralDraft>>({});
  const [draftLoading, setDraftLoading] = useState<Record<string, boolean>>({});
  const [copiedDraft, setCopiedDraft] = useState<string | null>(null);

  const contactKey = (contact: ReferralContact): string =>
    `${contact.name}-${contact.public_email ?? contact.linkedin_url ?? contact.current_role ?? "contact"}`;

  const prepareDraft = async (contact: ReferralContact): Promise<void> => {
    if (!job) return;
    const key = contactKey(contact);
    setDraftLoading((current) => ({ ...current, [key]: true }));
    try {
      const response = await fetch("http://127.0.0.1:8000/referrals/draft", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          company: analysis?.company ?? job.company,
          job_title: analysis?.title ?? job.title,
          job_description: job.description,
          job_url: job.url,
          contact_name: contact.name,
          contact_role: contact.current_role,
        }),
      });
      if (!response.ok) throw new Error(`Draft request failed: ${response.status}`);
      const draft = await response.json() as ReferralDraft;
      setDrafts((current) => ({ ...current, [key]: draft }));
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Could not prepare referral draft.");
      setError(true);
    } finally {
      setDraftLoading((current) => ({ ...current, [key]: false }));
    }
  };

  const copyDraft = async (key: string, messageText: string): Promise<void> => {
    try {
      await navigator.clipboard.writeText(messageText);
      setCopiedDraft(key);
      window.setTimeout(() => setCopiedDraft(null), 2000);
    } catch {
      setMessage("Clipboard access failed. Select and copy the draft text instead.");
      setError(true);
    }
  };

  // Analyze the currently opened job page
  const analyzeJob = async (): Promise<void> => {
    setLoading(true);
    setStage("extracting");
    setMessage("");
    setError(false);
    setJob(null);
    setContacts([]);
    setAnalysis(null);

    try {
      // STEP 1: Get currently active Chrome tab
      const [tab] = await chrome.tabs.query({
        active: true,
        currentWindow: true,
      });

      if (!tab || !tab.id) {
        throw new Error("Unable to identify the active tab.");
      }

      // STEP 2: Request job information from content script
      const response: ContentResponse =
        await chrome.tabs.sendMessage(tab.id, {
          type: "GET_JOB_DATA",
        });

      if (!response || !response.success || !response.data) {
        throw new Error(
          response?.error || "Unable to extract job information."
        );
      }

      const extractedJob: JobData = response.data;

      // STEP 3: Update extension UI
      setJob(extractedJob);
      setStage("analyzing");
      setMessage("Job details extracted. Preparing contact search...");

      // STEP 4: Send extracted job to FastAPI backend
      const backendResponse = await fetch(
        "http://127.0.0.1:8000/jobs/analyze",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(extractedJob),
        }
      );

      if (!backendResponse.ok) {
        throw new Error(
          `Backend request failed: ${backendResponse.status}`
        );
      }

      // STEP 5: Read backend response
      const result = await backendResponse.json();

      console.log("Backend Response:", result);

      if (result.success) {
        const profile = result.job as Record<string, unknown> | undefined;
        setAnalysis(profile ?? null);

        if (!profile?.company || !profile?.title) {
          setMessage("Job analyzed, but company or role was not extracted. Contact search was skipped.");
          setError(false);
          return;
        }

        setStage("searching");
        setMessage("Searching public profiles for relevant people...");
        const contactsResponse = await fetch("http://127.0.0.1:8000/contacts/find", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            company: profile.company,
            job_title: profile.title,
            location: profile.location ?? null,
            limit: 5,
          }),
        });
        if (!contactsResponse.ok) {
          throw new Error(`Contact search failed: ${contactsResponse.status}`);
        }
        const contactResult = await contactsResponse.json();
        const foundContacts = (contactResult.contacts ?? []) as ReferralContact[];
        setContacts(foundContacts);
        const emailCount = foundContacts.filter((contact) => contact.public_email).length;
        setMessage(
          foundContacts.length
            ? `Found ${foundContacts.length} relevant person/people; ${emailCount} public email lead(s). Use LinkedIn where no email is listed.`
            : contactResult.search_available === false
              ? `Public search is unavailable: ${contactResult.search_error ?? "check SearXNG and its configured search engines"}.`
              : "No relevant people were found. Try a broader job title or location."
        );
        setError(false);
      } else {
        throw new Error(
          result.message || "Backend could not analyze the job."
        );
      }
    } catch (err: unknown) {
      console.error("Job Analysis Error:", err);

      const errorMessage =
        err instanceof Error
          ? err.message
          : "An unexpected error occurred.";

      setMessage(errorMessage);
      setError(true);
    } finally {
      setStage("idle");
      setLoading(false);
    }
  };

  return (
    <div className="app">
      {/* Header */}
      <header>
        <h1>Job Referral Agent</h1>

        <p className="subtitle">
          Your personal AI-powered job assistant
        </p>
      </header>

      {/* Analyze Button */}
      <button
        type="button"
        onClick={analyzeJob}
        disabled={loading}
      >
        {loading
          ? stage === "searching"
            ? "Finding Contacts..."
            : stage === "extracting"
              ? "Reading Job..."
              : "Preparing Search..."
          : "Analyze Current Job"}
      </button>

      {/* Extracted Job Information */}
      {job && (
        <div className="job-card">
          <h2>Extracted Job</h2>

          <p>
            <strong>Title:</strong> {job.title}
          </p>

          <p>
            <strong>Website:</strong> {job.hostname}
          </p>
          {job.company && <p><strong>Company:</strong> {job.company}</p>}
          {job.location && <p><strong>Location:</strong> {job.location}</p>}

          <p>
            <strong>Job URL:</strong>{" "}
            <a
              href={job.url}
              target="_blank"
              rel="noopener noreferrer"
            >
              View Job
            </a>
          </p>

          <p>
            <strong>Description:</strong>
          </p>

          <p>
            {job.description.length > 250
              ? `${job.description.slice(0, 250)}...`
              : job.description}
          </p>
        </div>
      )}

      {analysis && (
        <div className="job-card">
          <h2>Analyzed Role</h2>
          <p><strong>Company:</strong> {String(analysis.company ?? "Not identified")}</p>
          <p><strong>Role:</strong> {String(analysis.title ?? "Not identified")}</p>
          {Array.isArray(analysis.required_skills) && (
            <p><strong>Skills:</strong> {(analysis.required_skills as string[]).join(", ")}</p>
          )}
        </div>
      )}

      {contacts.length > 0 && (
        <section className="contacts-card">
          <h2>People to Contact</h2>
          <p className="email-note">
            Contacts are ranked by likely referral usefulness from their public job titles. Check their profile and team before reaching out. Emails require public source evidence; no mailbox is verified.
          </p>
          {contacts.map((contact) => (
            <article className="contact-item" key={`${contact.name}-${contact.public_email}`}>
              <h3>{contact.name}</h3>
              <p>{contact.current_role ?? "Role not identified"} | {contact.current_company ?? ""}</p>
              <p className="email-note">Referral route: {contact.contact_type.replaceAll("_", " ")}</p>
              {contact.location && <p className="email-note">Profile location: {contact.location}{contact.location_verified === true ? " (matched)" : contact.location_verified === false ? " (different from job location)" : " (not confirmed)"}</p>}
              {contact.public_email ? (
                <p>
                  <strong>{contact.email_type === "personal_candidate" ? "Public personal email lead:" : "Public work email:"}</strong>{" "}
                  <a href={`mailto:${contact.public_email}`}>{contact.public_email}</a>
                </p>
              ) : (
                <p className="email-note">No suitable public email found. Contact through LinkedIn.</p>
              )}
              {contact.email_type !== "personal_candidate" && contact.public_email && (
                <p className="email-note">
                  Company mail routing: {contact.email_domain_has_mx === true ? "MX record found" : contact.email_domain_has_mx === false ? "No MX record found" : "not checked"}. This does not verify this mailbox.
                </p>
              )}
              <div className="contact-links">
                {contact.linkedin_url && <a href={contact.linkedin_url} target="_blank" rel="noopener noreferrer">LinkedIn profile</a>}
                {contact.github_url && <a href={contact.github_url} target="_blank" rel="noopener noreferrer">GitHub profile</a>}
                {contact.contact_evidence.map((evidence) => (
                  <a key={evidence.source_url} href={evidence.source_url} target="_blank" rel="noopener noreferrer">
                    {contact.public_email ? "Email source" : "Profile evidence"}: {evidence.source_type}
                  </a>
                ))}
              </div>
              {drafts[contactKey(contact)] ? (
                <div className="referral-draft">
                  <label htmlFor={`draft-${contactKey(contact)}`}>Personalized referral message</label>
                  <textarea
                    id={`draft-${contactKey(contact)}`}
                    rows={8}
                    value={drafts[contactKey(contact)].message}
                    onChange={(event) => setDrafts((current) => ({
                      ...current,
                      [contactKey(contact)]: { ...current[contactKey(contact)], message: event.target.value },
                    }))}
                  />
                  <div className="contact-links">
                    <button type="button" onClick={() => void copyDraft(contactKey(contact), drafts[contactKey(contact)].message)}>
                      {copiedDraft === contactKey(contact) ? "Copied" : "Copy LinkedIn message"}
                    </button>
                    {contact.public_email && (
                      <a href={`mailto:${encodeURIComponent(contact.public_email)}?subject=${encodeURIComponent(drafts[contactKey(contact)].subject)}&body=${encodeURIComponent(drafts[contactKey(contact)].message)}`}>
                        Open email draft
                      </a>
                    )}
                    {contact.linkedin_url && <a href={contact.linkedin_url} target="_blank" rel="noopener noreferrer">Open LinkedIn to message</a>}
                  </div>
                  {contact.public_email && <p className="email-note">This opens a draft in your configured email app; review it before sending.</p>}
                </div>
              ) : (
                <button type="button" className="prepare-draft" disabled={draftLoading[contactKey(contact)]} onClick={() => void prepareDraft(contact)}>
                  {draftLoading[contactKey(contact)] ? "Preparing message..." : "Prepare referral message"}
                </button>
              )}
            </article>
          ))}
        </section>
      )}

      {/* Status Message */}
      {message && (
        <div
          className="message"
          style={{
            color: error ? "#dc2626" : "#16a34a",
            marginTop: "15px",
          }}
        >
          {message}
        </div>
      )}

      {/* Footer */}
      <footer
        style={{
          marginTop: "20px",
          textAlign: "center",
          fontSize: "11px",
          color: "#888",
        }}
      >
        Job Referral Agent v0.1.0
      </footer>
    </div>
  );
}

export default App;
