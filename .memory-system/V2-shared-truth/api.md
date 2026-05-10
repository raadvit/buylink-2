# API Contract

REST API kontrakt projektového backendu. Konkrétní stack viz `V1-static-context/project.md`.

## Pravidla pro tento soubor

- **Sekční tagging:** povinné. `<!-- SECTION: name -->` ... `<!-- /SECTION: name -->`.
- **Kdo zapisuje:** pouze Architekt, pouze sekce dle `writes`.

## Globální konvence

| Konvence | Hodnota |
|---|---|
| API styl | REST |
| Base URL | `/api` |
| Auth | JWT Bearer (Alza Platform / Azure AD) |
| Content-Type | `application/json` |
| Field naming | camelCase v JSON (ASP.NET Core default) |
| ID formát | UUID (Guid), v URL jako `{id:guid}` |
| Health check | `GET /api/healthz` (liveness), `GET /api/readiness` (readiness) |
| Error format | string message (TBD — Architekt upřesní při první error-handling story) |

---

<!-- SECTION: listings -->
## Listings

Endpointy pro správu inzerátů.

### GET /api/listings

Vrátí seznam všech inzerátů.

**Auth:** TBD (aktuálně bez auth)

**Response 200:**
```json
[
  {
    "id": "uuid",
    "createdAt": "2024-01-01T00:00:00Z",
    "updatedAt": "2024-01-01T00:00:00Z"
  }
]
```

> Poznámka: aktuální DTO (`GetAllListingsDto`) vrací pouze `id`, `createdAt`, `updatedAt`. Rozšíření při první listing-detail story.

**Response 404:** `"Not found"` (string)

**Handler:** `GetAllListingsQueryHandler` → `OneOf<List<GetAllListingsDto>, NotFoundError>`

---

### GET /api/listings/{id:guid}

Vrátí inzerát dle ID.

**Auth:** TBD

**Path params:**
- `id` — Guid

**Response 200:**
```json
{
  "id": "uuid",
  "createdAt": "2024-01-01T00:00:00Z",
  "updatedAt": "2024-01-01T00:00:00Z"
}
```

> Poznámka: aktuální DTO (`GetListingByIdDto`) vrací pouze `id`, `createdAt`, `updatedAt`.

**Response 404:** `"Not found"` (string)

**Validation:** `GetListingByIdQueryValidator` (FluentValidation)

**Handler:** `GetListingByIdQueryHandler` → `OneOf<GetListingByIdDto, NotFoundError>`

<!-- /SECTION: listings -->
