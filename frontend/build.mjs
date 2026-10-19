// Builds the PWA into dist/: esbuild bundles React, Tailwind v4 compiles the CSS.
// Usage: node build.mjs            (production build)
//        node build.mjs --watch    (rebuild on change)
// If dependencies aren't installed locally, set EXTRA_NODE_MODULES to a folder that has them.
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const extra = process.env.EXTRA_NODE_MODULES ? [process.env.EXTRA_NODE_MODULES] : [];
const req = createRequire(path.join(here, "package.json"));
const load = (name) => {
  try { return req(name); } catch {
    for (const p of extra) { try { return createRequire(path.join(p, "x.js"))(name); } catch {} }
    throw new Error(`Cannot find ${name}. Run npm install in frontend/.`);
  }
};
const esbuild = load("esbuild");
const { compile } = load("tailwindcss");
const twDir = path.dirname(
  (() => { try { return req.resolve("tailwindcss/package.json"); } catch { return createRequire(path.join(extra[0], "x.js")).resolve("tailwindcss/package.json"); } })()
);

const src = path.join(here, "src");
const dist = path.join(here, "dist");
const assets = path.join(dist, "assets");

function walk(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((d) =>
    d.isDirectory() ? walk(path.join(dir, d.name)) : [path.join(dir, d.name)]);
}

async function buildCss() {
  const input = fs.readFileSync(path.join(src, "styles.css"), "utf8");
  const compiler = await compile(input, {
    base: src,
    loadStylesheet: async (id, base) => {
      const file = id === "tailwindcss" ? path.join(twDir, "index.css")
        : id.startsWith("tailwindcss/") ? path.join(twDir, id.slice("tailwindcss/".length))
        : path.resolve(base, id);
      return { path: file, base: path.dirname(file), content: fs.readFileSync(file, "utf8") };
    },
  });
  // candidate scan: every class-like token in the sources
  const candidates = new Set();
  for (const f of walk(src).filter((f) => /\.(jsx?|html)$/.test(f))) {
    for (const tok of fs.readFileSync(f, "utf8").split(/[\s"'`{}<>()=;,]+/)) if (tok) candidates.add(tok);
  }
  return compiler.build([...candidates]);
}

async function build() {
  fs.mkdirSync(assets, { recursive: true });
  await esbuild.build({
    entryPoints: [path.join(src, "main.jsx")],
    bundle: true, minify: true, sourcemap: false, format: "esm", target: ["es2020"],
    outfile: path.join(assets, "app.js"), jsx: "automatic", loader: { ".js": "jsx" },
    define: { "process.env.NODE_ENV": '"production"' },
    nodePaths: extra,
  });
  fs.writeFileSync(path.join(assets, "app.css"), await buildCss());
  for (const f of fs.readdirSync(path.join(here, "public"))) fs.copyFileSync(path.join(here, "public", f), path.join(dist, f));
  fs.copyFileSync(path.join(here, "index.html"), path.join(dist, "index.html"));
  console.log("built", new Date().toLocaleTimeString());
}

await build();
if (process.argv.includes("--watch")) {
  let t;
  fs.watch(src, { recursive: true }, () => { clearTimeout(t); t = setTimeout(() => build().catch(console.error), 150); });
  console.log("watching src/ …");
}
