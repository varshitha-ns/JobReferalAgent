

import { useState } from "react";
import "./popup.css";

// Job information extracted from the active Chrome tab
interface JobData {
  url: string;
  title: string;
  description: string;
  hostname: string;
}

// Response received from the content script
interface ContentResponse {
  success: boolean;
  data?: JobData;
  error?: string;
}

function App() {
  const [job, setJob] = useState<JobData | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [message, setMessage] = useState<string>("");
  const [error, setError] = useState<boolean>(false);

  // Analyze the currently opened job page
  const analyzeJob = async (): Promise<void> => {
    setLoading(true);
    setMessage("");
    setError(false);
    setJob(null);

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
        setMessage("Job analyzed successfully!");
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
        {loading ? "Analyzing Job..." : "Analyze Current Job"}
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