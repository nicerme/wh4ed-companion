# Winds of Magic — Reguły Parsowania PDF

Przewodnik po tym jak importer z `concept1/` czyta plik `winds_of_magic.pdf`.  
Możesz użyć tego jako mapy żeby ręcznie dostosować logikę do polskiego wydania.

Źródło: `concept1/common/src/commonMain/kotlin/cz/frantisekmasa/wfrp_master/common/compendium/domain/importer/books/WindsOfMagic.kt`

---

## 1. Wykrywanie Czcionek (`resolveToken`)

Parser rozpoznaje fragmenty tekstu po **nazwie czcionki** i **rozmiarze w pt**.  
Każdy fragment dostaje etykietę (`Token`), która mówi parserowi co to jest.

| Czcionka | Rozmiar | Token | Znaczenie |
|---|---|---|---|
| `CaslonAntique-Bold-SC700` | dowolny | `BoxHeader` | Nagłówek bocznego panelu (ramki) |
| `CaslonAntique-Bold` | 19pt lub 22pt | `Heading1` | Nagłówek rozdziału / sekcji (np. nazwa Tradycji magii) |
| `CaslonAntique-Bold` | 10pt | `TableHeadCell` | Nagłówek kolumny tabeli |
| `crossbatstfb` + tekst `"h"` | — | `CrossIcon` | Ikona krzyżyka (cross/dagger) przy karierze |
| `ACaslonPro-Bold` | 12pt | `Heading3` | Nazwa zaklęcia / nazwa poziomu kariery |
| `ACaslonPro-Regular` | 9pt | `BodyCellPart` | Treść komórki tabeli |
| `ACaslonPro-Bold` | 10pt lub 9pt | `BoldPart` | Pogrubiony tekst (etykiety pól: CN:, Range:, Target:, Duration:) |
| `ACaslonPro-Italic` | 10pt lub 9pt | `ItalicsPart` | Kursywa (rasy przy karierach, opis fluffu) |
| `ACaslonPro-Regular` | 10pt lub 9pt | `NormalPart` | Zwykły tekst (wartości pól, treść opisów) |

> **Dla polskiego PDF**: sprawdź czy wydawca użył tych samych czcionek. Otwórz PDF w Acrobat Reader → `Właściwości dokumentu → Czcionki`. Jeśli czcionki się zgadzają, token detection zadziała bez zmian. Jeśli nie — trzeba podmienić nazwy czcionek w tabeli powyżej.

---

## 2. Układ Strony

Parser używa `TwoColumnPdfLexer` — dzieli każdą stronę na **lewą i prawą kolumnę** według środka strony (wyliczanego jako `(minX + maxX) / 2`). Zaklęcia i kariery są ułożone w dwóch kolumnach.

---

## 3. Zaklęcia (`importSpells`)

### Strony

```
26..27   — Arcane Spells (wspólne dla wszystkich Tradycji)
62..65   — Tradycja 1 (Beasts/Ghur)
74..77   — Tradycja 2 (Death/Shyish)
86..89   — Tradycja 3 (Fire/Aqshy)
98..101  — Tradycja 4 (Heavens/Azyr)
110..113 — Tradycja 5 (Metal/Chamon)
122..125 — Tradycja 6 (Life/Ghyran)
134..137 — Tradycja 7 (Light/Hysh)
146..149 — Tradycja 8 (Shadows/Ulgu)
```

### Jak parser wykrywa sekcje Tradycji (lore headings)

Parser szuka tokenów `Heading1` lub `Heading2` których tekst pasuje do regex:

```
(The )?Lore of ([a-z ]+)
```

Przykłady które pasują:
- `"Lore of Beasts"` → `SpellLore.BEASTS`
- `"The Lore of Fire"` → `SpellLore.FIRE`
- `"Lore of the Heavens"` → fragment po "Lore of" to "the Heavens" → `.replace("THE ", "")` → `HEAVENS`

Wyjątek: nagłówek `"New Arcane Spells"` (str. 26–27) jest zdefiniowany jako `specialLores` i przypisuje zaklęcie do **wszystkich Tradycji** (każde arcane zaklęcie jest duplikowane raz per Tradycja).

Koniec parsowania zaklęć: gdy parser trafi na `Heading1` z tekstem `"Ritual Magic"` (ignorując wielkość liter) lub skończy się strumień tokenów.

