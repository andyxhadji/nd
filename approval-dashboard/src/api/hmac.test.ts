import { generateHmacSignature } from './hmac';

// Manual test - run in browser console
export async function testHmacSignature() {
  const secret = 'nd-approval-secret-dev';
  const payload = {
    requestId: 'post-537b',
    decision: 'approved',
  };

  const signature = await generateHmacSignature(secret, JSON.stringify(payload));
  console.log('Signature:', signature);

  // Expected format: sha256={64 hex chars}
  const isValid = /^sha256=[a-f0-9]{64}$/.test(signature);
  console.log('Valid format:', isValid);

  return isValid;
}
