# Project

> **JEDINÝ projekt-specific soubor v memory systému.**
> Po vyplnění je tento soubor read-only pro agenty (mění jen Business Owner).
> Vyplň všechny sekce před první story. Agent se na tento soubor odkazuje při generování stories.

---

## Project Identity

**Name:** TBD

**Repository:** TBD

**Project goal:** TBD

**Project type:** TBD

**Status:** TBD

---

## Business Model

TBD — popis hodnoty pro koncového uživatele a logiky transakce/služby.

---

## Role

| Role | Popis |
|---|---|
| TBD | TBD |

---

## Ubiquitous Language

| Pojem | Význam |
|---|---|
| TBD | TBD |

---

## Epicy (MVP)

| ID | Epic | Popis |
|---|---|---|
| EP-XX | TBD | TBD |

---

## Tech Stack

**Backend:**
- TBD

**Frontend:**
- TBD

**Integrace:**
- TBD

**AI infra:**
- Anthropic Claude — modely a režim viz `docs/token-strategy.md`
- Agenti definováni v `.memory-system/team/`

**Testování:**
- TBD

---

## Konvence

**Naming:** TBD

**Branches:** `story/us-NNN-{slug}` pro story větve

**Commit zprávy:** `[US-NNN] {popis}` pro story commity

**PR titulky:** squash merge přes PR, nikdy přímý push do main

**Stories:** `wiki/stories/US-{id:03d}.md`

---

## Scope a hranice

**V scope (MVP):**
- TBD

**Out of scope (MVP):**
- TBD

---

## Co agent musí vědět při generování stories

- TBD — projekt-specific pravidla, závislosti mezi epicy, povinné odkazy na integrace
