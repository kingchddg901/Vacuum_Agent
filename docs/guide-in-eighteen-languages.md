# One maintenance guide, eighteen languages

The filter's care card, in every language Vacuum Agent ships. It is here rather than in
the README because eighteen screenshots is a gallery, not an argument.

**This is the deep end of the translation work, not the shallow one.** Chips and buttons
are single words with obvious equivalents. This card is *prose* — five ordered care steps
and two warnings — plus a health readout, an editable interval with its own units, and a
reset. Getting it right means translating instructions someone follows with the machine
in front of them.

Three details worth looking for, because they are the ones a translation gets wrong when
it is only string substitution:

* **Turkish puts the percent sign first.** English reads `100% remaining`; Turkish reads
  `%100 kaldı`. The sign precedes the number, which no amount of `{value}%` templating
  gets right on its own.
* **The hour unit localises, not just the words around it.** English `Default 20h · Max
  120h` becomes Turkish `Varsayılan 20sa · En fazla 120sa` (*saat*) and Arabic
  `الافتراضي 20س · الحد الأقصى 120س` (*ساعة*).
* **Hebrew and Arabic mirror the whole card** — title and close button swap sides, the
  numbered steps right-align while keeping their numbering, and the interval row reverses
  so Save and Default sit to the left of the field.

Room names are absent here by design: this card describes a part, not a place.

Ordered as the in-app language menu orders them — English first, then by each language's
own name for itself, which is why Korean precedes Japanese.

### 1. English — English

![The filter maintenance card in English](screenshots/Filter_EN.png)

### 2. Bahasa Indonesia — Indonesian

![The filter maintenance card in Indonesian](screenshots/Filter_ID.png)

### 3. Čeština — Czech

![The filter maintenance card in Czech](screenshots/Filter_CS.png)

### 4. Deutsch — German

![The filter maintenance card in German](screenshots/Filter_DE.png)

### 5. Español — Spanish

![The filter maintenance card in Spanish](screenshots/Filter_ES.png)

### 6. Français — French

![The filter maintenance card in French](screenshots/Filter_FR.png)

### 7. Italiano — Italian

![The filter maintenance card in Italian](screenshots/Filter_IT.png)

### 8. Nederlands — Dutch

![The filter maintenance card in Dutch](screenshots/Filter_NL.png)

### 9. Polski — Polish

![The filter maintenance card in Polish](screenshots/Filter_PL.png)

### 10. Português — Portuguese

![The filter maintenance card in Portuguese](screenshots/Filter_PT.png)

### 11. Türkçe — Turkish

![The filter maintenance card in Turkish](screenshots/Filter_TR.png)

### 12. Русский — Russian

![The filter maintenance card in Russian](screenshots/Filter_RU.png)

### 13. עברית — Hebrew

![The filter maintenance card in Hebrew](screenshots/Filter_HE.png)

### 14. العربية — Arabic

![The filter maintenance card in Arabic](screenshots/Filter_AR.png)

### 15. 한국어 — Korean

![The filter maintenance card in Korean](screenshots/Filter_KO.png)

### 16. 日本語 — Japanese

![The filter maintenance card in Japanese](screenshots/Filter_JA.png)

### 17. 简体中文 — Simplified Chinese

![The filter maintenance card in Simplified Chinese](screenshots/Filter_ZH_Hans.png)

### 18. 繁體中文 — Traditional Chinese

![The filter maintenance card in Traditional Chinese](screenshots/Filter_ZH_Hant.png)
