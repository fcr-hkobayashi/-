import { createServer } from "node:http";
import { readFile, writeFile } from "node:fs/promises";
import { existsSync, readFileSync } from "node:fs";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";
import crypto from "node:crypto";

const root = fileURLToPath(new URL(".", import.meta.url));
const usersPath = join(root, "users.json");
const port = Number(process.env.PORT || 4173);
const host = process.env.HOST || (process.env.PORT ? "0.0.0.0" : "127.0.0.1");
const publicEditor = process.env.PUBLIC_EDITOR === "true";
// セッションはメモリではなく署名付きCookieに保持する。
// サーバー再起動（Renderのスリープ・再デプロイ）後もログイン状態が生き残る。
// 鍵はusers.jsonの内容から導出するので、パスワードを変えると全端末のログインが無効化される。
const sessionSecret = crypto
  .createHash("sha256")
  .update(process.env.SESSION_SECRET || readFileSync(usersPath, "utf8"))
  .digest();
const sessionMaxAgeMs = 1000 * 60 * 60 * 24 * 365;
const editableFiles = new Set(["index.html", "styles.css", "app.js"]);
const servedFiles = new Set(["index.html", "styles.css", "app.js", "login.html", "editor.html"]);

const mimeTypes = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
  ".ico": "image/x-icon",
};

function send(res, status, body, headers = {}) {
  res.writeHead(status, {
    "Content-Type": "text/plain; charset=utf-8",
    "X-Content-Type-Options": "nosniff",
    ...headers,
  });
  res.end(body);
}

function redirect(res, location) {
  res.writeHead(302, { Location: location });
  res.end();
}

function parseCookies(req) {
  return Object.fromEntries(
    String(req.headers.cookie || "")
      .split(";")
      .map((part) => part.trim().split("="))
      .filter(([key, value]) => key && value)
      .map(([key, value]) => [key, decodeURIComponent(value)]),
  );
}

async function loadUsers() {
  const data = JSON.parse(await readFile(usersPath, "utf8"));
  return data.users;
}

async function verifyPassword(username, password) {
  const users = await loadUsers();
  const user = users.find((entry) => entry.username === username);
  if (!user) return null;
  const hash = crypto.pbkdf2Sync(password, user.salt, user.iterations, 32, "sha256").toString("hex");
  const valid = crypto.timingSafeEqual(Buffer.from(hash, "hex"), Buffer.from(user.hash, "hex"));
  return valid ? { username: user.username, role: user.role } : null;
}

function createSession(user) {
  const payload = Buffer.from(
    JSON.stringify({ u: user.username, r: user.role, exp: Date.now() + sessionMaxAgeMs }),
  ).toString("base64url");
  const signature = crypto.createHmac("sha256", sessionSecret).update(payload).digest("base64url");
  return `${payload}.${signature}`;
}

function getSession(req) {
  const token = parseCookies(req).miraiya_session;
  if (!token) return null;
  const [payload, signature] = token.split(".");
  if (!payload || !signature) return null;
  const expected = crypto.createHmac("sha256", sessionSecret).update(payload).digest("base64url");
  const given = Buffer.from(signature);
  const wanted = Buffer.from(expected);
  if (given.length !== wanted.length || !crypto.timingSafeEqual(given, wanted)) return null;
  try {
    const data = JSON.parse(Buffer.from(payload, "base64url").toString("utf8"));
    if (typeof data.exp !== "number" || data.exp < Date.now()) return null;
    return { user: { username: data.u, role: data.r } };
  } catch {
    return null;
  }
}

function canEdit(session) {
  return publicEditor || (session && ["admin", "editor"].includes(session.user.role));
}

function getActiveSession(req) {
  const session = getSession(req);
  if (session) return session;
  if (publicEditor) return { user: { username: "public-editor", role: "editor" } };
  return null;
}

async function readBody(req) {
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  return Buffer.concat(chunks).toString("utf8");
}

