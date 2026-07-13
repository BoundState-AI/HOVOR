# Content Delta — ancestry-slice-0.2.3

**Date:** 2026-07-13
**Scope:** one slice, one version. Everything below ships together as
`ancestry-slice-0.2.3`, all flagged `PENDING_NATIVE_REVIEW` for the Prague
native-review pass. (Earlier drafts of this doc referenced 0.2.1/0.2.2
staging versions; those never shipped separately.)

## 1. Lexeme expansion (+28 over the 131-lexeme base)

- **Directions & navigation:** doľava, doprava, rovno, ďalej, zastávka,
  na rohu, oproti, vedľa
- **Motion & modals:** idem, môžem, musím, môžete, viem
- **Shopping & places:** pekáreň, kúpiť, rožok, trh
- **Politeness & address:** pán, pani, ďakujem pekne
- **Days of the week (complete):** pondelok, utorok, streda, štvrtok,
  piatok, sobota, nedeľa
- **Also:** Bratislava (proper noun)

Confusion pairs added in `skills.json`: zastávka/stanica, môžem/musím,
doľava/doprava, pekáreň/obchod. No new skill nodes.

## 2. Mission: `pezinok_square_stop` — "Pezinok: Bread and the Way Forward"

pani Szabová's bakery on the square: buy rožky, ask the price, get
directions to the Modra bus stop, survive one repair when she mishears the
destination. 6 objectives. Campaign now has 4 missions across 4 regions.

**Unlock note:** Modra still unlocks after `svaty_jur_family` alone.
An earlier draft gated Modra behind Pezinok too, but that retroactively
re-locks Modra for existing learners — Pezinok is a parallel stop on the
route, not a gate.

## 3. Day-0 alphabet & diacritics primer

`alphabet.json` (46 letters including dz/dž/ch digraphs, real-word minimal
contrast pairs with glosses, typing-practice word list, per-platform typing
tips) + `GET /api/v1/alphabet` + a no-scoring primer screen in the web
client. All primer strings (letters, examples, contrast words, practice
words) are registered in the `/tts` speakable set so every 🔊 works.
Practice words live in the JSON — not the client — so the native reviewer
sees them.

## Native-review packet impact

New items for the reviewer: the 28 lexemes, the pezinok_square_stop script,
and all alphabet primer content (letter examples, contrast pairs and
glosses, practice words, typing tips). Particular attention: rare-letter
examples (ĺ, ŕ, ä) and the naturalness of pani Szabová's lines.
