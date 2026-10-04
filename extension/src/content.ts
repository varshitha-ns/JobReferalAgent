interface ExtensionMessage {
  type: "GET_JOB_DATA";
}

interface JobPageData {
  url: string;
  title: string;
  description: string;
  hostname: string;
  company?: string;
  location?: string;
}

type JsonObject = Record<string, unknown>;

function asObject(value: unknown): JsonObject | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? value as JsonObject
    : null;
}

function textValue(value: unknown): string | undefined {
  if (typeof value === "string" && value.trim()) return value.trim();
  const object = asObject(value);
  if (!object) return undefined;
  if (typeof object.name === "string" && object.name.trim()) return object.name.trim();
  return undefined;
}

function jobPostingMetadata(): { company?: string; location?: string } {
  for (const script of document.querySelectorAll<HTMLScriptElement>('script[type="application/ld+json"]')) {
    try {
      const parsed: unknown = JSON.parse(script.textContent || "null");
      const queue: unknown[] = Array.isArray(parsed) ? [...parsed] : [parsed];
      while (queue.length) {
        const item = queue.shift();
        const object = asObject(item);
        if (!object) continue;
        if (Array.isArray(object["@graph"])) queue.push(...object["@graph"]);
        const type = object["@type"];
        const isPosting = type === "JobPosting" || (Array.isArray(type) && type.includes("JobPosting"));
        if (!isPosting) continue;

        const company = textValue(object.hiringOrganization);
        const jobLocation = Array.isArray(object.jobLocation) ? object.jobLocation[0] : object.jobLocation;
        const address = asObject(asObject(jobLocation)?.address);
        const locationParts = [address?.addressLocality, address?.addressRegion, address?.addressCountry]
          .map((part) => typeof part === "string" ? part.trim() : "")
          .filter(Boolean);
        return { company, location: locationParts.length ? locationParts.join(", ") : undefined };
      }
    } catch {
      // Ignore malformed JSON-LD and keep trying the page's semantic markup.
    }
  }
  return {};
}

function companyFromPage(title: string, lines: string[]): string | undefined {
  const clean = (value: string): string => value.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
  const target = clean(title);
  const index = lines.findIndex((line) => clean(line) === target);
  if (index < 0) return undefined;
  const excluded = /^(job description|description|full[- ]time|part[- ]time|contract|on[- ]site|hybrid|remote|technology|india(?:, india)?|bengaluru(?:,.*)?|bangalore(?:,.*)?)$/i;
  for (const line of lines.slice(index + 1, index + 5)) {
    if (line.length > 100 || excluded.test(line)) continue;
    if (/\b(months? ago|until \d|full[- ]time|on[- ]site)\b/i.test(line)) continue;
    if ((line.match(/[A-Za-z]{2,}/g) || []).length <= 8) return line;
  }
  return undefined;
}

function locationFromUrl(url: string): string | undefined {
  const path = new URL(url).pathname.toLowerCase().replace(/_/g, "-");
  const cities: Record<string, string> = {
    bengaluru: "Bengaluru, India", bangalore: "Bengaluru, India",
    mumbai: "Mumbai, India", hyderabad: "Hyderabad, India",
    chennai: "Chennai, India", pune: "Pune, India",
    gurugram: "Gurugram, India", gurgaon: "Gurugram, India",
    noida: "Noida, India", "new-delhi": "New Delhi, India",
    kolkata: "Kolkata, India", ahmedabad: "Ahmedabad, India",
    kochi: "Kochi, India", coimbatore: "Coimbatore, India",
  };
  return Object.entries(cities).find(([slug]) => new RegExp(`(?:^|[-/])${slug}(?:[-/]|$)`).test(path))?.[1];
}

function getJobPageData(): JobPageData {
  const title =
    document.querySelector("h1")?.textContent?.trim() ||
    document.title ||
    "";

  const pageText = document.body?.innerText || "";
  const description = pageText.slice(0, 15000);
  const lines = pageText.split(/\n+/).map((line) => line.trim()).filter(Boolean);
  const metadata = jobPostingMetadata();
  const company = metadata.company
    || document.querySelector('[itemprop="hiringOrganization"], [data-testid*="company-name"], [class*="company-name"]')?.textContent?.trim()
    || companyFromPage(title, lines);
  const pageLocation = document.querySelector('[itemprop="addressLocality"], [data-testid*="location"]')?.textContent?.trim();
  const location = metadata.location || locationFromUrl(window.location.href) || pageLocation;

  return {
    url: window.location.href,
    title,
    description,
    hostname: window.location.hostname,
    company,
    location,
  };
}

chrome.runtime.onMessage.addListener(
  (
    message: ExtensionMessage,
    _sender: chrome.runtime.MessageSender,
    sendResponse: (
      response: {
        success: boolean;
        data?: JobPageData;
        error?: string;
      }
    ) => void
  ) => {
    if (message.type === "GET_JOB_DATA") {
      const data = getJobPageData();

      sendResponse({
        success: true,
        data,
      });
    }

    return true;
  }
);
