// Token layout and move mapping adapted from CSSLab/maia-platform-frontend (GPL-3.0).
// Upstream revision and licenses are recorded in THIRD_PARTY.md.
import { Chess } from 'chess.js'
import mapping from './data/all_moves_maia3.json'

const MAIA_WEIGHTS = 'official-browser-2026-09-23'

const indices = mapping as Record<string, number>
type Pending = { resolve: (value: {logitsMove: Float32Array; logitsValue: Float32Array}) => void; reject: (error: Error) => void; timer: ReturnType<typeof setTimeout> }
/** Game outcome probabilities from White's point of view, as predicted by Maia's value head. */
export interface Outcome { win: number; draw: number; loss: number }
export interface Prediction { moves: {uci: string; san: string; probability: number}[]; whiteExpectedScore: number; whiteOutcome: Outcome }
class InvalidMaiaOutput extends Error {}
export function mirrorMove(move: string) {
  return move[0] + (9 - Number(move[1])) + move[2] + (9 - Number(move[3])) + move.slice(4)
}
export function encode(fen: string) {
  const board = new Chess(fen)
  const black = board.turn() === 'b'
  const tokens = new Float32Array(64 * 12)
  let rank = 7
  for (const row of fen.split(' ')[0].split('/')) {
    let file = 0
    for (const piece of row) {
      if (/\d/.test(piece)) { file += Number(piece); continue }
      let channel = 'PNBRQKpnbrqk'.indexOf(piece)
      if (black) channel = (channel + 6) % 12
      const square = (black ? 7 - rank : rank) * 8 + file
      tokens[square * 12 + channel] = 1
      file++
    }
    rank--
  }
  const legal = board.moves({ verbose: true }).map(move => {
    const uci = move.from + move.to + (move.promotion || '')
    const index = indices[black ? mirrorMove(uci) : uci]
    if (index === undefined) throw new Error('Mappatura Maia mancante: ' + uci)
    return { uci, san: move.san, index }
  })
  return { tokens, legal, black }
}

class MaiaEngine {
  private queue: Promise<void> = Promise.resolve()
  worker: Worker | null = null
  ready: Promise<void> | null = null
  pending = new Map<number, Pending>()
  nextId = 0
  status = 'Da caricare'
  onStatus = (_status: string) => {}
  update(status: string) { this.status = status; this.onStatus(status) }

  private reset(error: Error) {
    this.worker?.terminate()
    this.worker = null
    this.ready = null
    for (const request of this.pending.values()) { clearTimeout(request.timer); request.reject(error) }
    this.pending.clear()
    this.update('Riavvio Maia…')
  }

  load() {
    if (this.ready) return this.ready
    this.update('Caricamento Maia…')
    this.ready = new Promise<void>((resolve, reject) => {
      const worker = new Worker('/maia-worker.js')
      this.worker = worker
      const timeout = setTimeout(() => fail(new Error('Caricamento Maia scaduto. Riprova.')), 90000)
      const fail = (error: Error) => {
        clearTimeout(timeout)
        worker.terminate()
        this.worker = null
        this.ready = null
        this.update('Maia non disponibile')
        for (const request of this.pending.values()) { clearTimeout(request.timer); request.reject(error) }
        this.pending.clear()
        reject(error)
      }
      worker.onerror = event => fail(new Error(event.message || 'Errore del worker Maia'))
      worker.onmessage = event => {
        if (this.worker !== worker) return
        const message = event.data
        if (message.type === 'status') {
          if (message.status === 'no-cache') worker.postMessage({ type: 'download' })
          if (message.status === 'ready') { clearTimeout(timeout); this.update('Maia pronto'); resolve() }
        }
        if (message.type === 'progress') this.update(`Caricamento Maia ${message.progress}%`)
        if (message.type === 'error') {
          const request = this.pending.get(message.id)
          if (request) { clearTimeout(request.timer); this.pending.delete(message.id); request.reject(new Error(message.message)) }
          else fail(new Error(message.message))
        }
        if (message.type === 'inference-result') {
          const request = this.pending.get(message.id)
          if (request) {
            clearTimeout(request.timer)
            this.pending.delete(message.id)
            request.resolve({ logitsMove: new Float32Array(message.logitsMove), logitsValue: new Float32Array(message.logitsValue) })
          }
        }
      }
      worker.postMessage({ type: 'init', modelUrl: '/maia3/maia3_simplified.onnx', modelVersion: MAIA_WEIGHTS })
    })
    return this.ready
  }

  predict(fen: string, selfElo: number, opponentElo: number, signal?: AbortSignal): Promise<Prediction> {
    // One ONNX session is shared by play, review and rating. Never overlap runs.
    const request = this.queue.then(async () => {
      for (let attempt = 0; attempt < 2; attempt++) {
        signal?.throwIfAborted()
        try {
          const prediction = await this.predictOnce(fen, selfElo, opponentElo)
          signal?.throwIfAborted()
          return prediction
        } catch (error) {
          if (!(error instanceof InvalidMaiaOutput)) throw error
          this.reset(error)
          if (attempt === 1) throw new Error('Maia ha restituito valori non validi anche dopo il riavvio. Riprova il calcolo.')
        }
      }
      throw new Error('Maia non disponibile')
    })
    // A failure must not poison subsequent requests.
    this.queue = request.then(() => {}, () => {})
    return request
  }

