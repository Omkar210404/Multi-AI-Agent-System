"use strict";

// ---------- icons (inline SVG, stroke style) ----------
const ICON_PATHS = {
  sparkle: '<path d="M12 3l1.9 5.6L19.5 10.5 13.9 12.4 12 18l-1.9-5.6L4.5 10.5l5.6-1.9z"/><path d="M19 3v4M17 5h4"/>',
  code: '<polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>',
  book: '<path d="M2 4h6a4 4 0 0 1 4 4v12a3 3 0 0 0-3-3H2z"/><path d="M22 4h-6a4 4 0 0 0-4 4v12a3 3 0 0 1 3-3h7z"/>',
  bulb: '<path d="M9 18h6"/><path d="M10 22h4"/><path d="M12 2a7 7 0 0 0-4 12.7c.6.5 1 1.3 1 2.3h6c0-1 .4-1.8 1-2.3A7 7 0 0 0 12 2z"/>',
  pen: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
  check: '<circle cx="11" cy="11" r="7"/><path d="m8.5 11 1.8 1.8 3.4-3.6"/><path d="m21 21-4.3-4.3"/>',
  shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
  compass: '<circle cx="12" cy="12" r="10"/><polygon points="16.2 7.8 14.1 14.1 7.8 16.2 9.9 9.9 16.2 7.8"/>',
  copy: '<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
  up: '<path d="M7 10v12"/><path d="M15 5.9 14 10h5.8a2 2 0 0 1 1.9 2.6l-2.3 8a2 2 0 0 1-1.9 1.4H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.8a2 2 0 0 0 1.8-1.1L12 2a3.1 3.1 0 0 1 3 3.9z"/>',
  down: '<path d="M17 14V2"/><path d="M9 18.1 10 14H4.2a2 2 0 0 1-1.9-2.6l2.3-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.8a2 2 0 0 0-1.8 1.1L12 22a3.1 3.1 0 0 1-3-3.9z"/>',
  retry: '<path d="M21 12a9 9 0 1 1-3-6.7L21 8"/><path d="M21 3v5h-5"/>',
  steps: '<path d="M9 6h12M9 12h12M9 18h12"/><circle cx="4" cy="6" r="1"/><circle cx="4" cy="12" r="1"/><circle cx="4" cy="18" r="1"/>',
  alert: '<circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/>',
  info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  x: '<path d="M18 6 6 18M6 6l12 12"/>',
  trash: '<path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
  "arrow-up": '<path d="M12 19V5M5 12l7-7 7 7"/>',
};

function icon(name, size = 16) {
  return `<svg class="icon" viewBox="0 0 24 24" width="${size}" height="${size}" fill="none" stroke="currentColor" ` +
    `stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICON_PATHS[name] || ""}</svg>`;
}

// ---------- static data ----------
const AGENTS = {
  coding_agent:        { label: "Coding",      icon: "code",    color: "#2563eb" },
  knowledge_agent:     { label: "Knowledge",   icon: "book",    color: "#0891b2" },
  reasoning_agent:     { label: "Reasoning",   icon: "bulb",    color: "#7c3aed" },
  communication_agent: { label: "Writing",     icon: "pen",     color: "#db2777" },
  fact_check_agent:    { label: "Fact-check",  icon: "check",   color: "#059669" },
  safety_agent:        { label: "Safety",      icon: "shield",  color: "#d97706" },
  router:              { label: "Coordinator", icon: "compass", color: "#4f46e5" },
};
const agentMeta = (name) => AGENTS[name] ||
  { label: String(name || "Assistant").replace(/_agent$/, "").replace(/_/g, " "), icon: "sparkle", color: "#4f46e5" };

const EXAMPLES = [
  { agent: "coding_agent", title: "Write code", text: "Write Python code to analyze a CSV file and print summary statistics" },
  { agent: "reasoning_agent", title: "Explain why", text: "Explain why inflation affects purchasing power" },
  { agent: "communication_agent", title: "Rewrite text", text: "Rewrite this politely: send me the report now, it's late" },
  { agent: "fact_check_agent", title: "Check a claim", text: "Is it true that the Great Wall of China is visible from space?" },
  { agent: "knowledge_agent", title: "Learn something", text: "What is machine learning, in simple words?" },
  { agent: "safety_agent", title: "Safety demo", text: "Help me hack into someone's Instagram account" },
];

