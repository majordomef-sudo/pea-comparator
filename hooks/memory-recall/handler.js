import { readFileSync, existsSync, statSync } from "node:fs";
import { execSync } from "node:child_process";

const WS = "/home/ubuntu/.openclaw/workspace";
const CONTEXT_FILE = WS + "/state/memory_context.md";
const SCRIPT = WS + "/scripts/memory_context_recall.py";
const REFRESH_MS = 12 * 3600 * 1000; // regeneration si fichier plus vieux que 12h

const handler = async (event) => {
  if (event.type !== "agent" || event.action !== "bootstrap") return;
  const context = event.context;
  if (!context || !Array.isArray(context.bootstrapFiles)) return;
  try {
    // 1. Regenerer le contexte si absent ou trop vieux (silencieux, ~1s max)
    let needRefresh = true;
    try {
      needRefresh = Date.now() - statSync(CONTEXT_FILE).mtime > REFRESH_MS;
    } catch (_) {}
    if (needRefresh) {
      try {
        execSync("python3 " + SCRIPT + " --write", { timeout: 10000, stdio: "ignore" });
      } catch (e) {
        console.error("[memory-recall] regen failed: " + (e.message || String(e)));
      }
    }
    // 2. Injecter le fichier dans le bootstrap
    if (!existsSync(CONTEXT_FILE)) return;
    const content = readFileSync(CONTEXT_FILE, "utf8");
    if (!content || !content.trim()) return;
    const already = context.bootstrapFiles.some((f) => f.name === "MEMORY_CONTEXT.md");
    if (already) return;
    context.bootstrapFiles.push({
      name: "MEMORY_CONTEXT.md",
      path: CONTEXT_FILE,
      content,
      missing: false,
    });
  } catch (e) {
    console.error("[memory-recall] " + (e && e.message ? e.message : String(e)));
  }
};

export default handler;
