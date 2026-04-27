# Token Budget

Tvrdé limity input tokenů per agent run. Pokud agent přesáhne, eskalace na Human review.

## Limity

| Agent | Input limit | Typický skutečný | Co když přesáhne |
|---|---|---|---|
| Product Owner | 5 000 | ~3 000 | Příliš velký kontext z V1 → zkrátit `project.md` |
| Conflict Detector | 8 000 | ~5 000 | Sekce V2 přerostly → rozdělit |
| Architekt | 25 000 | ~15 000 | Story je moc velká → rozdělit na víc stories |
| Backend Developer | 15 000 | ~10 000 | Impl. plán moc velký → Architekt zúžil scope |
| Frontend Developer | 15 000 | ~10 000 | Impl. plán moc velký → Architekt zúžil scope |
| Code Reviewer | 10 000 | ~6 000 | PR je moc velký → developer rozdělit |

## Pravidla

1. **Limit je input only.** Output limit je dán modelem.
2. **Měření před runem.** Pre-flight check spočítá tokeny inputu (story + read kontrakt) a porovná s limitem. Pokud over, agent neběží.
3. **Velikost sekce V2:** max 1500 input tokenů na sekci. Pokud naroste, povinné rozdělení.
4. **Story self-contained:** po Architektově fázi musí story obsahovat vše potřebné. Developer čte pouze story, ne V2.

## Měření

- Každý agent run loguje `input_tokens`, `output_tokens`, `cost_usd`, `model`, `duration_ms`.
- Logy se ukládají do `metrics/agent_runs.jsonl`.
- Týdně agregace: medián, P95, total cost per story.

## Bottlenecks (typické)

| Symptom | Pravděpodobná příčina | Akce |
|---|---|---|
| Architekt opakovaně přesahuje | V2 sekce přerostly | Rozdělit sekce, zúžit `reads` |
| Developer dostává >15k | Architekt nezúžil impl. plán | Architekt extrahuje jen relevantní část V2 |
| Conflict Detector >8k | Story se týká příliš sekcí | Rozdělit story |
| PO opakovaně >5k | Story je nekonzistentní s V1 | Vyčistit V1, přidat ADR |

## Růst projektu

Tyto limity jsou orientační pro **menší až střední projekty** (~50-200 stories). Při růstu rekalibrovat:
- pokud V2 přeroste, zvýšit limity Architekta
- pokud Conflict Detector začne dělat false positives, zúžit jeho čtení přes V4 cache
- pokud Developer dostává moc, zvážit rozdělení velkých stories na menší
