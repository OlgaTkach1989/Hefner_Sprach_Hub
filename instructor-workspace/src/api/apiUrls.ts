const DEFAULT_API_ROOT_URL = "http://localhost:1212/api";
const DEFAULT_ONLINE_API_BASE_URL = `${DEFAULT_API_ROOT_URL}/online`;

const trimTrailingSlashes = (value: string) => value.replace(/\/+$/, "");

const deriveApiRootUrl = (onlineApiBaseUrl: string) => {
  const normalized = trimTrailingSlashes(onlineApiBaseUrl);
  if (normalized.endsWith("/online")) {
    return normalized.slice(0, normalized.length - "/online".length);
  }
  return normalized;
};

export const onlineApiBaseUrl = trimTrailingSlashes(
  import.meta.env.VITE_ONLINE_API_BASE_URL ?? DEFAULT_ONLINE_API_BASE_URL
);

export const apiRootUrl = trimTrailingSlashes(
  deriveApiRootUrl(onlineApiBaseUrl) ?? DEFAULT_API_ROOT_URL
);
