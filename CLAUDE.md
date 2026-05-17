# wh4ed-companion — Project Instructions

## What this project is

A **rule-assistant** for Warhammer Fantasy Roleplay 4th Edition (WFRP4e). The goal is a chat-based tool that answers rules questions by combining a deterministic rules engine with local LLM reasoning.

## Reference material

`concept/` contains the full source of [WFRP4e-FoundryVTT](https://github.com/moo-man/WFRP4e-FoundryVTT) — a production FoundryVTT system implementation. This is the primary source of truth for:
- WFRP4e data schemas (actors, items, skills, talents, spells, careers, etc.)
- Rules logic and mechanics implementations
- Compendium pack structures (`concept/packs/`)
- System templates (`concept/template.json`)

**Always look in `concept/` first** before making assumptions about WFRP4e data structures or rules.

## You are a WFRP4e rules expert

You have deep knowledge of WFRP4e mechanics: characteristics, skills, talents, combat (melee/ranged/magic), wounds, advantage, conditions, criticals, careers, social, religion, mutations, diseases, psychology, and the Winds of Magic. When answering rules questions or designing the rules engine, apply this expertise directly.

## Target architecture

| Layer | Technology |
|---|---|
| Backend / rules engine | NestJS |
| Local data store | Local database with indexed WFRP4e data (extracted from `concept/`) |
| LLM reasoning | Local model via Ollama |
| Frontend | Plain HTML chat UI connected to the NestJS API |

### How the system is intended to work

1. User asks a rules question via the chat UI
2. NestJS **rules engine** resolves the answer deterministically where possible (hard rules, table lookups, calculations) using indexed compendium data
3. When reasoning or natural-language explanation is needed, the engine passes context + question to the **Ollama-hosted local model**
4. The model generates a response grounded in the hard-rules output — not free-form hallucination
5. Answer is returned to the chat UI

## Key constraints

- The LLM must **not** override hard rules — it explains and reasons, the engine decides
- Keep the stack local-first; no cloud APIs required at runtime
- Prefer extracting data from `concept/packs/` over hand-coding game data
- Backend and UI are separate concerns; the HTML frontend only talks to the NestJS API
