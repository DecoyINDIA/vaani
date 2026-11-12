import { FormEvent, useEffect, useMemo, useState } from "react";

type Item = Record<string, unknown> & { _id: string };
type Tab = "inbox" | "bookings" | "escalations" | "deliveries" | "processing" | "knowledge" | "settings";
const PAGE_SIZE = 50;
const MESSAGE_PAGE_SIZE = 100;
const tabs: { id: Tab; label: string }[] = [
  { id: "inbox", label: "Inbox" }, { id: "bookings", label: "Appointments" },
  { id: "escalations", label: "Escalations" }, { id: "deliveries", label: "Delivery issues" },
  { id: "processing", label: "Processing issues" },
  { id: "knowledge", label: "Knowledge" },
  { id: "settings", label: "Business settings" },
];
const errorText = (value: unknown) => value instanceof Error ? value.message : "The request failed.";

async function api(path: string, init: RequestInit = {}, retry = true): Promise<unknown> {
  const access = sessionStorage.getItem("vaani_access");
  const response = await fetch(path, { ...init, headers: { "Content-Type": "application/json", ...(access ? { Authorization: `Bearer ${access}` } : {}), ...init.headers } });
  if (response.status === 401 && retry) {
    const refresh = sessionStorage.getItem("vaani_refresh");
    if (refresh) {
      const refreshed = await fetch("/api/auth/refresh", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token: refresh }) });
      if (refreshed.ok) {
        const tokens = await refreshed.json();
        sessionStorage.setItem("vaani_access", tokens.access_token);
        sessionStorage.setItem("vaani_refresh", tokens.refresh_token);
        return api(path, init, false);
      }
    }
    sessionStorage.clear();
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${response.status})`);
  }
  return response.json();
}

function Login({ done }: { done: () => void }) {
  const [token, setToken] = useState(new URLSearchParams(location.search).get("token") || "");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const tokens = await api("/api/auth/magic/consume", { method: "POST", body: JSON.stringify({ token: token.trim() }) }, false) as { access_token: string; refresh_token: string };
      sessionStorage.setItem("vaani_access", tokens.access_token); sessionStorage.setItem("vaani_refresh", tokens.refresh_token);
      history.replaceState({}, "", "/"); done();
    } catch (reason) { setError(errorText(reason)); } finally { setBusy(false); }
  }
  return <main className="login-shell" id="main-content">
    <section className="login-copy"><p className="eyebrow">Vaani business desk</p><h1>Customer conversations, without the front-desk scramble.</h1><p>Review handoffs, appointments and business knowledge in one private workspace.</p><div className="signal"><span /> Private tenant workspace</div></section>
    <form className="login-panel" onSubmit={submit}><div className="brand">वा</div><div><p className="eyebrow">Secure sign in</p><h2>Use your invitation</h2></div><label>Magic-link token<textarea required rows={4} value={token} onChange={(event) => setToken(event.target.value)} placeholder="Paste the token from your invitation link" /></label>{error && <p className="inline-error" role="alert">{error}</p>}<button className="primary" disabled={busy || !token.trim()}>{busy ? "Checking invitation…" : "Enter workspace"}</button><p className="fine">Invitation links expire after 15 minutes and work once.</p></form>
  </main>;
}

function Dashboard({ signedOut }: { signedOut: () => void }) {
  const [tab, setTab] = useState<Tab>("inbox");
  const [data, setData] = useState<Record<Tab, Item[]>>({ inbox: [], bookings: [], escalations: [], deliveries: [], processing: [], knowledge: [], settings: [] });
  const [hasMore, setHasMore] = useState<Record<Tab, boolean>>({ inbox: false, bookings: false, escalations: false, deliveries: false, processing: false, knowledge: false, settings: false });
  const [selected, setSelected] = useState<Item | null>(null);
  const [messages, setMessages] = useState<Item[]>([]);
  const [messageHasMore, setMessageHasMore] = useState(false);
  const [error, setError] = useState(""); const [loading, setLoading] = useState(true);
  async function load() {
    setLoading(true); setError("");
    try {
      const [inbox, bookings, escalations, deliveries, processing, knowledge, settings] = await Promise.all([api(`/api/conversations?limit=${PAGE_SIZE + 1}`), api(`/api/bookings?limit=${PAGE_SIZE + 1}`), api(`/api/escalations?limit=${PAGE_SIZE + 1}`), api(`/api/deliveries?limit=${PAGE_SIZE + 1}`), api(`/api/processing?limit=${PAGE_SIZE + 1}`), api(`/api/kb?limit=${PAGE_SIZE + 1}`), api("/api/settings")]);
      const pages = { inbox: inbox as Item[], bookings: bookings as Item[], escalations: escalations as Item[], deliveries: deliveries as Item[], processing: processing as Item[], knowledge: knowledge as Item[] };
      setData({ inbox: pages.inbox.slice(0, PAGE_SIZE), bookings: pages.bookings.slice(0, PAGE_SIZE), escalations: pages.escalations.slice(0, PAGE_SIZE), deliveries: pages.deliveries.slice(0, PAGE_SIZE), processing: pages.processing.slice(0, PAGE_SIZE), knowledge: pages.knowledge.slice(0, PAGE_SIZE), settings: [settings as Item] });
      setHasMore({ inbox: pages.inbox.length > PAGE_SIZE, bookings: pages.bookings.length > PAGE_SIZE, escalations: pages.escalations.length > PAGE_SIZE, deliveries: pages.deliveries.length > PAGE_SIZE, processing: pages.processing.length > PAGE_SIZE, knowledge: pages.knowledge.length > PAGE_SIZE, settings: false });
      setSelected((current) => current
        ? pages.inbox.find((item) => item._id === current._id) || pages.inbox[0] || null
        : pages.inbox[0] || null);
    } catch (reason) { setError(errorText(reason)); } finally { setLoading(false); }
  }
  async function loadMore() {
    if (tab === "settings") return;
    const endpoint = tab === "inbox" ? "conversations" : tab === "knowledge" ? "kb" : tab;
    try {
      const page = await api(`/api/${endpoint}?limit=${PAGE_SIZE + 1}&offset=${data[tab].length}`) as Item[];
      setData((current) => ({ ...current, [tab]: [...current[tab], ...page.slice(0, PAGE_SIZE)] }));
      setHasMore((current) => ({ ...current, [tab]: page.length > PAGE_SIZE }));
    } catch (reason) { setError(errorText(reason)); }
  }
  async function loadMessages(item: Item, append = false) {
    try {
      const offset = append ? messages.length : 0;
      const page = await api(`/api/conversations/${item._id}/messages?limit=${MESSAGE_PAGE_SIZE + 1}&offset=${offset}`) as Item[];
      setMessages((current) => append ? [...current, ...page.slice(0, MESSAGE_PAGE_SIZE)] : page.slice(0, MESSAGE_PAGE_SIZE));
      setMessageHasMore(page.length > MESSAGE_PAGE_SIZE);
    } catch (reason) { setError(errorText(reason)); }
  }
  useEffect(() => { void load(); }, []);
  useEffect(() => { if (selected && tab === "inbox") void loadMessages(selected); }, [selected, tab]);
  const open = useMemo(() => data.escalations.filter((item) => item.status === "open").length, [data.escalations]);
  async function logout() { await api("/api/auth/logout", { method: "POST" }).catch(() => undefined); sessionStorage.clear(); signedOut(); }
  return <div className="app-shell"><a className="skip" href="#main-content">Skip to content</a><header className="topbar"><div className="wordmark"><span className="brand small">वा</span><strong>Vaani</strong><em>business desk</em></div><nav aria-label="Workspace">{tabs.map((item) => <button key={item.id} className={tab === item.id ? "active" : ""} onClick={() => setTab(item.id)}>{item.label}{item.id === "escalations" && open > 0 && <span className="count">{open}</span>}</button>)}</nav><button className="text-button" onClick={logout}>Sign out</button></header>
    <main className="workspace" id="main-content"><header className="page-heading"><div><p className="eyebrow">Business operations</p><h1>{tabs.find((item) => item.id === tab)?.label}</h1></div><button className="quiet" onClick={load}>Refresh data</button></header>{error && <div className="error-banner" role="alert"><strong>Couldn’t load the workspace.</strong><span>{error}</span></div>}{loading ? <Loading /> : <>{tab === "inbox" && <Inbox items={data.inbox} selected={selected} select={setSelected} messages={messages} messageHasMore={messageHasMore} loadMessages={() => selected && loadMessages(selected, true)} reload={load} />}{tab === "bookings" && <Bookings items={data.bookings} reload={load} />}{tab === "escalations" && <Escalations items={data.escalations} />}{tab === "deliveries" && <Deliveries items={data.deliveries} />}{tab === "processing" && <Processing items={data.processing} />}{tab === "knowledge" && <Knowledge items={data.knowledge} reload={load} />}{tab === "settings" && <Settings item={data.settings[0]} reload={load} />}{hasMore[tab] && <button className="quiet load-more" onClick={loadMore}>Load older records</button>}</>}</main>
    <footer><span>Vaani operational workspace</span><span>Privacy · Terms · Support</span></footer></div>;
}

function Loading() { return <div className="loading" aria-label="Loading"><span /><span /><span /></div>; }
function Empty({ title, detail }: { title: string; detail: string }) { return <section className="empty"><div>⌁</div><h2>{title}</h2><p>{detail}</p></section>; }

function Inbox({ items, selected, select, messages, messageHasMore, loadMessages, reload }: { items: Item[]; selected: Item | null; select: (item: Item) => void; messages: Item[]; messageHasMore: boolean; loadMessages: () => void; reload: () => Promise<void> }) {
  const [reply, setReply] = useState(""); const [summary, setSummary] = useState(""); const [error, setError] = useState(""); const [busy, setBusy] = useState("");
  if (!items.length) return <Empty title="Inbox is clear" detail="New customer conversations will appear here." />;
  async function action(path: string, body?: object) { if (!selected || busy) return; setBusy(path); setError(""); try { await api(`/api/conversations/${selected._id}/${path}`, { method: "POST", body: body ? JSON.stringify(body) : undefined }); setReply(""); setSummary(""); await reload(); } catch (reason) { setError(errorText(reason)); } finally { setBusy(""); } }
  return <section className="inbox-layout"><div className="conversation-list">{items.map((item) => <button key={item._id} className={selected?._id === item._id ? "selected" : ""} onClick={() => select(item)}><span className={`state-dot ${item.state}`} /><span><strong>Conversation {item._id.slice(-6)}</strong><small>{String(item.channel || "WhatsApp")} · {String(item.state || "bot")}</small></span><time>now</time></button>)}</div>
    <article className="thread"><header><div><p className="eyebrow">Customer thread</p><h2>{selected ? `…${selected._id.slice(-8)}` : "Select a conversation"}</h2></div><span className={`flag ${selected?.state === "human" ? "warm" : ""}`}>{selected?.state === "human" ? "Staff owns this" : "Vaani responding"}</span></header><div className="message-stream">{messages.map((message) => <div key={message._id} className={`message ${message.direction}`}><small>{String(message.direction)}</small><p>{String(message.text || message.type)}</p></div>)}</div>{messageHasMore && <button className="text-button" onClick={loadMessages}>Load older messages</button>}{error && <p className="inline-error">{error}</p>}{selected?.state === "human" ? <div className="composer"><textarea value={reply} onChange={(event) => setReply(event.target.value)} placeholder="Reply as business staff" /><button className="primary" disabled={Boolean(busy) || !reply.trim()} onClick={() => action("reply", { text: reply, request_id: crypto.randomUUID() })}>{busy === "reply" ? "Sending…" : "Send reply"}</button><div className="return-row"><input value={summary} onChange={(event) => setSummary(event.target.value)} placeholder="Resolution summary required to return" /><button className="quiet" disabled={Boolean(busy) || !summary.trim()} onClick={() => action("return", { summary })}>{busy === "return" ? "Returning…" : "Return to Vaani"}</button></div></div> : <button className="quiet takeover" disabled={Boolean(busy)} onClick={() => action("takeover")}>{busy ? "Taking over…" : "Take over conversation"}</button>}</article></section>;
}

function Bookings({ items, reload }: { items: Item[]; reload: () => Promise<void> }) {
  const [error, setError] = useState(""); const [busy, setBusy] = useState(""); if (!items.length) return <Empty title="No appointments yet" detail="Confirmed customer bookings will collect here." />;
  async function cancel(id: string) { if (busy) return; setBusy(id); setError(""); try { await api(`/api/bookings/${id}`, { method: "PATCH", body: JSON.stringify({ status: "cancelled" }) }); await reload(); } catch (reason) { setError(errorText(reason)); } finally { setBusy(""); } }
  return <section className="table-panel">{error && <p className="inline-error">{error}</p>}<table><thead><tr><th>Customer reference</th><th>Service</th><th>Status</th><th>Source</th><th /></tr></thead><tbody>{items.map((item) => <tr key={item._id}><td className="mono">…{String(item.contact_id || "unknown").slice(-8)}</td><td>{String(item.service || "Consultation")}</td><td><span className={`flag ${item.status}`}>{String(item.status)}</span></td><td>{String(item.source || "WhatsApp")}</td><td>{!["cancelled", "completed"].includes(String(item.status)) && <button className="text-button danger" disabled={Boolean(busy)} onClick={() => cancel(item._id)}>{busy === item._id ? "Cancelling…" : "Cancel"}</button>}</td></tr>)}</tbody></table></section>;
}
function Escalations({ items }: { items: Item[] }) { if (!items.length) return <Empty title="No escalations" detail="Customer handoffs will appear here." />; return <section className="escalation-grid">{items.map((item) => <article key={item._id}><header><span className={`flag ${item.status}`}>{String(item.status)}</span><span className={`delivery ${item.notification_status}`}>{String(item.notification_status || "pending")}</span></header><h2>{String(item.reason || "Staff handoff")}</h2><p className="mono">Conversation …{String(item.conversation_id).slice(-8)}</p>{Boolean(item.notification_error) && <p className="inline-error">{String(item.notification_error)}</p>}</article>)}</section>; }
function Deliveries({ items }: { items: Item[] }) { if (!items.length) return <Empty title="No delivery issues" detail="Failed and uncertain sends will appear here without customer details." />; return <section className="table-panel"><table><thead><tr><th>Status</th><th>Channel item</th><th>Attempted</th><th>Reason</th></tr></thead><tbody>{items.map((item) => <tr key={item._id}><td><span className={`flag ${item.state}`}>{String(item.state)}</span></td><td>{String(item.kind || "message")}</td><td>{item.attempted_at ? new Date(String(item.attempted_at)).toLocaleString() : "Not recorded"}</td><td>{String(item.last_error || "Awaiting reconciliation")}</td></tr>)}</tbody></table></section>; }
function Processing({ items }: { items: Item[] }) { if (!items.length) return <Empty title="No processing issues" detail="Inbound work that exhausts retries will appear here without customer details." />; return <section className="table-panel"><table><thead><tr><th>Status</th><th>Attempts</th><th>Failed</th><th>Reason</th></tr></thead><tbody>{items.map((item) => <tr key={item._id}><td><span className={`flag ${item.status}`}>{String(item.status)}</span></td><td>{String(item.attempts || "Not recorded")}</td><td>{item.failed_at ? new Date(String(item.failed_at)).toLocaleString() : "Not recorded"}</td><td>{String(item.fail_reason || "Retry limit reached")}</td></tr>)}</tbody></table></section>; }
function Knowledge({ items, reload }: { items: Item[]; reload: () => Promise<void> }) {
  const [question, setQuestion] = useState(""); const [answer, setAnswer] = useState(""); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  async function save(event: FormEvent<HTMLFormElement>) { event.preventDefault(); if (busy) return; setBusy(true); setError(""); try { await api("/api/kb", { method: "PUT", body: JSON.stringify({ question: question.trim(), answer: answer.trim(), kind: "faq" }) }); setQuestion(""); setAnswer(""); await reload(); } catch (reason) { setError(errorText(reason)); } finally { setBusy(false); } }
  return <section className="knowledge-layout"><form className="knowledge-form" onSubmit={save}><div><p className="eyebrow">Grounded answers</p><h2>Add business knowledge</h2><p>Vaani can cite approved business facts. Updating an existing question replaces its answer.</p></div><label>Customer question<input value={question} onChange={(event) => setQuestion(event.target.value)} required /></label><label>Approved answer<textarea rows={5} value={answer} onChange={(event) => setAnswer(event.target.value)} required /></label>{error && <p className="inline-error">{error}</p>}<button className="primary" disabled={busy || !question.trim() || !answer.trim()}>{busy ? "Saving…" : "Save knowledge"}</button></form><div className="knowledge-list">{items.length ? items.map((item) => <article key={item._id}><p className="eyebrow">{String(item.kind || "faq")}</p><h3>{String(item.question)}</h3><p>{String(item.answer)}</p></article>) : <Empty title="No approved answers" detail="Add the business facts Vaani may use in customer replies." />}</div></section>;
}
function Settings({ item, reload }: { item?: Item; reload: () => Promise<void> }) {
  const [error, setError] = useState(""); const [busy, setBusy] = useState(false); if (!item) return <Empty title="Business record unavailable" detail="Ask an owner to complete onboarding." />;
  async function save(event: FormEvent<HTMLFormElement>) { event.preventDefault(); if (busy) return; setBusy(true); setError(""); const form = new FormData(event.currentTarget); try { await api("/api/settings", { method: "PUT", body: JSON.stringify(Object.fromEntries(form)) }); await reload(); } catch (reason) { setError(errorText(reason)); } finally { setBusy(false); } }
  return <form className="settings-form" onSubmit={save}><div><p className="eyebrow">Public business details</p><h2>Keep answers grounded</h2><p>These details appear in customer replies. Changes require an owner account.</p></div><div className="form-fields"><label>Business name<input name="name" defaultValue={String(item.name || "")} required /></label><label>Nearby landmark<input name="landmark_line" defaultValue={String(item.landmark_line || "")} required /></label><label>Map link<input name="location_pin" defaultValue={String(item.location_pin || "")} required /></label>{error && <p className="inline-error">{error}</p>}<button className="primary" disabled={busy}>{busy ? "Saving…" : "Save business details"}</button></div></form>;
}
export default function App() { const [loggedIn, setLoggedIn] = useState(Boolean(sessionStorage.getItem("vaani_access"))); return loggedIn ? <Dashboard signedOut={() => setLoggedIn(false)} /> : <Login done={() => setLoggedIn(true)} />; }
