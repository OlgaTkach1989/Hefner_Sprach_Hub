export const formatDateTime = (value?: string | null) => {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
};

export const toDatetimeLocalValue = (value?: string | null) => {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const offsetMinutes = date.getTimezoneOffset();
  return new Date(date.getTime() - offsetMinutes * 60_000).toISOString().slice(0, 16);
};

export const fromDatetimeLocalValue = (value: string) => {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const date = new Date(trimmed);
  if (Number.isNaN(date.getTime())) return null;
  return date.toISOString();
};

export const resolveApiErrorMessage = (error: unknown, fallback: string) => {
  const payload = error as {
    data?: { detail?: string; status?: string } | Record<string, string[] | string>;
  };

  const data = payload?.data;
  if (!data) return fallback;

  if ("detail" in data && typeof data.detail === "string" && data.detail) {
    return data.detail;
  }

  if ("status" in data && typeof data.status === "string" && data.status) {
    return data.status;
  }

  const entries = Object.values(data);
  for (const entry of entries) {
    if (Array.isArray(entry) && entry.length > 0 && typeof entry[0] === "string") {
      return entry[0];
    }
    if (typeof entry === "string" && entry) {
      return entry;
    }
  }

  return fallback;
};
