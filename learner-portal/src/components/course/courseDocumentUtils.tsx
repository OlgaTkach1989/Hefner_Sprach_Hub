import type { CourseLessonSectionItem } from "../../types";

const escapeHtml = (value: string) =>
  value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");

export const markdownToHtml = (body: string) => {
  const blocks = body
    .split(/\n\s*\n/g)
    .map((block) => block.trim())
    .filter(Boolean);

  return blocks
    .map((block) => {
      if (/^```/.test(block) && /```$/.test(block)) {
        const codeBody = block.replace(/^```[a-zA-Z0-9_-]*\n?/, "").replace(/\n?```$/, "");
        return `<pre><code>${escapeHtml(codeBody)}</code></pre>`;
      }

      if (/^#{1,6}\s/.test(block)) {
        const level = Math.min(block.match(/^#+/)?.[0].length ?? 1, 6);
        return `<h${level}>${escapeHtml(block.replace(/^#{1,6}\s+/, ""))}</h${level}>`;
      }

      const listRows = block
        .split("\n")
        .map((row) => row.trim())
        .filter(Boolean);

      if (listRows.length > 0 && listRows.every((row) => row.startsWith("- "))) {
        return `<ul>${listRows.map((row) => `<li>${escapeHtml(row.slice(2))}</li>`).join("")}</ul>`;
      }

      return `<p>${escapeHtml(block)}</p>`;
    })
    .join("");
};

export const renderLessonMarkdownBlocks = (body: string, baseClassName: string) => {
  const blocks = body
    .split(/\n\s*\n/g)
    .map((block) => block.trim())
    .filter(Boolean);

  return blocks.map((block, index) => {
    if (/^```/.test(block) && /```$/.test(block)) {
      const codeBody = block.replace(/^```[a-zA-Z0-9_-]*\n?/, "").replace(/\n?```$/, "");
      return (
        <pre key={`${block}_${index}`} className={`${baseClassName}__code`}>
          <code>{codeBody}</code>
        </pre>
      );
    }

    if (/^#{1,6}\s/.test(block)) {
      return (
        <h4 key={`${block}_${index}`} className={`${baseClassName}__heading`}>
          {block.replace(/^#{1,6}\s+/, "")}
        </h4>
      );
    }

    const listRows = block
      .split("\n")
      .map((row) => row.trim())
      .filter(Boolean);

    if (listRows.length > 0 && listRows.every((row) => row.startsWith("- "))) {
      return (
        <ul key={`${block}_${index}`} className={`${baseClassName}__list`}>
          {listRows.map((row) => (
            <li key={row}>{row.slice(2)}</li>
          ))}
        </ul>
      );
    }

    return (
      <p key={`${block}_${index}`} className={`${baseClassName}__copy`}>
        {block}
      </p>
    );
  });
};

export const resolveLessonItemLink = (item: CourseLessonSectionItem) =>
  item.externalUrl || item.fileUrl || item.trainingContent?.sourceUrl || "";

export const isPdfUrl = (value: string) => /\.pdf($|\?)/i.test(value);

export const isDirectVideoUrl = (value: string) => /\.(mp4|webm|ogg)($|\?)/i.test(value);

export const resolveVideoEmbedUrl = (value: string) => {
  if (!value) return "";
  const youtubeWatchMatch = value.match(/[?&]v=([^&]+)/);
  if (value.includes("youtube.com/watch") && youtubeWatchMatch?.[1]) {
    return `https://www.youtube.com/embed/${youtubeWatchMatch[1]}`;
  }
  const youtubeShortMatch = value.match(/youtu\.be\/([^?&]+)/);
  if (youtubeShortMatch?.[1]) {
    return `https://www.youtube.com/embed/${youtubeShortMatch[1]}`;
  }
  return value;
};

export const formatScheduleValue = (value?: string | null, options?: Intl.DateTimeFormatOptions) => {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "";
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    ...options,
  }).format(parsed);
};
