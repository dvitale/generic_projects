// Maia3 runs only on the server (backend/maia.py): the page asks for predictions to show, never chooses Maia's moves.
import { api } from '../api'

// Requests made in the same tick travel together: a rating pass asks many levels at once.
const REQUEST_LIMIT = 64

/** Game outcome probabilities from White's point of view, as predicted by Maia's value head. */
export interface Outcome { win: number; draw: number; loss: number }
export interface Prediction { moves: {uci: string; san: string; probability: number}[]; whiteExpectedScore: number; whiteOutcome: Outcome }
type Pending = { fen: string; selfElo: number; opponentElo: number; resolve: (prediction: Prediction) => void; reject: (error: unknown) => void }

class MaiaEngine {
  private waiting: Pending[] = []
  private scheduled = false
  status = 'Maia pronto'
  onStatus = (_status: string) => {}
  update(status: string) { if (status !== this.status) { this.status = status; this.onStatus(status) } }

  /** Nothing to download any more: kept so callers can still wait for Maia before a game. */
  load() { return Promise.resolve() }

  predict(fen: string, selfElo: number, opponentElo: number, signal?: AbortSignal): Promise<Prediction> {
    signal?.throwIfAborted()
    const request = new Promise<Prediction>((resolve, reject) => {
      this.waiting.push({ fen, selfElo, opponentElo, resolve, reject })
      if (!this.scheduled) { this.scheduled = true; setTimeout(() => void this.flush(), 0) }
    })
    if (!signal) return request
    return new Promise<Prediction>((resolve, reject) => {
      const abort = () => reject(signal.reason ?? new DOMException('Aborted', 'AbortError'))
      signal.addEventListener('abort', abort, { once: true })
      request.then(resolve, reject).finally(() => signal.removeEventListener('abort', abort))
    })
  }

  private async flush() {
    this.scheduled = false
    while (this.waiting.length) {
      const batch = this.waiting.splice(0, REQUEST_LIMIT)
      try {
        const { predictions } = await api<{ predictions: Prediction[] }>('/maia/predict',
          { positions: batch.map(({ fen, selfElo, opponentElo }) => ({ fen, selfElo: Math.round(selfElo), opponentElo: Math.round(opponentElo) })) })
        batch.forEach((request, i) => request.resolve(predictions[i]))
        this.update('Maia pronto')
      } catch (error) {
        this.update('Maia non disponibile')
        batch.forEach(request => request.reject(error))
      }
    }
  }
}
export const maia = new MaiaEngine()
/** Move selection modes for Play, fixed per game; drawn on the server (SELECTIONS in backend/maia.py). */
export const SELECTIONS = {
  'sample-full-distribution': { label: 'Completa' },
  'temperature-0.7-top-p-0.95': { label: 'Bilanciata' },
  'temperature-0.4-top-p-0.8': { label: 'Solida' },
  'top-move': { label: 'Prima scelta' },
} as const
export type Selection = keyof typeof SELECTIONS
export const FULL_SELECTION: Selection = 'sample-full-distribution'
