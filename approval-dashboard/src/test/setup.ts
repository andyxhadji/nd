// Vitest setup file
import { expect, afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

// Cleanup after each test
afterEach(() => {
  cleanup();
});

// Mock Web Crypto API for HMAC signature generation
if (!global.crypto) {
  Object.defineProperty(global, 'crypto', {
    value: {
      subtle: {
        importKey: async () => ({}),
        sign: async () => new Uint8Array(32).fill(0),
      },
    },
  });
}
