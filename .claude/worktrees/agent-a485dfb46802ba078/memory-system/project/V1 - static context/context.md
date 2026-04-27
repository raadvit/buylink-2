# Kontext projektu: Zlatnicek

## 🌐 Web
www.zlatnicek.cz

---

## 🧾 Business kontext

Projekt se zaměřuje na prodej a výkup investičních aktiv:

### Prodej:
- mince České národní banky (ČNB)
- investiční mince (zlato, stříbro, platina, palladium)
- investiční slitky
- bankovky

### Výkup:
- výkup mincí a drahých kovů od zákazníků

---

## 🛒 Platforma
- e-shop běží na Shoptetu (tarif Business)

---

## 👤 Chování zákazníků

Zákazníci:
- vytvářejí objednávky přes e-shop
- vytvářejí rezervace na budoucí emise mincí

---

## 🔑 Klíčový koncept: rezervace

- rezervace je realizována jako běžná objednávka v Shoptetu
- obsahuje produkt typu „rezervace“ (např. rezervace konkrétní mince)

### Význam:
- rezervace nejsou závazný nákup
- slouží jako indikace budoucí poptávky
- klíčové pro rozhodování:
  - kolik kusů objednat od dodavatele (např. ČNB)

---

## 📦 Data

Zdroj dat:
- exporty ze Shoptetu (CSV)

Typy dat:
- objednávky
- produkty
- zákazníci (odvozeno)

---

## 🔄 Aktualizace dat

- data se budou aktualizovat manuálně
- uživatel spustí import (např. tlačítkem „Načíst data“)
- aplikace může běžet lokálně

Do budoucna:
- spuštění importu z webového rozhraní

---

## 📊 Co potřebujeme sledovat

### Rezervace
- kdo co rezervoval
- kolik kusů
- agregace podle produktu

---

### Objednávky
- standardní prodeje
- historie zákazníků

---

### Produkty
- seznam aktivních produktů
- typy produktů:
  - rezervace
  - investiční
  - ČNB

---

### Sklad
- aktuální stav zásob
- vazba na:
  - nákupy (výkup / dodavatel)
  - prodeje

---

### Výkup
- evidence nákupů od zákazníků
- vstup do skladu

---

### Nákupní ceny
- sledování nákupních cen
- potřeba:
  - FIFO (first in, first out)
  - LIFO (last in, first out)

### Využití:
- výpočet marže
- podklady pro fakturaci (do budoucna)

---

## 🎯 Hlavní cíle

1. odstranit ruční přepisování dat  
2. mít přehled o rezervacích (kolik objednat)  
3. mít kontrolu nad skladovými zásobami  
4. připravit data pro další systémy (např. fakturace)  

---

## 🔮 Budoucí směr

### API
- přístup k datům (rezervace, objednávky, sklad)

---

### Zákaznický modul (na webu)
- zákazník uvidí:
  - své rezervace
  - historii

---

## Struktura repozitáře

| Adresář | Typ | Popis |
|---|---|---|
| `agents/` | project-agnostic | tým agentů, workflow, constraints, token strategie — přenositelné |
| `task-forge/` | project-agnostic | tool pro zadávání a správu stories — přenositelný |
| `memory-system/` | project-specific | V1/V2/V3/V4 paměťový systém pro tento projekt |
| `order-management/` | project-specific | samotná aplikace |

`agents/` a `task-forge/` nesmí obsahovat žádné reference na tento konkrétní projekt.

---

## ⚠️ Důležité poznámky

- Shoptet má omezené možnosti integrace (budeme si stahovat exporty)
- práce s daty bude založená na exportech
- rezervace je potřeba správně identifikovat v datech
