export const formatDateTime = (value?: string | null) => {
  if (!value) return "-";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
};

export const formatPercent = (value?: number | null) => {
  if (value === undefined || value === null || Number.isNaN(value)) return "-";
  return `${Math.round(value)}%`;
};

export const formatRelativeHealth = (attendancePercent?: number | null) => {
  if (attendancePercent === undefined || attendancePercent === null || Number.isNaN(attendancePercent)) {
    return "Unknown";
  }
  if (attendancePercent < 60) return "Needs attention";
  if (attendancePercent < 80) return "Monitor";
  return "Stable";
};

export const preferEnglishText = (
  englishValue?: string | null,
  fallbackValue?: string | null,
  emptyValue = "-"
) => {
  if (typeof englishValue === "string" && englishValue.trim()) return englishValue.trim();
  if (typeof fallbackValue === "string" && fallbackValue.trim()) return fallbackValue.trim();
  return emptyValue;
};

export const courseDisplayTitle = (
  course?: { titleEn?: string | null; titleDe?: string | null } | null,
  emptyValue = "Untitled course"
) => preferEnglishText(course?.titleEn, course?.titleDe, emptyValue);

export const courseDisplayDescription = (
  course?: { descriptionEn?: string | null; descriptionDe?: string | null } | null,
  emptyValue = "No extended description is configured for this course yet."
) => preferEnglishText(course?.descriptionEn, course?.descriptionDe, emptyValue);

export const formatLifecycleLabel = (status?: string | null) => {
  if (!status) return "Unknown";
  return status
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
};

export const lifecycleBadgeTone = (status?: string | null) => {
  if (status === "published") return "good";
  if (status === "approved") return "link";
  if (status === "in_review") return "neutral";
  if (status === "archived") return "warn";
  return "warn";
};

export const sumValues = (items: number[]) => items.reduce((sum, value) => sum + value, 0);
