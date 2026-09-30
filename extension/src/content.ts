interface ExtensionMessage {
  type: "GET_JOB_DATA";
}

interface JobPageData {
  url: string;
  title: string;
  description: string;
  hostname: string;
}

function getJobPageData(): JobPageData {
  const title =
    document.querySelector("h1")?.textContent?.trim() ||
    document.title ||
    "";

  const description =
    document.body?.innerText?.slice(0, 15000) || "";

  return {
    url: window.location.href,
    title,
    description,
    hostname: window.location.hostname,
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