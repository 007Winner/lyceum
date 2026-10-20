import { FormEvent, useEffect, useMemo, useState } from "react";

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api";
const philosophers = ["plato", "aristotle", "machiavelli", "hume", "kant"];
const names: Record<string, string> = { plato: "Plato", aristotle: "Aristotle", machiavelli: "Machiavelli", hume: "Hume", kant: "Kant" };

type Message = { role: "user" | "assistant"; content: string };
type State = { session_id: string; philosopher: string; philosopher_index: number; persuaded: string[]; messages: Message[]; budget_requests: number; budget_output_tokens: number; complete: boolean };
type Response = { reply: string; advanced: boolean; belief: string | null; evaluation: { reason: string; persuaded: boolean }; state: State };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, { headers: { "Content-Type": "application/json" }, ...init });
  if (!response.ok) throw new Error((await response.json()).detail ?? "The Lyceum is unavailable.");
  return response.json() as Promise<T>;
}

function App() {
  const [state, setState] = useState<State | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const currentIndex = state?.philosopher_index ?? 0;
  const progress = useMemo(() => Math.round(((state?.persuaded.length ?? 0) / philosophers.length) * 100), [state]);

  useEffect(() => { request<State>("/sessions", { method: "POST" }).then(setState).catch((e) => setError(e.message)); }, []);

  async function send(event: FormEvent) {
    event.preventDefault();
    if (!state || !draft.trim() || busy) return;
    setBusy(true); setError("");
    try {
      const result = await request<Response>(`/sessions/${state.session_id}/messages`, { method: "POST", body: JSON.stringify({ message: draft }) });
      setState(result.state); setDraft("");
    } catch (e) { setError(e instanceof Error ? e.message : "The conversation stalled."); }
    finally { setBusy(false); }
  }

  return <div className="shell">
    <header><div className="brand"><span className="seal">L</span><div><p className="eyebrow">A philosophical conversation game</p><h1>The Lyceum</h1></div></div><div className="counter"><span>RECONSIDERATIONS</span><strong>{state?.persuaded.length ?? 0} / 5</strong></div></header>
    <main>
      <section className="map-panel"><div className="panel-label">THE HALL OF MINDS</div><div className="map"><div className="room-grid" />{philosophers.map((person, index) => <div className={`node node-${index} ${index === currentIndex ? "active" : ""} ${state?.persuaded.includes(person) ? "won" : ""}`} key={person}><span className="node-dot">{state?.persuaded.includes(person) ? "✓" : index + 1}</span><span>{names[person]}</span></div>)}<div className="player"><span>YOU</span><i /></div><div className="table" /></div><div className="map-caption"><span className="status-dot" /> You are in the room with <strong>{names[state?.philosopher ?? "plato"]}</strong></div></section>
      <section className="dialogue-panel"><div className="dialogue-head"><div><p className="eyebrow">THE CURRENT interlocutor</p><h2>{names[state?.philosopher ?? "plato"]}</h2></div><div className="progress"><div><span>THE PATH</span><b>{progress}%</b></div><div className="bar"><i style={{ width: `${progress}%` }} /></div></div></div><div className="transcript">{state?.messages.map((message, index) => <div className={`message ${message.role}`} key={index}><div className="avatar">{message.role === "assistant" ? names[state?.philosopher ?? "plato"].slice(0, 1) : "Y"}</div><div><span className="speaker">{message.role === "assistant" ? names[state?.philosopher ?? "plato"] : "You"}</span><p>{message.content}</p></div></div>)}{busy && <div className="thinking">The philosopher considers your argument…</div>}</div><form onSubmit={send} className="composer"><textarea value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Offer a question, objection, or counterexample…" rows={3} disabled={busy || state?.complete} /><div className="compose-foot"><span>Make a case worth reconsidering.</span><button type="submit" disabled={busy || !draft.trim() || state?.complete}>{busy ? "Thinking…" : "Speak"} <b>↗</b></button></div></form>{error && <div className="error">{error}</div>}{state?.complete && <div className="complete">The five minds have reconsidered. The Lyceum is yours to leave changed.</div>}</section>
    </main>
    <footer><span>PORTKEY · {"gpt-6-luna"}</span><span>Every concession must be earned by argument.</span></footer>
  </div>;
}
export default App;