function safeFilePath(name) {
  if (!servedFiles.has(name)) return null;
  const resolved = normalize(join(root, name));
  return resolved.startsWith(root) ? resolved : null;
}

async function serveFile(res, name) {
  const filePath = safeFilePath(name);
  if (!filePath || !existsSync(filePath)) {
    send(res, 404, "Not found");
    return;
  }
  const body = await readFile(filePath);
  send(res, 200, body, { "Content-Type": mimeTypes[extname(filePath)] || "application/octet-stream" });
}

async function handleLogin(req, res) {
  const body = await readBody(req);
  const form = new URLSearchParams(body);
  const user = await verifyPassword(form.get("username") || "", form.get("password") || "");
  if (!user) {
    redirect(res, "/login?error=1");
    return;
  }
  const token = createSession(user);
  res.writeHead(302, {
    Location: "/",
    "Set-Cookie": `miraiya_session=${encodeURIComponent(token)}; HttpOnly; SameSite=Lax; Path=/; Max-Age=${Math.floor(sessionMaxAgeMs / 1000)}`,
  });
  res.end();
}

async function handleApi(req, res, session, url) {
  if (url.pathname === "/api/me" && req.method === "GET") {
    send(res, 200, JSON.stringify({ user: session.user }), { "Content-Type": "application/json; charset=utf-8" });
    return;
  }
  if (url.pathname === "/api/files" && req.method === "GET") {
    if (!canEdit(session)) return send(res, 403, "Forbidden");
    send(res, 200, JSON.stringify([...editableFiles]), { "Content-Type": "application/json; charset=utf-8" });
    return;
  }
  if (url.pathname === "/api/file" && req.method === "GET") {
    if (!canEdit(session)) return send(res, 403, "Forbidden");
    const name = url.searchParams.get("name") || "";
    const filePath = safeFilePath(name);
    if (!filePath || !editableFiles.has(name)) return send(res, 400, "Invalid file");
    send(res, 200, JSON.stringify({ name, content: await readFile(filePath, "utf8") }), {
      "Content-Type": "application/json; charset=utf-8",
    });
    return;
  }
  if (url.pathname === "/api/file" && req.method === "POST") {
    if (!canEdit(session)) return send(res, 403, "Forbidden");
    const payload = JSON.parse(await readBody(req));
    const filePath = safeFilePath(payload.name);
    if (!filePath || !editableFiles.has(payload.name) || typeof payload.content !== "string") {
      return send(res, 400, "Invalid file");
    }
    await writeFile(filePath, payload.content, "utf8");
    send(res, 200, JSON.stringify({ ok: true }), { "Content-Type": "application/json; charset=utf-8" });
    return;
  }
  send(res, 404, "Not found");
}

createServer(async (req, res) => {
  try {
    const url = new URL(req.url || "/", `http://${req.headers.host || "localhost"}`);

    if (url.pathname === "/login" && req.method === "GET") return serveFile(res, "login.html");
    if (url.pathname === "/login" && req.method === "POST") return handleLogin(req, res);

    if (url.pathname === "/logout") {
      res.writeHead(302, {
        Location: "/login",
        "Set-Cookie": "miraiya_session=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0",
      });
      res.end();
      return;
    }

    const session = getActiveSession(req);
    if (!session) return redirect(res, "/login");

    if (url.pathname.startsWith("/api/")) return handleApi(req, res, session, url);
    if (url.pathname === "/editor") {
      if (!canEdit(session)) return send(res, 403, "Forbidden");
      return serveFile(res, "editor.html");
    }

    const route = url.pathname === "/" ? "index.html" : url.pathname.slice(1);
    if (route.includes("..")) return send(res, 400, "Invalid path");
    if (route === "editor.html" && !canEdit(session)) return send(res, 403, "Forbidden");
    return serveFile(res, route);
  } catch (error) {
    console.error(error);
    send(res, 500, "Server error");
  }
}).listen(port, host, () => {
  console.log(`みらいや査定 server running: http://${host}:${port}`);
});