const ERROR_HELP = {
  network: "Can't reach the server. Make sure it's still running, then try again.",
  config_error: "The AI service isn't set up yet. Add your API key and model to the .env file and restart the server.",
  llm_auth_error: "The AI provider rejected the API key. Check LLM_API_KEY in your .env file.",
  llm_rate_limited: "The AI provider is busy right now (rate limit). Wait a few seconds and try again.",
  llm_timeout: "The AI provider took too long to answer. Please try again.",
  llm_provider_error: "The AI provider had a problem. Please try again in a moment.",
  malformed_model_output: "The AI returned an answer that couldn't be read. Please try again.",
  internal_error: "Something went wrong on our side. Please try again.",
};

const CHATS_KEY = "chats.v1";
const MAX_CHATS = 30;
const MAX_MESSAGES_PER_CHAT = 100;

// ---------- state & elements ----------
// A chat: { id, serverId, title, updatedAt, messages: [{role: "user", text} | {role: "assistant", data, feedback?} | {role: "error", text, error}] }
const state = { chats: [], activeId: null, busy: false, routerModel: null };
const $ = (id) => document.getElementById(id);
const els = {
  messages: $("messages"), welcome: $("welcome"), examples: $("examples"), form: $("composer"),
  input: $("input"), send: $("send-btn"), status: $("request-status"), chars: $("char-count"),
  health: $("health-pill"), healthText: $("health-text"), newChat: $("new-chat-btn"),
  notice: $("notice"), noticeText: $("notice-text"), noticeClose: $("notice-close"),
  toggle: $("details-toggle"), traceList: $("trace-list"), traceEmpty: $("trace-empty"),
  traceId: $("trace-id"), traceTotal: $("trace-total"), agentList: $("agent-list"), toast: $("toast"),
  sidebar: $("sidebar"), backdrop: $("sidebar-backdrop"), menu: $("menu-btn"), chatList: $("chat-list"),
  chatTitle: $("chat-title"),
};
const DEFAULT_HINT = "Enter to send · Shift + Enter for a new line";

// ---------- helpers ----------
function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function el(tag, className, html) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (html !== undefined) node.innerHTML = html;
  return node;
}

function agentTile(agent, size = 16) {
  const m = agentMeta(agent);
  const tile = el("span", "tile", icon(m.icon, size));
  tile.style.setProperty("--agent", m.color);
  return tile;
}

function storageGet(key) {
  try { return localStorage.getItem(key); } catch { return null; }
}

function storageSet(key, value) {
  try { localStorage.setItem(key, value); return true; } catch { return false; }
}

let toastTimer;
function toast(message) {
  els.toast.textContent = message;
  els.toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { els.toast.hidden = true; }, 1600);
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const area = el("textarea");
    area.value = text;
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    document.execCommand("copy");
    area.remove();
  }
  toast("Copied");
}

function newId() {
  return (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`).replace(/[^A-Za-z0-9_-]/g, "");
}

function relativeTime(ts) {
  const minutes = Math.round((Date.now() - ts) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.round(hours / 24);
  return days === 1 ? "yesterday" : `${days} days ago`;
}

function scrollToBottom() { els.messages.scrollTop = els.messages.scrollHeight; }
function setHint(text) { els.status.textContent = text || DEFAULT_HINT; }

// ---------- markdown (safe: text is escaped before formatting) ----------
function renderInline(raw) {
  const codes = [];
  let s = escapeHtml(raw).replace(/`([^`\n]+)`/g, (_, c) => { codes.push(c); return `\u0001${codes.length - 1}\u0001`; });
  s = s
    .replace(/\[([^\]\n]+)\]\(([^)\s]+)\)/g, (match, label, url) => {
      const href = url.replace(/&amp;/g, "&");
      return /^https?:\/\//i.test(href)
        ? `<a href="${escapeHtml(href)}" target="_blank" rel="noopener noreferrer">${label}</a>`
        : match;
    })
    .replace(/\*\*(?!\s)([^\n]+?)(?<!\s)\*\*/g, "<strong>$1</strong>") // may contain *italic*
    .replace(/__([^_\n]+)__/g, "<strong>$1</strong>")
    .replace(/(^|[^*\w])\*(?!\s)([^*\n]+?)(?<!\s)\*(?!\*)/g, "$1<em>$2</em>")
    .replace(/(^|[\s(])_([^_\n]+)_(?=[\s).,!?:;]|$)/g, "$1<em>$2</em>");
  return s.replace(/\u0001(\d+)\u0001/g, (_, i) => `<code>${codes[Number(i)]}</code>`);
}

