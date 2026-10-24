# Proxyman

Gestore di reverse proxy Nginx per Linux, scritto in Go. Un solo eseguibile con interfaccia web in italiano incorporata, senza Docker, Node o database esterni.

## Avvio

Servono Go 1.26 o successivo, GNU Make e util-linux (flock). Nginx serve solo per applicare le configurazioni. Il client SSH Go viene incorporato nel binario: non servono sshpass o un client SSH installato sulla macchina del gestore. La compilazione scarica i moduli dichiarati in go.mod; una precedente versione di Go con toolchain automatico può scaricare Go 1.26.

```sh
cp .env.example .env
chmod 600 .env
# Modifica PROXYMAN_PASSWORD in .env.
make build
make test
make start
make status
make logs
make restart
make stop
```

Apri http://127.0.0.1:8080 e accedi con admin e la password impostata. Il Makefile cerca Go nel PATH, poi in /usr/local/go/bin/go; puoi impostare GO=/percorso/go.

Il binario bin/proxyman include tutti gli asset: per distribuirlo basta copiarlo su un sistema Linux della stessa architettura. Build per ARM64: `GOOS=linux GOARCH=arm64 make build`. CGO è disabilitato.

Avvio diretto:
```sh
PROXYMAN_PASSWORD='una-password-lunga-e-personale' ./bin/proxyman
```

## Funzioni

- Crea, modifica, elimina, abilita e disabilita proxy.
- Cerca per dominio o destinazione.
- Backend HTTP/HTTPS e supporto WebSocket.
- Certificati TLS esistenti con redirect HTTP → HTTPS.
- Anteprima e download del file Nginx.
- Salvataggio persistente e controllo revisioni per evitare sovrascritture tra sessioni.
- Applicazione esplicita con nginx -t, ricaricamento e ripristino del file se il comando fallisce.

Salvare un proxy non modifica Nginx. Il pulsante di applicazione gestisce tutti i proxy salvati insieme. I contatori descrivono la configurazione, non la disponibilità dei servizi.

## Collegamento al Nginx di sistema

Di default l'applicazione permette di gestire ed esportare configurazioni, senza modificare il servizio. Per applicarle:

1. Verifica che il blocco http della configurazione principale Nginx includa `/etc/nginx/conf.d/*.conf`.
2. Scegli un file dedicato e non già usato, per esempio `/etc/nginx/conf.d/proxyman.conf`. Proxyman rifiuta di sovrascrivere file privi della propria intestazione.
3. L'utente del processo deve poter scrivere nella cartella del file dedicato, eseguire `nginx -t` con accesso ai certificati e inviare il segnale di reload al master Nginx. Con il normale Nginx di sistema queste operazioni richiedono tipicamente root. Non vengono aggiunti automaticamente sudo, permessi o modifiche al servizio.
4. Imposta `PROXYMAN_APPLY=1` in .env e riavvia il gestore con l'utente appropriato. Se scegli root, usa `sudo make start`, `sudo make stop`, ecc. sempre dalla stessa cartella.
5. Salva i proxy e premi **Applica a Nginx**.

Il comando usa il file di configurazione principale predefinito del binario Nginx indicato. Installazioni con `nginx -c` personalizzato richiedono un adattamento prima dell'uso. Non importa né modifica virtual host esistenti: evita domini e listener in conflitto. Il file gestito deve essere effettivamente incluso nella configurazione principale; `nginx -t` da solo non prova questo collegamento.

Per TLS specifica percorsi assoluti a certificato PEM e chiave privata sul server. Nessun caricamento di chiavi nel browser. Per backend HTTPS è attiva la verifica del certificato usando `/etc/ssl/certs/ca-certificates.crt`; i certificati privati devono essere riconosciuti da quel trust store.

Il reload è una richiesta al master: l'esito positivo del comando non è un health check dei backend. Dopo il riavvio dell'app lo stato applicato deve essere riconfermato.

## Dati e gestione del processo

- `var/hosts.json`: archivio delle configurazioni.
- `var/proxyman.log`: log dell'applicazione.
- `var/proxyman.pid`: PID usato dal Makefile, verificato tramite /proc prima di fermare il processo.
- `.env`: credenziali e opzioni, letto come file shell solo dallo script Make.
- `make stop` arresta il gestore; Nginx continua a servire la configurazione applicata.
- I comandi Make gestiscono l'avvio manuale; non installano un servizio di avvio al boot.
- Esegui una sola istanza del gestore per archivio/file Nginx; non modificare contemporaneamente il file gestito con altri strumenti.

