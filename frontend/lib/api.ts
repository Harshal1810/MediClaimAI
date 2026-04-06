function getApiBaseUrl(): string {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!base) {
    throw new Error(
      "NEXT_PUBLIC_API_BASE_URL is not set. Set it in `frontend/.env.local` (example: http://localhost:8000/api/v1) and restart `npm run dev`."
    );
  }
  return base.replace(/\/+$/, "");
}

async function safeFetch(input: RequestInfo | URL, init?: RequestInit) {
  try {
    return await fetch(input, init);
  } catch (e: any) {
    const msg = e?.message || String(e);
    throw new Error(`Network error (Failed to fetch). Check backend is running and CORS is allowed. Details: ${msg}`);
  }
}

export async function createClaim(payload: any) {
  const API_BASE_URL = getApiBaseUrl();
  const res = await safeFetch(`${API_BASE_URL}/claims`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`Failed to create claim (${res.status}). ${body}`);
  }
  return res.json();
}

export async function adjudicateClaim(claimContext: any) {
  const API_BASE_URL = getApiBaseUrl();
  const res = await safeFetch(`${API_BASE_URL}/adjudicate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ claim_context: claimContext }),
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`Failed to adjudicate claim (${res.status}). ${body}`);
  }
  return res.json();
}

export async function uploadDocument(claimId: string, file: File, documentType?: string) {
  const API_BASE_URL = getApiBaseUrl();
  const formData = new FormData();
  formData.append("file", file);
  const qs = documentType ? `?document_type=${encodeURIComponent(documentType)}` : "";
  const res = await safeFetch(`${API_BASE_URL}/claims/${claimId}/documents${qs}`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`Failed to upload document (${res.status}). ${body}`);
  }
  return res.json();
}

export async function adjudicateStoredClaim(claimId: string, llmConfig: any) {
  const API_BASE_URL = getApiBaseUrl();
  const res = await safeFetch(`${API_BASE_URL}/claims/${claimId}/adjudicate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(llmConfig),
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`Failed to adjudicate stored claim (${res.status}). ${body}`);
  }
  return res.json();
}

export async function getClaimDecision(claimId: string) {
  const API_BASE_URL = getApiBaseUrl();
  const res = await safeFetch(`${API_BASE_URL}/claims/${claimId}/decision`, { method: "GET" });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`Failed to fetch decision (${res.status}). ${body}`);
  }
  return res.json();
}

export async function processDocuments(claimId: string, payload: any) {
  const API_BASE_URL = getApiBaseUrl();
  const res = await safeFetch(`${API_BASE_URL}/claims/${claimId}/process-documents`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`Failed to process documents (${res.status}). ${body}`);
  }
  return res.json();
}
