import { AgentFieldRun, ApprovalRequest, ApprovalResponse } from './types';
import { generateHmacSignature } from './hmac';

export const AGENTFIELD_URL = 'http://localhost:8081';
export const WEBHOOK_SECRET = 'nd-approval-secret-dev';
export const POLL_INTERVAL_MS = 5000;
export const REQUEST_TIMEOUT_MS = 10000;

/**
 * Fetch all runs with status=waiting or paused from AgentField.
 * Uses the /api/ui/v2/workflow-runs endpoint.
 */
export async function fetchWaitingRuns(): Promise<AgentFieldRun[]> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(
      `${AGENTFIELD_URL}/api/ui/v2/workflow-runs?status=paused&page=1&page_size=50`,
      { signal: controller.signal }
    );

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();
    // The API returns { workflows: [...], total_count, page, page_size, has_more }
    return Array.isArray(data.workflows) ? data.workflows : Array.isArray(data.runs) ? data.runs : [];
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
 * Uses the workflow_id to get DAG details.
 */
export async function fetchRunDetails(runId: string): Promise<AgentFieldRun> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(
      `${AGENTFIELD_URL}/api/ui/v1/workflows/${runId}/dag`,
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
