// Joins the guided intake fields (plus an optional automated screenshot
// description) into the single alert_text string the backend expects.
// Keeps the investigation schema untouched -- this is pure client-side
// formatting, not a new data shape.
export function composeAlertText({ tryingTo, instead, page, notes, screenshotDescription }) {
  const reporterParts = [];
  if (tryingTo.trim()) reporterParts.push(`What they were trying to do: ${tryingTo.trim()}`);
  if (instead.trim()) reporterParts.push(`What happened instead: ${instead.trim()}`);
  if (page.trim()) reporterParts.push(`Page or feature: ${page.trim()}`);
  if (notes.trim()) reporterParts.push(notes.trim());

  const parts = [];
  if (reporterParts.length > 0) {
    parts.push(reporterParts.join("\n"));
  } else if (screenshotDescription) {
    parts.push("No reporter description provided; see screenshot analysis below.");
  } else {
    parts.push("Manual investigation triggered from UI.");
  }
  if (screenshotDescription) {
    parts.push(`Screenshot analysis (automated): ${screenshotDescription}`);
  }
  return parts.join("\n\n");
}