> **Dla polskiego PDF**: nagłówki Tradycji będą po polsku (np. "Tradycja Bestii", "Tradycja Ognia"). Trzeba zmienić regex i mapowanie na enum:
> ```
> (The )?Lore of ([a-z ]+)  →  Tradycja ([a-z ]+)
> ```
> I dopasować mapowanie np. `"Bestii"` → `SpellLore.BEASTS`, `"Ognia"` → `SpellLore.FIRE` itd.  
> Koniec sekcji zaklęć to odpowiednik "Ritual Magic" — po polsku sprawdź co stoi zamiast tego nagłówka.

### Jak parser czyta pojedyncze zaklęcie

Każde zaklęcie zaczyna się tokenem `Heading3` (ACaslonPro-Bold 12pt) — to **nazwa zaklęcia**.

Po nazwie parser oczekuje ściśle określonej sekwencji pól:

```
[BoldPart]   "CN:"
[NormalPart] <liczba całkowita>

[BoldPart]   "Range:"
[NormalPart] <tekst zasięgu>        ← może zawierać ItalicsPart (słowo "or")

[BoldPart]   "Target:"
[NormalPart] <tekst celu>

[BoldPart]   "Duration:"
[NormalPart] <czas trwania>
             <efekt — pierwszy akapit>

[NormalPart / BoldPart / ItalicsPart ...]  ← dalsza treść efektu aż do następnego Heading
```

> **Wyjątek**: zaklęcie `"Purple Pall of Shyish"` ma błędne formatowanie — brakuje oddzielnego `BoldPart "Duration:"`. Parser obsługuje to osobną ścieżką: jeśli po Target nie ma `BoldPart`, rozbija tekst na 3 linie i wyciąga z nich Target / Duration / effectStart.

> **Dla polskiego PDF**: etykiety pól (`CN:`, `Range:`, `Target:`, `Duration:`) będą po polsku. Trzeba sprawdzić jak wyglądają i podmienić logikę consumeOneOfType<Token.BoldPart>() — aktualnie parser po prostu konsumuje kolejny BoldPart bez sprawdzania jego treści, więc **polskie etykiety mogą zadziałać bez zmian** o ile kolejność pól w PDF jest zachowana.

---

## 4. Kariery (`importCareers`)

### Strony (numer strony → klasa społeczna)

```
36  → WARRIORS  (1 kariera)
38  → ACADEMICS (1 kariera)
42  → PEASANTS  (1 kariera)

Druga lista (wszystkie ACADEMICS):
40, 56, 68, 80, 92, 104, 116, 128, 140
```

Każda kariera zajmuje **jedną stronę**. Parser przetwarza po jednej stronie naraz.

### Jak parser czyta karierę (jedna strona)

**Lewa kolumna:**

1. `Heading` (dowolny) → **nazwa kariery**  
   (tekst jest normalizowany: każde słowo z wielką literą, np. `"HEDGE WIZARD"` → `"Hedge Wizard"`)

2. `NormalPart` → pierwsza linia to lista **ras** oddzielona przecinkami  
   (parser porównuje z `Race.values()`: `HUMAN`, `HIGH_ELF`, `DWARF`, `WOOD_ELF`, `HALFLING`, `GNOME`, `OGRE`)  
   Pozostałe linie = początek opisu kariery.

3. Następnie (jeśli opis nie wystartował) — `ItalicsPart` → opis fluffu (cytat)

4. Parser szuka sekcji atrybutów: `BoxHeader` lub `Heading1/2` lub `TableHeading/HeadCell` → skipuje je

5. Cztery poziomy kariery, dla każdego:
   - `BoldPart` → `"Nazwa Poziomu — Tier Standing"` (np. `"Apprentice Wizard — Brass 3"`)  
     Separator to `–` lub `—` (en-dash lub em-dash)
   - kolejne `BoldPart` → skipowane
   - tokeny do następnego `BoldPart "Talents"` → lista **umiejętności** (Skills)
   - tokeny po "Talents" do następnego `BoldPart` → **talenty** (comma-separated)
   - tokeny do następnego `BoldPart` lub `ItalicsPart` zaczynającego się od `'` → **wyposażenie** (Trappings)
   - Status tier: `BRASS` / `SILVER` / `GOLD` (case-insensitive match)

**Prawa kolumna:** dołączana do opisu kariery jako `BlockQuote` dla kursywy lub `NormalPart`.

