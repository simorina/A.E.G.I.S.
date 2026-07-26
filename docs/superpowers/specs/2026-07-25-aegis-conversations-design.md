# A.E.G.I.S. — Gestione conversazioni (chat salvate)

**Data:** 2026-07-25
**Stato:** Design approvato (in attesa di review finale dello spec)
**Scope:** Nuovo modulo `agent/conversations.py`, endpoint in `server.py`, checkpointer persistente in `agent/__init__.py`, UI sidebar in `aegis.html`/`js/script.js`/`css/style.css`, tabelle in `db/init.sql`.

---

## 1. Obiettivo

Oggi la memoria dell'agente vive in RAM (`MemorySaver`): riavviando il server le conversazioni spariscono, e non esiste alcun concetto di "chat" nella UI (un solo `session_id` anonimo per browser).

Obiettivo: **conversazioni persistenti e organizzate**, legate all'operatore che fa login, con sidebar per crearle, elencarle, riaprirle, rinominarle ed eliminarle.

---

## 2. Architettura

### 2.1 Persistenza applicativa (tabelle nostre, `schema1`)

```sql
CREATE TABLE schema1.conversations (
    id           UUID PRIMARY KEY,
    operator_id  VARCHAR(64)  NOT NULL,
    title        VARCHAR(120) NOT NULL,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX conversations_operator_idx ON schema1.conversations (operator_id, updated_at DESC);

CREATE TABLE schema1.messages (
    id               BIGSERIAL PRIMARY KEY,
    conversation_id  UUID NOT NULL REFERENCES schema1.conversations(id) ON DELETE CASCADE,
    role             VARCHAR(16) NOT NULL,   -- 'user' | 'assistant'
    content          TEXT NOT NULL,
    geojson          TEXT,                   -- solo per i messaggi assistant con geometria
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX messages_conversation_idx ON schema1.messages (conversation_id, id);
```

**Perché una tabella messaggi oltre al checkpointer:** il checkpointer LangGraph serve al *grafo* (contesto, resume) e il suo formato è interno, non pensato per la UI. La trascrizione dà titoli, anteprime e ricarica affidabile della chat.

Le tabelle vanno aggiunte a `db/init.sql` (che gira solo alla prima inizializzazione del volume) **e** create idempotentemente all'avvio (`CREATE TABLE IF NOT EXISTS` in `ensure_schema()`), così i DB esistenti si aggiornano da soli.

### 2.2 Modulo `agent/conversations.py`
Funzioni pure/SQL parametrizzato (nessuna generazione LLM), tutte con `engine` iniettato:
- `ensure_schema(engine)` — crea le tabelle se assenti.
- `create_conversation(engine, operator_id, title=DEFAULT_TITLE) -> dict`
- `list_conversations(engine, operator_id) -> list[dict]` (per `updated_at` desc)
- `get_messages(engine, conversation_id) -> list[dict]`
- `append_message(engine, conversation_id, role, content, geojson=None)` — aggiorna anche `updated_at`.
- `rename_conversation(engine, conversation_id, title)`
- `delete_conversation(engine, conversation_id)` (cascade sui messaggi)
- `derive_title(text, max_len=40) -> str` — **funzione pura**: prima riga del messaggio, normalizzata e troncata con `…`; stringa vuota → `DEFAULT_TITLE`.
- `DEFAULT_TITLE = "NUOVA CONVERSAZIONE"`.

Il titolo automatico si applica in `/api/chat` **solo se** il titolo corrente è ancora `DEFAULT_TITLE`.

