import { AgentFieldRun, ApprovalRequest, ApprovalResponse } from './types';
import { generateHmacSignature } from './hmac';

export const AGENTFIELD_URL = 'http://localhost:8081';
export const WEBHOOK_SECRET = 'nd-approval-secret-dev';
export const POLL_INTERVAL_MS = 5000;
export const REQUEST_TIMEOUT_MS = 10000;

/**
 * Fetch all runs with status=waiting from AgentField.
 */
export async function fetchWaitingRuns(): Promise<AgentFieldRun[]> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(
      `${AGENTFIELD_URL}/api/v1/runs?status=waiting`,
      { signal: controller.signal }
    );

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();
    return Array.isArray(data) ? data : [];
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      throw new Error('Request timeout');
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}

/**
 * Fetch detailed run information including execution trace.
 */
export async function fetchRunDetails(runId: string): Promise<AgentFieldRun> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(
      `${AGENTFIELD_URL}/api/v1/runs/${runId}`,
      { signal: controller.signal }
    );

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      throw new Error('Request timeout');
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}

/**
 * Send approval decision to AgentField with HMAC signature.
 */
export async function sendApproval(
  request: ApprovalRequest
): Promise<ApprovalResponse> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const signature = await generateHmacSignature(WEBHOOK_SECRET, request);

    const response = await fetch(
      `${AGENTFIELD_URL}/api/v1/webhooks/approval-response`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Hub-Signature-256': signature,
        },
        body: JSON.stringify(request),
        signal: controller.signal,
      }
    );

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`HTTP ${response.status}: ${errorText}`);
    }

    return await response.json();
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      throw new Error('Request timeout');
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}
