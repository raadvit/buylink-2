# API Endpoint Template

Šablona pro každý endpoint v `V2/api.md`. Strict format, validovatelný.

---

## Šablona

```markdown
### METHOD /api/path/{param}
- **Auth:** none | required | role:ROLE_NAME | signature:PROVIDER
- **Query:** `?param1=type&param2=type` [pokud relevantní]
- **Request:** `{ field1: type, field2: type }` [pokud METHOD má body]
- **Response 2XX:** `{ data: ResponseShape, meta?: {...} }`
- **Errors:** XXX (důvod), YYY (důvod), ...
- **Side effects:** [pokud nějaké — např. "vytvoří Payment v PENDING"]
- **Idempotence:** yes | no [pro POST/PATCH explicitně]
- **Rate limit:** [pokud specifický limit pro endpoint]
```

---

## Pravidla

### Auth hodnoty

| Hodnota | Význam |
|---|---|
| `none` | veřejný endpoint, bez autentizace |
| `required` | platný auth token (forma definovaná v ADR) |
| `role:ADMIN` | platný token + role=ADMIN |
| `role:OWNER` | platný token + uživatel je vlastníkem zdroje |
| `signature:XXX` | webhook s validní signaturou od providera XXX (např. `signature:STRIPE`) |

### Request / Response shapes

- Field names: dle konvence z `project.md` (typicky snake_case nebo camelCase).
- Pokud je shape sdílená mezi víc endpointy, definuj ji nahoře v sekci jako `### Common shapes` a referuj `{ data: EntityName }`.
- Pro pagination: dle konvence z V2 globálních konvencí.

### Errors

Format: `XXX (důvod)` — kód a krátký důvod.

Standardní (REST):
- `400 (validační chyba)` — payload nesplňuje schema
- `401 (chybí / neplatný token)`
- `403 (nedostatečná práva)`
- `404 (zdroj neexistuje)`
- `409 (konflikt — např. unique violation)`
- `422 (semanticky špatné)`

### Idempotence

- GET, PUT, DELETE: idempotentní z principu.
- POST: většinou ne. Pokud je idempotentní (např. webhook handler s deduplikací), explicitně uveď.
- PATCH: záleží — když replace polí, idempotentní; když increment counteru, není.

### Side effects

Cokoliv, co se děje navíc kromě uložení/přečtení dat:
- volání externích API
- odesílání emailů / notifikací
- atomické updaty napříč více entitami
- vznik nových zdrojů (např. Order → Payment)

Side effects musí být vyjmenovány explicitně, aby Conflict Detector a Architekt viděli plné dopady.

### Rate limit

Pokud má endpoint specifický rate limit (jiný než globální default projektu), uveď:
- limit (např. `10 req/min per user`)
- scope (per user, per IP, global)
