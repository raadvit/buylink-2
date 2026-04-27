# Decisions

**Append-only soubor.** Nikdy needituj existující ADR. Změna rozhodnutí = nový ADR s `Supersedes: ADR-XXX`.

ADR se přidávají postupně Architektem během průchodu storiemi, případně Business Ownerem při setup projektu.

## Formát ADR

```
## ADR-XXX — [Krátký název]
- **Datum:** YYYY-MM-DD
- **Status:** proposed | accepted | superseded
- **Autor:** [Architekt | Business Owner]
- **Kontext:** [Co řešíme, proč]
- **Rozhodnutí:** [Co jsme se rozhodli udělat]
- **Důsledky:** [Pozitivní i negativní]
- **Alternativy:** [Co jsme zvažovali a proč zamítli]
- **Supersedes:** [ADR-XXX | none]
```

## Konvence číslování

- ADR číslo je tříciferné s padding: `ADR-001`, `ADR-002`, ..., `ADR-099`, `ADR-100`.
- Číslo je inkrementální v pořadí přidání. Nikdy se nepřeskakuje, nikdy se nemaže.
- Pokud je ADR `superseded`, status se změní (jediná povolená editace), ale tělo zůstává nedotčené. Nový ADR pak referuje přes `Supersedes`.

## Pravidla pro Architekta

- ADR se přidává v okamžiku **netriviálního rozhodnutí**, ne při každé změně.
- Triviální = přidání pole do existující entity, nový endpoint dle existujícího vzoru.
- Netriviální = volba technologie, změna architektury, breaking change, security trade-off, nová externí integrace.
- Pokud si Architekt není jistý, ADR vytvoří. Lepší ADR navíc než scházející kontext.

---

## ADR Register

> Žádné ADR zatím nejsou. Architekt je přidá při průchodu prvními stories.
> První ADR (ADR-001) typicky volí tech stack, pokud není v `project.md` rozhodnutý.