### 2.3 Checkpointer persistente (`agent/__init__.py`)
- Se `langgraph-checkpoint-postgres` (+`psycopg`) è installato **e** il DB è raggiungibile → `PostgresSaver` con `.setup()` (tabelle proprie del checkpointer), altrimenti **fallback a `MemorySaver`** con log esplicito.
- `thread_id = conversation_id` (sostituisce l'attuale `session_id`).
- **Nota dipendenze (verificata):** `langgraph-checkpoint-postgres` e `psycopg` (v3) **non sono installati**; il progetto usa `psycopg2`. Vanno aggiunti a `requirements.txt` (gitignored → installazione locale). Se mancano, il fallback mantiene il sistema funzionante senza memoria persistente.

### 2.4 API (`server.py`)

| Metodo | Endpoint | Body/Query | Risposta |
|---|---|---|---|
| POST | `/api/conversations` | `{operator_id}` | conversazione creata |
| GET | `/api/conversations` | `?operator_id=` | lista |
| GET | `/api/conversations/{id}/messages` | — | trascrizione |
| PATCH | `/api/conversations/{id}` | `{title}` | `{status:"ok"}` |
| DELETE | `/api/conversations/{id}` | — | `{status:"ok"}` |

`ChatRequest` acquisisce `conversation_id: str | None`. In `/api/chat`:
1. `conversation_id` assente → comportamento attuale (thread effimero, nessun salvataggio);
2. presente → salva il messaggio utente, esegue l'agente, salva la risposta (con `geojson`), aggiorna `updated_at`, e imposta il titolo da `derive_title` se ancora quello di default.

Se il DB è offline gli endpoint conversazioni rispondono **503** con messaggio chiaro; `/api/chat` continua a funzionare senza salvataggio (coerente con la scelta "tool geo attivi col DB spento").

### 2.5 Frontend
- **Login** (`js/script.js`): salva `operator_id` in `localStorage` (`aegis_operator_id`).
- **Sidebar** (`aegis.html`): sopra `#chat-history`, un blocco conversazioni:
  - pulsante `+ NUOVA CHAT`;
  - lista scrollabile: titolo troncato, evidenziazione dell'attiva, azioni **✎ rinomina** / **🗑 elimina** visibili su hover.
- **Comportamento** (`js/script.js`):
  - all'avvio: carica la lista; se non c'è una conversazione attiva ne crea una nuova;
  - click su una conversazione → carica la trascrizione in `#chat-history` (markdown già renderizzato) e imposta `conversation_id`;
  - `sendMessage` invia `conversation_id` (sostituisce `session_id`) e, al primo messaggio, aggiorna il titolo nella lista;
  - elimina → conferma, poi rimuove; se era l'attiva, apre/crea un'altra conversazione.
- **CSS** (`css/style.css`): stile della lista coerente col tema ambra/tattico.

---

## 3. Errori

| Caso | Comportamento |
|---|---|
| DB offline | endpoint conversazioni → 503 con messaggio; `/api/chat` funziona senza persistenza; checkpointer → `MemorySaver` |
| `conversation_id` inesistente | 404 su messaggi/patch/delete; `/api/chat` procede senza salvare |
| Titolo vuoto in PATCH | 400 |
| Dipendenze Postgres checkpointer assenti | fallback `MemorySaver` + log warning |

---

## 4. Testing

- `derive_title`: troncamento, prima riga, spazi, stringa vuota → default. **Funzione pura, offline.**
- CRUD conversazioni: contro DB reale se disponibile, altrimenti `pytest.skip` (marker), così la suite resta verde anche col container spento.
- Selezione del checkpointer: con dipendenze assenti → `MemorySaver` (test sul selettore isolato).
- I test esistenti restano verdi (il campo `session_id` resta accettato per compatibilità).

---

## 5. Fuori scope (YAGNI)

- **Autenticazione reale**: `operator_id` è passato dal client e non verificato — separa le conversazioni, non le protegge. L'auth (JWT/sessioni) resta una feature a parte.
- Ricerca full-text nelle chat, cartelle/tag, export.
- Paginazione della lista (le conversazioni di una demo sono poche).
- Ripristino dei layer GeoJSON sulla mappa alla riapertura di una chat: la trascrizione salva `geojson`, ma il redraw automatico dello storico è fuori scope (si ridisegna solo alla nuova risposta).

---

## 6. Rischi e mitigazioni

| Rischio | Mitigazione |
|---|---|
| Dipendenze checkpointer mancanti | fallback `MemorySaver`, sistema comunque operativo |
| `db/init.sql` non rieseguito su volumi esistenti | `ensure_schema()` idempotente all'avvio |
| Regressione del contratto chat | `session_id` resta accettato; `conversation_id` è opzionale |
| Sidebar già affollata (contiene la chat) | il blocco conversazioni è compatto e scrollabile, sopra `#chat-history` |

---

## 7. Criteri di successo

- Creo una chat, scrivo, **riavvio il server**, riapro la chat: trascrizione e contesto ci sono.
- La sidebar elenca le conversazioni dell'operatore, ordinate per attività recente.
- Rinomina ed elimina funzionano; il titolo si genera dal primo messaggio.
- Col DB spento la chat continua a funzionare (senza salvataggio) e l'app non crasha.
- Suite esistente verde + nuovi test.
