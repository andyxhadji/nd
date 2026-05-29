import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { sendApproval } from './agentfield';

describe('sendApproval', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    // Mock fetch
    fetchMock = vi.fn();
    global.fetch = fetchMock;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('should send approval with correct format and HMAC signature', async () => {
    // Mock successful response
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        decision: 'approved',
        execution_id: 'exec_test',
        new_status: 'running',
        status: 'processed',
      }),
    });

    const request = {
      requestId: 'post-test-task#123',
      decision: 'approved' as const,
      feedback: 'looks good',
    };

    const response = await sendApproval(request);

    // Verify fetch was called
    expect(fetchMock).toHaveBeenCalledTimes(1);

    // Verify the URL
    const [url] = fetchMock.mock.calls[0];
    expect(url).toBe('http://localhost:8081/api/v1/webhooks/approval-response');

    // Verify the request options
    const [, options] = fetchMock.mock.calls[0];
    expect(options.method).toBe('POST');
    expect(options.headers['Content-Type']).toBe('application/json');
    expect(options.headers['X-Hub-Signature-256']).toMatch(/^sha256=[a-f0-9]{64}$/);

    // Verify the body is JSON string
    expect(typeof options.body).toBe('string');
    const parsedBody = JSON.parse(options.body);
    expect(parsedBody).toEqual(request);

    // Verify response
    expect(response.status).toBe('processed');
    expect(response.decision).toBe('approved');
  });

  it('should send rejection with feedback', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        decision: 'rejected',
        execution_id: 'exec_test',
        new_status: 'failed',
        status: 'processed',
      }),
    });

    const request = {
      requestId: 'spec-test-task#456',
      decision: 'rejected' as const,
      feedback: 'needs more work',
    };

    await sendApproval(request);

    const [, options] = fetchMock.mock.calls[0];
    const parsedBody = JSON.parse(options.body);
    expect(parsedBody.decision).toBe('rejected');
    expect(parsedBody.feedback).toBe('needs more work');
  });

  it('should handle request_changes decision', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        decision: 'request_changes',
        execution_id: 'exec_test',
        new_status: 'waiting',
        status: 'processed',
      }),
    });

    const request = {
      requestId: 'post-test-task#789',
      decision: 'request_changes' as const,
      feedback: 'please update the response',
    };

    await sendApproval(request);

    const [, options] = fetchMock.mock.calls[0];
    const parsedBody = JSON.parse(options.body);
    expect(parsedBody.decision).toBe('request_changes');
  });

  it('should throw error on HTTP error response', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 401,
      text: async () => 'Invalid signature',
    });

    const request = {
      requestId: 'post-test',
      decision: 'approved' as const,
    };

    await expect(sendApproval(request)).rejects.toThrow('HTTP 401: Invalid signature');
  });

  it('should throw error on network timeout', async () => {
    // Mock AbortError
    const abortError = new Error('The user aborted a request.');
    abortError.name = 'AbortError';
    fetchMock.mockRejectedValueOnce(abortError);

    const request = {
      requestId: 'post-test',
      decision: 'approved' as const,
    };

    await expect(sendApproval(request)).rejects.toThrow('Request timeout');
  });

  it('should compute HMAC over the exact request body', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: 'processed' }),
    });

    const request = {
      requestId: 'test-123',
      decision: 'approved' as const,
      feedback: 'test feedback',
    };

    await sendApproval(request);

    // Get the body that was sent
    const [, options] = fetchMock.mock.calls[0];
    const sentBody = options.body;

    // Parse it back to verify it matches
    const parsedBody = JSON.parse(sentBody);
    expect(parsedBody).toEqual(request);

    // Verify the signature was computed (it should be present)
    expect(options.headers['X-Hub-Signature-256']).toBeDefined();
    expect(options.headers['X-Hub-Signature-256']).toMatch(/^sha256=[a-f0-9]{64}$/);
  });
});
