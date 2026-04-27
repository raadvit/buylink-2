# Domain Entity Template

Šablona pro každou entitu v `V2/domain.md`. **Strict format** — žádné odchylky bez ADR.

---

## Šablona

```markdown
<!-- SECTION: section_name_kebab -->
## EntityName

**Atributy:**
- field_name: type [, modifier1, modifier2]
- field_name: type
- ...

**Stavy a přechody:** [vynechat, pokud entita nemá stavový diagram]
- STATE_FROM → STATE_TO  [trigger / podmínka]
- ...

**Operations:**
- methodName(params) → return [popis side-effectů, pre/post conditions]
- ...

**Invariants:**
- [Pravidlo, které musí vždy platit]
- ...

**Vztahy:**
- EntityName 1--* RelatedEntity (popis vztahu)
- EntityName *--1 OtherEntity (...)
<!-- /SECTION: section_name_kebab -->
```

---

## Pravidla pro pole

### Atributy

Format: `field_name: type [, modifier1, modifier2]`

**Typy:**
- `UUID` — uuid v4
- `string` — text bez specifikace délky
- `string, max N` — text s max délkou
- `text` — long text
- `int` — celé číslo
- `decimal(P,S)` — decimal s precision a scale
- `boolean`
- `timestamp` — UTC ISO 8601
- `date`
- `enum: VAL1 | VAL2 | VAL3` — výčet hodnot
- `array<type>` — pole typů
- `json` — strukturované JSON pole
- `→ EntityName` — foreign key reference

**Modifikátory:**
- `pk` — primary key (typicky `id: UUID, pk`)
- `unique` — unikátní hodnota
- `required` — not null
- `default X` — výchozí hodnota
- `> N`, `≥ N`, `< N`, `≤ N` — numerické constraint
- `max N`, `min N` — délkové constraint pro string

### Stavy a přechody

Format: `STATE_FROM → STATE_TO  [trigger / podmínka]`

- Stavy SCREAMING_SNAKE_CASE.
- Pokud stav má více možných přechodů, samostatný řádek pro každý.
- Pokud přechod má podmínku, uveď ji v hranatých závorkách.
- Zakázané přechody explicitně uveď: `STATE_X → STATE_Y [zakázáno; důvod]`.

### Operations

Format: `methodName(params) → return [popis]`

- methodName camelCase nebo snake_case (drž konzistenci s konvencí projektu z `project.md`).
- Parametry s typy nepovinné, ale pomáhá to.
- Return value: typ nebo stav (např. `→ ACTIVE`).
- V hranatých závorkách side-effecty a constraints (`[pouze admin]`, `[atomicky s X]`).

### Invariants

Format: prostá věta nebo logické pravidlo.

- Píše se v přítomném čase, indikativu (`amount > 0`, ne `amount musí být větší než 0` — to už je v `> 0` modifikátoru).
- Pokud se týká vztahu mezi entitami, jasně to říct (např. `buyer_id ≠ Listing.owner_id`).

### Vztahy

Format: `EntityA cardinality EntityB (popis)`

- Cardinality: `1--1`, `1--*`, `*--1`, `*--*`, `1--0..1`, `*--0..*`.
- Pokud má vztah role (např. buyer/seller), uveď v popisu.
- Pokud je vztah composition (parent vlastní child a child bez parenta neexistuje), zaznač: `*-- (composition)`.

## Princip non-anemic model

Každá entita musí mít:
- atributy (data)
- operations (chování)
- invariants (obchodní pravidla)

Entity bez `Operations` jsou anemic data carriers, ne doménové objekty. Architekt přidává Operations vždy, i když "se to volá z service vrstvy" — operation tady popisuje **co se s entitou dá dělat z pohledu domény**, ne implementaci.