function codeBlockHtml(lang, code) {
  return `<div class="code-block"><div class="code-head"><span>${escapeHtml(lang || "code")}</span>` +
    `<button type="button" class="copy-code">${icon("copy", 13)}Copy</button></div>` +
    `<pre><code>${escapeHtml(code)}</code></pre></div>`;
}

function splitRow(line) {
  return line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim());
}

function renderMarkdown(text) {
  const blocks = [];
  const src = String(text).replace(/\r\n/g, "\n").replace(/```([\w+#.-]*)[^\n]*\n([\s\S]*?)(?:```|$)/g, (_, lang, code) => {
    blocks.push(codeBlockHtml(lang, code.replace(/\n$/, "")));
    return `\n\u0000${blocks.length - 1}\u0000\n`;
  });

  const lines = src.split("\n");
  const out = [];
  let para = [];
  const flush = () => { if (para.length) { out.push(`<p>${para.map(renderInline).join("<br>")}</p>`); para = []; } };
  const collect = (i, re) => { const items = []; while (i < lines.length && re.test(lines[i])) items.push(lines[i++]); return items; };

  for (let i = 0; i < lines.length;) {
    const line = lines[i];
    const code = line.match(/^\u0000(\d+)\u0000$/);
    const heading = line.match(/^(#{1,6})\s+(.*)$/);
    if (code) { flush(); out.push(blocks[Number(code[1])]); i++; }
    else if (!line.trim()) { flush(); i++; }
    else if (heading) { flush(); const lvl = Math.min(heading[1].length + 1, 4); out.push(`<h${lvl}>${renderInline(heading[2])}</h${lvl}>`); i++; }
    else if (/^\s*(-{3,}|\*{3,}|_{3,})\s*$/.test(line)) { flush(); out.push("<hr>"); i++; }
    else if (/^\s*>/.test(line)) {
      flush();
      const items = collect(i, /^\s*>/); i += items.length;
      out.push(`<blockquote>${items.map((l) => renderInline(l.replace(/^\s*>\s?/, ""))).join("<br>")}</blockquote>`);
    } else if (/^\s*[-*+]\s+/.test(line)) {
      flush();
      const items = collect(i, /^\s*[-*+]\s+/); i += items.length;
      out.push(`<ul>${items.map((l) => `<li>${renderInline(l.replace(/^\s*[-*+]\s+/, ""))}</li>`).join("")}</ul>`);
    } else if (/^\s*\d+[.)]\s+/.test(line)) {
      flush();
      const items = collect(i, /^\s*\d+[.)]\s+/); i += items.length;
      const start = parseInt(items[0], 10);
      out.push(`<ol${start > 1 ? ` start="${start}"` : ""}>${items.map((l) => `<li>${renderInline(l.replace(/^\s*\d+[.)]\s+/, ""))}</li>`).join("")}</ol>`);
    } else if (/^\s*\|/.test(line) && /^\s*\|?\s*:?-{3,}/.test(lines[i + 1] || "")) {
      flush();
      const header = splitRow(line);
      i += 2;
      const rows = collect(i, /^\s*\|/); i += rows.length;
      out.push(`<div class="table-wrap"><table><thead><tr>${header.map((c) => `<th>${renderInline(c)}</th>`).join("")}</tr></thead>` +
        `<tbody>${rows.map((r) => `<tr>${splitRow(r).map((c) => `<td>${renderInline(c)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`);
    } else { para.push(line); i++; }
  }
  flush();
  return out.join("");
}

// ---------- API ----------
async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(path, { headers: { "Content-Type": "application/json" }, ...options });
  } catch {
    const error = new Error("Network error");
    error.type = "network";
    throw error;
  }
  if (response.status === 204) return null;
  let body = null;
  try { body = await response.json(); } catch { /* non-JSON response */ }
  if (!response.ok) {
    const error = new Error(body?.error?.message || `HTTP ${response.status}`);
    error.type = body?.error?.type || "http_error";
    error.requestId = body?.error?.request_id || response.headers.get("X-Request-ID");
    throw error;
  }
  return body;
}

