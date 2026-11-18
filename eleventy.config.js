// Eleventy configuration: how templates/ + content/ + site/ become public/.
// PROTECTED file (the owner changes it, the client's editor and Claude don't).
//
// Build, everywhere (CI, Netlify, GitHub Pages, pre-commit hook):
//   python3 checks/validate_content.py && npx --no @11ty/eleventy && python3 checks/check_site.py
//
// Division of labour:
// - checks/validate_content.py runs FIRST and refuses bad content with Polish
//   messages (empty fields, price as text, bad dates, unsafe links, HTML in a
//   post). This file assumes valid content but still refuses the dangerous
//   cases itself (unsafe link, image from elsewhere), so a skipped validator
//   can't produce an unsafe page.
// - this file renders;
// - checks/check_site.py checks the built pages afterwards.
//
// Mechanisms worth knowing before changing anything:
// 1. Closed input. Eleventy reads the whole repo root, so anything with a
//    template extension would become a page (README.md, a stray .njk file).
//    We ignore every top-level entry except templates/ and content/, and in
//    content/ only blog/*.md is a template. Pages exist only because a
//    protected file under templates/pages/ or a post in content/blog/ says so.
// 2. Posts are data, not code. Markdown is NOT run through a template
//    language first (markdownTemplateEngine: false), so "{{ }}" or "{% %}" in
//    a post is plain text. Raw HTML is escaped (html: false). JavaScript front
//    matter ("---js"), which Eleventy would execute, is switched off.
//    A post's layout and address are fixed here (eleventyComputed), so its
//    front matter can't move it onto another page's address. Data files
//    (blog.json, *.11tydata.js — Eleventy would import and run the latter)
//    are switched off entirely; the only data is content/strona.json, read
//    explicitly below.
// 3. Root-independent URLs. Templates and posts write internal URLs from the
//    site root ("/assets/style.css", "/img/…"). The last step (transform
//    "relative-urls") rewrites each one relative to the page it's on
//    ("../../assets/style.css" on /blog/slug/), so the same build works at a
//    domain root (Netlify) and in a subfolder (GitHub Pages /self-edit-kit/)
//    without knowing which. check_site.py fails the build if a root-absolute
//    URL survives.

import fs from "node:fs";

const MONTHS = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca",
  "sierpnia", "września", "października", "listopada", "grudnia"];

// Same allow-lists as checks/validate_content.py.
// Inline markup in strona.json texts (unchanged from the old build.py).
const SAFE_INLINE_URL = /^(https:\/\/|mailto:|tel:|\/|#)/;
// Post bodies: links go out (https) or to e-mail; images come from our own /img/.
const SAFE_POST_LINK = /^(https:\/\/|mailto:)/i;
const SAFE_POST_IMAGE = /^\/img\/[^?#]*$/;

const POSTS_GLOB = "content/blog/*.md";
const isPost = (inputPath) => /^\.\/content\/blog\/[^/]+\.md$/.test(inputPath);

// ---- text helpers (ported 1:1 from the old build.py) ----------------------

// Python's html.escape(s, quote=True): the five characters, ' as &#x27;.
function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#x27;");
}

// Inverse of escapeHtml, single pass, like Python's html.unescape on text we
// escaped ourselves (only these five entities can occur in it).
function unescapeHtml(s) {
  const map = { amp: "&", lt: "<", gt: ">", quot: '"', "#x27": "'" };
  return s.replace(/&(amp|lt|gt|quot|#x27);/g, (_, e) => map[e]);
}

// Escape, then turn **bold** and [text](url) into HTML. The ONLY markup a
// strona.json text field supports; anything else stays literal characters.
function inline(text) {
  let out = escapeHtml(text);
  out = out.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_, label, rawUrl) => {
    const url = unescapeHtml(rawUrl);
    if (!SAFE_INLINE_URL.test(url)) {
      throw new Error(`Link „${url}” musi zaczynać się od https://, mailto: lub tel:.`);
    }
    const rel = url.startsWith("https://") ? ' rel="noopener"' : "";
    return `<a href="${escapeHtml(url)}"${rel}>${label}</a>`;
  });
  return out.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
}

// Blank line = new paragraph, single newline = line break.
function paragraphs(text) {
  return String(text).split(/\n\s*\n/).map((b) => b.trim()).filter(Boolean)
    .map((b) => "<p>" + inline(b).replace(/\n/g, "<br>") + "</p>")
    .join("\n    ");
}

// "2026-12-05" or a Date → { y, m, d }. Dates are calendar days: read in UTC,
// because YAML/ISO dates without a time are UTC midnight.
function ymd(value) {
  const d = value instanceof Date ? value : new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) throw new Error(`„${value}” to nie jest data.`);
  return { y: d.getUTCFullYear(), m: d.getUTCMonth(), d: d.getUTCDate() };
}

