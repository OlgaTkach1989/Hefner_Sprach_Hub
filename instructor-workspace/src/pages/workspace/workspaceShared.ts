export const formatDateTime = (value?: string | null) => {
  if (!value) return "-";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString("en-GB", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
};

export const formatPercent = (value?: number | null) => {
  if (value === undefined || value === null || Number.isNaN(value)) return "-";
  return `${Math.round(value)}%`;
};

export const resolveApiErrorMessage = (error: unknown, fallback: string) => {
  const data = (error as { data?: { detail?: string; subject?: string[]; message?: string[] } })?.data;
  if (data?.detail) return data.detail;
  if (data?.subject?.[0]) return data.subject[0];
  if (data?.message?.[0]) return data.message[0];
  return fallback;
};
