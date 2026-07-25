# Archived experiment — generation contract for single-file browser games

To make functional verification tractable *across arbitrary implementations*, the
generator must expose a small, stable, testable hook. The gate drives this hook
deterministically instead of reverse-engineering each app's DOM.

This is a deliberate trade (D15 / Q9): a sliver of generation freedom for large
gains in gate reliability and generality.

## Wordle contract

The page MUST define, on `window`, an object `__wordle` with:

- `setAnswer(word: string): void` — force the secret word (5 letters, any case).
- `guess(word: string): string` — return exactly 5 characters, one per letter:
  - `'G'` — right letter, right position (green)
  - `'Y'` — letter is in the answer but wrong position (yellow), correctly
    limited by remaining letter counts after greens (duplicate handling)
  - `'B'` — letter not in the answer / no remaining count (gray)

The visible game may be built however the model likes; the hook is what the gate
tests. `guess` must be a pure function of the current answer + the guessed word.

Every game vertical gets its own contract + acceptance module (see
`wordle_spec.py`). This is the seed of the per-app "acceptance criteria" layer.