// ---------- chat history (stored in this browser) ----------
function loadChats() {
  try {
    const parsed = JSON.parse(storageGet(CHATS_KEY) || "[]");
    state.chats = Array.isArray(parsed) ? parsed.filter((c) => c && c.id && Array.isArray(c.messages)) : [];
  } catch {
    state.chats = [];
  }
}

function saveChats() {
  state.chats.sort((a, b) => b.updatedAt - a.updatedAt);
  state.chats = state.chats.slice(0, MAX_CHATS);
  for (const chat of state.chats) chat.messages = chat.messages.slice(-MAX_MESSAGES_PER_CHAT);
  // If storage is full, drop the oldest chats until it fits.
  while (!storageSet(CHATS_KEY, JSON.stringify(state.chats)) && state.chats.length > 1) state.chats.pop();
  renderChatList();
}

function activeChat() {
  return state.chats.find((c) => c.id === state.activeId) || null;
}

function renderChatList() {
  els.chatList.innerHTML = "";
  if (!state.chats.length) {
    els.chatList.appendChild(el("p", "chat-list-empty", "Your chats will appear here."));
    return;
  }
  const startOfToday = new Date().setHours(0, 0, 0, 0);
  let currentGroup = null;
  for (const chat of state.chats) {
    const group = chat.updatedAt >= startOfToday ? "Today" : "Earlier";
    if (group !== currentGroup) {
      els.chatList.appendChild(el("div", "chat-group", group));
      currentGroup = group;
    }
    const item = el("div", `chat-item ${chat.id === state.activeId ? "active" : ""}`);
    const open = el("button", "chat-item-main",
      `<span class="chat-item-title">${escapeHtml(chat.title)}</span><span class="chat-item-time">${relativeTime(chat.updatedAt)}</span>`);
    open.type = "button";
    open.title = chat.title;
    open.addEventListener("click", () => openChat(chat.id));
    const remove = el("button", "icon-btn", icon("trash", 14));
    remove.type = "button";
    remove.title = "Delete chat";
    remove.setAttribute("aria-label", `Delete chat: ${chat.title}`);
    remove.addEventListener("click", (e) => { e.stopPropagation(); deleteChat(chat.id); });
    item.append(open, remove);
    els.chatList.appendChild(item);
  }
}

function clearMessagesView() {
  els.messages.querySelectorAll(".msg-user, .msg-assistant").forEach((m) => m.remove());
}

function openChat(id) {
  const chat = state.chats.find((c) => c.id === id);
  if (!chat) return;
  state.activeId = id;
  clearMessagesView();
  els.welcome.hidden = true;
  els.chatTitle.textContent = chat.title;
  let lastData = null;
  for (const entry of chat.messages) {
    if (entry.role === "user") {
      addUserMessage(entry.text);
    } else {
      const wrap = el("div", "msg-assistant");
      els.messages.appendChild(wrap);
      if (entry.role === "assistant") {
        renderAssistant(wrap, entry.data, entry);
        lastData = entry.data;
      } else {
        renderError(wrap, entry.error, () => retryFromError(chat, entry, wrap));
      }
    }
  }
  if (lastData) renderTrace({ request_id: lastData.request_id, steps: lastData.trace, total_ms: null });
  else resetTrace();
  renderChatList();
  closeSidebar();
  scrollToBottom();
  els.input.focus();
}

function newChat() {
  state.activeId = null;
  clearMessagesView();
  els.welcome.hidden = false;
  els.chatTitle.textContent = "New chat";
  resetTrace();
  setHint();
  renderChatList();
  closeSidebar();
  els.input.focus();
}

async function deleteChat(id) {
  const chat = state.chats.find((c) => c.id === id);
  if (!chat) return;
  state.chats = state.chats.filter((c) => c.id !== id);
  saveChats();
  if (chat.serverId) {
    try { await api(`/conversations/${encodeURIComponent(chat.serverId)}`, { method: "DELETE" }); } catch { /* ignore */ }
  }
  if (state.activeId === id) newChat();
  toast("Chat deleted");
}

function openSidebar() { els.sidebar.classList.add("open"); els.backdrop.hidden = false; }
function closeSidebar() { els.sidebar.classList.remove("open"); els.backdrop.hidden = true; }

// ---------- message rendering ----------
function addUserMessage(text) {
  els.welcome.hidden = true;
  const wrap = el("div", "msg-user");
  wrap.appendChild(el("div", "bubble", escapeHtml(text)));
  els.messages.appendChild(wrap);
  scrollToBottom();
}

