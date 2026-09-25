// Token layout and move mapping adapted from CSSLab/maia-platform-frontend (GPL-3.0).
// Upstream revision and licenses are recorded in THIRD_PARTY.md.
import { Chess } from 'chess.js'
import mapping from './data/all_moves_maia3.json'

const indices = mapping as Record<string, number>
type Pending = { resolve: (value: {logitsMove: Float32Array; logitsValue: Float32Array}) => void; reject: (error: Error) => void; timer: ReturnType<typeof setTimeout> }
export interface Prediction { moves: {uci: string; san: string; probability: number}[]; whiteExpectedScore: number }
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
      worker.postMessage({ type: 'init', modelUrl: '/maia3/maia3_simplified.onnx', modelVersion: 'official-browser-2026-09-23' })
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
    if (!input.legal.length) return { moves: [], whiteExpectedScore: 0.5 }
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
    const expected = (values[2] + 0.5 * values[1]) / values.reduce((a, b) => a + b, 0)
    return { moves: input.legal.map((move, i) => ({ uci: move.uci, san: move.san, probability: exp[i] / sum })).sort((a, b) => b.probability - a.probability), whiteExpectedScore: input.black ? 1 - expected : expected }
  }
}
export const maia = new MaiaEngine()
export function sample(prediction: Prediction) {
  let draw = Math.random()
  for (const move of prediction.moves) { draw -= move.probability; if (draw <= 0) return move.uci }
  return prediction.moves.at(-1)?.uci
}
