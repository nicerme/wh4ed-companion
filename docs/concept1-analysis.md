# WFRP Master (concept1/) — Rules Analysis

> Source: `concept1/` (wfrp-master — Kotlin/Android + Firebase companion app)  
> Repo: https://github.com/fmasa/wfrp-master

---

## TL;DR

To aplikacja mobilna (Android, Kotlin Multiplatform + Firebase), nie silnik reguł. Zawiera **fragmentaryczną, ale czystą implementację kluczowych formuł mechanicznych** oraz kompletny model domenowy. Brak osadzonych danych z podręcznika (careers, talenty, bronie, zaklęcia) — są importowane z PDFów przez użytkownika w runtime.

Dla NestJS rule-assistant **największa wartość to**: implementacja SL/testu d100, formuła wounds, enumeracje (wszystkie typy broni, zbroi, jakości, warunki, ludy), mapowania talent/cecha → modyfikator statu oraz struktura Firestore jako schema dokumentów.

---

## 1. Zaimplementowane Reguły

### Test d100 i Success Levels
`concept1/common/src/commonMain/kotlin/cz/frantisekmasa/wfrp_master/common/core/domain/rolls/TestResult.kt`

```kotlin
successLevel = testedValue/10 - rollValue/10
AUTO_SUCCESS_THRESHOLD = 5   // roll ≤ 5 → zawsze sukces
AUTO_FAILURE_THRESHOLD = 96  // roll ≥ 96 → zawsze porażka
fumble/critical: rollValue % 11 == 0  // doubles
```

`DramaticResult` enum:
| SL | Wynik |
|---|---|
| 6+ | Astounding Success |
| 4–5 | Impressive Success |
| 2–3 | Success |
| 0–1 | Marginal Success |
| −1–0 | Marginal Failure |
| −3–−2 | Failure |
| −5–−4 | Impressive Failure |
| ≤−6 | Astounding Failure |

Testy jednostkowe w `common/src/commonTest/.../core/domain/rolls/TestResultTest.kt` — "roll 9 vs 60 = +6 SL", "roll 100 = fumble", "roll 11 vs 60 = critical" itd. Goldmine do weryfikacji implementacji.

Testy umiejętności: `testedValue = characteristic + advances + testModifier`. Zaawansowane umiejętności z 0 advances zablokowane (cytat z p.117 podręcznika).

### Formuła Wounds
`concept1/common/src/commonMain/kotlin/cz/frantisekmasa/wfrp_master/common/encounters/domain/Wounds.kt`

| Rozmiar | Formuła |
|---|---|
| TINY | 1 |
| LITTLE | TB |
| SMALL | 2×TB + WPB |
| AVERAGE | SB + 2×TB + WPB |
| LARGE | (SB + 2×TB + WPB) × 2 |
| ENORMOUS | (SB + 2×TB + WPB) × 4 |
| MONSTROUS | (SB + 2×TB + WPB) × 8 |

Modyfikatory wounds (`WoundsModifiers`):
- **Hardy** → +TB za każdy poziom talent
- **Swarm** → ×5 max wounds (non-stacking)
- **Construct** → WPB → SB w formule

### Hit Locations
`concept1/common/src/commonMain/kotlin/cz/frantisekmasa/wfrp_master/common/core/domain/HitLocation.kt`

| Lokalizacja | d100 |
|---|---|
| HEAD | 1–9 |
| LEFT_ARM | 10–24 |
| RIGHT_ARM | 25–44 |
| BODY | 45–79 |
| LEFT_LEG | 80–89 |
| RIGHT_LEG | 90–100 |

### Encumbrance
`common/.../core/domain/trappings/Encumbrance.kt`
- `max = SB + TB`
- Ubrana zbroja: −1 Enc
- Przedmioty w kontenerach: nie liczą się do Enc
- Protezy (ubrane): 0 Enc

### Damage Expression
`common/.../core/domain/trappings/DamageExpression.kt`
- Parsuje wyrażenia `SB + 4`, `+2` etc.
- `finalDamage = expression + SL` (min 0)

### Range Expression
`common/.../core/domain/trappings/WeaponRangeExpression.kt`
- Oblicza zasięg w jardach z podstawieniem SB.

### Initiative (4 strategie)
`common/.../combat/domain/initiative/`
- `InitiativeCharacteristicStrategy` — Initiative + Agility (opposed SL)
- `InitiativePlus1d10Strategy` — Initiative + d10
- `BonusesPlus1d10Strategy` — InitiativeBonus + AgilityBonus + d10
- `InitiativeTestStrategy` — d100 vs Initiative, rank po SL

### Waluta
`common/.../core/domain/Money.kt`
- 12 pennies = 1 shilling, 20 shillings = 1 crown (penny-based internally)

