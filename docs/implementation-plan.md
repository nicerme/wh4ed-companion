# Implementation Plan — WFRP4e Rule Assistant

## Założenia

- **Faza 1**: w pełni lokalnie, zero kosztów — Docker Compose
- **Faza 2**: deployment na tanie/darmowe usługi (Mikrus / Render / Fly.io + Supabase/Neon + Groq)
- **Dane**: znormalizowany pipeline dla Core Rulebook + 7 dodatków
- **Frontend MVP**: prosty HTML/JS chat → potem React Web / React Native

---

## Architektura

```
Browser / React Native
        │
        ▼
   NestJS API  (:3000)
        │
   ┌────┴─────────────────┐
   │                       │
Router (Ollama/Groq)   Entity Search
JSON intent            PostgreSQL + pgvector
   │                       │
   └────────┬──────────────┘
            │
      Rules Engine
     (NestJS services)
            │
      RAG context
     (pgvector chunks)
            │
   Answer Generator
   (Ollama/Groq LLM)
            │
        odpowiedź
```

---

## Stack

| Warstwa | Lokalnie (Faza 1) | Produkcja (Faza 2) |
|---|---|---|
| Frontend | Plik HTML + fetch | Cloudflare Pages / Vercel Free |
| Backend | NestJS w Docker | Render Free / Fly.io / Mikrus |
| Baza | PostgreSQL + pgvector w Docker | Supabase Free / Neon Free |
| LLM router | Ollama (lokalne) | Groq API (darmowy tier) |
| LLM generator | Ollama (lokalne) | Groq API |
| Embeddingi | Ollama `nomic-embed-text` | Groq / OpenRouter |

---

## Etap 0 — Przygotowanie Danych (już częściowo zrobione)

### 0.0 Seed Script — ręczne zasilenie bazy danych

Na tym etapie nie piszemy parsera PDF od nowa. Używamy tego co mamy:
- concept1 Kotlin importer (już działa) → surowy JSON w `data/output/`
- `scripts/normalize_spells.py` → znormalizowany JSON w `data/normalized/`

Potrzebujemy tylko jednego skryptu TypeScript który wczyta znormalizowane JSON-y
i wstawi je do PostgreSQL. Odpala się z palca jeden raz per ksiąg.

```bash
npx ts-node scripts/seed.ts --book winds_of_magic
npx ts-node scripts/seed.ts --book core_rulebook
npx ts-node scripts/seed.ts --all
```

#### `scripts/seed.ts`

```typescript
// Wczytuje data/normalized/<book>/*.json i wstawia do tabeli entities
// Wymaga działającego PostgreSQL (lokalnie przez Docker Compose)
// DATABASE_URL z .env lub argumentu

// Użycie:
//   npx ts-node scripts/seed.ts --book winds_of_magic
//   npx ts-node scripts/seed.ts --all
```

Skrypt:
1. Wczytuje pliki z `data/normalized/<book>/` (spells.json, careers.json itd.)
2. Upsert do tabeli `entities` (insert or update by id)
3. Generuje embeddingi przez Ollama i wstawia do `chunks`
4. Wypisuje podsumowanie: ile wstawiono / zaktualizowano

> Ten skrypt jest tymczasowy — docelowo seed data będą statycznymi plikami
> w repozytorium (po zakończeniu ekstrakcji ze wszystkich ksiąg) i będą
> automatycznie ładowane przy `docker compose up`.

#### Śledzenie numerów stron (`sourcePages`)

Każda encja w znormalizowanym JSON-ie musi mieć pole `sourcePages: number[]`
z numerami stron PDF na których się pojawia. Umożliwia referencje w odpowiedziach:
*"Patrz Winds of Magic str. 62"*.

Podejście dla obecnego Kotlin importera (zanim zrobimy port TS):
- Strony są hardcoded w klasach Book (np. `WindsOfMagic.importSpells` — patrz
  `concept1/…/books/WindsOfMagic.kt` i `docs/wom-parser-rules.md`)
- Skrypt `normalize_*.py` uzupełnia `sourcePages` na podstawie mapy zakresów stron:

