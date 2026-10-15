import type { IsaView, StatusLineMode } from './types.ts';

const HEX_DONE = '#22c55e'; // vivid green
const HEX_STAGE = '#f59e0b'; // vivid amber
const HEX_OPEN = '#38bdf8'; // vivid sky blue

const TEXT_MID = '#7d8590';
const TEXT_BRIGHT = '#f4f6f8';

const AUTO_WIDE_THRESHOLD = 70;
const WIDE_BAR_CAP = 20;
const SEP = ' · ';

function hexToRgb(hex: string): [number, number, number] {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function paint(text: string, hex: string, color: boolean, bold = false): string {
  if (!color || !text) return text;
  const [r, g, b] = hexToRgb(hex);
  return `${bold ? '\x1b[1m' : ''}\x1b[38;2;${r};${g};${b}m${text}\x1b[0m`;
}

// A row is a list of [plain text, hex, bold] pieces. The width is measured
// on the plain text and the row cut with `…` where it runs out, *before* any
// ANSI color is applied, so escape codes never count against the width.
type Piece = [string, string, boolean?];

function fit(pieces: Piece[], columns: number, color: boolean): string {
  let out = pieces;
  if (pieces.reduce((n, [t]) => n + t.length, 0) > columns) {
    out = [];
    let room = Math.max(0, columns - 1);
    for (const [text, hex, bold] of pieces) {
      if (text.length >= room) {
        out.push([text.slice(0, room) + '…', hex, bold]);
        break;
      }
      out.push([text, hex, bold]);
      room -= text.length;
    }
  }
  return out.map(([t, hex, bold]) => paint(t, hex, color, bold)).join('');
}

function counts(view: IsaView): { done: number; total: number; label: string } {
  const done = view.iscs.filter((i) => i.done).length;
  const total = view.iscs.length;
  // `progress` is what the ISA itself claims (lint keeps it equal to the
  // checkboxes); fall back to the count if it's missing or malformed.
  const label = /^\d+\/\d+$/.test(String(view.progress ?? '')) ? String(view.progress) : `${done}/${total}`;
  return { done, total, label };
}

// The engine's stage, without the `ISA ` prefix the status line has no room
// for: DRAFT, REFINE, BUILD, CLOSED (SPEC DRAFT / SPEC ACKED stay whole).
function stageLabel(view: IsaView): string {
  return String(view.stage || '?').replace(/^ISA /, '');
}

// The first open leaf in file order, by id only: titles never fit.
function current(view: IsaView): string {
  if (view.stage === 'CLOSED') return '';
  return view.iscs.find((i) => !i.done)?.id ?? 'all verified';
}

function progressBar(done: number, total: number, color: boolean): Piece[] {
  let filled = done;
  let empty = total - done;
  if (total > WIDE_BAR_CAP) {
    filled = Math.round((done / total) * WIDE_BAR_CAP);
    empty = WIDE_BAR_CAP - filled;
  }
  return [
    [(color ? '●' : '#').repeat(Math.max(0, filled)), HEX_DONE],
    [(color ? '○' : '-').repeat(Math.max(0, empty)), TEXT_MID],
  ];
}

function tier(view: IsaView): Piece {
  return [`${view.effort || '?'} - `, TEXT_BRIGHT, true];
}

// Only a spec is bound: `E3 - SPEC DRAFT · 2026-10-13-foo-01-spec.md`.
function renderSpec(view: IsaView, columns: number, color: boolean): string {
  const name = String(view.spec).split('/').pop() || '';
  return fit([tier(view), [stageLabel(view), HEX_STAGE], [SEP, TEXT_MID], [name, TEXT_MID]], columns, color);
}

function renderCompact(view: IsaView, columns: number, color: boolean): string {
  const { label } = counts(view);
  const isc = current(view);
  const pieces: Piece[] = [tier(view), [`${label} `, TEXT_MID], [stageLabel(view), HEX_STAGE]];
  if (isc) pieces.push([' ', TEXT_MID], [isc, HEX_OPEN]);
  return fit(pieces, columns, color);
}

function renderWide(view: IsaView, columns: number, color: boolean): string {
  const { done, total, label } = counts(view);
  const isc = current(view);
  const pieces: Piece[] = [tier(view), ...progressBar(done, total, color), [` ${label}`, TEXT_MID], [SEP, TEXT_MID],
    [stageLabel(view), HEX_STAGE]];
  if (isc) pieces.push([SEP, TEXT_MID], [isc, HEX_OPEN]);
  const used = pieces.reduce((n, [t]) => n + t.length, 0);
  if (view.task && columns - used - SEP.length >= 4) pieces.push([SEP, TEXT_MID], [view.task, TEXT_BRIGHT, true]);
  return fit(pieces, columns, color);
}

// One row. Nothing bound (and no spec in its draft or acked stage) renders nothing.
export function renderStatusLine(view: IsaView | null, columns: number, mode: StatusLineMode, color: boolean): string {
  if (!view) return '';
  if (!view.bound) {
    return view.spec && String(view.stage || '').startsWith('SPEC ') ? renderSpec(view, columns, color) : '';
  }
  const resolved = mode === 'auto' ? (columns < AUTO_WIDE_THRESHOLD ? 'compact' : 'wide') : mode;
  return resolved === 'compact' ? renderCompact(view, columns, color) : renderWide(view, columns, color);
}