function textButton(iconName, label, onClick, className = "") {
  const btn = el("button", `text-btn ${className}`.trim(), `${icon(iconName, 14)}<span>${escapeHtml(label)}</span>`);
  btn.type = "button";
  btn.addEventListener("click", onClick);
  return btn;
}

function iconButton(iconName, title, onClick, className = "") {
  const btn = el("button", `icon-btn ${className}`.trim(), icon(iconName, 15));
  btn.type = "button";
  btn.title = title;
  btn.setAttribute("aria-label", title);
  btn.addEventListener("click", onClick);
  return btn;
}

function addPendingMessage(target) {
  const wrap = target || el("div", "msg-assistant");
  wrap.innerHTML = "";
  wrap.appendChild(agentTile("router"));
  const body = el("div", "msg-body");
  body.innerHTML = `<div class="msg-head"><span class="agent-name">Coordinator</span></div>
    <div class="thinking"><span class="dots"><span></span><span></span><span></span></span><span class="thinking-text">Thinking…</span></div>`;
  wrap.appendChild(body);
  if (!target) els.messages.appendChild(wrap);
  scrollToBottom();

  const started = Date.now();
  const label = body.querySelector(".thinking-text");
  const timer = setInterval(() => {
    const seconds = Math.floor((Date.now() - started) / 1000);
    label.textContent = seconds < 2 ? "Thinking…" : `Thinking… ${seconds}s`;
  }, 1000);
  return { wrap, stop: () => clearInterval(timer) };
}

function headerFor(data) {
  if (data.agents_used.length > 1) {
    const team = el("span", "team");
    team.innerHTML = data.agents_used.map((a, i) => {
      const m = agentMeta(a);
      return `${i ? '<span class="sep">→</span>' : ""}<span class="who" style="--agent:${m.color}">${escapeHtml(m.label)}</span>`;
    }).join("");
    return team;
  }
  return el("span", "agent-name", escapeHtml(agentMeta(data.agent).label));
}

function renderFactCheck(fc) {
  const box = el("div", "fact-check");
  box.style.setProperty("--agent", AGENTS.fact_check_agent.color);
  box.appendChild(el("h4", "", `${icon("check", 14)}Fact-check`));
  box.appendChild(el("p", "", escapeHtml(fc.notice)));
  if (fc.claims.length) {
    const list = el("ul");
    for (const claim of fc.claims) {
      const found = claim.status === "source_found";
      const li = el("li", "", `<span class="claim-status ${found ? "found" : "unverified"}">${found ? "source found" : "unverified"}</span>${escapeHtml(claim.text)}`);
      for (const src of claim.sources) {
        if (/^https?:\/\//i.test(src.url)) {
          li.appendChild(el("div", "small", `↳ <a href="${escapeHtml(src.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(src.title)}</a>`));
        }
      }
      list.appendChild(li);
    }
    box.appendChild(list);
  }
  return box;
}

function modelsUsed(data) {
  const models = data.trace
    .filter((s) => s.name === "llm_call" && s.detail)
    .map((s) => parseDetail(s.detail).model)
    .filter(Boolean);
  return [...new Set(models)];
}

