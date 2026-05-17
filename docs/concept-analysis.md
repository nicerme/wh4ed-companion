# WFRP4e FoundryVTT — Concept Repo Analysis

> Source: `concept/` (WFRP4e-FoundryVTT v9.6.0, Foundry V13)  
> Goal: extract what we can reuse and what we need to build for the NestJS rule-assistant.

---

## TL;DR

The repo is the **engine, not the encyclopedia**. It contains:
- Full data schemas (all actor/item types).
- Every deterministic rule formula (wounds, SL, damage, XP costs, conditions).
- All static lookup tables (difficulties, ranges, qualities, XP ladders, etc.).
- ~2100 active-effect scripts describing how premium-content items modify rules at runtime.

It does **not** contain actual game content (careers, talents, spells, weapons, creatures, species stats, critical tables) — those live in the paid `wfrp4e-core` module. The repo is essentially useless as a rules encyclopedia, but excellent as a rules **machine**.

---

## What's in the Repo

### `concept/system.json`

- System ID: `wfrp4e`, version `9.6.0`.
- Initiative formula: `i.value + ag.value / 100` (ag as tiebreaker).
- Primary token attribute: `status.wounds`; secondary: `status.advantage`.
- Grid distance: **2 yards per square**.
- Depends on external module `warhammer-lib ≥ 3.2.0` for base document classes.

### `concept/template.json` — Data Schemas

**Actor types**: `character`, `npc`, `creature`, `vehicle`.

Shared fields across all humanoid actors:
- **Characteristics** (10): `ws`, `bs`, `s`, `t`, `i`, `ag`, `dex`, `int`, `wp`, `fel` — each with `initial`, `modifier`, `advances`, `bonusMod`, `calculationBonusModifier`.
- **Status**: `wounds {value, max}`, `advantage {value, max}`, `criticalWounds {value, max}`, `sin`, `corruption`, `encumbrance {current, max}`, `mount`.
- **Details**: `species`, `gender`, `biography`, `gmnotes`, `size` (default `"avg"`), `move {value, walk, run}`, `hitLocationTable`.

Character-specific additions: `fate`, `fortune`, `resilience`, `resolve`, `experience {total, spent, log[]}`, career data, personal details (age, height, starsign, etc.).

**Item types**: `ammunition`, `armour`, `career`, `container`, `critical`, `disease`, `injury`, `money`, `mutation`, `prayer`, `psychology`, `talent`, `trapping`, `skill`, `spell`, `trait`, `weapon`, `extendedTest`, `vehicleMod`, `vehicleRole`, `vehicleTest`, `cargo`, `template`.

Notable item schemas:
- **Career**: `careergroup`, `class`, `level 1-5`, `status {tier, standing}`, `characteristics[]`, `skills[]`, `talents[]`, `trappings[]`, `incomeSkill[]`.
- **Weapon**: `damage {value, dice}`, `reach`, `range`, `weaponGroup`, `qualities[]`, `flaws[]`, `equipped`, `loaded {value, repeater, amt}`.
- **Armour**: `armorType`, `penalty`, `qualities`, `flaws`, `AP {head, lArm, rArm, lLeg, rLeg, body}`, `APdamage`.
- **Skill**: `advanced (bsc/adv)`, `grouped (isSpec/noSpec)`, `characteristic`, `advances`, `total`.
- **Spell**: `lore`, `CN {value, SL}`, `range`, `target`, `duration`, `damage`, `magicMissile`, `ritual`, `memorized`, `overcast {initial, valuePerOvercast}`.
- **Trait**: `rollable {damage, skill, rollCharacteristic, bonusCharacteristic, dice, attackType}`, `specification`, `qualities`, `flaws`.
- **ExtendedTest**: `SL {current, target}`, `test`, `failingDecreases`, `completion (none/reset/remove)`.

### `concept/packs/basic/` — Compendium Data

Only **154 JSON files** — all free content:
- **152 skills**: every Basic and Advanced skill with `characteristic`, `advanced (bsc/adv)`, `grouped (isSpec/noSpec)` flags. Specialist skills have a few canonical specialisations (Channelling per Wind, Language per culture, etc.).
- **3 money items**: Brass Penny (1p), Silver Shilling (12p), Gold Crown (240p).

> All careers, talents, weapons, spells, creatures, etc. live in the paid `wfrp4e-core` module — **not here**.

### `concept/src/system/config-wfrp4e.js` — Static Rule Constants

The single most portable file in the repo — pure lookup tables, no Foundry dependencies:

