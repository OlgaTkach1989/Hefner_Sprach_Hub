const LEGACY_AUTH_KEYS = ["online_access_token", "online_refresh_token"] as const

const removeLegacyAuthKeys = () => {
  if (typeof window === "undefined") return
  for (const key of LEGACY_AUTH_KEYS) {
    try {
      window.localStorage.removeItem(key)
      window.sessionStorage.removeItem(key)
    } catch {
      // Ignore storage failures in hardened or privacy-restricted browsers.
    }
  }
}

const readCookie = (name: string): string => {
  if (typeof document === "undefined") return ""
  const prefix = `${encodeURIComponent(name)}=`
  const cookie = document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(prefix))

  return cookie ? decodeURIComponent(cookie.slice(prefix.length)) : ""
}

export const clearTokens = () => {
  removeLegacyAuthKeys()
}

export const storeTokens = (_access: string, _refresh: string) => {
  removeLegacyAuthKeys()
}

export const getAccessToken = () => ""

export const getRefreshToken = () => ""

export const getCsrfToken = () => readCookie("csrftoken")

removeLegacyAuthKeys()
