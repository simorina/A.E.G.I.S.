/**
 * Utility to resolve API Base URL targeting FastAPI server on port 8000
 */
export const getApiBaseUrl = (): string => {
  if (typeof window !== 'undefined') {
    // If running on Vite dev server (e.g. port 3000) or file protocol, target http://localhost:8000
    if (window.location.port !== '8000' || window.location.protocol === 'file:') {
      return 'http://localhost:8000';
    }
  }
  return '';
};

export const apiFetch = async (endpoint: string, options?: RequestInit): Promise<Response> => {
  const baseUrl = getApiBaseUrl();
  const url = `${baseUrl}${endpoint}`;
  try {
    return await fetch(url, options);
  } catch (err) {
    // Retry with explicit localhost:8000 if relative fetch fails
    if (!baseUrl) {
      return await fetch(`http://localhost:8000${endpoint}`, options);
    }
    throw err;
  }
};