```python
# Mapa: book → content_type → lista zakresów stron
PAGE_MAP = {
    "winds_of_magic": {
        "spells": [
            {"pages": list(range(26, 28)),  "lores": None},           # Arcane (wszystkie lore)
            {"pages": list(range(62, 66)),  "lores": ["BEASTS"]},
            {"pages": list(range(74, 78)),  "lores": ["DEATH"]},
            {"pages": list(range(86, 90)),  "lores": ["FIRE"]},
            {"pages": list(range(98, 102)), "lores": ["HEAVENS"]},
            {"pages": list(range(110,114)), "lores": ["METAL"]},
            {"pages": list(range(122,126)), "lores": ["LIFE"]},
            {"pages": list(range(134,138)), "lores": ["LIGHT"]},
            {"pages": list(range(146,150)), "lores": ["SHADOWS"]},
        ],
        "careers": [
            {"pages": [36],  "class": "WARRIORS"},
            {"pages": [38],  "class": "ACADEMICS"},
            {"pages": [42],  "class": "PEASANTS"},
            {"pages": [40,56,68,80,92,104,116,128,140], "class": "ACADEMICS"},
        ],
        "trappings": [{"pages": [151]}],
    },
    "core_rulebook": {
        "skills":   [{"pages": list(range(118,132))}],
        "talents":  [{"pages": list(range(132,148))}],
        "spells":   [{"pages": list(range(240,258))}],
        "careers":  [{"pages": list(range(53,153))}],   # przybliżone — per klasa
        "traits":   [{"pages": list(range(338,344))}],
        "trappings":[{"pages": list(range(294,310))}],
        "diseases": [{"pages": list(range(186,189))}],
        "blessings":[{"pages": [221]}],
        "miracles": [{"pages": list(range(222,229))}],
    },
}
```

Zaklęcia przypisywane są do stron na podstawie lore:
- zaklęcie z `lore: ["BEASTS"]` → `sourcePages: [62, 63, 64, 65]`
- zaklęcie arcane (wszystkie lore) → `sourcePages: [26, 27]`

> **Dokładność**: to są zakresy sekcji, nie dokładne strony konkretnego zaklęcia.
> Wystarczy dla referencji ("szukaj w tej okolicy").
> Dokładne numery stron per encję daje dopiero port TS z `pdfjs-dist`
> (patrz sekcja 0.0.OPTIONAL).

#### Kolejność

```
[x] 0.0.1 — normalize_spells.py (gotowe — WoM, bez sourcePages)
[ ] 0.0.2 — dodanie sourcePages do normalize_spells.py (mapa zakresów WoM)
[ ] 0.0.3 — normalize_*.py dla pozostałych typów (skills, talents, careers itd.)
[ ] 0.0.4 — normalize_all.py (master script dla wszystkich ksiąg)
[ ] 0.0.5 — scripts/seed.ts (wstawienie do DB)
```

---

### 0.0.OPTIONAL — Port Importera PDF → TypeScript + Platformy

> **Opcjonalne — wraca po MVP.**

Cel: własna implementacja parsera PDF w TypeScript, bez zależności od JVM/Kotlina.
Potrzebna gdy chcemy parser jako część aplikacji (web, Android, iOS).

#### Node.js / NestJS CLI — `pdfjs-dist`

Biblioteka: `pdfjs-dist` (Mozilla PDF.js) — działa w Node.js, udostępnia
`fontName`, `transform[0]` (rozmiar pt), `transform[4/5]` (pozycja X/Y).
Port logiki tokenizacji z Kotlina jest 1:1.

Każda encja dostaje `sourcePages: number[]` — numery stron z których pochodzi.
Umożliwia referencje: *"Patrz Winds of Magic str. 62"*.

Weryfikacja przed pisaniem — sprawdź czy pdfjs zwraca te same nazwy czcionek:
```bash
npx ts-node scripts/inspect-fonts.ts --pdf data/pdfs/winds_of_magic.pdf
```

#### React Web — import w przeglądarce

`pdfjs-dist` działa natywnie w przeglądarce (to silnik PDF Firefoksa).
PDF zostaje na urządzeniu użytkownika — do backendu leci tylko JSON.

