# Constraints

Globální pravidla, která dodržuje **každý agent** bez ohledu na roli a projekt.

**Status:** re-usable napříč všemi projekty firmy. Editace pouze pokud existuje firmemní rozhodnutí (ne projektové).

## Memory pravidla

1. **V2 je jediná pravda.** Pokud V2 a V3 odporují, vyhrává V2.
2. **Agent píše pouze do vrstev definovaných v `agent-memory-contract.md`.** Zápis do nepovolené vrstvy je kritická chyba — agent zastaví práci.
3. **V1 je read-only.** Mění pouze Business Owner manuálně mimo workflow. Výjimka: `decisions.md` má append-only přístup pro Architekta.
4. **`decisions.md` je append-only.** Nikdy needituj existující ADR. Změna rozhodnutí = nový ADR s `Supersedes: ADR-XXX`.
5. **Selektivní čtení V2.** Agent čte pouze sekce / soubory podle `reads` ve story, ne celý V2.

## Konflikty a eskalace

6. **Při detekci rozporu s V1 agent zastaví práci.** Nepokračuje. Eskaluje na Human review s popisem rozporu.
7. **Při nejednoznačnosti V2 agent eskaluje na Architekta.** Nedohaduje. Pokud je sekce V2 prázdná tam, kde to potřebuje, ohlásí to.
8. **Conflict Detector → Product Owner smyčka má max 3 iterace.** Po třetí neúspěšné iteraci povinná eskalace na Business Ownera (status `blocked`).

## Format pravidla

9. **Strict format > volná próza.** Entity v `domain.md`, endpointy v `api.md`, integrace v `integrations.md` a stories vždy podle šablony v `templates/`.
10. **Strojově validovatelné.** Po každém zápisu agenta běží validační skript. Pokud selže, agent dostane chybu a musí opravit formát.
11. **Žádné UML diagramy jako autoritativní zdroj.** Vztahy entit v textu (`Order *-- LineItem`). Mermaid je doplněk pro lidi, ne pravda.
12. **Strukturovaná pole, ne věty.** `status: OPEN | PAID | CANCELLED` místo "může být v OPEN, PAID nebo CANCELLED stavu".

## Token pravidla

13. **Token budget per agent run je tvrdý limit.** Definováno v `token_budget.md`. Pokud agent přesáhne, eskalace.
14. **Maximální velikost sekce v V2 souboru: 1500 tokenů.** Pokud naroste, povinné rozdělení (např. `orders` → `orders-core`, `orders-payments`).
15. **Story je self-contained po fázi 1.** Architekt zkopíruje výtahy z V2 do story. Developer čte pouze story, ne V2 přímo.

## Workflow pravidla

16. **Status story je jediný indikátor fáze.** Žádné implicitní stavy. Změna statusu = explicitní zápis do `story_register.md` + do hlavičky story souboru.
17. **Branch per story.** `story/us-NNN-{slug}`. Žádné komitování více stories do jedné větve.
18. **Code Reviewer je poslední AI brána.** Bez explicitního `APPROVE` nemůže story přejít na `ready_for_testing`.
19. **`ready_for_testing` vyžaduje manuální QA.** Před mergem člověk projde smoke test / klikací cestu podle `Manuální QA scénář` ze story.
20. **Merge dělá Human Reviewer.** Žádný agent nemerguje do mainu.
21. **Worktree při paralelní implementaci.** Každá story `in_development` má vlastní worktree. Detail v `docs/worktrees.md`.

## Bezpečnostní pravidla

22. **Žádné secrets v kódu, V2, ani ve story.** Pouze env proměnné a reference (např. `STRIPE_API_KEY`).
23. **Změna autentizace / autorizace = povinná eskalace na Human review** před implementací, i kdyby Conflict Detector nehlásil problém.
24. **Externí volání musí mít timeout a error handling.** Žádné nezachycené HTTP requesty. Default timeout 10s, retry s exponential backoff (3 pokusy).

## Wiki soubory

25. **Wiki soubory hotových stories neexistují lokálně — to je záměr.** Po dosažení statusu `done` nebo `ready_for_testing` se wiki soubor automaticky smaže z lokálního filesystému (zůstává v git historii). Pokud agent nenajde `wiki/stories/US-NNN.md` pro story v těchto stavech, **nesmí** ji obnovovat ani znovu vytvářet.
26. **Wiki soubor je working state, ne source of truth pro obsah.** Autoritativní obsah story je GitHub issue body. Wiki soubor slouží pouze pro agenty během aktivní práce.

## Co agent NIKDY nedělá

- Needituje `decisions.md` (jen append)
- Nemění `project.md`, `constraints.md`, `token_budget.md` (vlastník Business Owner)
- Nečte V2 soubory mimo svůj contract
- Negeneruje kód s hard-coded credentials
- Neignoruje validační chybu — vždy opravit, nikdy obejít
- Nevymýšlí si entity / fieldy, které nejsou ve V2 (eskalace na Architekta)
- Developer nečte V2 přímo
- Mergne PR sám (jen Human Reviewer)
