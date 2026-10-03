// Mirrors the JSON `isa status --json` prints (runtime/isa/status.py).
// `iscs` holds the leaf ISCs `progress` counts, in file order: no parents,
// no dropped tombstones, no waived ISCs.
export interface Isc {
  id: string;
  text: string;
  done: boolean;
}

export interface IsaView {
  bound: string;
  task?: string | null;
  effort?: string | null;
  phase?: string | null;
  progress?: string | null;
  iteration?: number | null;
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