### Corruption
- `corruptionPointsBuffer = WPB + TB + bonus` (cytat p.183)
- **Pure Soul** talent → bonus do bufora

### Kondycje (state machine — TODO w kodzie, jeszcze niezaimplementowane)
`Condition.getFutureConditions` — Bleeding → Fatigued, Unconscious → Prone+Fatigued — oznaczone `@Suppress("unused") // TODO`.

---

## 2. Embedded Enumeracje (kompletne, bezpośrednio przenoszalne)

| Enum | Zawartość |
|---|---|
| `Characteristic` | WS, BS, S, T, I, Ag, Dex, Int, WP, Fel (+ canonical ORDER) |
| `Race` | HUMAN, HIGH_ELF, DWARF, WOOD_ELF, HALFLING, GNOME, OGRE + default size |
| `Size` | TINY → MONSTROUS (7 poziomów) |
| `SocialClass` | 9 klas (ACADEMICS, BURGHERS, COURTIERS…) |
| `SocialStatus.Tier` | BRASS / SILVER / GOLD |
| `Condition` | 12 kondycji z flagą stackable |
| `HitLocation` | 6 lokalizacji z d100 ranges |
| `MeleeWeaponGroup` | BASIC, BRAWLING, CAVALRY, FENCING, FLAIL, PARRY, POLEARM, TWO_HANDED |
| `RangedWeaponGroup` | BLACKPOWDER, BOW, CROSSBOW, ENTANGLING, ENGINEERING, EXPLOSIVES, SLING, THROWING |
| `WeaponQuality` | 23 jakości (ACCURATE, DAMAGING, IMPACT, IMPALE, PENETRATING, SHIELD…) z flagą `isRated` |
| `WeaponFlaw` | 7 wad (DANGEROUS, TIRING, UNDAMAGING, RELOAD…) |
| `ArmourType` | SOFT_LEATHER, BOILED_LEATHER, MAIL, PLATE, OTHER |
| `ArmourQuality` | FLEXIBLE, IMPENETRABLE |
| `ArmourFlaw` | PARTIAL, WEAKPOINTS |
| `ItemQuality` | DURABLE, FINE, LIGHTWEIGHT, PRACTICAL |
| `ItemFlaw` | BULKY, UGLY, SHODDY, UNRELIABLE |
| `Reach` | PERSONAL, VERY_SHORT, SHORT, AVERAGE, LONG, VERY_LONG, MASSIVE |
| `Availability` | COMMON, SCARCE, RARE, EXOTIC |
| `SpellLore` | 17 lore z przypisanym wiatrem (BEASTS/Ghur, FIRE/Aqshy…, PETTY, GREAT_MAW) |

### Talent/Trait → Modyfikatory Statystyk
`common/.../character/effects/CharacteristicChange.kt`

Hardcoded (25 talent/cech + delty statów):

| Talent/Cecha | Modyfikacja |
|---|---|
| Big | +10 S, +10 T, −5 Ag |
| Brute | +10 T, +10 S, −10 Ag |
| Clever | +10 Int, +10 I |
| Elite | +20 WS, BS, WP |
| Fast | +10 Ag |
| Leader | +10 Fel, WP |
| Tough | +10 T, WP |
| Savvy | +5 Int (×poziom) |
| Suave | +5 Fel (×poziom) |
| Marksman | +5 BS (×poziom) |
| Very Strong | +5 S (×poziom) |
| Lightning Reflexes | +5 Ag (×poziom) |
| Warrior Born | +5 WS (×poziom) |
| Very Resilient | +5 T (×poziom) |
| Nimble Fingered | +5 Dex (×poziom) |
| Sharp | +5 I (×poziom) |
| Coolheaded | +5 WP (×poziom) |
| Strong Back | +1 Enc max (×poziom) |
| Sturdy | +2 Enc max (×poziom) |

> Uwaga: mapowanie odbywa się po **przetłumaczonej nazwie** (string), nie po ID — wymaga mapowania na canonical English keys.

### Kalendarz Imperialny
`common/.../core/domain/time/ImperialDate.kt`
- 12 miesięcy (32–33 dni), 6 świąt wypadających między miesiącami (Hexenstag, Geheimnistag itd.)
- 8 dni tygodnia (Wellentag…Festag), 400 dni/rok

---

## 3. Modele Domenowe

Wszystko pod `common/src/commonMain/kotlin/cz/frantisekmasa/wfrp_master/common/`:

