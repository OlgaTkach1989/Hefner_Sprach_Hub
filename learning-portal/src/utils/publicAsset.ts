const ensureTrailingSlash = (value: string) => (value.endsWith("/") ? value : `${value}/`);

const baseUrl = ensureTrailingSlash(import.meta.env.BASE_URL ?? "/");

export const publicAsset = (assetPath: string) => {
  const normalizedPath = assetPath.replace(/^\/+/, "");
  return `${baseUrl}${normalizedPath}`;
};
