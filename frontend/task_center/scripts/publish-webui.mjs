import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, "../../..");
const distDir = path.resolve(__dirname, "../dist");
const runtimeWebuiDir = process.env.SOCIAL_CRAWLER_WEBUI_DIR
  ? path.resolve(process.env.SOCIAL_CRAWLER_WEBUI_DIR)
  : path.resolve(projectRoot, "runtime", "webui");
const legacyWebuiDir = path.resolve(projectRoot, "api", "webui");

function copyDir(src, dst) {
  fs.mkdirSync(dst, { recursive: true });
  fs.cpSync(src, dst, { recursive: true, force: true });
}

if (!fs.existsSync(distDir)) {
  console.error(`[publish-webui] dist not found: ${distDir}`);
  process.exit(1);
}

copyDir(distDir, runtimeWebuiDir);
copyDir(distDir, legacyWebuiDir);

console.log(`[publish-webui] runtime webui: ${runtimeWebuiDir}`);
console.log(`[publish-webui] legacy webui:  ${legacyWebuiDir}`);
