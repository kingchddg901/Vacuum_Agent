# Dreame L10s Ultra Gen 2 — manual inventory and language coverage

Device: `dreame.vacuum.r2469a`, firmware `4.3.9_1636`, retail SKU **RLL32SE** (robot) /
**RCLE0304** (base station). Marketing name **L10s Ultra Gen 2**.

Files mirrored to `C:\Users\CKing\Documents\durable\dreame-port-fixture\manuals\`
(10 PDFs, ~119 MB). **Not in the repo — vendor copyright, and this repo is public.**

## Coverage against the project's 18 i18n languages

**In hand (15):** ar de en es fr he id it ja nl pl pt ru tr zh-Hant
**Absent (3):** cs ko zh-Hans

The three negatives are evidenced, not merely unfound:

* **cs** — Czech entered Dreame's documentation set at **Gen 3** (the Gen 3 Series manual
  bundles CZ/SK/SL/HU/SR/LT/LV/RO). Gen 2 predates it. Product-timeline fact.
* **ko** — device is sold in Korea, but `kr.dreametech.com/guide/manual` carries exactly
  12 entries (X60 / Aqua10 / Matrix10 / X50s family) and no L10s of any generation;
  adjacent ids probed to prove the list is complete. Dreame Korea never published it.

  ⚠ **THIS IS A GEN 2 FINDING AND DOES NOT GENERALISE TO DREAME (added 2026-08-25).**
  It stands exactly as written — but the 12 entries it names are other models, and
  `durable/dreame-port-fixture/manuals/korean-vocabulary-source/` already holds nine of
  them, including **`R2489F` (X50 Ultra)** and **`R5089F` (X60 Ultra)** — both now
  authored families. So Korean IS in hand for `x50` and `x60_ultra`; it is absent only
  for the L10s Gen 2, which is all this file was ever about. Quote it with its scope
  attached, or it reads as "Dreame has no Korean manuals", which is false.

  Those PDFs are print-production files whose first page is Chinese production notes
  (`R2489F- 韩版 A00 ...`), so a first-page language sniff calls them Chinese. The model
  id in that header is what identifies them.
* **zh-Hans** — L10s Ultra Gen 2 looks **export-only**; the domestic 追覓 catalogue is
  S/X-series with no L-series equivalent, and Dreame CN ships manuals inside the app
  rather than as web PDFs. No domestic SKU to match against.

## Which file holds which language

| file | pages | languages |
|---|---|---|
| `R2469X-..._EN_DE_FR_IT_ES.pdf` | 147 | EN DE FR IT ES |
| `R2469X-..._PL_NL_NO_SV_EL.pdf` | 144 | PL NL NO SV EL |
| `R2469X-..._PT_HE_AR.pdf` | 84 | PT HE AR |
| `R2469A-_EN_FI_DA_MS_*.pdf` | 58 | EN FI DA MS |
| `R2469A-_RU_KK_UZ_UA.pdf` | 55 | RU KK UZ UA |
| `R2469B-...-A01_ERP.pdf` | 143 | **EN TR VI TH ID** |
| `R2469D-...-A02_ERP.pdf` | 88 | **EN AR ZH-HK** |
| `R2469E-L10s_Ultra_Gen2-JA.pdf` | 16 | **JA** (Dreame Japan, 100 V variant) |
| `TW-L10s_Ultra_Gen2-zh-Hant-TW.pdf` | 16 | **ZH-HANT (TW)** |
| `R2469B-TR_site-EN_TR.pdf` | 30 | EN TR (2-language subset from the TR store) |

Variant suffix = market, not product: A/B/C/D/X global, **E = Japan**. R2469E was not in
the known-variants list and had to be added. Two *different* documents both call
themselves R2469B (the 143-page SEA/TR edition and a 30-page EN+TR subset on the Turkish
store) — the suffix does not uniquely identify a file.

zh-Hant exists in **two** regional flavours: **ZH-HK** inside `R2469D`, and a separate
**TW** edition from Dreame Taiwan. Wording differs between HK and TW Traditional; pick
deliberately if transferring text.

## ⚠ The filename is not a manifest — it under-reports

`R2469X-..._EN_DE_FR_IT_ES.pdf` names its languages. `R2469B-...-A01_ERP.pdf` and
`R2469D-...-A02_ERP.pdf` do not, and the linking page labels them only "EU" and "UK".
Both are multi-language editions:

* `R2469B` contains **Turkish and Indonesian** — two languages independently searched for
  across dozens of regional domains, sitting in a file already downloaded from the global
  site.
* `R2469D` contains a complete **ZH-HK** edition, likewise declared absent from the global
  site.

This cost three separate wrong conclusions in one session — mine (reading the filename
list as complete), and two subagents' (`id` and `zh-Hant` both reported "not on any
Dreame-owned domain" after reading the *page label* for R2469B/D rather than opening the
files). A third subagent (`cs`) downloaded and text-extracted the same PDF and reported
`EN / TR / VI / TH / ID` correctly.

**Rule: open the file. A container's name and its index page are both metadata, and
metadata under-reports.** Same shape as the `custom_name` and CRLF failures logged
elsewhere in these notes — the cheap surface disagreed with the payload, and only reading
the payload settled it.

## TECHNIQUE — back-work terminology from a sibling model's manual

Chris's idea, 2026-08-10, and it works. Dreame reuses manual boilerplate almost verbatim
across generations, so a language missing for *this* model can often be recovered from
*another* model's manual. Czech is absent for Gen 2 but present in the **Gen 3 Series**
14-language edition:

`cdn.shopify.com/s/files/1/0302/5276/1220/files/User_Manual-L10s_Ultra_Gen3_Series-MS_FI_DA_KK_UZ_UA_CZ_SK_SL_HU_SR_LT_LV_RO.pdf`
(225 pp, 13.3 MB; CZ block pp. 97-112; mirrored locally as `GEN3-...pdf`)

**Lift the VOCABULARY, never the prose.** Gen 3 is different hardware (robot RLL53SE vs
Gen 2's RLL32SE) — its manual documents parts Gen 2 does not have. Transferring sentences
would ship claims about the wrong machine.

### Verified EN -> CS glossary (aligned against the Gen 2 EN maintenance table)

| Gen 2 EN | CS (Dreame's own wording) |
|---|---|
| Used water tank | Nádržka na použitou vodu |
| Clean water tank | Nádržka na čistou vodu |
| Main brush | Hlavní kartáč |
| Side brush | Boční kartáč |
| Dust box | Prachový box |
| Dust box's filter | Filtr prachového boxu |
| Dust bag | Prachový sáček |
| Mop pad | Mopovací podložka |
| Mop pad holder | Držák mopovací podložky |
| Base station | Základní stanice |
| Base station's signaling area | Signalizační oblast na základní stanici |
| Charging contacts | Nabíjecí kontakty |
| Auto-empty vents | Automatické vyprázdnění ventilačního otvoru |
| Omnidirectional wheel | Všesměrové kolo |
| Edge sensor | Senzor okraje |
| Cliff sensors | Senzory srázu |
| Carpet sensor | Senzor koberce |
| Bumper | Nárazník |
| Laser Distance Sensor (LDS) | Laserový snímač vzdálenosti (LDS) |
| Spot cleaning | Bodové čištění |
| Vacuum and mop | Vysávání a mopování |
| Routine maintenance | Rutinní údržba |
| Maintenance frequency | Frekvence údržby |
| Replacement period | Doba výměny |

**Maintenance intervals match exactly** across the two generations for every shared part
(after each use / 2 weeks / 6-12 months / 3-6 months / monthly / 2-4 months / 1-3 months),
and the troubleshooting prose aligns too ("The robot will not turn off" -> "Robot se
nevypíná", identical 3.5 h / 3 s / 10 s figures).

**Where they diverge — why the table is not copyable:** Gen 3 adds `Filtr mycí desky`
(washboard filter, 1-2 months) and `Hlavní kola` (main wheels); Gen 2 has a *3D line laser
sensor* entry Gen 3's list does not. Map term by term, never row by row.

## Note for guide content

Per the standing rule, guide content is AI-authored by default and only transferred when a
manual is genuinely in hand. For this model it is in hand for **15 of 18** languages, so a
Dreame upkeep guide would be a split: manufacturer text for those 15, AI-authored for
cs/ko/zh-Hans. That split is a property of what Dreame printed, not of the guide.
