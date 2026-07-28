/**
 * Host-side settings for the local Ollama provider.
 *
 * Ollama runs natively for Metal acceleration. Agent containers reach it
 * through Docker's host gateway and bypass the OneCLI proxy for that host.
 */
import { registerProviderContainerConfig } from './provider-container-registry.js';

registerProviderContainerConfig('ollama', () => ({
  env: {
    OLLAMA_BASE_URL: process.env.OLLAMA_BASE_URL || 'http://host.docker.internal:11434',
    NO_PROXY: 'host.docker.internal,127.0.0.1,localhost',
    no_proxy: 'host.docker.internal,127.0.0.1,localhost',
  },
}));