| Constant | Content |
|---|---|
| `xpCost.characteristic` | `[25,30,40,50,70,90,120,150,190,230,280,330,390,450,520]` |
| `xpCost.skill` | `[10,15,20,30,40,60,80,110,140,180,220,270,320,380,440]` |
| `difficultyModifiers` | `veasy:+60, easy:+40, average:+20, challenging:0, difficult:-10, hard:-20, vhard:-30` |
| `rangeModifiers` | Point Blank→Easy, Short→Average, Normal→Challenging, Long→Difficult, Extreme→Very Hard |
| `conditions` | 15 canonical conditions (ablaze, bleeding, blinded, broken, deafened, entangled, fatigued, poisoned, prone, stunned, surprised, unconscious, grappling, engaged, defeated) |
| `actorSizes` | tiny / ltl / sml / avg / lrg / enor / mnst + numeric equivalents |
| `itemQualities / itemFlaws` | full quality/flaw catalogue (Penetrating, Damaging, Impact, Durable, Precise, Reliable, Sharp, etc.) |
| `weaponQualities / weaponFlaws` | weapon-specific quality/flaw catalogue |
| `armorQualities / armorFlaws` | armour-specific |
| `propertyHasValue` | flags which qualities take a numeric value (Shield 2, Penetrating 3, etc.) |
| `magicLores` | petty, beasts, death, fire, heavens, metal, life, light, shadow + dark lores |
| `magicWind` | lore → wind name mapping |
| `moneyValues` | gc:240, ss:20, bp:1 (in pennies) |
| `earningValues` | b:2d10, s:1d10, g:1 |
| `traitBonuses` | Big/Brute/Fast/Tough etc. → characteristic deltas |
| `talentBonuses` | Savvy→+int, Suave→+fel, Marksman→+bs, etc. |
| `overCastTablesPerWind` | cost-per-dimension overcast tables per wind |
| `scriptTriggers` | ~40 hook names (preWoundCalc, woundCalc, preApplyDamage, applyDamage, calculateOpposedDamage, startTurn, endTurn, endRound, etc.) |

> `speciesCharacteristics`, `speciesSkills`, `speciesTalents`, etc. are **empty `{}`** — filled at runtime by premium modules.

### `concept/src/system/rolls/` — Deterministic Test Engine

The core rules machine (~3100 lines total):

**`test-wfrp4e.js`** — `computeResult()` (lines 190-481):
- `baseSL = floor(target/10) - floor(roll/10)` (standard mode).
- Automatic success threshold (default 96+, configurable), automatic failure (05-).
- Roll reversal (swap tens/units digit if result is better).
- Hit-location roll (separate d100 lookup).
- Critical/fumble: `roll % 11 == 0` (doubles). `roll <= target && doubles` → critical; `roll > target && doubles` OR `99/100` → fumble.
- Extended test SL accrual, fortune reroll, advantage add/drain mechanics.

**`attack-test.js` + `weapon-test.js`**:
- Quality effects: Dangerous (fumble on any roll with 9), Unreliable (-1 SL on success), Practical (+1 SL), Impale (crit on multiples of 10), Throwing (scatter on fail).
- Damage formula: `SL [base] + weapon.Damage (e.g. SB+4) + Damaging (unit die if > base) + Impact (add unit die) ± Spread (per range band)`.
- Blackpowder/Engineering/Explosives: misfire on even fumble.
- Ammo consumption, repeater `loaded.amt` decrement, reload ExtendedTest auto-creation.

**`cast-test.js`** — CN handling, partial channelling, miscast counter (minor/major/catastrophic), ingredient power/protection, overcast cost deduction.

**`opposed-test.js`** — SL comparison (attacker vs defender), tie-break by target number, weapon-length penalty (defender reach > attacker reach with no Infighter), size damage multiplier (≥2 size categories larger → multiplier = delta).

**`prayer-test.js`** — blessing/miracle handling, Wrath of the Gods on doubles failure.

### `concept/src/documents/actor.js` — Damage & Conditions

**`applyDamage()`** (canonical damage flow):
1. Determine hit location.
2. Per armour layer at location: process Weakpoints (ignored on even roll/crit), Partial (ignored on odd roll), Penetrating (ignores 1 AP for metal / all for non-metal), Zzap (ignores metal AP). Tally metal / non-metal / magical AP separately.
3. Add shield AP.
4. Apply TB (unless `DAMAGE_TYPE.IGNORE_TB` or `IGNORE_ALL`).
5. Apply Undamaging flaw (doubles total AP used).
6. Minimum 1 wound (unless Undamaging).
7. Queue critical wound if `wounds < 0` after hit.
8. Hack quality → `AP damage` on armour item.

