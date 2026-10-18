# Server pubblico sparringmate.u-s.it

Rilevato il 17 ottobre 2026. Le password non sono in questo repository.

## Macchina

| Voce | Valore |
|---|---|
| Host | `sparringmate.u-s.it` |
| Sistema | Debian GNU/Linux 11 (bullseye), glibc 2.31 |
| CPU | x86-64 con AVX2 |
| Accesso | SSH come `root` |
| Server web | nginx 1.18.0 |
| Altri strumenti | `uv` 0.12.10 (`/usr/local/bin/uv`), Python 3.12 in `/opt/uv-python`; il Python di sistema è 3.9 |

Il server ospita anche altri siti, con i propri virtual host in `/etc/nginx/sites-enabled/`: non vanno modificati per SparringMate.

## SparringMate

| Voce | Valore |
|---|---|
| Codice | `/opt/sparringmate` (proprietario root) |
| Dati | `/opt/sparringmate/data` (utente `sparringmate`, permessi 750): `coach.sqlite3` e `session.key` |
| Credenziali di accesso | `/opt/sparringmate/.env` (`SPARRINGMATE_USER`, `SPARRINGMATE_PASSWORD`; utente `sparringmate`, permessi 600) |
| Python | `/opt/sparringmate/.venv`, Python 3.12.14, dipendenze da `requirements.lock` |
| Stockfish | `/opt/sparringmate/engine/stockfish`, Stockfish 19 compilato sul server (vedi sotto) |
| Servizio | `sparringmate.service`, utente `sparringmate`, Uvicorn su `127.0.0.1:8033` con `--proxy-headers` (copia in `sparringmate.service`) |
| nginx | `/etc/nginx/sites-enabled/sparringmate.conf` (copia in `sparringmate.conf`) |
| Log nginx | `/var/log/nginx/sparringmate-access.log`, `/var/log/nginx/sparringmate-error.log` |
| Log applicazione | `journalctl -u sparringmate` |
| TLS | `/etc/ssl/certs/u-s.it.cer` e `/etc/ssl/private/u-s.it.key`, certificato `*.u-s.it` (scadenza 5 novembre 2026), condiviso con gli altri siti |

Il servizio usa `ProtectSystem=strict`: l'unica cartella in cui può scrivere è `data/`. La chiave DeepSeek è installata dal 18 ottobre 2026 in `.secrets/deepseek.json` (utente `sparringmate`, cartella 700, file 600, modello `deepseek-flash`): il tutor e **Spiega motivo** usano DeepSeek, con addebito sulla chiave. `make deploy` non tocca `.secrets/`. Per sostituirla: `.venv/bin/python scripts/configure_deepseek.py` sul server, poi `chown -R sparringmate:sparringmate .secrets`.

## Aggiornare

```bash
make deploy                # usa la chiave SSH
SSHPASS='…' make deploy    # in alternativa, la password tramite sshpass
```

`scripts/deploy.sh` esegue questi passi:

1. compila l'interfaccia (`SKIP_BUILD=1` per saltare il passo);
2. sincronizza la cartella con `rsync --delete --no-owner --no-group --chmod=Dgo-w,Fgo-w`: il codice resta di `root` e non è scrivibile da gruppo e altri, qualunque siano i permessi della copia locale; non tocca `.env`, `.secrets/`, `data/`, `.venv/` né `engine/`;
   se esiste in locale, copia anche `data/lichess_puzzles.sqlite3` (i problemi di `make puzzles`, sola lettura); gli altri file di `data/` restano solo sul server;
3. aggiorna le dipendenze con `uv pip install`;
4. installa unit e virtual host se sono cambiati: crea prima una copia in `/root/sparringmate.conf.bak-…`, esegue `nginx -t` e ripristina la copia se il test fallisce;
5. riavvia il servizio e verifica `/api/health`, poi che `/api/games` senza login risponda 401.

Variabili disponibili: `DEPLOY_HOST` (predefinito `root@sparringmate.u-s.it`), `DEPLOY_DIR`, `DEPLOY_URL`.

## Stockfish

Il binario `vendor/stockfish/stockfish-linux-x86-64-universal` richiede glibc 2.35 e non parte su Debian 11. Per ricompilarlo:

```bash
mkdir -p /opt/sparringmate-build && cd /opt/sparringmate-build
cp -r /opt/sparringmate/vendor/stockfish/src /opt/sparringmate/vendor/stockfish/scripts .
cd src && make -j8 profile-build ARCH=x86-64-avx2 COMP=gcc   # scarica la rete NNUE e ne verifica l'hash
install -m 755 stockfish /opt/sparringmate/engine/stockfish && systemctl restart sparringmate
```

Il binario compilato dà la stessa valutazione e la stessa mossa di quello locale: verificato a 200.000 nodi su una posizione di prova.

## Storia della configurazione nginx

Prima del 17 ottobre 2026 `sparringmate.conf` era la copia del virtual host di un altro sito: inoltrava a quell'applicazione e ne condivideva i log. Sul server la versione originale è conservata in `/root/sparringmate.conf.bak-20261017`.

Le copie di backup vanno tenute fuori da `sites-enabled`: `nginx.conf` include tutti i file di quella cartella, compresi i backup.
