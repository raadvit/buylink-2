# Metrics — měření úspěchu

Pokud je projekt **pilot AI-first developmentu**, je důkaz pro vedení. Bez čísel není důkaz.

I pro non-pilot projekty má smysl měřit minimum (cycle time, cost), aby šlo postupně optimalizovat.

## Hlavní otázka

> Funguje AI-first development? Konkrétně: dokáže agent pipeline spolehlivě převést user story na merge-ready kód s minimální lidskou intervencí?

## Klíčové metriky

### 1. Cycle time per story

**Definice:** doba od `status=draft` po `status=done`.

**Proč:** ukazuje, jak rychle pipeline funguje od byznys záměru po hotový kód.

**Jak měřit:** timestamps ve `story_register.md` (created_at, updated_at při každé změně statusu).

**Cíl (orientační):**
- medián < 2 dny
- P95 < 5 dní

### 2. Human intervention rate

**Definice:** % stories, které projdou bez zásahu člověka mimo finální merge a manuální QA.

**Proč:** klíčová metrika pro AI-first. Pokud člověk musí opravovat každou story, není to AI-first, je to "AI assist".

**Jak měřit:**
- count `Conflict Detector → Product Owner` smyček > 0 = intervence
- count `Code Reviewer CHANGES NEEDED` > 0 = intervence Developera (= další iterace)
- count `Manuální QA FAIL` > 0 = intervence Developera po QA
- count manuálních edits ze strany Human Reviewera před mergem
- count eskalací na Business Ownera

**Cíl:** ≥ 70 % stories projde bez human intervence (kromě finálního merge schválení a manuálního QA).

### 3. Token cost per story

**Definice:** suma tokenů × ceny modelů za všechny agent runy v rámci jedné story.

**Proč:** ekonomika AI-first. Pokud cost > hodina vývojáře, není to obhajitelné.

**Jak měřit:** logy v `metrics/agent_runs.jsonl`:
```json
{"ts":"...","story_id":"US-007","agent":"architekt","model":"sonnet-4-6","input_tokens":15234,"output_tokens":3102,"cost_usd":0.092,"duration_ms":12300}
```

**Cíl:** medián < $0.50 per story v VÝVOJ režimu.

### 4. Iteration count (Conflict Detector loop)

**Definice:** kolikrát se story vrátila z Conflict Detectora zpět na Product Ownera.

**Proč:** vysoká hodnota signalizuje špatně psané user stories nebo nevhodné V1 / V2.

**Jak měřit:** counter `conflict_check_iterations` ve frontmatteru story.

**Cíl:**
- medián 0 (story projde napoprvé)
- P95 ≤ 2

### 5. Code Review rejection rate

**Definice:** % PR, které Code Reviewer odmítne (CHANGES NEEDED).

**Proč:** vysoká hodnota = Architekt předává špatné plány nebo Developer ignoruje constraint.

**Jak měřit:** GitHub API + status story (kolikrát byl `ready_for_review` → `in_development` zpět).

**Cíl:** < 30 % rejection rate. Při > 50 % = problém v Architekt / Developer link.

### 6. Manuální QA fail rate

**Definice:** % stories, kde manuální QA (Human Reviewer) řekl FAIL po Code Review APPROVE.

**Proč:** Code Reviewer selhal, AI brána neodchytila problém. Důležitý ukazatel kvality reviewe.

**Jak měřit:** count `ready_for_testing → in_development` přechodů.

**Cíl:** < 15 %. Vyšší = potřeba zlepšit Code Reviewera nebo přidat QA agenta.

### 7. Bug rate per merged story

**Definice:** počet nahlášených bugů během 7 dní po mergi, attributable to story.

**Proč:** kvalita merge-ready kódu. Pokud AI-first generuje buggy kód, není to úspora.

**Jak měřit:** GitHub issues s labelem `bug` vytvořené po `done` stories. Manuální attribuce na story.

**Cíl:** < 0.3 bugů per story.

### 8. AC coverage rate

**Definice:** % acceptance criteria, která byla v PR pokryta testem.

**Proč:** garance, že implementace skutečně dělá, co AC říká.

**Jak měřit:** Code Reviewer reportuje v review komentáři (povinná sekce). Pre-commit hook pro story validuje.

**Cíl:** ≥ 90 % AC mají odpovídající test.

### 9. ADR creation rate

**Definice:** počet nových ADR per story.

**Proč:** Architekt by měl psát ADR pro netriviální rozhodnutí. Pokud nikdy nepíše, něco mu uniká. Pokud píše vždy, je to overkill.

**Jak měřit:** diff `V1/decisions.md` per story.

**Cíl:** 10-30 % stories generuje ADR.

---

## Dashboard

Týdenní dashboard pro vedení (jeden screen):

```
[Project Name] AI-first Pilot — Week N
─────────────────────────────────────────

Throughput:
  Stories done this week:     12
  Stories in pipeline:        8
  Stories blocked:            1

Quality:
  Human intervention rate:    78 % ✅ (cíl ≥ 70%)
  Code Review rejection:      22 % ✅ (cíl < 30%)
  Manuální QA fail rate:      8 %  ✅ (cíl < 15%)
  Bug rate:                   0.2 ✅ (cíl < 0.3)
  AC coverage:                94 % ✅ (cíl ≥ 90%)

Speed:
  Cycle time median:          1.4 days ✅ (cíl < 2)
  Cycle time P95:             3.8 days ✅ (cíl < 5)

Economy:
  Cost per story median:      $0.18 ✅ (cíl < $0.50)
  Total cost this week:       $2.16
  Total cost cumulative:      $14.32

Health indicators:
  Conflict Detector loops:    median 0 ✅
  ADR creation rate:          18 % ✅ (10-30%)
  Token budget overflows:     0 ✅
```

---

## Postmortem každé story

Krátký postmortem (5 řádků) po `status=done`:

```markdown
## Postmortem
- Co šlo dobře: [...]
- Co špatně: [...]
- Surprise: [neočekávaná věc]
- Změna v promptu / contractu: [pokud nějaká]
```

Postmortem v `wiki/stories/us-NNN.md` jako poslední sekce. Po 20 stories agregovat do `docs/learnings.md`.

---

## Anti-metriky (nesledujeme)

- **Lines of code generated** — nesouvisí s hodnotou
- **Number of agent runs** — vyšší ≠ horší (dělíme práci)
- **Time spent by Architect** — Architekt má kvalitnější výstup, ne rychlejší

---

## Reportování vedení (pokud je projekt pilot)

**Týdenní 15min sync:**
- jedna konkrétní story end-to-end (od byznys záměru po merge)
- aktuální dashboard
- co se naučilo, co se mění

**Měsíční milestone review:**
- agregované metriky
- ROI vs odhad
- doporučení další fáze (pokračovat / upravit / zastavit)

**Riziko:** pokud po 2 týdnech metriky ukazují, že to bude déle, **komunikuj to ihned**, ne na konci. Včasná špatná zpráva > pozdní špatná zpráva.
