# Domain Model

Entity, jejich atributy, stavy a operace pro BuyLink.

## Pravidla pro tento soubor

- **Format:** každá entita uzavřená do `<!-- SECTION: name -->` ... `<!-- /SECTION: name -->`.
- **Sekční tagging:** povinné. Section name v kebab-case, identický s referencí ve story (`reads: domain:section`).
- **Velikost sekce:** max 1500 tokenů.
- **Kdo zapisuje:** pouze Architekt, pouze sekce dle `writes` aktuální story.

## Globální konvence

| Konvence | Hodnota |
|---|---|
| ID typ | UUID nebo int (dle entity) |
| Timestamp | ISO 8601, UTC |
| Soft delete | TBD (Architekt rozhodne při první relevantní story) |
| Enum case | kebab-case (status values) |
| Wiki path | `wiki/stories/US-{id:03d}.md` |

---

> Žádné entity zatím nejsou definovány. Architekt je přidá při průchodu prvními stories.
