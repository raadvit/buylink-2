# BuyLink — Technical Reference

Tento dokument popisuje architekturu, konvence a tech stack pro vývoj buy-link platformy. Je primárním vstupem pro Architekta a Developery při analýze a implementaci stories.

---

## Architektura overview

```
buylinkFe (Next.js 16, App Router)
    │ HTTP /api/*
    ▼
buylinkApi (ASP.NET Core, Clean Architecture)
    │ EF Core (read/write)
    ▼
PostgreSQL
    ▲ schema migrations
dbBuylink (Flyway, samostatný repo)
```

**Repozitáře:**
- `buylinkApi` — C#/.NET backend
- `buylinkFe` — Next.js frontend
- `dbBuylink` — Flyway migrace (schéma DB)
- `buylink-2` — tento repozitář (task-forge orchestrátor)

Všechny tři projekty jsou přístupné jako symlinky v `buy-link/`.

---

## Backend (buylinkApi)

### Vrstvová struktura (Clean Architecture)

```
BuyLink.Domain/          ← entity, interfaces, Result pattern, ErrorCode
BuyLink.Application/     ← CQRS handlers, DTOs, FluentValidation validators
BuyLink.Infrastructure/  ← EF Core DbContext, Repository implementace, seeding
BuyLink.Api/             ← Controllers, DI composers, konfigurace
```

### Přidání nové funkce — standardní postup

1. **Domain:** Přidej/uprav entitu (dědí `BaseEntity`), přidej operaci do `I{Entity}Repository`
2. **Application:** Vytvoř `{ActionName}Query.cs` / `{ActionName}Command.cs`, `{ActionName}Dto.cs`, `{ActionName}QueryHandler.cs`, volitelně `{ActionName}QueryValidator.cs`
3. **Infrastructure:** Implementuj novou metodu v `{Entity}Repository.cs`; přidej DB tabulku přes Flyway skript (ne EF)
4. **Api:** Přidej endpoint do `{Domain}Controller.cs`

### Feature folder struktura (Application vrstva)

```
Features/
└── Listings/
    ├── Commands/
    │   └── CreateListing/
    │       ├── CreateListingCommand.cs
    │       ├── CreateListingCommandHandler.cs
    │       └── CreateListingCommandValidator.cs
    └── Queries/
        ├── GetAllListings/
        │   ├── GetAllListingsDto.cs
        │   ├── GetAllListingsQuery.cs
        │   └── GetAllListingsQueryHandler.cs
        └── GetListingById/
            ├── GetListingByIdDto.cs
            ├── GetListingByIdQuery.cs
            ├── GetListingByIdQueryHandler.cs
            └── GetListingByIdQueryValidator.cs
```

### BaseEntity

Každá entita **dědí** `BaseEntity`:

```csharp
public abstract class BaseEntity
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
    public DateTime UpdatedAt { get; set; } = DateTime.UtcNow;
}
```

### Result / OneOf pattern

Handlery vrací `OneOf<TSuccess, TError>`:

```csharp
// Handler
public async Task<OneOf<GetListingByIdDto, NotFoundError>> Handle(...)
{
    var listing = await repo.GetByIdAsync(request.Id, ct);
    if (listing is null) return new NotFoundError("Listing not found");
    return new GetListingByIdDto(listing.Id, listing.CreatedAt, listing.UpdatedAt);
}

// Controller
return result.Match<IActionResult>(
    dto   => Ok(dto),
    error => NotFound(error.Message)
);
```

`ErrorCode` enum: `None, NotFound, Validation, Conflict, Forbidden, Unexpected`

**Error records:**
```csharp
// NotFoundError — statická factory pro specifické entity
NotFoundError.ForEntity("Listing", id)
// → "Entity 'Listing' with identifier (guid) was not found."
new NotFoundError("The requested record was not found.")  // vlastní zpráva

// ValidationError(IDictionary<string, string[]>) — field-level chyby
// ForbiddenError() — generické odepření přístupu
```

