import { FlaskConical, Info } from "lucide-react";

/** Shown on anything that is not real data yet, so nobody mistakes an example for a result. */
export function Sample({ what, title = "Sample data.", tone = "sample" }: { what: string; title?: string; tone?: "sample" | "note" }) {
  return (
    <p className={tone === "note" ? "sample note-tone" : "sample"} role="note">
      {tone === "note" ? <Info size={14} aria-hidden /> : <FlaskConical size={14} aria-hidden />} <strong>{title}</strong> {what}
    </p>
  );
}
