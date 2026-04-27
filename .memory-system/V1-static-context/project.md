# Project

> **JEDINÝ projekt-specific soubor v memory systému.**
> Po vyplnění je tento soubor read-only pro agenty (mění jen Business Owner).

---

## Project Identity

**Name:** BuyLink

**Repository:** raadvit/buylink-2

**Project goal:** Mini bazar / platební brána bez katalogu — umožňuje prodávat věci mezi uživateli přes AlzaBox s eskrow platbou (kupující platí předem, prodejce dostane peníze až po vložení zboží do boxu).

**Project type:** veřejná webová aplikace / platební platforma

**Status:** MVP

---

## Business Model

Prodejce vytvoří inzerát a obdrží unikátní BuyLink URL, který pošle kupujícímu. Kupující přes URL zaplatí, platforma drží platbu v escrow. Až prodejce fyzicky vloží zboží do AlzaBoxu a systém to potvrdí, platba se uvolní prodejci. Hodnota: důvěryhodnost transakce bez nutnosti osobního setkání — AlzaBox jako neutrální místo předání.

---

## Role

| Role | Popis |
|---|---|
| **Prodejce** | Vytváří inzerát, nastavuje cenu a počet kusů, odnáší zboží do AlzaBoxu |
| **Kupující** | Otevírá link inzerátu, volí množství, vybírá AlzaBox, platí |
| **Admin** | Interní administrace platformy |
| **Systém / API** | Automatizované kroky — notifikace, potvrzení platby, komunikace s AlzaBox API |

---

## Ubiquitous Language

| Pojem | Význam |
|---|---|
| **Inzerát** | Neveřejná nabídka prodejce — existuje jen přes přímý URL link |
| **BuyLink** | URL link inzerátu zaslaný kupujícímu |
| **AlzaBox** | Výdejní box jako doručovací místo zásilky |
| **Transakce** | Celý průběh od platby po doručení |
| **Escrow** | Platba je držena platformou, uvolní se až po vložení zboží do boxu |
| **Vložení zboží** | Potvrzená akce prodejce — trigger pro uvolnění platby a notifikaci kupujícímu |

---

## Epicy (MVP)

| ID    | Epic                  | Popis                                                     |
|-------|-----------------------|-----------------------------------------------------------|
| EP-01 | BuyLink               | Zobrazení URL stránky pro kupujícího                      |
| EP-02 | Administrace          | Generování inzerátu a administrace účtu                   |
| EP-03 | Platba                | Výběr množství, výpočet ceny, platební brána              |
| EP-04 | Košík                 | Nákupní proces                                            |
| EP-05 | Doručení              | Výběr AlzaBoxu, integrace AlzaBox API                     |
| EP-06 | Escrow výplata & účto | Držení platby, potvrzení vložení, uvolnění peněz prodejci |
| EP-07 | Notifikace            | Emaily / SMS prodejci i kupujícímu v klíčových krocích    |
| EP-08 | Customer service      | Interní správa platformy                                  |

---

## Tech Stack

**Backend:**
- Jazyk: Python 3.12
- Framework: Flask ≥ 3.0

**Frontend:**
- Vanilla JS (ES modules), HTML5, CSS
- Bez build toolu (žádný Vite/Webpack)

**Integrace:**
- **Adyen for Platforms** — platební brána, escrow logika
- **AlzaBox API** — rezervace boxu, vložení zásilky, potvrzení
- GitHub CLI (`gh`) — issues, PR
- Claude Code CLI (`claude`) — spouštění agentů přes subprocess

**AI infra:**
- Anthropic Claude (Sonnet 4.6 / Haiku 4.5) — volání přes `claude` CLI s `--output-format json`
- Agenti definováni v `.memory-system/team/`

**Testování:**
- Selenium — automatizované backend testy pro integrace

---

## Konvence

**Naming:**
- Backend: snake_case (Python)
- Frontend: camelCase (JS), kebab-case (CSS třídy, HTML atributy)

**Branches:** `story/us-NNN-{slug}` pro story větve

**Commit zprávy:** `[US-NNN] {popis}` pro story commity

**PR titulky:** squash merge přes PR, nikdy přímý push do main

**Stories:** `wiki/stories/US-{id:03d}.md`

---

## Scope a hranice

**V scope (MVP):**
- Vytvoření inzerátu a generování BuyLink URL
- Nákupní flow kupujícího (výběr množství, AlzaBox, platba)
- Escrow — držení platby, trigger při vložení zboží, výplata prodejci
- Notifikace prodejci i kupujícímu v klíčových krocích
- Integrace Adyen for Platforms + AlzaBox API
- Interní admin pro customer service

**Out of scope (MVP):**
- Veřejný katalog inzerátů
- Hodnocení / recenze
- Opakované nebo předplatné platby

---

## Co agent musí vědět při generování stories

- Inzerát je vždy **neveřejný** — žádný katalog, jen přímý link
- Platba funguje jako **escrow** — peníze nejdou prodejci okamžitě
- Každý krok má **notifikační dopad** — při psaní story zkontroluj jestli story vyžaduje notifikaci a pokud ano, zmiň vazbu na EP-07
- Při stories týkajících se AlzaBoxu vždy zmiň závislost na **AlzaBox API**
- Při stories týkajících se platby vždy zmiň závislost na **Adyen for Platforms**
- MVP = nezbytné minimum — agent upozorní pokud story přesahuje MVP rozsah