function polishDate(value) {
  const { y, m, d } = ymd(value);
  return `${d} ${MONTHS[m]} ${y}`;
}

function isoDate(value) {
  const { y, m, d } = ymd(value);
  return `${y}-${String(m + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
}

// "5 grudnia 2026", "12–13 grudnia 2026", "30 grudnia 2026 – 2 stycznia 2027".
function dateRange(start, end) {
  if (!end || end === start) return polishDate(start);
  const s = ymd(start), e = ymd(end);
  if (s.y === e.y && s.m === e.m) return `${s.d}–${polishDate(end)}`;
  if (s.y === e.y) return `${s.d} ${MONTHS[s.m]} – ${polishDate(end)}`;
  return `${polishDate(start)} – ${polishDate(end)}`;
}

// 1290 → "1 290 zł" (Polish thousands separator is a space).
const price = (n) => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, " ") + " zł";

// ---- Markdown for posts ----------------------------------------------------

function configureMarkdown(md) {
  // html: false → any HTML in a post is printed as text, never as tags.
  // breaks: true → a single line break (Shift+Enter in the editor) shows up.
  md.set({ html: false, breaks: true, linkify: false, typographer: false });
  // Only headings, bold/italic, lists, links, quotes and images. The rest
  // stays literal text: code blocks, tables, horizontal rules, strikethrough.
  md.disable(["code", "fence", "table", "hr", "strikethrough", "html_block", "html_inline"]);

  // First gate: markdown-it calls this for every link and image address
  // (after decoding entities, so "java&#115;cript:" is caught too). A
  // refused address is left as plain text.
  md.validateLink = (url) => SAFE_POST_LINK.test(url) || (SAFE_POST_IMAGE.test(url) && !url.includes(".."));

  // Second gate: a link must not point at an image path and vice versa.
  const render = (tokens, idx, options, env, self) => self.renderToken(tokens, idx, options);
  const linkOpen = md.renderer.rules.link_open || render;
  md.renderer.rules.link_open = (tokens, idx, options, env, self) => {
    const href = tokens[idx].attrGet("href") || "";
    if (!SAFE_POST_LINK.test(href)) {
      throw new Error(`Link „${href}” we wpisie musi zaczynać się od https:// lub mailto:.`);
    }
    if (href.toLowerCase().startsWith("https://")) tokens[idx].attrSet("rel", "noopener");
    return linkOpen(tokens, idx, options, env, self);
  };
  const image = md.renderer.rules.image;
  md.renderer.rules.image = (tokens, idx, options, env, self) => {
    const src = tokens[idx].attrGet("src") || "";
    if (!SAFE_POST_IMAGE.test(src) || src.includes("..")) {
      throw new Error(`Zdjęcie „${src}” we wpisie musi leżeć w folderze /img/ tej strony.`);
    }
    tokens[idx].attrSet("loading", "lazy");
    return image(tokens, idx, options, env, self);
  };

  // The post title is the page's only <h1>; "# Heading" in the body becomes
  // <h2> so the page keeps one h1 (check_site.py requires exactly one).
  md.core.ruler.push("demote_h1", (state) => {
    for (const t of state.tokens) {
      if ((t.type === "heading_open" || t.type === "heading_close") && t.tag === "h1") t.tag = "h2";
    }
  });
}

// ---- relative URLs ----------------------------------------------------------

// "/blog/slug/" → "../../", "/blog/" → "../", "/" → "".
function rootPrefix(pageUrl) {
  const depth = pageUrl.split("/").length - 2;
  return "../".repeat(Math.max(depth, 0));
}

function relativeUrls(html, pageUrl) {
  const prefix = rootPrefix(pageUrl);
  // Only src="/…" and href="/…" attributes (not "//host", which is external).
  // Text from content can't match: in text, " is always escaped to &quot;.
  return html.replace(/(\s(?:src|href)=")\/(?!\/)([^"]*)"/g,
    (_, attr, rest) => `${attr}${prefix + rest || "./"}"`);
}

