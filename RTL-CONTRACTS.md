# Corrected RTL build contracts (before implementation)

The rejected candidate is db7d68aedbfec6a64ec06c536c98fcd8ebf3be9c. Reviewed APK and executable reproductions: `/home/matan/research/hermes-android/APK-REVIEW.md` and `apk-review-evidence/ReviewProbe.java`.

## Decision

Replace source-level bidi insertion and guessed clipboard/anchor cleanup, rather than extend their scanners. Retain a minimal rendering/style-only subset of lama's PR #267 (original cherry-picks remain attributed in Git history): content direction, local list/table layout, and LTR code text/viewport; prompt/composer stay style-only. No claim of perfect RTL or guaranteed contiguous Latin phrases in mixed prose. No new inline run isolation implementation is attempted.

## Invariants and acceptance

1. The bidi layer never adds, removes, or normalizes any source or selectable text code point. Native selection therefore slices original rendered block text at unchanged UTF-16 offsets; no bidi clipboard provider, global stripper, or inferred insertion provenance remains. Markdown syntax itself is normally not selectable; native Copy preserves the rendered block substring, not raw Markdown markup. Whole-message/code Copy retain their existing original-source paths (including existing code display trailing-newline trimming).
2. All authored controls (RLM/LRM/LRI/PDI/RLI/FSI, Latin and numeric isolate pairs, unbalanced boundaries) are data, including inside inline/fenced code. Preserve all ranges, not merely complete isolation pairs. Tests compare UTF-16 ranges and valid code-point UTF-8 slices. Emoji/repeated strings/cross-block comments retain offsets.
3. Markdown source reaches the existing math preparation/parser pipeline without bidi edits. Compare actual Markdown 0.7.9 AST node types, offsets and source slices: Hebrew ordered list, inline and reference destinations, four-backtick block containing three backticks, tilde and nested/container fences. The pre-existing math rendering feature is not redesigned; regression tests establish no new bidi mutation relative to MathMarkup.prepare.
4. Chat, selectable Markdown file preview and Journey all use the same non-mutating Markdown renderer. Their ordinary platform clipboard is sufficient, including code Copy pills. No special cleanup coverage list is needed.
5. Comments/Explain/Ask-aside, original raw saved highlights and raw code compare directly against the rendered text, with no guessed removal. Authored RLM inside `foo\u200Fbar`, authored Latin/numeric isolates and partial boundaries must survive anchors/highlights byte-for-byte. Old raw comments stay compatible. Corrupted comments saved by the rejected candidate are not silently migrated.
6. New regression tests must demonstrably fail against the rejected design before the replacement; bounded local suites and assembly/lint run one worker, offline warm cache, no daemon, in-process Kotlin, bounded heap and a low-available-memory abort monitor. No global swap/service/production changes. Stop with a precise blocker if the build cannot fit safely.
7. Preserve co-install package `dev.herald.android.matanrtl`, label `Herald RTL Test`, existing debug signer, no voice/UI additions, no workflows/upstream writes. Commit source before final assembly, embed exact SHA, copy to distinct `apk/herald-rtl-corrected.apk`, verify hash/package/signature/revision and fork remote SHA. Deliver for independent re-review, not self-approval. Native phone-menu, locale visuals/caret and installation remain explicitly unverified without a device.

## Root-cause predictions

- Highest confidence: removing Markdown insertion fixes ordered-list grammar, reference destinations and code-fence corruption together; parser AST must equal the unchanged pipeline.
- Removing heuristic removal fixes authored Latin/numeric controls in copied code and anchors/highlights; direct text equality/offset tests must pass.
- Removing both eliminates the partial-pair and preview/Journey bypass class entirely: selectable strings contain no display-only boundary to leak. Source guards and exhaustive short-fixture range comparisons establish that architecture; they do not simulate an Android native menu.