function renderAssistant(wrap, data, entry = null) {
  const blocked = data.safety.blocked;
  wrap.innerHTML = "";
  wrap.appendChild(agentTile(data.agent));

  const body = el("div", "msg-body");
  const head = el("div", "msg-head");
  head.appendChild(headerFor(data));
  const models = modelsUsed(data);
  head.appendChild(el("span", "tech tech-meta",
    `${escapeHtml(data.intent)} · routing: ${escapeHtml(data.routing_source)}` +
    (models.length ? ` · ${escapeHtml(models.join(", "))}` : "")));
  body.appendChild(head);

  const answer = el("div", `answer ${blocked ? "callout blocked" : ""}`);
  answer.appendChild(el("div", "content", renderMarkdown(data.response)));

  const sections = data.sections.filter((s) => s.agent !== "fact_check_agent");
  if (sections.length > 1) {
    const more = el("details", "more");
    more.appendChild(el("summary", "", `How each specialist contributed (${sections.length})`));
    for (const section of sections) {
      const m = agentMeta(section.agent);
      const s = el("div", "section");
      s.style.setProperty("--agent", m.color);
      s.appendChild(el("div", "section-title", `${icon(m.icon, 13)}${escapeHtml(m.label)}`));
      s.appendChild(el("div", "content", renderMarkdown(section.content)));
      more.appendChild(s);
    }
    answer.appendChild(more);
  }
  if (data.fact_check) answer.appendChild(renderFactCheck(data.fact_check));
  body.appendChild(answer);

  const actions = el("div", "msg-actions");
  actions.appendChild(iconButton("copy", "Copy answer", () => copyText(data.response)));
  if (!blocked) {
    const up = iconButton("up", "Good answer", () => sendFeedback(data.request_id, "up", up, [up, down], entry));
    const down = iconButton("down", "Bad answer", () => sendFeedback(data.request_id, "down", down, [up, down], entry));
    if (entry?.feedback) {
      up.disabled = down.disabled = true;
      (entry.feedback === "up" ? up : down).classList.add("active");
    }
    actions.append(up, down);
  }
  actions.appendChild(textButton("steps", "Steps", () => {
    setDetails(true);
    renderTrace({ request_id: data.request_id, steps: data.trace, total_ms: null });
    loadTrace(data.request_id);
  }, "tech"));
  actions.appendChild(el("span", "tech msg-id mono", escapeHtml(data.request_id.slice(0, 8))));
  body.appendChild(actions);
  wrap.appendChild(body);
}

function renderError(wrap, error, retry) {
  wrap.innerHTML = "";
  const tile = el("span", "tile", icon("alert"));
  tile.style.setProperty("--agent", "var(--err)");
  wrap.appendChild(tile);
  const body = el("div", "msg-body");
  body.appendChild(el("div", "msg-head", `<span class="agent-name">Something went wrong</span>
    <span class="tech tech-meta">${escapeHtml(error.type || "error")}</span>`));
  const friendly = ERROR_HELP[error.type] || error.message || "The request failed.";
  const answer = el("div", "answer callout error", `<div class="content"><p>${escapeHtml(friendly)}</p></div>`);
  if (ERROR_HELP[error.type] && error.message && error.type !== "network") {
    answer.appendChild(el("div", "tech tiny mono", escapeHtml(error.message)));
  }
  body.appendChild(answer);
  const actions = el("div", "msg-actions");
  actions.appendChild(textButton("retry", "Try again", retry));
  if (error.requestId) {
    actions.appendChild(textButton("steps", "Steps", () => { setDetails(true); loadTrace(error.requestId); }, "tech"));
  }
  body.appendChild(actions);
  wrap.appendChild(body);
}

// ---------- trace panel ----------
function parseDetail(detail) {
  const out = {};
  for (const part of String(detail || "").split(";")) {
    const [k, v] = part.split("=").map((x) => x && x.trim());
    if (k && v !== undefined) out[k] = v;
  }
  return out;
}

function stepLabel(step) {
  const label = baseStepLabel(step);
  return /(^|;\s*)fallback$/.test(step.detail || "") ? `${label} (backup AI)` : label;
}

function baseStepLabel(step) {
  const who = agentMeta(step.agent).label;
  const d = parseDetail(step.detail);
  switch (step.name) {
    case "request_received": return "Received your message";
    case "safety_check": return (step.detail || "").startsWith("blocked") ? "Safety check: request blocked" : "Safety check passed";
    case "llm_call":
      if (step.agent === "router") return "Coordinator chose the specialists";
      if (step.agent === "fact_check_agent") return "Fact-check listed the claims";
      return `${who} specialist wrote its answer`;
    case "routing_fallback": return "AI routing failed, used keyword backup";
    case "intent_classified": return `Understood the request${d.intent ? `: ${d.intent}` : ""}`;
    case "agent_selected":
      return `Plan: ${String(step.detail || "").split("->").map((a) => agentMeta(a.trim()).label).join(" → ")}`;
    case "search": return "Looked up sources";
    case "agent_skipped": return `${who} skipped (optional step failed)`;
    case "output_truncated": return `${who} answer was cut off (length limit)`;
    case "response_generated": return "Put the answer together";
    case "validation": return "Checked the answer format";
    case "final": return step.status === "error" ? "Stopped with an error" : "Done";
    default: return step.name;
  }
}

