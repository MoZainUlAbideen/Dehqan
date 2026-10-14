/** "Tomato___Late_blight" -> { crop: "Tomato", condition: "Late blight" } */
export function prettyLabel(raw: string): { crop: string; condition: string } {
  const [crop, ...rest] = raw.split("___");
  const clean = (s: string) =>
    s
      .replace(/_+$/g, "")
      .replace(/_/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  const condition = rest.join(" ") ? clean(rest.join(" ")) : "";
  return { crop: clean(crop).replace(/\s*\(.*\)$/, ""), condition: condition.charAt(0).toUpperCase() + condition.slice(1) };
}
