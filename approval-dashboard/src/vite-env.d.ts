/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_AGENTFIELD_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