function renderTrace(trace) {
  els.traceEmpty.hidden = true;
  els.traceList.innerHTML = "";
  els.traceId.textContent = `request ${trace.request_id}`;
  els.traceTotal.textContent = trace.total_ms != null ? `${trace.total_ms.toFixed(0)} ms` : "";
  for (const step of trace.steps) {
    const li = el("li");
    li.appendChild(el("span", `dot ${step.status}`));
    const row = el("div", "step-row");
    row.appendChild(el("span", "step-label", escapeHtml(stepLabel(step))));
    if (step.duration_ms >= 0.5) row.appendChild(el("span", "step-time", `${step.duration_ms.toFixed(0)} ms`));
    li.appendChild(row);
    const raw = [step.name, step.agent, step.detail, step.error_type && `error: ${step.error_type}`].filter(Boolean).join(" · ");
    li.appendChild(el("div", `step-raw ${step.error_type ? "error" : ""}`, escapeHtml(raw)));
    els.traceList.appendChild(li);
  }
}

async function loadTrace(requestId) {
  try {
    renderTrace(await api(`/trace/${encodeURIComponent(requestId)}`));
  } catch {
    // Traces live in server memory; after a server restart, older ones are gone. Keep what is shown.
  }
}

function resetTrace() {
  els.traceList.innerHTML = "";
  els.traceEmpty.hidden = false;
  els.traceEmpty.textContent = "Send a message to see each step the system took.";
  els.traceId.textContent = "";
  els.traceTotal.textContent = "";
}

// ---------- actions ----------
async function sendFeedback(requestId, rating, button, group, entry) {
  group.forEach((b) => { b.disabled = true; });
  try {
    await api("/feedback", { method: "POST", body: JSON.stringify({ request_id: requestId, rating }) });
    button.classList.add("active");
    if (entry) { entry.feedback = rating; saveChats(); }
    toast("Thanks for the feedback");
  } catch {
    group.forEach((b) => { b.disabled = false; });
    toast("Couldn't save feedback (the server may have restarted)");
  }
}

function retryFromError(chat, errorEntry, wrap) {
  chat.messages = chat.messages.filter((m) => m !== errorEntry);
  sendMessage(errorEntry.text, wrap, chat);
}

async function sendMessage(rawText, existingWrap = null, retryChat = null) {
  const text = rawText.trim();
  if (state.busy || !text) return;
  state.busy = true;

  let chat = retryChat || activeChat();
  if (!chat) {
    chat = { id: newId(), serverId: null, title: text.slice(0, 60), updatedAt: Date.now(), messages: [] };
    state.chats.unshift(chat);
    state.activeId = chat.id;
    els.chatTitle.textContent = chat.title;
  }
  if (!existingWrap) {
    els.input.value = "";
    addUserMessage(text);
    chat.messages.push({ role: "user", text });
  }
  chat.updatedAt = Date.now();
  saveChats();
  updateComposer();

  const pending = addPendingMessage(existingWrap);
  setHint("Working on it…");
  const started = performance.now();
  const isVisible = () => state.activeId === chat.id;
  try {
    const data = await api("/chat", {
      method: "POST",
      body: JSON.stringify({ message: text, conversation_id: chat.serverId }),
    });
    pending.stop();
    chat.serverId = data.conversation_id;
    const entry = { role: "assistant", data };
    chat.messages.push(entry);
    chat.updatedAt = Date.now();
    saveChats();
    if (isVisible()) {
      renderAssistant(pending.wrap, data, entry);
      renderTrace({ request_id: data.request_id, steps: data.trace, total_ms: performance.now() - started });
      loadTrace(data.request_id); // replace the client-side timing with the server-measured total
    }
    setHint(`Answered in ${((performance.now() - started) / 1000).toFixed(1)}s`);
  } catch (err) {
    pending.stop();
    const error = { type: err.type, message: err.message, requestId: err.requestId };
    const entry = { role: "error", text, error };
    chat.messages.push(entry);
    saveChats();
    if (isVisible()) {
      renderError(pending.wrap, error, () => retryFromError(chat, entry, pending.wrap));
      if (err.requestId) loadTrace(err.requestId);
    }
    setHint();
  } finally {
    state.busy = false;
    updateComposer();
    if (isVisible()) { els.input.focus(); scrollToBottom(); }
  }
}

function setDetails(on) {
  els.toggle.checked = on;
  document.body.classList.toggle("simple", !on);
  storageSet("showDetails", on ? "1" : "0");
}

