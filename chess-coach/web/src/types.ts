export type Color = 'w' | 'b'
export interface Evaluation { cp: number; mate: number | null; pv: string[]; san: string[]; depth: number; nodes: number; perspective: Color }
export interface Decision { ply: number; fen: string; played: string; playedSan: string; best: Evaluation; actual: Evaluation; loss: number; theme: string; label: string }
export interface Analysis { createdAt:string; decisions: Decision[]; critical: Decision[]; engine: string; version: number; note: string }
export interface Rating { estimate:number|null; low:number; high:number; boundary:'lower'|'upper'|null; status:'estimated'|'inconclusive'; positions:number; totalPositions:number; opponentElo:number; opponentAssumed:boolean; createdAt:string; method:string }
export interface Game { id: string; fen: string; initialFen: string; moves: string[]; version: number; revision:number; canUndo:boolean; rating:Rating|null; playerColor: Color; elo: number; turn: Color; title: string; pgn: string; legalMoves: string[]; result: string | null; source: string; analysis: Analysis | null; drill: {name:string; goal:string; theme:string; target:number; decisions:number; startPly:number; complete:boolean} | null }
export interface Exercise { id: string; gameId: string; ply: number; theme: string; fen: string; turn: Color; dueAt: string; streak: number; legalMoves: string[] }
export interface Attempt { success: boolean; assisted: boolean; message: string; best: Evaluation | null; actual: Evaluation | null; dueAt: string; loss: number | null; version:number; closed:boolean }
export interface PuzzleSession {id:string; version:number; exposure:string}
export interface Profile { games: number; attempts: number; independentAttempts:number; unaidedSuccesses: number; due: number; themes: {theme: string; examples: number}[]; confidence: string; plan: {title: string; minutes: number; description: string}[] }
