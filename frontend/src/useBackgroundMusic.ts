import { useCallback, useEffect, useRef, useState } from "react";

export type MusicPhilosopher = "plato" | "aristotle" | "machiavelli" | "hume" | "kant";

export const MUSIC_TRACKS: Record<MusicPhilosopher, string> = {
  plato: "/audio/plato.mp3",
  aristotle: "/audio/aristotle.mp3",
  machiavelli: "/audio/machiavelli.mp3",
  hume: "/audio/hume.mp3",
  kant: "/audio/kant.mp3",
};

const DEFAULT_VOLUME = 0.22;
// Versioned keys reset preferences saved by the earlier unreliable player so
// the hosted site starts audible instead of inheriting a stuck mute/zero volume.
const VOLUME_KEY = "lyceum-music-volume-v2";
const MUTED_KEY = "lyceum-music-muted-v2";

type ActiveTrack = { philosopher: MusicPhilosopher; audio: HTMLAudioElement };

function readVolume() {
  const stored = Number(localStorage.getItem(VOLUME_KEY));
  return Number.isFinite(stored) && stored >= 0 && stored <= 1 ? stored : DEFAULT_VOLUME;
}

function readMuted() {
  return localStorage.getItem(MUTED_KEY) === "true";
}

class AudioManager {
  private active: ActiveTrack | null = null;
  private audios = new Set<HTMLAudioElement>();
  private frame: number | null = null;
  private volume: number;
  private muted: boolean;
  private onMissing: (philosopher: MusicPhilosopher) => void;
  private onBlocked: () => void;

  constructor(onMissing: (philosopher: MusicPhilosopher) => void, onBlocked: () => void) {
    this.volume = readVolume();
    this.muted = readMuted();
    this.onMissing = onMissing;
    this.onBlocked = onBlocked;
  }

  private level() {
    return this.muted ? 0 : this.volume;
  }

  private cancelFade() {
    if (this.frame !== null) {
      cancelAnimationFrame(this.frame);
      this.frame = null;
    }
  }

  private safelyPlay(audio: HTMLAudioElement) {
    // Explicitly load the asset before playing. This avoids a race on hosted
    // browsers where the first play request can arrive before the MP3 has
    // been attached to the media element's resource selection algorithm.
    if (audio.readyState === HTMLMediaElement.HAVE_NOTHING) audio.load();
    const attempt = audio.play();
    attempt.catch(() => this.onBlocked());
  }

  private silenceStale(keep: HTMLAudioElement | null) {
    for (const audio of this.audios) {
      if (audio === keep) continue;
      audio.pause();
      audio.currentTime = 0;
      audio.volume = 0;
      this.audios.delete(audio);
    }
  }

  play(philosopher: MusicPhilosopher, duration = 1500) {
    if (this.active?.philosopher === philosopher) {
      if (this.active.audio.paused) this.safelyPlay(this.active.audio);
      return;
    }

    this.cancelFade();
    const old = this.active;
    this.silenceStale(old?.audio ?? null);
    const next = new Audio(MUSIC_TRACKS[philosopher]);
    next.loop = true;
    next.preload = "auto";
    next.volume = 0;
    next.addEventListener("error", () => this.onMissing(philosopher), { once: true });
    this.audios.add(next);
    this.active = { philosopher, audio: next };
    this.safelyPlay(next);

    const started = performance.now();
    const oldVolume = old?.audio.volume ?? 0;
    const fade = (now: number) => {
      const progress = Math.min(1, (now - started) / duration);
      next.volume = this.level() * progress;
      if (old) old.audio.volume = oldVolume * (1 - progress);
      if (progress < 1) {
        this.frame = requestAnimationFrame(fade);
      } else {
        if (old) {
          old.audio.pause();
          old.audio.currentTime = 0;
          this.audios.delete(old.audio);
        }
        this.frame = null;
      }
    };
    this.frame = requestAnimationFrame(fade);
  }

  stop(duration = 2000) {
    if (!this.active) return;
    this.cancelFade();
    const track = this.active;
    this.silenceStale(track.audio);
    const started = performance.now();
    const initial = track.audio.volume;
    const fade = (now: number) => {
      const progress = Math.min(1, (now - started) / duration);
      track.audio.volume = initial * (1 - progress);
      if (progress < 1) {
        this.frame = requestAnimationFrame(fade);
      } else {
        track.audio.pause();
        track.audio.currentTime = 0;
        this.audios.delete(track.audio);
        if (this.active === track) this.active = null;
        this.frame = null;
      }
    };
    this.frame = requestAnimationFrame(fade);
  }

  setVolume(volume: number) {
    this.volume = volume;
    localStorage.setItem(VOLUME_KEY, String(volume));
    if (this.active && this.frame === null && !this.muted) this.active.audio.volume = volume;
  }

  setMuted(muted: boolean) {
    this.muted = muted;
    localStorage.setItem(MUTED_KEY, String(muted));
    if (this.active && this.frame === null) this.active.audio.volume = this.level();
  }

  dispose() {
    this.cancelFade();
    for (const audio of this.audios) {
      audio.pause();
      audio.src = "";
    }
    this.audios.clear();
    this.active = null;
  }
}

export function useBackgroundMusic(
  philosopher: MusicPhilosopher | null,
  shouldPlay: boolean,
  fadeOut = false,
) {
  const [volume, setVolumeState] = useState(() => readVolume());
  const [muted, setMutedState] = useState(() => readMuted());
  const [missing, setMissing] = useState<MusicPhilosopher | null>(null);
  const [blocked, setBlocked] = useState(false);
  const manager = useRef<AudioManager | null>(null);

  // Initialize synchronously so a very fast START GAME click cannot beat the
  // effect that would otherwise create the audio manager.
  if (!manager.current) {
    manager.current = new AudioManager((track) => setMissing(track), () => setBlocked(true));
  }

  useEffect(() => {
    return () => manager.current?.dispose();
  }, []);

  // A deployment may be opened without a user gesture. If the browser blocks
  // that first autoplay attempt, retry the current track on the first real
  // interaction anywhere in the document (the game already exposes the same
  // retry through its music control).
  useEffect(() => {
    const retry = () => {
      if (manager.current && philosopher && shouldPlay && !fadeOut) {
        setBlocked(false);
        manager.current.play(philosopher);
      }
    };
    window.addEventListener("pointerdown", retry, { passive: true });
    window.addEventListener("keydown", retry, { passive: true });
    return () => {
      window.removeEventListener("pointerdown", retry);
      window.removeEventListener("keydown", retry);
    };
  }, [fadeOut, philosopher, shouldPlay]);

  useEffect(() => {
    if (fadeOut || !shouldPlay || !philosopher) manager.current?.stop();
    else manager.current?.play(philosopher);
  }, [fadeOut, philosopher, shouldPlay]);

  const startNow = useCallback((track: MusicPhilosopher) => {
    setBlocked(false);
    manager.current?.play(track);
  }, []);
  const resume = useCallback(() => {
    if (philosopher) {
      setBlocked(false);
      manager.current?.play(philosopher);
    }
  }, [philosopher]);
  const setVolume = useCallback((next: number) => {
    setVolumeState(next);
    manager.current?.setVolume(next);
  }, []);
  const setMuted = useCallback((next: boolean) => {
    setMutedState(next);
    manager.current?.setMuted(next);
  }, []);

  return { volume, muted, missing, blocked, startNow, resume, setVolume, setMuted };
}
