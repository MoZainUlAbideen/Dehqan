// Copies ../evals/*.json into data/evals/ so the site always shows the repo's latest eval results.
// If ../evals is not there (e.g. a deploy rooted at frontend/), keep the committed copies.
import { copyFileSync, existsSync, mkdirSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const src = join(here, "..", "..", "evals");
const dest = join(here, "..", "data", "evals");

if (!existsSync(src)) {
  console.log("sync-evals: ../evals not found, keeping committed copies");
} else {
  mkdirSync(dest, { recursive: true });
  const files = readdirSync(src).filter((f) => f.endsWith(".json"));
  files.forEach((f) => copyFileSync(join(src, f), join(dest, f)));
  console.log(`sync-evals: copied ${files.length} eval files`);
}