L'interfaccia ascolta solo su loopback. Per gestire un server remoto usa un tunnel SSH: `ssh -L 8080:127.0.0.1:8080 utente@server`. L'autenticazione HTTP Basic deve passare attraverso HTTPS o tunnel SSH se esposta oltre loopback.

## Limiti della prima versione

Nessuna emissione o rinnovo Let's Encrypt, gestione utenti multipli, importazione di configurazioni arbitrarie, direttive personalizzate o monitoraggio dei backend. Il formato è intenzionalmente limitato ai reverse proxy più comuni.

## Server remoti via SSH

Il file .env contiene sezioni per prod e backup, inizialmente disattivate. Imposta gli identificativi in PROXYMAN_REMOTE_IDS per renderli disponibili nel selettore della GUI:

```sh
PROXYMAN_REMOTE_IDS='prod'
PROXYMAN_REMOTE_PROD_IP='192.0.2.10'
PROXYMAN_REMOTE_PROD_PORT=22
PROXYMAN_REMOTE_PROD_USER='root'
PROXYMAN_REMOTE_PROD_PASSWORD='la-password-ssh'
PROXYMAN_REMOTE_PROD_HOST_KEY='SHA256:impronta-da-sostituire'
PROXYMAN_REMOTE_PROD_HOST_KEY_TYPE='ssh-ed25519'
PROXYMAN_REMOTE_PROD_CONFIG='/etc/nginx/conf.d/proxyman.conf'
PROXYMAN_REMOTE_PROD_NGINX='/usr/sbin/nginx'
PROXYMAN_REMOTE_PROD_SUDO=0
PROXYMAN_REMOTE_PROD_APPLY=1
```

Per aggiungere altri server usa nomi minuscoli (lettere, numeri e underscore, iniziando con una lettera), ad esempio PROXYMAN_REMOTE_IDS='prod backup'. Il prefisso corrispondente nel .env usa il nome maiuscolo. IP accetta anche un hostname o IPv6 senza parentesi.

HOST_KEY è l'impronta della chiave host SSH, verificata prima di inviare la password. Ottienila dalla console fidata del server remoto:

```sh
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub -E sha256
```

Copia solo il campo SHA256:... in HOST_KEY. Per un server che usa un altro tipo di chiave, modifica anche HOST_KEY_TYPE (ECDSA o rsa-sha2-256/rsa-sha2-512). La verifica dell'identità non viene mai disabilitata.

Dopo aver modificato il .env, riavvia il gestore. Seleziona il server e premi **Verifica SSH** per controllare autenticazione, permessi sulla cartella e nginx -t. Le password restano sul backend e non vengono restituite alle API o alla GUI. Il file .env viene caricato da scripts/service.sh: avviando il binario direttamente occorre esportare le variabili.

Ogni server ha un archivio locale indipendente in var/remote-IDENTIFICATIVO.json; var/hosts.json rimane l'archivio del Nginx locale. Anche revisioni e stato applicato sono separati. La rimozione di un identificativo dal .env nasconde il server senza cancellarne l'archivio.

**Applica a Nginx** trasferisce solo il file generato al server selezionato, verifica la configurazione completa con nginx -T (che esegue anche il controllo di sintassi), verifica che il file sia effettivamente incluso e richiede il reload. In caso di errore ripristina il file precedente. Un lock remoto impedisce applicazioni simultanee sullo stesso file. Una perdita di connessione o un timeout può lasciare l'esito non confermato: controlla il server prima di riprovare.

Sul server remoto servono Nginx, una shell POSIX, util-linux (flock), coreutils (timeout, mktemp, ecc.) e SSH con autenticazione password abilitata per l'utente scelto. Non occorrono Go o Proxyman sul server remoto. L'utente deve poter gestire il file e il master Nginx. Con SUDO=1 i comandi vengono eseguiti tramite sudo -n: serve un'autorizzazione sudo senza password già configurata. La password SSH non viene usata come password sudo.

APPLY=0 permette salvataggio, anteprima e verifica SSH senza applicazione; questo valore è indipendente dal PROXYMAN_APPLY del server locale. Backend, certificati e chiavi TLS si riferiscono al filesystem e alla rete del server selezionato. Per esempio 127.0.0.1 come destinazione indica il server remoto, non il computer del gestore.

