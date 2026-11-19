import { useEffect, useMemo, useState } from "react";
import {
  Activity, ArrowUp, Bot, Check, ChevronDown, CircleHelp, Command,
  FileText, Menu, MessageSquare, MoreHorizontal, Plus, Search, Settings2,
  ShieldCheck, Sparkles, Users, X,
} from "lucide-react";

type Mode = "chat" | "council";
type Message = { id: number; role: "user" | "assistant"; text: string };

const starterPrompts = [
  "Compare several approaches to this problem",
  "Find weaknesses in my reasoning",
  "Build a plan and identify unknowns",
];

export default function App() {
  const [mode, setMode] = useState<Mode>("council");
  const [prompt, setPrompt] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [menuOpen, setMenuOpen] = useState(false);
  const [apiState, setApiState] = useState<"checking" | "online" | "offline">("checking");
  const [mobileNav, setMobileNav] = useState(false);

  useEffect(() => {
    let active = true;
    fetch("/api/v1/health/live")
      .then((response) => {
        if (!active) return;
        setApiState(response.ok ? "online" : "offline");
      })
      .catch(() => active && setApiState("offline"));
    return () => { active = false; };
  }, []);

  const title = useMemo(() => mode === "council" ? "Council room" : "New conversation", [mode]);

  function sendMessage(value = prompt) {
    const text = value.trim();
    if (!text) return;
    setMessages((current) => [
      ...current,
      { id: Date.now(), role: "user", text },
    ]);
    setPrompt("");
  }

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileNav ? "sidebar-open" : ""}`}>
        <div className="brand-row">
          <div className="brand-mark"><Sparkles size={19} /></div>
          <div className="brand-name">YJ64 <span>COUNCIL</span></div>
          <button className="icon-button mobile-close" aria-label="Close navigation" onClick={() => setMobileNav(false)}><X size={18} /></button>
        </div>
        <button className="new-chat" onClick={() => { setMessages([]); setMode("chat"); setMobileNav(false); }}>
          <Plus size={17} /> New conversation <span>⌘ K</span>
        </button>
        <div className="nav-caption">WORKSPACE</div>
        <button className={`nav-item ${mode === "council" ? "active" : ""}`} onClick={() => { setMode("council"); setMobileNav(false); }}>
          <Users size={17} /> Council room <span className="nav-count">1</span>
        </button>
        <button className={`nav-item ${mode === "chat" ? "active" : ""}`} onClick={() => { setMode("chat"); setMobileNav(false); }}>
          <MessageSquare size={17} /> Individual chats
        </button>
        <button className="nav-item" disabled><FileText size={17} /> Research library <span className="soon">SOON</span></button>
        <div className="sidebar-bottom">
          <div className="workspace-card">
            <div className="workspace-icon">Y</div>
            <div><strong>Personal workspace</strong><small>Local preview</small></div>
            <MoreHorizontal size={17} />
          </div>
          <button className="nav-item" disabled><Settings2 size={17} /> Settings</button>
          <div className="user-row"><div className="avatar">G</div><div><strong>Guest workspace</strong><small>Authentication not connected</small></div><ChevronDown size={15} /></div>
        </div>
      </aside>

      {mobileNav && <button className="scrim" aria-label="Close menu" onClick={() => setMobileNav(false)} />}

      <main className="main-area">
        <header className="topbar">
          <div className="top-left">
            <button className="icon-button mobile-menu" aria-label="Open navigation" onClick={() => setMobileNav(true)}><Menu size={19} /></button>
            <span className="breadcrumb">Workspace</span><span className="crumb-sep">/</span><strong>{title}</strong>
          </div>
          <div className="top-actions">
            <div className={`api-status ${apiState}`}><span /> API {apiState === "checking" ? "checking" : apiState}</div>
            <button className="icon-button" aria-label="Help"><CircleHelp size={18} /></button>
            <button className="icon-button" aria-label="More options" onClick={() => setMenuOpen(!menuOpen)}><MoreHorizontal size={19} /></button>
            {menuOpen && <div className="top-menu"><div><ShieldCheck size={15} /> Privacy & permissions</div><div><Activity size={15} /> System status</div></div>}
          </div>
        </header>

        <section className="content">
          <div className="mode-switch">
            <button className={mode === "chat" ? "selected" : ""} onClick={() => setMode("chat")}><MessageSquare size={15} /> Individual chat</button>
            <button className={mode === "council" ? "selected" : ""} onClick={() => setMode("council")}><Users size={15} /> Council</button>
          </div>

          {messages.length === 0 ? (
            <div className="welcome">
              <div className="eyebrow"><span className="eyebrow-line" /> MULTI-MODEL RESEARCH SPACE</div>
              <div className="hero-icon"><Sparkles size={25} /></div>
              <h1>{mode === "council" ? <>Think beyond<br /><em>one perspective.</em></> : <>A clear space<br /><em>to think.</em></>}</h1>
              <p className="intro">{mode === "council"
                ? "Bring a difficult question to the Council. Independent perspectives, constructive critique and evidence — without confusing agreement with truth."
                : "Start a focused conversation. Connect a model provider when API connections become available."}</p>
              <div className="prompt-grid">
                {starterPrompts.map((item) => <button key={item} className="prompt-card" onClick={() => sendMessage(item)}><span>{item}</span><ArrowUp size={15} /></button>)}
              </div>
              <div className="participants">
                <div className="participant-icon"><Bot size={15} /></div>
                <div><strong>{mode === "council" ? "Council participants" : "Model connection"}</strong><span>{mode === "council" ? "No model providers connected yet" : "Provider setup is coming next"}</span></div>
                <span className="pending-pill">NOT CONNECTED</span>
              </div>
            </div>
          ) : (
            <div className="conversation">
              <div className="conversation-heading"><span className="live-dot" /> LOCAL DRAFT</div>
              {messages.map((message) => <div className={`message ${message.role}`} key={message.id}><div className="message-avatar">{message.role === "user" ? "G" : <Bot size={17} />}</div><div><strong>{message.role === "user" ? "You" : "Browser Council"}</strong><p>{message.text}</p></div></div>)}
              <div className="draft-note"><ShieldCheck size={16} /> This is a local interface preview. Messages are not sent to an AI provider or saved to a server yet.</div>
            </div>
          )}

          <div className="composer-wrap">
            <div className="composer">
              <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); sendMessage(); } }} placeholder={mode === "council" ? "Ask the Council a question..." : "Message..."} rows={2} />
              <div className="composer-bottom">
                <div className="composer-tools"><button disabled><Plus size={16} /> Attach</button><button disabled><Search size={15} /> Research</button><button disabled><Command size={14} /> Tools</button></div>
                <button className="send-button" onClick={() => sendMessage()} disabled={!prompt.trim()} aria-label="Add local draft message"><ArrowUp size={18} /></button>
              </div>
            </div>
            <div className="composer-foot"><span>Shift + Enter for a new line</span><span><Check size={12} /> Private workspace preview</span></div>
          </div>
        </section>
        <footer className="footer-note">YJ64 BROWSER COUNCIL <span>·</span> INDEPENDENT THINKING, VERIFIED EVIDENCE</footer>
      </main>
    </div>
  );
}
