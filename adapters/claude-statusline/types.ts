// Mirrors the JSON `isa status --json` prints (runtime/isa/status.py).
// `iscs` holds the leaf ISCs `progress` counts, in file order: no parents,
// no dropped tombstones, no waived ISCs.
export interface Isc {
  id: string;
  text: string;
  done: boolean;
}

export interface IsaView {
  // The bound ISA, or null while only a spec is bound.
  bound: string | null;
  // off (the gate judges each prompt), on, or disabled (the user's /isa-off).
  mode?: string | null;
  // The bound spec (a path), whatever the stage.
  spec?: string | null;
  // The engine's lifecycle stage: TRIAGE, SPEC DRAFT, SPEC ACKED, ISA DRAFT,
  // ISA REFINE, BUILD, CLOSED.
  stage?: string | null;
  task?: string | null;
  // The tier, E1–E4 (the spec's own while only a spec is bound).
  effort?: string | null;
  phase?: string | null;
  progress?: string | null;
  iscs: Isc[];
}

export type StatusLineMode = 'auto' | 'compact' | 'wide';

export interface StatusLineConfig {
  // 'auto' picks compact vs wide from the terminal's reported column count;
  // 'compact'/'wide' pin it regardless of width.
  mode: StatusLineMode;
  // Master color switch. Even when true, NO_COLOR (if set) still wins.
  color: boolean;
  // The `isa` launcher. Defaults to $ISA_BIN, then ~/.local/bin/isa.
  isaBin?: string;
}
