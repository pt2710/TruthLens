const LOCAL_DEV_API_BASE = 'http://127.0.0.1:8000';
const HOSTED_BETA_API_BASE = 'https://truthlens-beta-api.onrender.com';
function normalizeApiBase(rawValue: string): string {
  return rawValue.replace(/\/+$/, '');
}

export function resolveTruthLensApiBase(): string {
  const configuredValue = (import.meta.env.VITE_TRUTHLENS_API_BASE as string | undefined)?.trim();
  if (configuredValue) {
    return normalizeApiBase(configuredValue);
  }
  if (import.meta.env.DEV) {
    return LOCAL_DEV_API_BASE;
  }
  return HOSTED_BETA_API_BASE;
}

export function buildTruthLensApiUrl(path: string): string {
  const apiBase = resolveTruthLensApiBase();
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${apiBase}${normalizedPath}`;
}

export { HOSTED_BETA_API_BASE, LOCAL_DEV_API_BASE };
