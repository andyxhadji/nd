/**
 * Generate HMAC-SHA256 signature for approval webhook.
 *
 * Uses Web Crypto API (available in secure contexts like localhost).
 */
export async function generateHmacSignature(
  secret: string,
  payload: string
): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(payload);
  const keyData = encoder.encode(secret);

  // Import secret as HMAC key
  const key = await crypto.subtle.importKey(
    'raw',
    keyData,
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  );

  // Generate signature
  const signature = await crypto.subtle.sign('HMAC', key, data);

  // Convert to hex string
  const hashArray = Array.from(new Uint8Array(signature));
  const hashHex = hashArray
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');

  return `sha256=${hashHex}`;
}
