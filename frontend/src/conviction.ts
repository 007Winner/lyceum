export type EncounterPhase = "conversation" | "final_concession" | "victory" | "transitioning";

export function displayedConviction(
  phase: EncounterPhase,
  conviction: Record<string, number> | undefined,
  philosopher: string,
): number {
  if (phase === "final_concession" || phase === "victory") return 0;
  return conviction?.[philosopher] ?? 100;
}
