import { FormEvent, useEffect, useRef, useState } from "react";
import { MusicPhilosopher, useBackgroundMusic } from "./useBackgroundMusic";

const API = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8001/api";
const CAMPAIGN_STORAGE_KEY = "lyceum_campaign_session";
const order: MusicPhilosopher[] = ["plato", "aristotle", "machiavelli", "hume", "kant"];
const info: Record<string, [string, string, string]> = {
  plato: ["Plato", "athens", "plato"], aristotle: ["Aristotle", "lyceum", "aristotle"],
  machiavelli: ["Machiavelli", "florence", "machiavelli"], hume: ["Hume", "edinburgh", "hume"],
  kant: ["Kant", "konigsburg", "kant"],
};
const HOW_TO_PLAY = [
  "Welcome to The Lyceum, where the greatest minds in philosophy are waiting to meet you.",
  "Your journey will take you through five encounters with Plato, Aristotle, Machiavelli, David Hume, and Immanuel Kant.",
  "Your objective is simple: change their minds.",
  "Speak freely with each philosopher. Challenge their arguments, question their assumptions, and construct arguments of your own. There are no predetermined dialogue options, secret passwords, or single correct answers.",
  "But persuasion will not come easily. These thinkers will defend their convictions, expose weaknesses in your reasoning, and demand more than superficial agreement.",
  "To advance, you must persuade each philosopher to genuinely reconsider a significant philosophical belief. An independent evaluator determines whether you've succeeded.",
  "Five philosophers. Five minds to change.", "Let the dialogue begin.",
];

type Msg = { role: "user" | "assistant"; content: string; speaker?: string };
type State = {
  session_id: string; philosopher: string; philosopher_index: number; persuaded: string[]; surrendered: string[];
  messages: Msg[]; complete: boolean; is_revisit: boolean; campaign_session_id?: string | null;
  victory_pending: boolean; transition_pending: boolean;
};
type Phase = "conversation" | "final_concession" | "surrender_pending" | "victory" | "transitioning";

async function req<T>(path: string, init?: RequestInit) {
  const response = await fetch(API + path, { headers: { "Content-Type": "application/json" }, ...init });
  if (!response.ok) { const body = await response.json().catch(() => ({})); throw Error(body.detail ?? "The Lyceum is unavailable."); }
  return response.json() as Promise<T>;
}
function rememberCampaign(state: State) { try { localStorage.setItem(CAMPAIGN_STORAGE_KEY, state.session_id); } catch { /* optional storage */ } }
function clearRememberedCampaign() { try { localStorage.removeItem(CAMPAIGN_STORAGE_KEY); } catch { /* optional storage */ } }
function rememberedCampaignId() { try { return localStorage.getItem(CAMPAIGN_STORAGE_KEY); } catch { return null; } }
function phaseFor(state: State): Phase { if (state.victory_pending) return "final_concession"; if (state.transition_pending) return "surrender_pending"; return "conversation"; }

function ProgressionTree({ campaign, onRevisit }: { campaign: State; onRevisit: (philosopher: MusicPhilosopher) => void }) {
  const nextIndex = campaign.complete ? -1 : order.findIndex((name, index) => index >= campaign.philosopher_index && !campaign.persuaded.includes(name) && !campaign.surrendered.includes(name));
  const revisitUnlocked = !campaign.victory_pending && !campaign.transition_pending;
  return <nav className="progression" aria-label="Philosopher progression">{order.map((name, index) => {
    const completed = campaign.persuaded.includes(name); const available = completed || campaign.surrendered.includes(name); const revisitable = available && revisitUnlocked; const current = !available && index === nextIndex;
    return <span className="progression-step" key={name}><button type="button" className={`progression-node ${available ? "completed" : current ? "current" : "locked"}${available && !revisitUnlocked ? " pending" : ""}`} disabled={!revisitable} onClick={() => revisitable && onRevisit(name)} aria-label={`${info[name][0]}${revisitable ? ", available; revisit" : available ? ", available after continue" : current ? ", current encounter" : ", locked"}`}><img src={`/assets/philosophers/${info[name][2]}.png`} alt="" /><span>{info[name][0]}</span></button>{index < order.length - 1 && <i className={`progression-line ${index < nextIndex || available ? "lit" : ""}`} aria-hidden="true" />}</span>;
  })}</nav>;
}