| Model | Kluczowe pola |
|---|---|
| `Character` | id, type (PC/NPC), name, career, socialClass, race, characteristicsBase/Advances (Stats), points (Points), conditions, woundsModifiers, money, size |
| `Stats` | 10 charakterystyk + agilityBonus, strengthBonus, toughnessBonus (= value/10) |
| `Points` | corruption, fate, fortune, wounds, maxWounds, resilience, resolve, sin, experience, spentExperience |
| `Career` | name, class, socialClass, Level[] {name, status, characteristics[], skills[], talents[], trappings[]} |
| `Skill` | name, characteristic, advanced (bool) |
| `Talent` | name, tests, maxTimesTaken |
| `Spell` | range, target, duration, castingNumber, effect, lore (SpellLore) |
| `Trait` | name, specifications, hasAttack, specifications[] |
| `Trapping` | name, encumbrance, availability, quantity + sealed TrappingType (MeleeWeapon, RangedWeapon, Armour, Container, Ammunition, SpellIngredient, Prosthetic…) |
| `Disease` | name, incubation (Countdown), duration (Countdown), symptoms[], diagnosis, treatment |
| `InventoryItem` | compendiumId, quantity, location (stored/carried/worn), containerItem, damage |
| `ArmourPart` | hitLocation, wornPieces, sumPoints() |
| `EquippedWeapon` | oblicza damage w czasie equipowania |
| `Combat` | round, turn, combatants[], advantage per side |
| `Wounds` | current, max, calculateMax(size, TB, SB, WPB) |

---

## 4. Firestore Schema (`firebase/firestore.rules`, 962 linie)

Najbardziej wartościowy plik dla definicji DTO w NestJS — zawiera kompletne walidatory dla każdego dokumentu z enumami inlinowanymi jako tablice stringów. Struktura kolekcji:

```
parties/{partyId}
  ├── skills, talents, spells, blessings, miracles, traits, trappings
  ├── diseases, careers, journalEntries, encounters
  └── characters/{characterId}
      ├── inventoryItems, skills, talents, traits
      ├── spells, blessings, miracles, diseases, countdowns
```

---

## 5. Czego Brakuje

| Brakujące | Uwagi |
|---|---|
| **XP advancement cost table** | Tylko `experience: Int` / `spentExperience: Int`, bez ladder 25/30/40/50/70… |
| **Difficulty modifier table** | `testModifier` to zwykły `Int`, bez mapy Very Easy +60…Very Hard −30 |
| **Automated damage resolution** | Aplikacja liczy rany manualnie (brak T+zbroja vs damage pipeline) |
| **Casting/miscast/channelling** | `castingNumber` jest w modelu ale bez logiki |
| **Critical-hit tables** | Brak |
| **Condition state machine** | Tylko TODO w kodzie |
| **Osadzone dane podręcznikowe** | Careers/talenty/bronie/zaklęcia importowane z PDFa przez usera — nie ma ich w repo |

---

## Co Przenosić do NestJS

**Priorytet wysoki (czyste funkcje, proste):**
- `TestResult.kt` + testy → `TestResolverService` (+ unit testy 1:1)
- `Wounds.calculateMax()` → `DerivedStatsService`
- `HitLocation` d100 ranges → lookup function
- Wszystkie enumeracje → TypeScript enums/union types
- Initiative strategies (4 funkcje)
- Talent → stat-change mappings (25 wpisów z `CharacteristicChange.kt`)
- `ImperialDate.kt` → kalendarz

**Priorytet średni:**
- `Encumbrance` formuły
- `DamageExpression` parser
- `firestore.rules` → wzorzec walidacji DTO

**Nie przenosić:**
- Logika importu z PDF (tightly coupled do Apache PDFBox + font metadata podręcznika)
- Firebase Cloud Functions (tylko avatar/duplication hooks)
- Logika UI (Jetpack Compose screens)

---

## Porównanie z concept/ (FoundryVTT)

| Aspekt | concept/ (FoundryVTT) | concept1/ (wfrp-master) |
|---|---|---|
| Silnik testów d100 | Pełny (SL, auto/fumble/crit, reversal, fortune) | Pełny (SL, auto/fumble/crit) + testy jednostkowe |
| Formuła wounds | Pełna z hookami | Pełna + WoundsModifiers |
| Enumeracje | W config-wfrp4e.js (2859 linii) | W Kotlinowych enumach (czyste, typowane) |
| Damage pipeline | Pełny (AP layers, TB, ward, Undamaging) | Brak |
| Osadzone dane | 152 skills + money | Brak (import z PDF) |
| Lookup tables (XP, difficulty) | Pełne w config-wfrp4e.js | Brak |
| Condition state machine | Pełna | TODO |
| Casting/magic | Pełne | Brak |
| Advancement | Pełne (XP ladders) | Brak |
| Domain model | FoundryVTT-coupled | Czysty, standalone |
| Testy jednostkowe | Brak | Są (TestResultTest goldmine) |