> **Dla polskiego PDF**: największy problem to **tier kariery** — parser szuka `"Brass"`, `"Silver"`, `"Gold"` jako pierwszego słowa w statusie. Po polsku będzie `"Mosiądz"`, `"Srebro"`, `"Złoto"` — to wymaga zmiany w `SocialStatus.Tier.values().first { it.name.equals(tier, ignoreCase = true) }`.  
> Druga zmiana: etykieta `"Talents"` — parser szuka `BoldPart` którego tekst zaczyna się od `"Talents"`. Po polsku będzie inaczej.  
> Rasy też są matchowane po angielskiej nazwie (`HUMAN`, `HIGH_ELF` itd.) — trzeba dodać mapowanie z polskich nazw.

---

## 5. Ekwipunek (`importTrappings`)

### Strony

```
151 — tylko lewa kolumna, typ: ClothingOrAccessory
```

Parser używa `BasicTrappingsParser` z `ListDescriptionParser` (opisy jako lista punktowana).

---

## 6. Mapa Zmian dla Polskiego PDF

Podsumowanie co trzeba zmienić żeby zaadaptować importer pod polskie wydanie:

| Co | Gdzie w kodzie | Co zmienić |
|---|---|---|
| Numery stron | `WindsOfMagic.importSpells()`, `.importCareers()`, `.importTrappings()` | Nowe numery stron polskiego PDF |
| Regex nagłówka Tradycji | `SpellParser.loreHeadingRegex` | `"(The )?Lore of ([a-z ]+)"` → `"Tradycja ([a-z ]+)"` (lub inny wzorzec) |
| Mapowanie nazwy Tradycji → enum | `SpellParser.extractLore()` | Dodać tłumaczenia: `"Bestii"` → `BEASTS`, `"Ognia"` → `FIRE` itd. |
| Koniec sekcji zaklęć | `WindsOfMagic.importSpells() isEnd` | `"Ritual Magic"` → polska nazwa rozdziału |
| Tier statusu kariery | `CareerParser` linia z `SocialStatus.Tier.values().first` | `"Brass"/"Silver"/"Gold"` → `"Mosiądz"/"Srebro"/"Złoto"` (lub enum po polsku) |
| Etykieta "Talents" w karierze | `CareerParser` — `consumeUntil { it is Token.BoldPart && it.text.startsWith("Talents") }` | Polska nazwa sekcji talentów |
| Rasy w karierze | `CareerParser` — `Race.values().first { value.contains(it.name...) }` | Polskie nazwy ras → Race enum |
| Czcionki (jeśli inne) | `WindsOfMagic.resolveToken()` | Nowe nazwy czcionek z polskiego PDF |
| Arcane Spells nagłówek | `WindsOfMagic.importSpells() specialLores` | `"New Arcane Spells"` → polska nazwa |

---

## 7. Jak Sprawdzić Czcionki w Polskim PDF

1. Otwórz PDF w **Adobe Acrobat Reader** → `Plik → Właściwości → Zakładka Czcionki`
2. Poszukaj czcionek z rodziny `Caslon` lub `ACaslon`
3. Kliknij na tekst zaklęcia — Acrobat w panelu bocznym pokaże nazwę czcionki i rozmiar
4. Porównaj z tabelą z sekcji 1

Alternatywnie: narzędzie `pdffonts` (pakiet `poppler-utils`):
```bash
pdffonts winds_of_magic_pl.pdf
```

---

## 8. Struktura JSON Wyjściowego

Po poprawnym sparsowaniu każde zaklęcie wygląda tak:

```json
{
    "name": "Nazwa Zaklęcia",
    "range": "Willpower Bonus yards",
    "target": "1 target",
    "duration": "Instant",
    "castingNumber": 7,
    "effect": "Treść efektu w Markdown...",
    "lore": "BEASTS",
    "customLore": "",
    "isVisibleToPlayers": true
}
```

Każda kariera:
```json
{
    "name": "Hedge Wizard",
    "description": "Opis kariery w Markdown...",
    "socialClass": "ACADEMICS",
    "races": ["HUMAN"],
    "levels": [
        {
            "name": "Apprentice",
            "status": { "tier": "BRASS", "standing": 3 },
            "characteristics": ["WS", "T"],
            "skills": [
                { "name": "Channelling", "isIncomeSkill": false },
                { "name": "Endurance",   "isIncomeSkill": false }
            ],
            "talents": ["Petty Magic", "Second Sight"],
            "trappings": ["Knife", "Sling Bag"]
        }
    ]
}
```
