import { useCallback, useEffect, useRef, useState } from "react";

export type MusicPhilosopher = "plato" | "aristotle" | "machiavelli" | "hume" | "kant";

export const MUSIC_TRACKS: Record<MusicPhilosopher, string> = {
  plato: "/audio/plato.mp3?v=2",
  aristotle: "/audio/aristotle.mp3",
  machiavelli: "/audio/machiavelli.mp3",
  hume: "/audio/hume.mp3",
  kant: "/audio/kant.mp3",
};

const DEFAULT_VOLUME = 0.22;
const VOLUME_KEY = "lyceum-music-volume-v2";
const MUTED_KEY = "lyceum-music-muted-v2";

type PlaybackStatus = {
  playing: boolean;
  blocked: boolean;
  missing: MusicPhilosopher | null;
};

function readVolume() {
  const saved = localStorage.getItem(VOLUME_KEY);
  if (saved === null) return DEFAULT_VOLUME;
  const volume = Number(saved);
  return Number.isFinite(volume) && volume >= 0 && volume <= 1 ? volume : DEFAULT_VOLUME;
}

function readRequested() {
  return localStorage.getItem(MUTED_KEY) === "false";
}

/** Owns the only audio element used by the app and keeps requested and actual playback separate. */
class AudioManager {
  private readonly audio = new Audio();
  private track: MusicPhilosopher | null = null;
  private requested = false;
  private available = false;
  private disposed = false;
  private generation = 0;
  private volume = readVolume();
  private status: PlaybackStatus = { playing: false, blocked: false, missing: null };

  constructor(private readonly onStatus: (status: PlaybackStatus) => void, requested: boolean) {
    this.requested = requested;
    this.audio.loop = true;
    this.audio.preload = "auto";
    this.audio.volume = this.volume;
    this.audio.addEventListener("playing", this.onPlaying);
    this.audio.addEventListener("pause", this.onPause);
    this.audio.addEventListener("waiting", this.onWaiting);
    this.audio.addEventListener("error", this.onError);
  }

  private publish(next: Partial<PlaybackStatus>) {
    this.status = { ...this.status, ...next };
    this.onStatus(this.status);
  }

  private onPlaying = () => {
    if (this.requested && this.available && !this.disposed) {
      this.publish({ playing: true, blocked: false, missing: null });
    } else {
      this.audio.pause();
    }
  };

  private onPause = () => this.publish({ playing: false });
  private onWaiting = () => this.publish({ playing: false });
  private onError = () => {
    if (this.track) this.publish({ playing: false, missing: this.track });
  };

  private attemptPlay() {
    if (!this.requested || !this.available || !this.track || this.disposed) return;
    const attemptGeneration = ++this.generation;
    this.publish({ blocked: false, missing: null });
    try {
      void this.audio.play().catch(() => {
        if (attemptGeneration === this.generation && this.requested && this.available) {
          this.publish({ playing: false, blocked: true });
        }
      });
    } catch {
      if (attemptGeneration === this.generation) this.publish({ playing: false, blocked: true });
    }
  }

  configure(track: MusicPhilosopher | null, available: boolean, fadeOut: boolean) {
    this.disposed = false;
    const trackChanged = track !== this.track;
    const becameAvailable = available && track !== null && !this.available;
    this.available = available && track !== null;

    if (trackChanged) {
      this.generation += 1;
      this.audio.pause();
      this.track = track;
      this.publish({ playing: false, blocked: false, missing: null });
      if (track) {
        this.audio.src = MUSIC_TRACKS[track];
        this.audio.load();
      } else {
        this.audio.removeAttribute("src");
        this.audio.load();
      }
    }

    if (!this.available) {
      if (fadeOut && !this.audio.paused) {
        // The victory screen retains its existing short fade; user-requested OFF is always immediate.
        const startVolume = this.audio.volume;
        const started = performance.now();
        const generation = ++this.generation;
        const fade = (now: number) => {
          if (generation !== this.generation) return;
          const progress = Math.min(1, (now - started) / 2000);
          this.audio.volume = startVolume * (1 - progress);
          if (progress < 1) requestAnimationFrame(fade);
          else {
            this.audio.pause();
            this.audio.volume = this.volume;
          }
        };
        requestAnimationFrame(fade);
      } else {
        this.generation += 1;
        this.audio.pause();
        this.audio.volume = this.volume;
        this.publish({ playing: false });
      }
      return;
    }

    this.audio.volume = this.volume;
    if (this.requested && (trackChanged || becameAvailable)) this.attemptPlay();
  }

  startNow(track: MusicPhilosopher) {
    this.configure(track, true, false);
  }

  setRequested(requested: boolean) {
    this.requested = requested;
    localStorage.setItem(MUTED_KEY, String(!requested));
    if (!requested) {
      this.generation += 1;
      this.audio.pause();
      this.audio.volume = this.volume;
      this.publish({ playing: false, blocked: false });
    } else {
      this.attemptPlay();
    }
  }

  retry() {
    if (this.requested && !this.status.playing) this.attemptPlay();
  }

  setVolume(volume: number) {
    this.volume = Math.max(0, Math.min(1, volume));
    localStorage.setItem(VOLUME_KEY, String(this.volume));
    this.audio.volume = this.volume;
  }

  dispose() {
    this.disposed = true;
    this.available = false;
    this.generation += 1;
    this.audio.pause();
    this.audio.removeAttribute("src");
    this.audio.load();
    this.publish({ playing: false });
  }
}

export function useBackgroundMusic(
  philosopher: MusicPhilosopher | null,
  shouldPlay: boolean,
  fadeOut = false,
) {
  const [volume, setVolumeState] = useState(readVolume);
  const [requested, setRequestedState] = useState(readRequested);
  const [playback, setPlayback] = useState<PlaybackStatus>({ playing: false, blocked: false, missing: null });
  const manager = useRef<AudioManager | null>(null);

  if (!manager.current) manager.current = new AudioManager(setPlayback, requested);

  useEffect(() => {
    manager.current?.configure(philosopher, shouldPlay, fadeOut);
  }, [fadeOut, philosopher, shouldPlay]);

  useEffect(() => {
    const retry = (event: Event) => {
      if (event.target instanceof Element && event.target.closest(".music-toggle")) return;
      manager.current?.retry();
    };
    window.addEventListener("pointerdown", retry, { passive: true });
    window.addEventListener("keydown", retry);
    return () => {
      window.removeEventListener("pointerdown", retry);
      window.removeEventListener("keydown", retry);
      manager.current?.dispose();
    };
  }, []);

  const setRequested = useCallback((next: boolean) => {
    setRequestedState(next);
    manager.current?.setRequested(next);
  }, []);

  const setVolume = useCallback((next: number) => {
    const safeVolume = Math.max(0, Math.min(1, next));
    setVolumeState(safeVolume);
    manager.current?.setVolume(safeVolume);
  }, []);

  const resume = useCallback(() => manager.current?.retry(), []);
  const startNow = useCallback((track: MusicPhilosopher) => manager.current?.startNow(track), []);

  return {
    volume,
    requested,
    playing: playback.playing,
    blocked: playback.blocked,
    missing: playback.missing,
    startNow,
    resume,
    setVolume,
    setRequested,
  };
}