**Error response format:** Controllers vrací `NotFound(error.Message)` — plain string, ne ProblemDetails.

### Testování discriminated union (OneOf)

```csharp
// V unit testech:
var result = await handler.Handle(query, ct);
Assert.True(result.IsT0);              // úspěch
var dto = result.AsT0;                 // rozbal hodnotu
Assert.True(result.IsT1);              // chyba
var error = result.AsT1;              // rozbal error
```

**Test fixture:**
```csharp
// WebServiceFixture : WebApplicationFactory<Program> ("Test" environment → InMemory DB + seeding)
// Tests/Controllers/*.cs — integrace přes HttpClient
// Tests/Handlers/*.cs — unit testy s NSubstitute mock repository
```

### FluentValidation

```csharp
public class GetListingByIdQueryValidator : AbstractValidator<GetListingByIdQuery>
{
    public GetListingByIdQueryValidator()
    {
        RuleFor(x => x.Id).NotEmpty();
    }
}
```

Registrace: `services.AddValidatorsFromAssembly(assembly)` — automaticky.

### EF Core & Database

- **DbContext:** `BuyLinkDbContext` v `BuyLink.Infrastructure/Data/`
- **Mapping:** `IEntityTypeConfiguration<T>` v `Data/Configurations/`
- **NIKDY** `dotnet ef migrations add` — migrace jsou v `dbBuylink` přes Flyway
- **Seeding:** `DbSeeder` s Bogus (jen pro InMemory dev/test)
- **Repository:** vždy `AsNoTracking()` pro read operace

```csharp
// Repository pattern
public async Task<IReadOnlyList<Listing>> GetAllAsync(CancellationToken ct = default)
    => await db.Listings.AsNoTracking().ToListAsync(ct);
```

### DI registrace

Každá vrstva má extension metodu:
```csharp
services.AddApplication();         // MediatR + FluentValidation
services.AddInfrastructure(config, env);  // DbContext + Repositories
```

Nové repository: registruj v `InfrastructureRegistrations.cs`.

### Controller vzor

```csharp
[ApiController]
[Route("api/listings")]
public class ListingsController(IMediator mediator) : ControllerBase
{
    [HttpGet("{id:guid}")]
    public async Task<IActionResult> GetById(Guid id, CancellationToken ct)
    {
        var result = await mediator.Send(new GetListingByIdQuery(id), ct);
        return result.Match<IActionResult>(
            dto   => Ok(dto),
            error => NotFound(error.Message)
        );
    }
}
```

### Health checks

- `GET /api/healthz` — liveness (bez auth), tag "live"
- `GET /api/readiness` — readiness (bez auth), tag "ready"
- `GET /api/metrics` — Prometheus scraping (OpenTelemetry)
- Defaultní port: **8980** (`urls: http://*:8980` v appsettings.json)
- APP_NAME: `"buylinkapi"` (pro OpenTelemetry service name)

### Composer pattern

`IListingComposer` / `ListingComposer` v `BuyLink.Api/Composers/` — konverze DTO → Response model.
Aktuálně zaregistrovaný ale v controllerech nepoužívaný (vrací se DTO přímo). Při přidání nového endpointu s response modelem použij composer.

### Testování (Backend)

- **Framework:** xUnit + NSubstitute + `Microsoft.AspNetCore.Mvc.Testing`
- **Fixture:** `WebServiceFixture : WebApplicationFactory<Program>` s "Test" environment → InMemory DB + seeding
- **Povinné pro každý endpoint:** happy path + validační chyba + NotFound case
- **InMemory DB** pro integrační testy, seedovaná přes `DbSeeder` (Bogus, 20 záznamů)
- Testovací projekt: `tests/BuyLink.Api.Tests/`

### Observability

- Serilog (logging)
- OpenTelemetry: metriky + tracing + Prometheus scraping na `/api/metrics`
- Spravováno Alza Platform packages — nepřidávej vlastní implementaci

