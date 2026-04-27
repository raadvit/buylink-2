# Integration Template

Šablona pro každou integraci v `V2/integrations.md`. Strict format.

---

## Šablona

```markdown
<!-- SECTION: section_name_kebab -->
## Section Name (např. Payment Providers)

### ProviderName
- **Účel:** [k čemu se používá v projektu]
- **Endpoint:** [base URL nebo klíčové endpointy]
- **Webhook URL:** [naše endpoint pro příjem webhooku, pokud relevantní]
- **Auth:** [API key / OAuth2 / HMAC, env proměnné]
- **Sledované eventy:** [pokud má webhooky]
  - `event_a` → [doménový důsledek]
  - `event_b` → [důsledek]
- **Sledované endpointy:** [pokud aktivně voláme provider API]
  - `POST /provider-endpoint` — [účel volání]
- **Signature ověření:** [jak se ověřuje webhook signature]
- **Limity:** [rate limits, payload velikosti, jiné]
- **Error handling:** [jak se zachází s failed callem — retry, fallback, alert]
- **Idempotence:** yes | no [pro POST do providera]
- **Status:** MVP | planned | deprecated
- **Owner:** [kdo má integraci na starosti, pokud je to relevantní]
<!-- /SECTION: section_name_kebab -->
```

---

## Pravidla

### Sekční organizace

- Sekce sdružuje providery stejné kategorie (`payment-providers`, `shipping-providers`, `email`, `storage`, `analytics`).
- Více providerů ve stejné kategorii v jedné sekci, oddělené `### ProviderName`.
- Mezi sekce nepatří interní integrace mezi moduly stejného projektu — ty patří do `domain.md` jako vztahy nebo do `api.md` jako interní endpointy.

### Povinné položky

Každá integrace musí mít:
- **Účel** (proč ji projekt potřebuje)
- **Auth** (jak se autentizujeme, env proměnné)
- **Status** (MVP / planned / deprecated)
- **Error handling** (jak reagujeme na selhání)

### Volitelné položky (vyplnit pokud relevantní)

- **Webhook URL** + **Sledované eventy** — pokud provider posílá events
- **Sledované endpointy** — pokud aktivně voláme provider
- **Signature ověření** — pokud webhooky
- **Limity** — pokud má provider limity, na které bychom mohli narazit
- **Idempotence** — pokud děláme POST/PATCH do providera

### Kdy přidat ADR

- Volba mezi více providery stejné kategorie (např. Stripe vs PayPal) → ADR
- Změna provider z jednoho na druhý (migration) → nový ADR s `Supersedes`
- Bezpečnostně sensitivní integrace (auth, payments) → ADR

### Globální principy (z `constraints.md`, opakuji pro důraz)

- **Timeout:** každé externí volání má timeout (default 10s).
- **Retry:** exponential backoff, 3 pokusy, jen idempotentní operace.
- **Credentials:** nikdy v kódu, jen env. Reference v sekci přes název env (`STRIPE_API_KEY`).
- **Webhooks:** povinné ověření signature. Idempotence přes deduplikaci podle external ID.