```
User wybiera PDF → pdfjs parsuje lokalnie → POST /import { entities: [...] }
```

#### React Native Android — Native Module

Kotlin z concept1 pakowany jako Android Native Module.
Cienki bridge: `parseBook(pdfPath, bookType)` → JSON string → JS.
PDF pbox-android już jest w concept1 — tylko owinąć w RN module.

#### React Native iOS — opcjonalne / odkładamy

Brak iOS targetu w concept1 KMP. Opcje: PDFKit (Swift port) lub WebView fallback.
Odkładamy po stabilnym Android + Web.

```
[ ] OPTIONAL.1 — inspect-fonts.ts (weryfikacja czcionek w pdfjs)
[ ] OPTIONAL.2 — pdf-loader.ts + two-column-lexer.ts (Node.js)
[ ] OPTIONAL.3 — token-stream.ts + text-token.ts
[ ] OPTIONAL.4 — winds-of-magic.ts book + resolveToken
[ ] OPTIONAL.5 — spell-parser.ts (weryfikacja vs Kotlin output)
[ ] OPTIONAL.6 — sourcePages tracking
[ ] OPTIONAL.7 — pozostałe parsery i księgi
[ ] OPTIONAL.8 — React Web adapter (pdfjs browser build)
[ ] OPTIONAL.9 — React Native Android Native Module
[ ] OPTIONAL.10 — iOS (PDFKit Swift port)
```

---

### 0.1 Pipeline ekstrakcji (concept1 importer)

Każdy PDF przechodzi przez ten sam pipeline:

```
PDF (oficjalny Cubicle 7)
        │
concept1 PdfCompendiumImporter
        │
raw JSON (skills/talents/spells/careers/traits/trappings/diseases/journal)
        │
scripts/normalize_*.py
        │
normalized JSON (ustandaryzowany format z id/type/lore/effects/rawText)
        │
data/output/<book_name>/
```

Obsługiwane księgi i pliki wejściowe:

| Plik PDF | Zawartość |
|---|---|
| `rulebook.pdf` | skills(123), talents(167), careers(64), traits(81), trappings(227), blessings(19), miracles(60), diseases, journal |
| `winds_of_magic.pdf` | spells(200+), careers(12) |
| `up_in_arms.pdf` | careers(14), talents(12), weapons |
| `archives_of_the_empire_1.pdf` | careers, trappings |
| `archives_of_the_empire_2.pdf` | careers, trappings |
| `enemy_in_shadows_companion.pdf` | spells |
| `sea_of_claws.pdf` | TBD |

### 0.2 Znormalizowany format (wspólny dla wszystkich ksiąg)

Każda encja ma:

```json
{
  "id": "spell_belligerence_bloodmarsh",
  "name": "Belligerence of the Bloodmarsh",
  "type": "spell",
  "source": "winds_of_magic",
  "lore": ["BEASTS", "DEATH"],
  "castingNumber": 2,
  "range": { "type": "formula", "value": "WP_BONUS_YARDS" },
  "target": { "type": "creature", "count": 1, "entity": "Fenbeast" },
  "duration": "instant",
  "effects": [],
  "references": [{ "book": "WFRP", "page": 190 }],
  "rawText": "You imbue a Fenbeast..."
}
```

Pole `source` dodawane automatycznie przez skrypt na podstawie nazwy folderu wejściowego.  
Pole `effects[]` wypełniany w Etapie 2 przez LLM enrichment pipeline.

### 0.3 Skrypty normalizacji do napisania

```
scripts/
  normalize_spells.py      ✅ gotowe
  normalize_skills.py      
  normalize_talents.py     
  normalize_careers.py     
  normalize_traits.py      
  normalize_trappings.py   
  normalize_all.py         ← master script, odpala wszystkie
```

`normalize_all.py` przyjmuje `--book <nazwa>` lub `--all`, produkuje jeden zbiorczy plik `data/normalized/<book>.json`.

---

## Etap 1 — Lokalny Backend (Docker Compose)

### 1.1 Struktura projektu