**Condition state machine** (`addCondition` / `removeCondition`):
- Unconscious → also add Prone; on removal → add Fatigued.
- Bleeding / Poisoned / Broken / Stunned: when value reaches 0 → add Fatigued.
- Blinded / Deafened: track `roundReceived` for duration.

### `concept/src/model/actor/standard.js` — Derived Stats

Formulas (pure arithmetic — trivial to port):
| Derived value | Formula |
|---|---|
| Characteristic value | `initial + modifier + advances` |
| Characteristic bonus | `floor(value / 10) + bonusMod` |
| Walk | `move × 2` |
| Run | `move × 4` |
| Encumbrance max | `t.bonus + s.bonus` (×2 if species == Ogre) |
| Wounds (avg) | `sb + 2×tb + wpb` |
| Wounds (sml) | `2×tb + wpb` |
| Wounds (lrg) | `2 × avg formula` |
| Wounds (enor) | `4 × avg formula` |
| Wounds (mnst) | `8 × avg formula` |
| Wounds (tiny) | `1 + tb × multiplier` |
| Wounds (ltl) | `tb` |
| Advantage cap | `i.bonus` (or world-settings hard cap) |
| Skill total | `characteristic.value + advances + modifier` |
| Corruption max | `t.bonus + wp.bonus` |
| Critical Wounds max | `t.bonus` |

### `concept/src/system/advancement.js`

- `calculateAdvCost(currentAdvances, type)` → `xpCost[type][floor(advances/5)]` (in-career); double if out-of-career.
- Spell cost: Petty first `wp.bonus` free, then 50 XP each; arcane cost scales by `currentlyKnown / bonus`; ritual: fixed price; Chaos lores: free.
- Miracle cost: `100 × existingMiraclesTotalCount`.
- NPC auto-advance: sets characteristics and skills to `level × 5`, adds all talents.

### `concept/src/system/combat.js`

- Fear/Terror by size delta: **1 size smaller** → Fear; **2+ sizes smaller** → Terror (severity = delta).
- End-of-combat: corruption test, infection test, disease progression.
- Per-turn condition triggers via `scriptTriggers`.

### `concept/scripts/` — ~2100 Active Effect Scripts

Each file is a tiny JS snippet, keyed by item ID. These are the rule-riders for premium-content items (talents granting bonuses, mutations, etc.). They cannot be eval'd in NestJS, but can be used as a **semantic specification** of what each item does if you have the premium module. Trigger catalog: `~40 named hooks` (listed in `scriptTriggers`).

### `concept/static/` — Static Data Files

| File | Content |
|---|---|
| `lang/en.json` (2605 lines) | All UI strings, condition descriptions, difficulty names, lore names — useful as LLM context |
| `moo/tables/minormis.json` | Minor miscast table (1d100 → entry) |
| `moo/tables/majormis.json` | Major miscast table |
| `moo/tables/catastrophicmis.json` | Catastrophic miscast table |
| `moo/tables/gunfumble.json` | Blackpowder fumble table |
| `data/travel_data.json` | Road/river/sea distances between Empire settlements |
| `names/*.txt` | Name-generator wordlists (Human/Elf/Dwarf/Halfling, male/female) |

---

## What We Can Reuse Directly

### Extract into local DB (seed data)

- All 152 skills from `packs/basic/` → `skills` collection.
- 3 money items → `money` collection.
- All lookup tables from `config-wfrp4e.js` → JSON constants or a `rules_config` collection.
- 4 miscast/fumble tables from `static/moo/tables/` → `tables` collection.
- Travel distances from `static/data/travel_data.json` → `settlements` collection.
- Name wordlists from `static/names/*.txt` → `name_generator` data.
- `static/lang/en.json` → string localisation store (also feed to LLM as context).

### Port verbatim as NestJS services (pure functions, no Foundry deps)

- All arithmetic formulas from `standard.js`, `character.js`, `components/characteristics.js` — `DerivedStatsService`.
- `computeResult()` from `test-wfrp4e.js` — `TestResolverService`.
- `calculateAdvCost`, `calculateAdvRangeCost`, `calculateSpellCost` from `advancement.js` — `AdvancementService`.
- All static constants from `config-wfrp4e.js` — TypeScript `const` modules.
- `alterDifficulty(difficulty, steps)` from `utility-wfrp4e.js` — inline utility.

### Port with moderate effort

- Weapon/attack test pipeline (`attack-test.js` + `weapon-test.js`) — `CombatService`.
- Casting / channelling / prayer pipeline — `MagicService` + `PrayerService`.
- Opposed test resolver (`opposed-test.js`) — part of `CombatService`.
- `applyDamage()` from `actor.js` — `DamageService` (drop audio/socket calls, keep rule math).
- Condition state machine (`addCondition`/`removeCondition`) — `ConditionService`.
- Combat tick events from `combat.js` — `CombatRoundService`.
- Market/availability from `market-wfrp4e.js` — `MarketService`.