---

## Frontend (buylinkFe)

### Struktura

```
buylinkFe/
├── app/                   # Next.js App Router
│   ├── layout.tsx         # Root layout
│   ├── page.tsx           # Homepage
│   ├── globals.css        # Global styles (Tailwind directives)
│   └── api/
│       ├── healthz/       # Health check
│       └── readiness/     # Readiness
├── public/                # Statické assety
└── container/             # Platform build output (generovaný)
```

### Konvence

- **App Router** — vše v `app/` directory
- **TypeScript strict** — bez `any`, bez `@ts-ignore`
- **Tailwind 4** — utility classes, žádné inline styly
- **Path alias:** `@/` = root projektu
- **API volání:** vždy relativní `/api/*`, nikdy absolutní URL

### Přidání nové stránky

```tsx
// app/listings/page.tsx
export default async function ListingsPage() {
  const listings = await fetch('/api/listings').then(r => r.json());
  return <div>...</div>;
}
```

### Linting & code style

```bash
yarn lint        # ESLint check
yarn lint:fix    # ESLint autofix
```

Pre-commit hook (Husky + lint-staged) spouští lint automaticky.

**Prettier** (`.prettierrc`): `trailingComma: es5`, `singleQuote: true`, `tabWidth: 2`, `arrowParens: avoid`, `endOfLine: lf`

**ESLint plugins:** `perfectionist` (import pořadí — `sort-imports: error`), `better-tailwindcss` (validace Tailwind tříd)

### Health check route vzor (Next.js)

```typescript
// app/api/healthz/route.ts
import { NextResponse } from 'next/server';
export async function GET() {
  return NextResponse.json({ status: 'ok', time: new Date().toISOString() });
}
export const dynamic = 'force-dynamic'; // vždy fresh, ne staticky generovaný
```

### Private registry (@alza)

Yarn je nakonfigurovaný pro privátní Alza.FE package registry (Azure Artifacts). Pokud story vyžaduje `@alza/*` package, je třeba token — viz `.yarnrc.yml`. Aktuálně žádné `@alza` packages nejsou použity.

### Build & deploy

```bash
yarn build                 # Next.js build
yarn platform-postbuild    # Kopíruje output do container/
```

---

## Database — Flyway migrace

> **KRITICKÉ:** Schéma DB spravuje výhradně Flyway v repozitáři `dbBuylink`.

- Nová tabulka nebo sloupec = nový Flyway SQL skript v `dbBuylink`
- Naming: `V{version}__{description}.sql` (Flyway konvence)
- EF Core pouze mapuje existující tabulky — nesmí migrovat schéma

---

## CI/CD

Azure DevOps pipelines v `.azuredevops/pipelines/`:

| Pipeline | Trigger | Akce |
|---|---|---|
| `pr.yaml` | Pull request | Build + testy |
| `ci.yaml` | Push do feature větve | Build |
| `cd.yaml` | Merge do develop/main | Deploy |
| `release.yaml` | Release tag | Release deploy |

---

## Lokální vývoj

### Backend

```bash
# Přidej do appsettings.Development.json nebo env:
# UseInMemoryDatabase=true (bez PostgreSQL)
# nebo nastav ConnectionStrings__Buylink

cd buy-link/buylinkApi
dotnet run --project src/BuyLink.Api
# API běží na https://localhost:{port}
```

### Frontend

```bash
cd buy-link/buylinkFe
yarn install
yarn dev
# FE běží na http://localhost:3000
```

---

## Klíčové NE

- ❌ `dotnet ef migrations add` — migrace jsou v Flyway
- ❌ Absolutní URL v FE (`http://localhost:8000/api/...`)
- ❌ Hard-coded credentials nebo API klíče v kódu
- ❌ Přímý přístup k DbContext mimo Infrastructure vrstvu
- ❌ Business logika v Controlleru (patří do Application handleru)
- ❌ Čtení V2 memory souborů přímo Developerem (vše je inline ve story)
