"""Sequential monthly research pipeline, with replay, fixed validation and guarded cleanup."""
import argparse
import fcntl
import json
import math
from pathlib import Path
import re
import shutil
import signal
import sqlite3
from types import SimpleNamespace

import torch

from dataset import Positions
from download_month import check_space, download, write_json
from monthly_data import copy_rows, fixed_and_training, get_meta, heldout_keys, prepare_month
from policy import Config, Policy
from train import evaluate, fingerprint, train

ROOT = Path(__file__).resolve().parent


def read_json(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def atomic_copy(source, target):
    temp = target.with_suffix(target.suffix + '.tmp')
    shutil.copyfile(source, temp)
    temp.replace(target)


def metrics(checkpoint, data):
    state = torch.load(checkpoint, map_location='cpu', weights_only=True)
    if not all(torch.isfinite(v).all() for v in state['model'].values()):
        raise ValueError('Checkpoint con valori non finiti')
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model = Policy(Config(**state['config'])).to(device)
    model.load_state_dict(state['model'], strict=True)
    return evaluate(model, Positions(data, 'validation'), device, 64)


def acceptance(candidate, previous=None):
    reasons = []
    values = candidate.get('all', {})
    if not values.get('count') or not math.isfinite(values.get('nll', math.nan)):
        reasons.append('Validation assente o non finita')
    elif values['nll'] >= values['uniform_nll']:
        reasons.append('Previsione non migliore della distribuzione uniforme')
    if previous and not reasons:
        if values['nll'] > previous['all']['nll'] + .03:
            reasons.append('Peggioramento NLL globale oltre 0,03')
        for band in ('all', '600', '800', '1000', '1200', '1400'):
            old, new = previous.get(band), candidate.get(band)
            if old and new and min(old['count'], new['count']) >= 100 and new['top1'] < old['top1'] - .05:
                reasons.append(f'Calo top-1 oltre 5 punti percentuali nella fascia {band}')
    return dict(accepted=not reasons, reasons=reasons)


def storage_budget(root, host_disk, limit_gib=8):
    total = sum(p.stat().st_size for folder in (root/'data/cycles', root/'runs/monthly')
                if folder.exists() for p in folder.rglob('*') if p.is_file())
    if total >= limit_gib*1024**3:
        raise RuntimeError('Budget di 8 GiB per campioni/checkpoint del ciclo esaurito')
    check_space(root/'data', host_disk)


def guarded_remove_archive(root, month, record):
    """Only a verified, exactly named archive may be removed, after a committed cycle."""
    if not re.fullmatch(r'20\d{2}-(0[1-9]|1[0-2])', month) or record.get('state') != 'complete':
        raise ValueError('Ciclo non completato: archivio conservato')
    run = root/'runs/monthly'/month
    checkpoint = run/'best.pt'
    verification = read_json(run/'verification.json', {})
    fixed = root/'data/cycles/fixed.sqlite'
    replay = root/'data/cycles/replay.sqlite'
    if (not verification.get('accepted') or verification.get('checkpoint_sha256') != record.get('checkpoint_sha256')
        or fingerprint(run/'verification.json') != record.get('verification_sha256')
        or not checkpoint.exists() or fingerprint(checkpoint) != record.get('checkpoint_sha256')
        or fingerprint(fixed) != record.get('fixed_sha256')
        or fingerprint(replay) != record.get('replay_sha256')):
        raise ValueError('Checkpoint, verifica o dati permanenti non corrispondenti: archivio conservato')
    bounds = record.get('rating_range', [600, 2600])
    if bounds != [600, 2600]:
        validation = root/'data/cycles'/f'fixed-{bounds[0]}-{bounds[1]}.sqlite'
        if (not validation.exists() or fingerprint(validation) != record.get('validation_sha256')
            or verification.get('validation_sha256') != record.get('validation_sha256')):
            raise ValueError('Sottoinsieme di verifica modificato: archivio conservato')
    archive_dir = root/'data/monthly'
    archive = archive_dir/f'lichess_db_standard_rated_{month}.pgn.zst'
    if archive.is_symlink() or archive.resolve().parent != archive_dir.resolve():
        raise ValueError('Percorso archivio non consentito')
    if archive.exists():
        if fingerprint(archive) != record['archive_sha256']:
            raise ValueError('Archivio diverso da quello elaborato: nessuna cancellazione')
        archive.unlink()
    # Retain evidence even when the payload is removed.
    write_json(archive_dir/f'{month}.cleanup.json', dict(removed=True, sha256=record['archive_sha256'],
                                                       checkpoint_sha256=record['checkpoint_sha256']))


def prune_old_artifacts(root, ledger):
    completed = [m for m, record in ledger['months'].items() if record['state'] == 'complete']
    for month in completed[:-2]:
        if not re.fullmatch(r'20\d{2}-(0[1-9]|1[0-2])', month):
            raise ValueError('Mese nel registro non valido')
        for relative in (f'data/cycles/months/{month}.sqlite', f'data/cycles/months/{month}.train.sqlite',
                         f'data/cycles/months/{month}.replay.sqlite', f'runs/monthly/{month}/last.pt',
                         f'runs/monthly/{month}/best.pt'):
            path = root/relative
            if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
                raise ValueError('Percorso da conservare: fuori dal laboratorio')
            if path.exists():
                path.unlink()


def train_month(root, month, data, fixed, replay, parent, args):
    run = root/'runs/monthly'/month
    run.mkdir(parents=True, exist_ok=True)
    parent_state = torch.load(parent, map_location='cpu', weights_only=True) if parent else None
    base_step = parent_state['step'] if parent_state else 0
    plan = dict(data_sha256=fingerprint(data), fixed_sha256=fingerprint(fixed),
                replay_sha256=fingerprint(replay) if replay else None,
                parent_sha256=fingerprint(parent) if parent else None, base_step=base_step,
                max_steps=args.max_steps, chunk_steps=args.chunk_steps, patience=args.patience,
                preset='tiny', batch_size=64, schema=1)
    previous_plan = read_json(run/'plan.json')
    if previous_plan and previous_plan != plan:
        raise ValueError('Configurazione del ciclo cambiata: ripresa rifiutata')
    write_json(run/'plan.json', plan)
    progress = read_json(run/'progress.json', dict(best_nll=None, stale=0))
    best, last = run/'best.pt', run/'last.pt'
    if best.exists() and fingerprint(best) != progress.get('best_sha256'):
        recovered = torch.load(best, map_location='cpu', weights_only=True)
        if recovered['dataset_sha256'] != plan['data_sha256'] or recovered['validation_sha256'] != plan['fixed_sha256']:
            raise ValueError('Checkpoint migliore non corrispondente al dataset')
        progress.update(best_nll=metrics(best, fixed)['all']['nll'], stale=0,
                        best_sha256=fingerprint(best), best_step=recovered['step'])
        write_json(run/'progress.json', progress)
    while progress['stale'] < args.patience:
        step = torch.load(last, map_location='cpu', weights_only=True)['step'] if last.exists() else base_step
        remaining = base_step + args.max_steps - step
        if remaining <= 0:
            break
        report = train(SimpleNamespace(data=str(data), validation_data=str(fixed),
                        replay_data=str(replay) if replay else None, initialize_from=str(parent) if parent and not last.exists() else None,
                        run=str(run), preset='tiny', steps=min(args.chunk_steps, remaining), batch_size=64,
                        threads=4, lr=.0003, seed=42, save_every=100, device='auto', resume=last.exists()))
        if report['interrupted']:
            raise KeyboardInterrupt('Training interrotto: archivio conservato')
        # Restore immediate cancellation between training chunks.
        signal.signal(signal.SIGTERM, interrupt)
        signal.signal(signal.SIGINT, interrupt)
        nll = report['validation']['all']['nll']
        if progress['best_nll'] is None or nll < progress['best_nll'] - .001:
            atomic_copy(last, best)
            progress.update(best_nll=nll, stale=0, best_sha256=fingerprint(best), best_step=report['step'])
        else:
            progress['stale'] += 1
        write_json(run/'progress.json', progress)
        storage_budget(root, args.host_disk)
    if not best.exists():
        if not last.exists():
            raise ValueError('Nessun checkpoint verificabile; archivio conservato')
        # Recover an interruption between a completed chunk and best-checkpoint promotion.
        recovered = torch.load(last, map_location='cpu', weights_only=True)
        if recovered['dataset_sha256'] != plan['data_sha256'] or recovered['validation_sha256'] != plan['fixed_sha256']:
            raise ValueError('Checkpoint finale non corrispondente al dataset')
        atomic_copy(last, best)
        progress.update(best_nll=metrics(best, fixed)['all']['nll'], stale=0,
                        best_sha256=fingerprint(best), best_step=recovered['step'])
        write_json(run/'progress.json', progress)
    return best


def run_month(root, month, args):
    cycles = root/'data/cycles'
    (cycles/'months').mkdir(parents=True, exist_ok=True)
    ledger_path = cycles/'ledger.json'
    ledger = read_json(ledger_path, dict(months={}, active_month=None, fixed_sha256=None))
    status = cycles/'status.json'
    request_path = root/'runs/monthly'/month/'request.json'
    saved_request = read_json(request_path)
    existing = ledger['months'].get(month)
    parent_record = ledger['months'].get(ledger['active_month'], {})
    inherited = (saved_request or existing or parent_record).get('rating_range', [600, 2600])
    low = getattr(args, 'min_elo', None)
    high = getattr(args, 'max_elo', None)
    bounds = [inherited[0] if low is None else low, inherited[1] if high is None else high]
    if not 600 <= bounds[0] <= bounds[1] <= 2600:
        raise ValueError('Intervallo rating non valido: 600 <= minimo <= massimo <= 2600')
    if saved_request and saved_request['rating_range'] != bounds:
        raise ValueError('Fascia del ciclo già fissata: ripresa con filtri diversi rifiutata')
    if existing and existing.get('rating_range', [600, 2600]) != bounds:
        raise ValueError('Mese già elaborato con una fascia diversa')
    focused = bounds != [600, 2600]
    if existing and existing['state'] == 'complete':
        if not args.keep_archive and (root/'data/monthly'/f'lichess_db_standard_rated_{month}.pgn.zst').exists():
            guarded_remove_archive(root, month, existing)
        write_json(status, dict(month=month, stage='complete', checkpoint=existing['checkpoint']))
        return
    if (ledger['active_month'] and month <= max(ledger['months'])
        and not getattr(args, 'allow_earlier_month', False)):
        raise ValueError('Mese storico: richiede --allow-earlier-month esplicito')
    parent = root/ledger['months'][ledger['active_month']]['checkpoint'] if ledger['active_month'] else None
    if parent and fingerprint(parent) != ledger['months'][ledger['active_month']]['checkpoint_sha256']:
        raise ValueError('Checkpoint precedente modificato')
    fixed, replay_pool = cycles/'fixed.sqlite', cycles/'replay.sqlite'
    saved_plan = read_json(root/'runs/monthly'/month/'plan.json')
    if parent and not saved_plan and (not replay_pool.exists() or
        fingerprint(replay_pool) != ledger['months'][ledger['active_month']]['replay_sha256']):
        raise ValueError('Memoria precedente modificata o mancante')
    if ledger['fixed_sha256'] and fingerprint(fixed) != ledger['fixed_sha256']:
        raise ValueError('Holdout fisso modificato')
    storage_budget(root, args.host_disk)
    request_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(request_path, dict(rating_range=bounds))
    write_json(status, dict(month=month, stage='download', rating_range=bounds))
    download(month, root/'data/monthly', args.host_disk)
    archive_meta = read_json(root/'data/monthly'/f'{month}.manifest.json')
    archive = root/'data/monthly'/archive_meta['name']
    month_data = cycles/'months'/f'{month}.sqlite'
    training_data = cycles/'months'/f'{month}.train.sqlite'
    replay_input = cycles/'months'/f'{month}.replay.sqlite'
    write_json(status, dict(month=month, stage='sampling'))
    prepare_month(archive, month_data, month, args.host_disk, low=bounds[0], high=bounds[1])
    if not training_data.exists():
        fixed_and_training(month_data, fixed, training_data)
    if saved_plan and saved_plan['replay_sha256'] and not replay_input.exists():
        raise ValueError('Snapshot replay del training mancante: archivio conservato')
    if parent and replay_pool.exists() and not replay_input.exists():
        blocked = heldout_keys(fixed)
        copy_rows(replay_input, [replay_pool], ['train'], 100000,
                  dict(speed='rapid', purpose='replay_input', month=month, low=bounds[0], high=bounds[1]),
                  exclude_keys=blocked, rating_range=bounds)
    if not ledger['fixed_sha256']:
        ledger['fixed_sha256'] = fingerprint(fixed)
        write_json(ledger_path, ledger)
    validation = fixed
    if focused:
        validation = cycles/f'fixed-{bounds[0]}-{bounds[1]}.sqlite'
        view_settings = dict(purpose='fixed_rating_view', fixed_sha256=fingerprint(fixed), rating_range=bounds)
        if not validation.exists():
            copy_rows(validation, [fixed], ['validation'], 10000, view_settings, rating_range=bounds)
        with sqlite3.connect(f'file:{validation.resolve()}?mode=ro', uri=True) as db:
            if get_meta(db, 'settings') != view_settings:
                raise ValueError('Sottoinsieme di verifica non coerente con holdout e fascia')
    write_json(status, dict(month=month, stage='training', rating_range=bounds))
    best = train_month(root, month, training_data, validation, replay_input if replay_input.exists() else None, parent, args)
    write_json(status, dict(month=month, stage='validation', rating_range=bounds))
    candidate = metrics(best, validation)
    old = metrics(parent, validation) if parent else None
    decision = acceptance(candidate, old)
    verification = dict(**decision, validation=candidate, previous_validation=old,
                        rating_range=bounds, validation_sha256=fingerprint(validation),
                        global_validation=metrics(best, fixed) if focused else candidate,
                        previous_global_validation=metrics(parent, fixed) if focused and parent else old,
                        month_validation=metrics(best, month_data), test='Not evaluated',
                        month_validation_warning='May contain positions seen in current or earlier training; fixed validation is the quality gate',
                        checkpoint_sha256=fingerprint(best), fixed_sha256=fingerprint(fixed),
                        data_sha256=fingerprint(training_data), archive_sha256=archive_meta['sha256'])
    write_json(best.parent/'verification.json', verification)
    if not decision['accepted']:
        write_json(status, dict(month=month, stage='rejected', reasons=decision['reasons']))
        raise ValueError('Qualità peggiorata: modello precedente e archivio conservati')
    blocked = heldout_keys(fixed)
    # Use the immutable input snapshot: safe to repeat after a crash before ledger commit.
    sources = ([replay_input] if replay_input.exists() else []) + [training_data]
    copy_rows(replay_pool, sources, ['train'], 100000,
              dict(speed='rapid', purpose='replay', through_month=month, low=bounds[0], high=bounds[1]),
              blocked, rating_range=bounds)
    record = dict(state='complete', rating_range=bounds, validation_sha256=fingerprint(validation),
                  checkpoint=str(best.relative_to(root)), checkpoint_sha256=fingerprint(best),
                  archive_sha256=archive_meta['sha256'], fixed_sha256=fingerprint(fixed),
                  replay_sha256=fingerprint(replay_pool), verification_sha256=fingerprint(best.parent/'verification.json'))
    ledger['months'][month] = record
    ledger['active_month'] = month
    write_json(ledger_path, ledger)
    if not args.keep_archive:
        write_json(status, dict(month=month, stage='cleanup'))
        guarded_remove_archive(root, month, record)
    prune_old_artifacts(root, ledger)
    write_json(status, dict(month=month, stage='complete', checkpoint=record['checkpoint'], archive_removed=not args.keep_archive))


def interrupt(signum, frame):
    raise KeyboardInterrupt('Interruzione richiesta; ripresa disponibile')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['run', 'status'])
    parser.add_argument('--months', default='2026-09', help='Mesi espliciti, disponibili e in ordine cronologico')
    parser.add_argument('--host-disk', default='/mnt/c')
    parser.add_argument('--min-elo', type=int, help='Rating minimo incluso; eredita ciclo o modello precedente')
    parser.add_argument('--max-elo', type=int, help='Rating massimo incluso; eredita ciclo o modello precedente')
    parser.add_argument('--max-steps', type=int, default=10000)
    parser.add_argument('--chunk-steps', type=int, default=1000)
    parser.add_argument('--patience', type=int, default=3)
    parser.add_argument('--keep-archive', action='store_true')
    parser.add_argument('--allow-earlier-month', action='store_true',
                        help='Consente un mese storico non ancora elaborato, continuando dal modello attivo')
    args = parser.parse_args()
    cycles = ROOT/'data/cycles'
    cycles.mkdir(parents=True, exist_ok=True)
    if args.command == 'status':
        print(json.dumps(read_json(cycles/'status.json', {'stage': 'not_started'}), indent=2))
    else:
        months = args.months.split(',')
        if months != sorted(set(months)) or not all(re.fullmatch(r'20\d{2}-(0[1-9]|1[0-2])', m) for m in months):
            parser.error('Mesi validi, distinti e in ordine cronologico richiesti')
        if min(args.max_steps, args.chunk_steps, args.patience) < 1:
            parser.error('Limiti di training positivi richiesti')
        signal.signal(signal.SIGTERM, interrupt)
        signal.signal(signal.SIGINT, interrupt)
        with (cycles/'cycle.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            for month in months:
                try:
                    run_month(ROOT, month, args)
                except BaseException as exc:
                    previous = read_json(cycles/'status.json', {})
                    write_json(cycles/'status.json', dict(**{k:v for k,v in previous.items() if k not in ('error','stage')},
                               stage='interrupted' if isinstance(exc, KeyboardInterrupt) else 'failed', error=str(exc)))
                    raise