Non vengono importati virtual host preesistenti. Usa un file dedicato incluso nel blocco http del Nginx remoto; un file esistente non creato da Proxyman o un link simbolico viene rifiutato. Si usa la configurazione principale predefinita del binario Nginx indicato.

Per il deploy del gestore copia anche tutti gli archivi var/remote-*.json necessari. Conserva .env con permessi 600.

## Visualizzare i proxy già esistenti

La sezione **Proxy rilevati su Nginx** legge la configurazione del server selezionato tramite nginx -T e mostra i reverse proxy HTTP/HTTPS già definiti, inclusi quelli in sites-enabled, conf.d e negli snippet inclusi. La lettura avviene automaticamente al caricamento o al cambio server; **Aggiorna dal server** aggiorna l'elenco.

La vista riporta domini, listener, destinazioni proxy_pass, TLS, file e riga di origine. Nei dettagli vengono mostrati anche i backend dei gruppi upstream. Le credenziali eventualmente presenti negli URL non vengono mostrate. I blocchi di solo redirect, i server statici e i proxy TCP/UDP non sono elencati.

Si tratta della configurazione su disco verificata da Nginx, non di un controllo della disponibilità dei servizi o della configurazione caricata in memoria. Il comando non applica modifiche e non richiede un reload. Eventuali errori di lettura sono mostrati al posto di un elenco vuoto.

I proxy rilevati possono essere modificati tramite **Modifica guidata** direttamente nel file originale, con anteprima e backup. Non vengono copiati nell’archivio del file dedicato Proxyman. La sezione **Proxy gestiti da Proxyman** mantiene le azioni per i proxy creati dall’applicazione. Evita di ricreare un dominio già configurato in un altro file.

Se è configurato un solo server remoto, la prima apertura lo seleziona automaticamente. Le successive aperture ricordano il server scelto nel browser.


## Modifica guidata dei proxy esistenti

Nella tabella **Proxy rilevati su Nginx**, premi **Modifica guidata**. Il modulo legge nuovamente il file originale e presenta quattro passaggi:

1. **Domini e ascolto**: domini, indirizzo, porta e TLS del listener. Le opzioni aggiuntive vengono conservate.
2. **Percorsi e servizi**: percorsi pubblici, protocollo, host, porta e percorso di ogni proxy_pass, versione HTTP e header WebSocket. È possibile aggiungere nuovi percorsi.
3. **TLS e opzioni**: percorsi del certificato e della chiave, timeout e dimensione massima della richiesta, anche per singolo percorso.
4. **Riepilogo**: confronta i valori prima/dopo e premi **Salva e applica a Nginx**.

L'anteprima non scrive sul server. L'applicazione controlla l'impronta SHA256 del file: se un'altra sessione o un amministratore lo ha modificato, occorre riaprire il modulo. Vengono sostituiti solo gli argomenti delle direttive selezionate; i blocchi, le direttive e i commenti non coinvolti restano invariati. Svuotare un campo opzionale rimuove la relativa direttiva locale e ripristina il comportamento ereditato di Nginx.

Quando sites-enabled contiene un collegamento simbolico, viene aggiornato il file di destinazione senza sostituire il collegamento. Il proprietario e i permessi del file sono conservati. Prima della scrittura viene salvato un backup nella cartella nascosta .proxyman-backups accanto al file originale. Il messaggio finale riporta il percorso del backup. I backup non vengono eliminati automaticamente.

Il nuovo file viene verificato con nginx -t; solo se valido viene richiesto il reload. In caso di errore viene ripristinato il file precedente. Un timeout o una perdita della connessione possono rendere l'esito non confermato: controllare il server prima di riprovare.

Le direttive negli include esterni, i gruppi upstream condivisi e le direttive avanzate non esposte nel modulo vengono conservate. Le destinazioni contenenti credenziali sono oscurate e non modificabili dal modulo. Espressioni regolari o variabili già presenti possono essere conservate senza modifiche; per un nuovo valore il modulo accetta i formati comuni indicati dai campi. Non è un editor arbitrario di testo Nginx.

Il pulsante finale richiede che l'applicazione sia abilitata per il server (APPLY=1). Sul server servono anche readlink, sha256sum e le utility POSIX già richieste per l'applicazione SSH. Non servono agenti o installazioni Proxyman sul server remoto.