// ---- configuration ----------------------------------------------------------

export default function (eleventyConfig) {
  // 1. Closed input (see the header).
  for (const name of fs.readdirSync(".")) {
    if (name !== "templates" && name !== "content") eleventyConfig.ignores.add(name);
  }
  for (const name of fs.readdirSync("content")) {
    if (name !== "blog") eleventyConfig.ignores.add(`content/${name}`);
  }
  eleventyConfig.ignores.add("content/blog/**/*.njk");
  eleventyConfig.ignores.add("content/blog/*/**");

  // A fresh public/ on every build, like the old build.py: a deleted post or
  // photo must not linger in the output and pass the link checks.
  eleventyConfig.on("eleventy.before", () => {
    fs.rmSync("public", { recursive: true, force: true });
  });

  // Static files (styles, consent script, thank-you page, privacy policy,
  // images, the /admin/ editor) are copied as they are.
  eleventyConfig.addPassthroughCopy({ site: "/" }, { filter: ["**/*", "!**/.gitkeep"] });

  // 2. Posts are data (see the header).
  const refuse = (kind) => () => {
    throw new Error(`Nagłówek wpisu w formacie „${kind}” jest niedozwolony — tylko zwykły YAML między liniami ---.`);
  };
  eleventyConfig.setFrontMatterParsingOptions({
    engines: { javascript: refuse("js"), js: refuse("js"), jsLegacy: refuse("js"), json: refuse("json") },
  });
  eleventyConfig.amendLibrary("md", configureMarkdown);
  // No template or directory data files anywhere (see the header).
  eleventyConfig.setDataFileSuffixes([]);

  eleventyConfig.setNunjucksEnvironmentOptions({
    autoescape: true,        // every {{ value }} is HTML-escaped unless marked | safe
    throwOnUndefined: true,  // a typo in a template field name fails the build
  });

  // Home page content.
  eleventyConfig.addGlobalData("strona", () =>
    JSON.parse(fs.readFileSync("content/strona.json", "utf-8")));

  // Every post gets the post layout and the address /blog/<file name>/,
  // whatever its front matter says. Other templates keep their own values.
  eleventyConfig.addGlobalData("eleventyComputed", {
    layout: (data) => (isPost(data.page.inputPath) ? "post.njk" : data.layout),
    permalink: (data) => (isPost(data.page.inputPath) ? `blog/${data.page.fileSlug}/index.html` : data.permalink),
  });

  // Newest first; same date → by address, so the order is stable.
  eleventyConfig.addCollection("wpisy", (api) =>
    api.getFilteredByGlob(POSTS_GLOB).sort((a, b) =>
      (b.date - a.date) || a.page.fileSlug.localeCompare(b.page.fileSlug)));

  // Filters return HTML; templates mark them | safe explicitly, so every place
  // where markup enters the page is visible in the template.
  eleventyConfig.addFilter("inline", inline);
  eleventyConfig.addFilter("akapity", paragraphs);
  eleventyConfig.addFilter("data_pl", polishDate);
  eleventyConfig.addFilter("data_iso", isoDate);
  eleventyConfig.addFilter("zakres_dat", dateRange);
  eleventyConfig.addFilter("cena", price);
  eleventyConfig.addFilter("po_dacie", (items) => [...items].sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0)));
  // Cover/photo paths: our own /img/ folder only (validate_content.py says
  // the same with a friendlier message).
  eleventyConfig.addFilter("obraz", (path) => {
    if (typeof path !== "string" || !path.startsWith("/img/") || path.includes("..")) {
      throw new Error(`Zdjęcie „${path}” musi leżeć w folderze /img/ tej strony.`);
    }
    return path;
  });

  // 3. Root-independent URLs (see the header).
  eleventyConfig.addTransform("relative-urls", function (content) {
    if (!(this.page.outputPath || "").endsWith(".html")) return content;
    return relativeUrls(content, this.page.url);
  });

  return {
    // data: the global-data folder (Eleventy imports every .js in it). It
    // sits inside protected templates/, where every file must be pinned, and
    // doesn't exist; the default would be an unprotected _data/ at the root.
    dir: { input: ".", includes: "templates/layouts", data: "templates/data", output: "public" },
    templateFormats: ["njk", "md"],
    markdownTemplateEngine: false,
    htmlTemplateEngine: false,
  };
}