export default function App() {
  const [state, setState] = useState<State | null>(null); const [campaign, setCampaign] = useState<State | null>(null);
  const transcript = useRef<HTMLDivElement>(null); const stickToBottom = useRef(true); const encounterRef = useRef(0); const transitionInFlight = useRef(false);
  const [shown, setShown] = useState<State | null>(null); const [displayed, setDisplayed] = useState<Msg[]>([]); const [phase, setPhase] = useState<Phase>("conversation");
  const [draft, setDraft] = useState(""); const [busy, setBusy] = useState(false); const [err, setErr] = useState(""); const [title, setTitle] = useState(true); const [restoring, setRestoring] = useState(true); const [howToPlay, setHowToPlay] = useState(false); const [optionsOpen, setOptionsOpen] = useState(false);
  const p = (shown?.philosopher ?? "plato") as MusicPhilosopher, c = info[p], last = displayed[displayed.length - 1];
  const activePhilosopher = (shown?.philosopher ?? null) as MusicPhilosopher | null;
  const music = useBackgroundMusic(activePhilosopher, !title && !(state?.complete && phase === "victory"), Boolean(state?.complete && phase === "victory"));

  useEffect(() => { const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") { setHowToPlay(false); setOptionsOpen(false); } }; window.addEventListener("keydown", onKey); return () => window.removeEventListener("keydown", onKey); }, []);
  useEffect(() => {
    const savedId = rememberedCampaignId();
    if (!savedId) { setRestoring(false); return; }
    encounterRef.current += 1;
    req<State>(`/sessions/${savedId}`).then(saved => { if (saved.is_revisit) throw Error("Saved campaign session is unavailable."); setCampaign(saved); setState(saved); setShown(saved); setDisplayed(saved.messages); setPhase(phaseFor(saved)); setTitle(true); }).catch(() => clearRememberedCampaign()).finally(() => setRestoring(false));
  }, []);
  useEffect(() => { const element = transcript.current; if (element && stickToBottom.current) element.scrollTop = element.scrollHeight; }, [displayed.length, last?.content]);

  function applyCampaign(next: State) { setCampaign(next); setState(next); setShown(next); setDisplayed(next.messages); setPhase(phaseFor(next)); rememberCampaign(next); }
  async function start() {
    music.startNow("plato"); setBusy(true); setErr(""); stickToBottom.current = true; encounterRef.current += 1;
    try { const next = await req<State>("/sessions", { method: "POST" }); applyCampaign(next); setTitle(false); } catch (error) { setErr(String(error)); } finally { setBusy(false); }
  }
  function continueGame() {
    if (!campaign) return;
    music.startNow(campaign.philosopher as MusicPhilosopher);
    encounterRef.current += 1;
    setState(campaign); setShown(campaign); setDisplayed(campaign.messages); setPhase(phaseFor(campaign)); setDraft(""); setErr(""); setTitle(false);
  }
  async function newGame() {
    setOptionsOpen(false);
    if (!window.confirm("Start a new game? Your current campaign will be replaced.")) return;
    await start();
  }
  async function send(event: FormEvent) {
    event.preventDefault(); const canChat = phase === "conversation" || (phase === "final_concession" && Boolean(state?.victory_pending));
    if (!state || !shown || !draft.trim() || busy || !canChat) return;
    const text = draft, outgoing = shown.philosopher, encounter = encounterRef.current; setDraft(""); setBusy(true);
    try {
      const response = await req<{ state: State; advanced: boolean }>(`/sessions/${state.session_id}/messages`, { method: "POST", body: JSON.stringify({ message: text }) });
      if (encounter !== encounterRef.current) return;
      const reply = response.state.messages[response.state.messages.length - 1]; const nextMessages: Msg[] = [...displayed, { role: "user", content: text }, { role: "assistant", content: reply?.content ?? "", speaker: outgoing }];
      setState(response.state); setShown(response.advanced ? { ...response.state, philosopher: outgoing } : response.state); setDisplayed(nextMessages);
      if (!response.state.is_revisit) { const nextCampaign = { ...response.state, messages: nextMessages }; setCampaign(nextCampaign); rememberCampaign(nextCampaign); }
      if (response.advanced) setPhase(response.state.victory_pending ? "final_concession" : "surrender_pending");
    } catch (error) { if (encounter === encounterRef.current) { setDraft(text); setErr(String(error)); } } finally { if (encounter === encounterRef.current) setBusy(false); }
  }
  async function continueVictory() {
    if (phase === "final_concession" && state?.victory_pending) { setPhase("victory"); return; }
    if ((phase !== "surrender_pending" && phase !== "victory") || !state || state.is_revisit || transitionInFlight.current) return;
    transitionInFlight.current = true; const sessionId = state.session_id, surrendering = phase === "surrender_pending", encounter = ++encounterRef.current; setErr(""); setPhase("transitioning");
    try { const response = await req<{ state: State }>(`/sessions/${sessionId}/continue`, { method: "POST" }); if (encounter !== encounterRef.current) return; stickToBottom.current = true; applyCampaign(response.state); setDraft(""); setTitle(response.state.complete); }
    catch (error) { if (encounter === encounterRef.current) { setErr(String(error)); setPhase(surrendering ? "surrender_pending" : "victory"); } } finally { transitionInFlight.current = false; if (encounter === encounterRef.current) setBusy(false); }
  }
  async function revisit(philosopher: MusicPhilosopher) {
    if (!campaign || busy || campaign.is_revisit) return; const encounter = ++encounterRef.current; setBusy(true); setErr("");
    try { const response = await req<{ state: State }>(`/sessions/${campaign.session_id}/revisit/${philosopher}`, { method: "POST" }); if (encounter !== encounterRef.current) return; const next = response.state; setState(next); setShown(next); setDisplayed(next.messages); setPhase("conversation"); setTitle(false); }
    catch (error) { if (encounter === encounterRef.current) setErr(String(error)); } finally { if (encounter === encounterRef.current) setBusy(false); }
  }
  async function returnToJourney() {
    if (!state?.is_revisit || busy) return; const encounter = ++encounterRef.current; setBusy(true); setErr("");
    try { const response = await req<{ state: State }>(`/sessions/${state.session_id}/return`, { method: "POST" }); if (encounter !== encounterRef.current) return; applyCampaign(response.state); setTitle(false); }
    catch (error) { if (encounter === encounterRef.current) setErr(String(error)); } finally { if (encounter === encounterRef.current) setBusy(false); }
  }

  if (restoring) return <div className="title-screen"><div className="title-card"><small>✦ RESTORING YOUR JOURNEY ✦</small></div></div>;
  if (title) return <div className="title-screen"><div className="title-card"><small>✦ A PHILOSOPHICAL RPG ✦</small><h1>THE<br /><em>LYCEUM</em></h1><p>Five philosophers. Five conversations.<br />One question: can you change a great mind?</p>{campaign && <button onClick={continueGame} disabled={busy}>▶ CONTINUE GAME</button>}<button onClick={start} disabled={busy}>▶ START GAME</button><button className="how-to-play-button" onClick={() => setHowToPlay(true)}>HOW TO PLAY</button>{err && <b>{err}</b>}{howToPlay && <div className="how-to-play-overlay" role="dialog" aria-modal="true" aria-labelledby="how-to-play-title"><section className="how-to-play-panel"><h2 id="how-to-play-title">HOW TO PLAY</h2>{HOW_TO_PLAY.map((paragraph, index) => <p key={index} className={index === 2 || index === 6 ? "emphasis" : ""}>{paragraph}</p>)}<button onClick={() => setHowToPlay(false)}>BACK</button></section></div>}</div></div>;

  const placeholder = !last ? `${c[0]} awaits your argument.` : ""; const canChat = (!state?.complete || Boolean(state?.victory_pending)) && (phase === "conversation" || (phase === "final_concession" && Boolean(state?.victory_pending)));
  return <div className={`game scene-${p} phase-${phase}`} style={{ backgroundImage: `url(/assets/backgrounds/${c[1]}.png)` }}><main>{campaign && <ProgressionTree campaign={campaign} onRevisit={revisit} />}{state?.is_revisit && <button type="button" className="return-journey" onClick={returnToJourney} disabled={busy}>RETURN TO JOURNEY</button>}{state?.complete && !state?.victory_pending && !state?.is_revisit && <aside className="completion-banner">THE LYCEUM IS COMPLETE · SELECT A PHILOSOPHER TO REVISIT</aside>}<div className="nameplate">{c[0]}<small>ENCOUNTER {order.indexOf(p) + 1} / 5</small></div><div className="music-control" aria-label="Background music controls"><button type="button" className="music-toggle" onClick={() => { if (music.requested) { if (music.playing) music.setRequested(false); else music.resume(); } else music.setRequested(true); }} aria-pressed={music.playing} title={music.playing ? "Mute music" : music.requested ? "Retry music playback" : "Turn music on"}>{music.playing ? "MUSIC ON" : "MUSIC OFF"}</button><label><span className="sr-only">Music volume</span><input type="range" min="0" max="1" step="0.01" value={music.volume} onChange={event => music.setVolume(Number(event.target.value))} aria-label="Music volume" /></label>{music.missing && <small className="music-status">ADD {music.missing}.MP3</small>}{music.blocked && music.requested && <small className="music-status">CLICK TO PLAY</small>}<div className="options-wrap"><button type="button" className="options-toggle" onClick={() => setOptionsOpen(open => !open)} aria-expanded={optionsOpen} aria-haspopup="menu">⚙ OPTIONS</button>{optionsOpen && <div className="options-menu" role="menu"><button type="button" role="menuitem" onClick={() => setOptionsOpen(false)}>CONTINUE GAME</button><button type="button" role="menuitem" onClick={newGame}>NEW GAME</button></div>}</div></div><img className={`philosopher ${busy ? "thinking" : ""}`} src={`/assets/philosophers/${c[2]}.png`} /><img className="player" src="/assets/player/player_silhouette.png" /><section className="dialogue"><div ref={transcript} className="transcript" onScroll={event => { const element = event.currentTarget; stickToBottom.current = element.scrollHeight - element.scrollTop - element.clientHeight < 40; }}>{displayed.length ? displayed.map((message, index) => { const speaker = message.role === "user" ? "YOU" : message.speaker ? info[message.speaker][0] : c[0]; return <article key={`${index}-${message.role}`} className={message.role}><b>{speaker}</b><p>{message.content}</p></article>; }) : <article className="placeholder"><b>{c[0]}</b><p>{placeholder}</p></article>}{busy && <i role="status">{displayed.length ? "…" : "Thinking…"}</i>}</div><form onSubmit={send}><textarea value={draft} onChange={event => setDraft(event.target.value)} onKeyDown={event => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} placeholder="Stake your claim…" disabled={busy || !canChat} /><button disabled={busy || !canChat || !draft.trim()}>SPEAK ↗</button></form>{(phase === "final_concession" || phase === "surrender_pending") && !state?.is_revisit && <button className="continue" disabled={busy} onClick={continueVictory}>CONTINUE</button>}</section></main>{err && <aside className="error">{err}</aside>}{phase === "victory" && <div className="modal victory"><div><h2>{c[0].toUpperCase()} WAS PERSUADED!</h2><p>A great mind has reconsidered.</p><button onClick={continueVictory}>CONTINUE</button></div></div>}{phase === "transitioning" && <div className="modal transition"><div><small>THE NEXT ENCOUNTER</small><h2>{state?.complete ? "THE LYCEUM" : info[state?.philosopher ?? "plato"][0].toUpperCase()}</h2></div></div>}</div>;
}