---

## What We Need to Build (Not in Repo)

### Content not present — needs licensed source or manual entry

| Missing | Notes |
|---|---|
| **All careers** (64+) | Schema is present, data is in `wfrp4e-core` premium module |
| **All talents** | Same — schema only |
| **All weapons & armour** | Schema only |
| **All spells** | Schema only |
| **All prayers / blessings** | Schema only |
| **All traits** | Schema only |
| **Bestiary / creatures** | Schema only |
| **Critical hit tables** | Per body part; in premium tables |
| **Species data** | All `speciesXxx` objects in config are empty `{}` |
| **Hit-location table rows** | Only key names present (`hitloc`, `snake`, `spider`); data in premium |
| **Mutations, diseases, injuries, psychology** | Schema only |
| **Random encounter / event / weather tables** | Not present |
| **Rules narrative text** | All `@UUID[Compendium.wfrp4e-core.journal-entries.*]` — in premium journals |
| **God/religion data**, **lore effect descriptions**, **symptom data** | All empty `{}` in config |
| **Class trappings (chargen)** | Empty `{}` |

### Infrastructure to build from scratch

- **LLM integration layer** — NestJS service wrapping Ollama HTTP API; passes rules-engine output + question as context, returns explanation. The engine's verdict is authoritative; the LLM explains.
- **Effect DSL** — Replace the `eval()`-based script runner with a typed discriminated-union effect system (e.g. `{ type: "modifyCharacteristic", stat: "ws", value: 5 }`) that covers the most common effect patterns.
- **Data extraction scripts** — One-time scripts to parse `concept/packs/basic/` and `config-wfrp4e.js` into seed migrations.
- **Query layer** — NLP → rules-engine intent mapping (the part that turns "what's the wound threshold for a Large creature?" into a `computeWounds("lrg", sb, tb, wpb)` call).
- **Chat API** — NestJS controller serving the HTML frontend; session management, question history.

---

## Recommended Implementation Order

1. **Constants extraction** — Copy all `config-wfrp4e.js` tables to TypeScript constants. Zero risk, immediate value.
2. **Schemas / DTOs** — Translate `template.json` into NestJS DTOs and local DB schemas (SQLite or MongoDB).
3. **Seed data** — Parse and import `packs/basic/` + money items into local DB.
4. **`DerivedStatsService`** — Wound formula, encumbrance, walk/run, skill total, corruption max — all pure arithmetic.
5. **`TestResolverService`** — Port `computeResult()` — the d100 engine. Write unit tests against known rolls.
6. **`AdvancementService`** — XP cost tables, spell cost.
7. **`CombatService`** — Weapon test pipeline → opposed resolution → damage → conditions.
8. **Ollama integration** — Wire LLM to explain hard-rule outputs; seed it with `lang/en.json` for terminology.
9. **Chat API + HTML UI** — Thin HTTP layer on top; chat-window frontend.
10. **Content** — Decide on content strategy (manual entry, licensed import, or restrict scope to user-supplied stats).

---

## Key File Paths

| Purpose | Path |
|---|---|
| System metadata | `concept/system.json` |
| Actor/item schemas | `concept/template.json` |
| All static rule constants | `concept/src/system/config-wfrp4e.js` |
| d100 test engine | `concept/src/system/rolls/test-wfrp4e.js` |
| Weapon/attack tests | `concept/src/system/rolls/attack-test.js`, `weapon-test.js` |
| Casting tests | `concept/src/system/rolls/cast-test.js`, `channel-test.js`, `wom-cast-test.js` |
| Prayer test | `concept/src/system/rolls/prayer-test.js` |
| Opposed test | `concept/src/system/opposed-test.js` |
| Damage + conditions | `concept/src/documents/actor.js` (lines 362-700 damage; 1045-1141 conditions) |
| Derived stats | `concept/src/model/actor/standard.js`, `character.js` |
| Advancement costs | `concept/src/system/advancement.js` |
| Combat round events | `concept/src/system/combat.js` |
| Skill seeds | `concept/packs/basic/` (154 JSON files) |
| UI strings / LLM context | `concept/static/lang/en.json` |
| Miscast / fumble tables | `concept/static/moo/tables/*.json` |
| Travel distances | `concept/static/data/travel_data.json` |
| Name wordlists | `concept/static/names/*.txt` |
| Effect scripts (rule riders) | `concept/scripts/*.js` (~2100 files) |