```
wh4ed-companion/
  concept/          (FoundryVTT reference — read only)
  concept1/         (wfrp-master reference — read only)
  data/
    pdfs/           (gitignored)
    output/         (raw JSON z importera — gitignored)
    normalized/     (znormalizowany JSON — gitignored)
  docs/
  scripts/          (Python transform scripts)
  backend/          (NestJS — tworzone w tym etapie)
  frontend/         (HTML chat — tworzone w tym etapie)
  docker-compose.yml
```

### 1.2 `docker-compose.yml`

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: wfrp
      POSTGRES_USER: wfrp
      POSTGRES_PASSWORD: wfrp
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  ollama:
    image: ollama/ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama

  backend:
    build: ./backend
    ports:
      - "3000:3000"
    environment:
      DATABASE_URL: postgres://wfrp:wfrp@postgres:5432/wfrp
      OLLAMA_URL: http://ollama:11434
    depends_on:
      - postgres
      - ollama

  frontend:
    image: nginx:alpine
    ports:
      - "8080:80"
    volumes:
      - ./frontend:/usr/share/nginx/html:ro

volumes:
  pgdata:
  ollama_data:
```

Modele Ollama do pobrania po `docker compose up`:
```bash
docker exec wh4ed-ollama ollama pull llama3.2        # router + generator (~2GB)
docker exec wh4ed-ollama ollama pull nomic-embed-text # embeddingi (~270MB)
```

### 1.3 Schemat Bazy Danych

```sql
-- Encje gry (zaklęcia, talenty, kariery, bronie, traity itd.)
CREATE TABLE entities (
  id          TEXT PRIMARY KEY,          -- "spell_belligerence_bloodmarsh"
  type        TEXT NOT NULL,             -- "spell" | "talent" | "career" | "trait" | ...
  name        TEXT NOT NULL,
  aliases     TEXT[],                    -- alternatywne nazwy do wyszukiwania
  source      TEXT NOT NULL,             -- "core_rulebook" | "winds_of_magic" | ...
  raw_json    JSONB NOT NULL,            -- pełny znormalizowany obiekt
  raw_text    TEXT,                      -- surowy tekst efektów/opisów
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_entities_type   ON entities(type);
CREATE INDEX idx_entities_name   ON entities USING gin(to_tsvector('english', name));
CREATE INDEX idx_entities_source ON entities(source);

-- Relacje między encjami (wypełniane przez LLM enrichment w Etapie 2)
CREATE TABLE relations (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_entity_id TEXT REFERENCES entities(id),
  relation_type    TEXT NOT NULL,    -- "grants_trait" | "requires_skill" | "modifies_characteristic" | ...
  target_entity_id TEXT REFERENCES entities(id),
  condition        TEXT,             -- "if_missing" | "on_critical" | ...
  metadata         JSONB
);

CREATE INDEX idx_relations_source ON relations(source_entity_id);
CREATE INDEX idx_relations_target ON relations(target_entity_id);

-- Chunki tekstu z embeddingami (RAG)
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE chunks (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_id   TEXT REFERENCES entities(id),
  text        TEXT NOT NULL,
  embedding   vector(768),           -- nomic-embed-text = 768 dims
  metadata    JSONB
);

CREATE INDEX idx_chunks_embedding ON chunks USING ivfflat (embedding vector_cosine_ops);

-- Historia rozmów
CREATE TABLE conversations (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id  TEXT NOT NULL,
  role        TEXT NOT NULL,         -- "user" | "assistant"
  content     TEXT NOT NULL,
  metadata    JSONB,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_conversations_session ON conversations(session_id);
```

### 1.4 Struktura NestJS (`backend/`)

```
backend/src/
  app.module.ts
  
  chat/
    chat.controller.ts       POST /chat
    chat.service.ts          orkiestracja całego pipeline
    chat.module.ts
  
  router/
    router.service.ts        tekst → JSON intent (Ollama)
    router.module.ts
    dto/intent.dto.ts        typy Intent + Entity
  
  entities/
    entities.service.ts      search + CRUD
    entities.module.ts
    entities.repository.ts   zapytania do PostgreSQL
  
  rules/
    rules.module.ts
    handlers/
      wounds.handler.ts      obliczanie ran
      test.handler.ts        d100 + SL resolver
      advancement.handler.ts koszty XP
      combat.handler.ts      damage, conditions
      spell.handler.ts       CN, lore, overcasting
    
  rag/
    rag.service.ts           similarity search po pgvector
    embeddings.service.ts    generowanie embeddingów (Ollama)
    rag.module.ts
  
  llm/
    llm.service.ts           wrapper na Ollama HTTP API
    llm.module.ts
  
  seed/
    seed.service.ts          import normalized JSON → DB
    seed.command.ts          CLI: npm run seed
```

### 1.5 Pipeline Chat (`chat.service.ts`)

```typescript
async chat(message: string, sessionId: string): Promise<string> {
  // 1. Router — klasyfikacja pytania
  const intent = await this.routerService.classify(message);
  // → { intent: "check_interaction", entities: [{type:"spell", name:"Belligerence..."}, ...] }

  // 2. Entity Resolver — znajdź encje w bazie
  const entities = await this.entitiesService.resolveMany(intent.entities);

  // 3. Rules Handler — deterministyczna odpowiedź jeśli możliwa
  const rulesResult = await this.rulesService.execute(intent, entities);

  // 4. RAG — dodatkowy kontekst z embeddingów
  const ragContext = await this.ragService.search(message, { limit: 5 });

  // 5. Generator — naturalna odpowiedź
  const answer = await this.llmService.generate({
    question: message,
    rulesResult,
    ragContext,
    entities,
  });

  // 6. Zapis historii
  await this.conversationsService.save(sessionId, message, answer);

  return answer;
}
```

### 1.6 Router Service — prompt

```typescript
const ROUTER_PROMPT = `
You are a WFRP4e question classifier. Return ONLY valid JSON.

Intent types:
- explain_entity: user asks what something is or does
- check_interaction: user asks if/how two things interact
- calculate_rule: user asks for a numeric result (wounds, XP cost, SL)
- find_entity: user is looking for something by description
- unknown: anything else

Entity types: spell, talent, trait, skill, career, weapon, armour, condition

Question: "${message}"

Return: { "intent": "...", "entities": [{ "type": "...", "name": "..." }] }
`;
```

### 1.7 Intent Types

```typescript
type IntentType =
  | "explain_entity"      // "co robi Frenzy?"
  | "check_interaction"   // "czy X stackuje z Y?"
  | "calculate_rule"      // "ile ran ma Ogr?"
  | "find_entity"         // "szukam zaklęcia które daje Frenzy"
  | "unknown";            // fallback → czysty RAG

interface ResolvedEntity {
  type: string;
  name: string;
  record: Entity | null;  // null jeśli nie znaleziono w DB
}
```

---

## Etap 2 — LLM Enrichment (effects[])

Po uruchomieniu Etapu 1 odpalamy enrichment pipeline który wypełnia `effects[]` dla każdej encji.

### 2.1 Skrypt enrichment

```bash
scripts/enrich_effects.py --input data/normalized/winds_of_magic.json \
                          --output data/enriched/winds_of_magic.json \
                          --ollama http://localhost:11434
```

Dla każdego zaklęcia z pustym `effects[]`:

```
prompt → Ollama:
"Extract structured effects from this WFRP4e spell description.
Return JSON array of effects.
Possible types: grant_trait, modify_characteristic, apply_condition,
                deal_damage, heal_wounds, create_entity, special

Description: <rawText>"
```

Wynik trafia z powrotem do JSON i do tabeli `relations` w bazie.

### 2.2 Tabela relacji po enrichmencie

```json
{
  "source": "spell_belligerence_bloodmarsh",
  "relation": "grants_trait",
  "target": "trait_frenzy",
  "condition": "if_missing"
}
```

Dzięki temu pytanie "czy stackuje z Frenzy?" odpowiada deterministycznie:
→ `relations` WHERE `source = spell AND target = trait_frenzy AND condition = if_missing`  
→ odpowiedź: "Nie stackuje — zaklęcie nadaje Frenzy tylko jeśli cel go nie posiada."

---

## Etap 3 — Rules Handlers

Porty z `concept/src/system/` i `concept1/` do NestJS TypeScript:

| Handler | Źródło | Co liczy |
|---|---|---|
| `WoundsHandler` | `concept1/Wounds.kt` + `concept/standard.js` | Max wounds per size + talent mods |
| `TestHandler` | `concept1/TestResult.kt` | d100 → SL, critical/fumble |
| `AdvancementHandler` | `concept/advancement.js` | Koszt XP per advance |
| `DamageHandler` | `concept/actor.js#applyDamage` | Damage z AP layers, TB, Undamaging |
| `CombatHandler` | `concept/opposed-test.js` | Opposed SL, size multiplier |
| `SpellHandler` | `concept/cast-test.js` | CN, overcasting cost |
| `ConditionHandler` | `concept/actor.js#addCondition` | Condition state machine |

---

## Etap 4 — Frontend (HTML Chat MVP)

Prosty `frontend/index.html`:

```html
<!-- POST /chat { message, sessionId } → { answer } -->
```

Bez frameworka, bez bundlera — plain fetch + EventSource dla streamingu.  
Serwowany przez nginx w Docker.

React Native / React Web wchodzi **po** tym jak backend jest stabilny.

---

## Etap 5 — Deployment (Faza 2)

### Stack produkcyjny (darmowy)

| Co | Gdzie | Koszt |
|---|---|---|
| PostgreSQL + pgvector | Supabase Free (500MB) | $0 |
| NestJS backend | Render Free / Fly.io Free | $0 |
| Frontend | Cloudflare Pages | $0 |
| LLM (router + generator) | Groq API Free Tier | $0 (limity req/min) |
| Embeddingi | Groq / nomic via API | $0 |

### Zmiana konfiguracji lokalnie → produkcja

Tylko zmiana zmiennych środowiskowych:
```env
# Lokalnie
OLLAMA_URL=http://ollama:11434
DATABASE_URL=postgres://wfrp:wfrp@postgres:5432/wfrp

# Produkcja
GROQ_API_KEY=...
DATABASE_URL=postgres://...supabase.co/...
```

`LlmService` ma dwa adaptery (`OllamaAdapter`, `GroqAdapter`) wybierane przez env.

---

## Kolejność Implementacji (MVP)

```
[x] Etap 0.1 — Ekstrakcja danych z PDFów (concept1 importer)
[x] Etap 0.2 — normalize_spells.py
[ ] Etap 0.3 — normalize_*.py dla pozostałych typów + normalize_all.py

[ ] Etap 1.1 — docker-compose.yml (postgres + ollama + backend + frontend)
[ ] Etap 1.2 — Schemat bazy + migracje (TypeORM / Drizzle)
[ ] Etap 1.3 — seed command (JSON → DB)
[ ] Etap 1.4 — NestJS scaffold + moduły
[ ] Etap 1.5 — LlmService (Ollama wrapper)
[ ] Etap 1.6 — RouterService (intent classification)
[ ] Etap 1.7 — EntitiesService (search + resolve)
[ ] Etap 1.8 — RagService (embeddingi + similarity search)
[ ] Etap 1.9 — ChatService (orkiestracja pipeline)
[ ] Etap 1.10 — HTML frontend (prosty chat)

[ ] Etap 2 — LLM enrichment pipeline (effects[] + relations)

[ ] Etap 3 — Rules Handlers (wounds, test, damage, combat, spell)

[ ] Etap 4 — React Web / React Native (po stabilnym backendzie)

[ ] Etap 5 — Deployment na darmowe usługi
```

---

## Decyzje Techniczne

**ORM**: Drizzle ORM — lekki, TypeScript-first, dobry support dla Postgresa i pgvector.  
**Walidacja**: Zod na DTO poziomie zamiast class-validator.  
**LLM response**: structured outputs (JSON mode) przez Ollama i Groq — router nigdy nie zwraca plain tekstu.  
**Embeddingi**: `nomic-embed-text` przez Ollama lokalnie (768 dims) — ten sam model na produkcji przez API żeby wektory były kompatybilne.  
**Chunking**: każda encja dzielona na maksymalnie 3 chunki (opis, efekty, references) — nie robimy chunków całych rozdziałów.