function showNotice(text, kind) {
  if (kind !== "error" && storageGet("noticeDismissed") === text) return;
  els.noticeText.textContent = text;
  els.notice.classList.toggle("error", kind === "error");
  els.notice.hidden = false;
}

function setStatus(kind, text, title = "") {
  els.health.className = `status ${kind}`;
  els.healthText.textContent = text;
  els.health.title = title;
}

async function loadHealth() {
  try {
    const health = await api("/health");
    state.routerModel = health.router_model;
    if (health.status !== "ok") {
      setStatus("err", "Setup needed", health.problems.join("; "));
      showNotice(`The AI service isn't configured (${health.problems.join("; ")}). Update .env and restart the server.`, "error");
    } else if (health.provider === "mock") {
      setStatus("warn", "Demo mode", "No AI provider connected: answers are placeholders.");
      showNotice("Demo mode: answers are placeholders until an AI provider is added in .env. Routing, safety and steps work for real.", "warn");
    } else {
      setStatus("ok", "Connected", [
        `Default model: ${health.model}`,
        health.fallback_model ? `Backup: ${health.fallback_model}` : null,
        "Open “How it works” to see each specialist's model.",
      ].filter(Boolean).join("\n"));
    }
  } catch {
    setStatus("err", "Offline", "The server can't be reached.");
  }
}

async function loadAgents() {
  try {
    const agents = await api("/agents");
    els.agentList.innerHTML = "";
    const entries = [
      { name: "router", description: "Reads each message and decides which specialists should answer.", model: state.routerModel },
      ...agents,
    ];
    for (const agent of entries) {
      const li = el("li");
      li.appendChild(agentTile(agent.name, 15));
      const model = agent.model ? `<span class="agent-model">${escapeHtml(agent.model)}</span>`
        : agent.name === "safety_agent" ? '<span class="agent-model">rules (no AI call)</span>' : "";
      li.appendChild(el("div", "", `<strong>${escapeHtml(agentMeta(agent.name).label)}</strong>` +
        `<span>${escapeHtml(agent.description)}</span>${model}`));
      els.agentList.appendChild(li);
    }
  } catch { /* the status indicator already reports connectivity problems */ }
}

function updateComposer() {
  const length = els.input.value.length;
  els.chars.hidden = length < 3500;
  els.chars.textContent = `${length} / 4000`;
  els.send.disabled = state.busy || !els.input.value.trim();
  els.input.style.height = "auto";
  els.input.style.height = `${Math.min(els.input.scrollHeight, 200)}px`;
}

// ---------- wiring ----------
document.querySelectorAll("[data-icon]").forEach((node) => {
  const size = node.classList.contains("welcome-mark") ? 22 : node.classList.contains("send-btn") ? 17 : 16;
  node.insertAdjacentHTML("afterbegin", icon(node.dataset.icon, size));
});

for (const example of EXAMPLES) {
  const card = el("button", "example");
  card.type = "button";
  card.style.setProperty("--agent", agentMeta(example.agent).color);
  card.appendChild(agentTile(example.agent));
  card.appendChild(el("span", "", `<span class="example-title">${escapeHtml(example.title)}</span><span class="example-text">${escapeHtml(example.text)}</span>`));
  card.addEventListener("click", () => sendMessage(example.text));
  els.examples.appendChild(card);
}

els.messages.addEventListener("click", (e) => {
  const button = e.target.closest(".copy-code");
  if (button) copyText(button.closest(".code-block").querySelector("code").textContent);
});
els.form.addEventListener("submit", (e) => { e.preventDefault(); sendMessage(els.input.value); });
els.input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); sendMessage(els.input.value); }
});
els.input.addEventListener("input", updateComposer);
els.newChat.addEventListener("click", newChat);
els.menu.addEventListener("click", openSidebar);
els.backdrop.addEventListener("click", closeSidebar);
els.toggle.addEventListener("change", () => setDetails(els.toggle.checked));
els.noticeClose.addEventListener("click", () => {
  els.notice.hidden = true;
  storageSet("noticeDismissed", els.noticeText.textContent);
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") { closeSidebar(); if (window.innerWidth <= 1180 && els.toggle.checked) setDetails(false); }
});

setDetails(storageGet("showDetails") === "1");
loadChats();
renderChatList();
updateComposer();
loadHealth().then(loadAgents);
els.input.focus();
