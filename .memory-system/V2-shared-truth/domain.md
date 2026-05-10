# Domain Model

Entity, jejich atributy, stavy a operace projektu. Identitu projektu drží `V1-static-context/project.md`.

## Pravidla pro tento soubor

- **Format:** každá entita uzavřená do `<!-- SECTION: name -->` ... `<!-- /SECTION: name -->`.
- **Sekční tagging:** povinné. Section name v kebab-case, identický s referencí ve story (`reads: domain:section`).
- **Velikost sekce:** max 1500 tokenů.
- **Kdo zapisuje:** pouze Architekt, pouze sekce dle `writes` aktuální story.

## Globální konvence

| Konvence | Hodnota |
|---|---|
| ID typ | `Guid` (UUID v4, generovaný na BE) |
| Timestamp | `DateTime` UTC, ISO 8601 v API odpovědích |
| Soft delete | Není (hard delete nebo `IsActive` flag dle entity) |
| Enum case | PascalCase v C#, snake_case v API JSON |
| BaseEntity | `Guid Id`, `DateTime CreatedAt`, `DateTime UpdatedAt` — dědí všechny entity |
| DB migrations | Flyway (repo `dbBuylink`) — EF nespravuje schéma |
| Wiki path | `wiki/stories/US-{id:03d}.md` |

---

<!-- SECTION: listing -->
## Listing

Základní entita platformy. Reprezentuje inzerát vytvořený prodejcem.

### Atributy

| Atribut | Typ | Nullable | Popis |
|---|---|---|---|
| Id | Guid | ne | PK, generovaný na BE |
| Title | string | ne | Název inzerátu |
| Description | string | ne | Popis inzerátu |
| Price | decimal | ne | Cena (měna TBD) |
| IsActive | bool | ne | Viditelnost inzerátu; default `true` |
| CreatedAt | DateTime UTC | ne | Čas vytvoření (z BaseEntity) |
| UpdatedAt | DateTime UTC | ne | Čas poslední změny (z BaseEntity) |

### DB tabulka

`Listings` — konfigurováno přes `ListingConfiguration : IEntityTypeConfiguration<Listing>`

### Operace

| Operace | Popis |
|---|---|
| GetAll | Vrátí seznam všech inzerátů |
| GetById | Vrátí inzerát dle Guid ID |
| Create | Vytvoří nový inzerát (TBD) |
| Update | Aktualizuje existující inzerát (TBD) |
| Deactivate | Nastaví `IsActive = false` (TBD) |

### Invarianty

- `Title` a `Description` nesmějí být prázdné
- `Price` musí být > 0
- `IsActive` default `true` při vytvoření

### Repository interface

```csharp
// BuyLink.Domain/Listings/IListingRepository.cs
Task<IReadOnlyList<Listing>> GetAllAsync(CancellationToken ct = default);
Task<Listing?> GetByIdAsync(Guid id, CancellationToken ct = default);
Task AddAsync(Listing entity, CancellationToken ct = default);
Task AddAndSaveChangesAsync(Listing entity, CancellationToken ct = default);
```

Existuje generický `IRepository<T> where T : BaseEntity` — `GetAllAsync` a `GetByIdAsync` jsou generické, `AddAsync`/`AddAndSaveChangesAsync` jsou hardcoded na `Listing` (technický dluh, ADR při první command story).

### Status

Stávající implementace: GetAll + GetById (read-only). Create/Update/Deactivate TBD.
<!-- /SECTION: listing -->
