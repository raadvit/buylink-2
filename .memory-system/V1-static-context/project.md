# Project

> **JEDINÝ projekt-specific soubor v memory systému.**
> Po vyplnění je tento soubor read-only pro agenty (mění jen Business Owner).
> Agent se na tento soubor odkazuje při generování stories.

---

## Project Identity

**Name:** BuyLink

**Repositories:**
- API: `buylinkApi` (buy-link/buylinkApi) — C#/.NET backend
- FE: `buylinkFe` (buy-link/buylinkFe) — Next.js frontend
- DB migrations: `dbBuylink` — Flyway, samostatný repozitář
- Orchestrátor (task-forge): `buylink-2` (tento repozitář)

**Project goal:** Tržiště pro nákup a prodej inzertních pozic (Listings). Propojuje prodejce a kupující.

**Project type:** Full-stack webová aplikace (C#/.NET API + Next.js FE)

**Status:** MVP ve vývoji

---

## Business Model

Platforma umožňující uživatelům vytvářet a spravovat inzeráty (Listings) a propojovat kupující s prodejci.

---

## Role

| Role | Popis |
|---|---|
| Seller | Vytváří a spravuje vlastní inzeráty |
| Buyer | Prohlíží a reaguje na aktivní inzeráty |
| Admin | Správa platformy (TBD) |

---

## Ubiquitous Language

| Pojem | Význam |
|---|---|
| Listing | Inzerát — základní entita platformy. Má cenu, popis a stav aktivity. |
| IsActive | Příznak, zda je inzerát veřejně viditelný kupujícím |
| Seller | Vlastník inzerátu |

---

## Epicy (MVP)

| ID | Epic | Popis |
|---|---|---|
| EP-01 | Listings | Správa inzerátů — CRUD, vyhledávání, filtrování |

---

## Tech Stack

### Backend (buylinkApi)

- **Language:** C# (.NET 8+)
- **Framework:** ASP.NET Core — Clean Architecture (4 vrstvy: Domain / Application / Infrastructure / Api)
- **Pattern:** CQRS + MediatR; OneOf pro discriminated union výsledky z handlerů
- **Validation:** FluentValidation (registrace přes `AddValidatorsFromAssembly`)
- **ORM:** Entity Framework Core + Npgsql (PostgreSQL provider)
- **DB:** PostgreSQL — **migrace výhradně přes Flyway** (repo `dbBuylink`, EF migrace NIKDY)
- **Dev/test DB:** InMemory EF + seeding přes Bogus (config `UseInMemoryDatabase=true`)
- **Auth:** JWT Bearer; identita uživatele přes Alza Platform / Azure AD
- **Observability:** OpenTelemetry (metrics, tracing, OTLP export, Prometheus scraping), Serilog
- **Platform packages:** `Alza.Platform.Applications.WebService`, `Alza.Platform.Applications.Common`, `Alza.Platform.Hosting.Extensions`
- **Result pattern:** `Result` / `Result<T>` s `ErrorCode` enum (None, NotFound, Validation, Conflict, Forbidden, Unexpected)
- **Health:** `GET /api/healthz` (liveness), `GET /api/readiness` (readiness)
- **Testing:** xUnit + NSubstitute + `Microsoft.AspNetCore.Mvc.Testing` (WebApplicationFactory)

### Frontend (buylinkFe)

- **Framework:** Next.js 16.2 (App Router, `output: 'standalone'`)
- **Language:** TypeScript 6.x (strict mode)
- **UI Library:** React 19
- **Styling:** Tailwind CSS 4.x
- **Package manager:** Yarn 4.13
- **Linting:** ESLint 9 + Prettier + `eslint-plugin-perfectionist` + `eslint-plugin-better-tailwindcss`
- **Pre-commit:** Husky + lint-staged
- **Path alias:** `@/*` → root projektu

### Database

- **Engine:** PostgreSQL
- **Migrations:** Flyway (repo `dbBuylink`) — **NIKDY EF Core migrations**
- EF pouze mapuje existující tabulky přes `IEntityTypeConfiguration`

### CI/CD

- Azure DevOps pipelines (`.azuredevops/pipelines/`)
- Pipelines: `ci.yaml`, `cd.yaml`, `pr.yaml`, `release.yaml`

### AI infra

- Anthropic Claude — modely a režim viz `docs/token-strategy.md`
- Agenti definováni v `.memory-system/team/`
- Issue tracker: Jira (projekt `DSC`)

### Testování

**Backend:**
- xUnit, NSubstitute, `Microsoft.AspNetCore.Mvc.Testing`
- Povinné pro každý endpoint: happy path + error case + validační test

**Frontend:**
- TBD (framework nebyl ještě zvolen)

---

## Konvence

**BE naming:**
- Namespace: `BuyLink.{Layer}.{Feature}`
- Feature folder v Application: `Features/{Domain}/{Commands|Queries}/{ActionName}/`
- Query handler: `{ActionName}QueryHandler`, DTO: `{ActionName}Dto`
- Repository interface: `I{Entity}Repository`, implementace: `{Entity}Repository`
- Controller route: `[Route("api/{resource}")]`

**BaseEntity (povinné pro všechny entity):**
```csharp
Guid Id = Guid.NewGuid()
DateTime CreatedAt = DateTime.UtcNow
DateTime UpdatedAt = DateTime.UtcNow
```

**FE naming:**
- Komponenty: PascalCase soubory
- API volání: relativní cesty `/api/*`, nikdy absolutní URL

**Branches:** `story/us-NNN-{slug}`

**Commit zprávy:** `[US-NNN] BE: {popis}` nebo `[US-NNN] FE: {popis}`

**Stories:** `wiki/stories/US-{id:03d}.md`

**Jira projekt:** `DSC`

---

## Scope a hranice

**V scope (MVP):**
- CRUD pro Listings (BE + FE)
- Autentizace přes Alza Platform (JWT/Azure AD)
- Základní vyhledávání a filtrování inzerátů

**Out of scope (MVP):**
- Platební brána
- Real-time notifikace
- Messaging mezi uživateli
- Mobile aplikace

---

## Co agent musí vědět při generování stories

- **DB migrace = Flyway** v repozitáři `dbBuylink`. EF nikdy nespravuje schéma. Agent nesmí generovat `dotnet ef migrations add`.
- **EF mapuje** existující tabulky přes `IEntityTypeConfiguration<T>` v `BuyLink.Infrastructure`.
- **InMemory DB** pouze pro lokální vývoj a testy (`UseInMemoryDatabase=true` v config).
- **Alza Platform packages** řeší config loading, Serilog, hosting — nezdvojovat vlastní implementací.
- **OneOf pattern:** Application handlery vrací `OneOf<SuccessType, ErrorType>`, Controller volá `.Match()`.
- **Result<T>:** použij `Result<T>.Success(value)`, `Result<T>.NotFound()`, `Result<T>.Invalid()` atd.
- **FE je boilerplate** — žádné business pages/komponenty zatím neexistují. Každá story implementuje od základů.
- **Jira DSC:** všechny stories jsou issues v Jira projektu DSC.
- **Nejdřív BE, pak FE** — implementační pořadí v každé full-stack story.