  private async predictOnce(fen: string, selfElo: number, opponentElo: number): Promise<Prediction> {
    const input = encode(fen)
    if (!input.legal.length) return { moves: [], whiteExpectedScore: 0.5, whiteOutcome: { win: 0, draw: 1, loss: 0 } }
    await this.load()
    const id = ++this.nextId
    const output = await new Promise<{logitsMove: Float32Array; logitsValue: Float32Array}>((resolve, reject) => {
      const timer = setTimeout(() => { this.reset(new Error('Maia non ha risposto. Riprova.')) }, 30000)
      this.pending.set(id, {resolve, reject, timer})
      const selfs = new Float32Array([selfElo])
      const oppos = new Float32Array([opponentElo])
      this.worker!.postMessage({ type: 'inference', id, tokens: input.tokens.buffer, eloSelfs: selfs.buffer, eloOppos: oppos.buffer, batchSize: 1 }, [input.tokens.buffer, selfs.buffer, oppos.buffer])
    })
    const logits = input.legal.map(move => output.logitsMove[move.index])
    if (output.logitsMove.length !== 4352 || output.logitsValue.length !== 3 ||
        logits.some(v => !Number.isFinite(v)) || output.logitsValue.some(v => !Number.isFinite(v))) {
      throw new InvalidMaiaOutput('Output Maia non valido')
    }
    const max = Math.max(...logits)
    const exp = logits.map(v => Math.exp(v - max))
    const sum = exp.reduce((a, b) => a + b, 0)
    const valueMax = Math.max(...output.logitsValue)
    const values = Array.from(output.logitsValue, x => Math.exp(x - valueMax))
    const total = values.reduce((a, b) => a + b, 0)
    // Value logits are loss, draw, win for the side to move.
    const own = { win: values[2] / total, draw: values[1] / total, loss: values[0] / total }
    const expected = own.win + 0.5 * own.draw
    return { moves: input.legal.map((move, i) => ({ uci: move.uci, san: move.san, probability: exp[i] / sum })).sort((a, b) => b.probability - a.probability),
      whiteExpectedScore: input.black ? 1 - expected : expected, whiteOutcome: input.black ? { win: own.loss, draw: own.draw, loss: own.win } : own }
  }
}
export const maia = new MaiaEngine()
/** Recorded with each new Maia game: the model the browser loads for Play. */
export const MAIA_MODEL_VERSION = `maia3_simplified.onnx@${MAIA_WEIGHTS}`
// A low temperature replays the same opening every game: up to this move number, sharpened modes draw
// with OPENING (temperature 1, rare moves still cut) so games diverge before their own rule applies.
const OPENING_MOVES = 8
const OPENING = { temperature: 1, topP: 0.9 }
/** Move selection modes for Play, fixed per game; keys match MAIA_SELECTIONS in backend/opponents.py. */
export const SELECTIONS = {
  'sample-full-distribution': { label: 'Completa', temperature: 1, topP: 1 },
  'temperature-0.7-top-p-0.95': { label: 'Bilanciata', temperature: 0.7, topP: 0.95, openingMoves: OPENING_MOVES },
  'temperature-0.4-top-p-0.8': { label: 'Solida', temperature: 0.4, topP: 0.8, openingMoves: OPENING_MOVES },
  'top-move': { label: 'Prima scelta', temperature: 0, topP: 1 },
} as const
export type Selection = keyof typeof SELECTIONS
export const FULL_SELECTION: Selection = 'sample-full-distribution'
/** Sharpen the distribution with the temperature, keep the smallest set reaching top-p, then draw. */
export function sample(prediction: Prediction, selection: Selection = FULL_SELECTION, moveNumber = Infinity) {
  const mode: { temperature: number; topP: number; openingMoves?: number } = SELECTIONS[selection] ?? SELECTIONS[FULL_SELECTION]
  const { temperature, topP } = mode.openingMoves && moveNumber <= mode.openingMoves ? OPENING : mode
  const moves = prediction.moves
  if (!moves.length) return undefined
  if (temperature === 0) return moves[0].uci
  const top = moves[0].probability
  let weights = moves.map(move => top > 0 ? (move.probability / top) ** (1 / temperature) : 1)
  const total = weights.reduce((a, b) => a + b, 0)
  let cumulative = 0, kept = 0
  while (kept < moves.length && (kept === 0 || cumulative < topP * total - 1e-12)) cumulative += weights[kept++]
  weights = weights.slice(0, kept)
  let draw = Math.random() * cumulative
  for (let i = 0; i < kept; i++) { draw -= weights[i]; if (draw < 0) return moves[i].uci }
  return moves[kept - 1].uci
}
