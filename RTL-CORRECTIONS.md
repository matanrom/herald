# RTL corrections — style-only replacement

**Status: implementation candidate for independent re-review, not approval.** This supersedes the rejected source-injection/clipboard-cleanup design at `db7d68aedbfec6a64ec06c536c98fcd8ebf3be9c`. The prior `IMPLEMENTATION.md` is historical; its safety claims and exact-head CI claim are superseded by `APK-REVIEW.md` in `/home/matan/research/hermes-android/`.

## Contract and design

`RTL-CONTRACTS.md` was written before production edits. The fallback is deliberately smaller than upstream PR #267: content-direction styles, content-local unordered-list/table layout, LTR code text/viewport, style-only prompt/composer. Original lama commits `72feae418eeeebb56d79088a4ef38bef2cad3b80` and `3ad3ceb46ae9e779281742b11c86ef9f35fc5615` remain in history; retained classifier/style work is attributed to lama. We remove their source isolation and our subsequently rejected guessed cleanup rather than pretending it is reversible.

No LRI/PDI insertion, no guessed raw/display map, no clipboard interception. `prepareMarkdown` delegates only to the pre-existing `MathMarkup.prepare`; Markdown parsing and normal renderer annotation determine text/code/link context. Direction never edits parser input or `AnnotatedString.text`. Thus native Copy can select any substring (including half of an authored isolate) without a sanitizer. Raw Markdown formatting itself is not part of native rendered selection. Whole-message Copy and code Copy use their unchanged original-input paths; code display retains its pre-existing trailing-newline trim. Math rendering semantics remain the baseline's, not an assertion that raw TeX markup is copied from a formula picture.

| Review blocker | Correction and regression |
|---|---|
| B1 partial native Copy leaks | Remove injected boundaries altogether; enumerate every UTF-16 selection of short plain/authored-control fixtures and compare characters/UTF-8 bytes. No repair with selected-text-only provenance. |
| B2 preview/Journey bypass | The shared renderer no longer injects text on any surface. No clipboard provider is required on chat, FileViewer or Journey. Architecture guard verifies shared route and absence of rewriting. |
| B3 Hebrew numbered lists/reference destination mutation | Real Markdown 0.7.9 AST types, offsets and source slices stay identical for ordered lists and inline/reference destinations. |
| B4 long-fence code corruption | Delete scanner rather than implement another fence grammar. AST equality includes four-backtick/tilde fences containing shorter delimiters, blockquote/list containers, and ordinary code control. |
| B5 authored RLM and authored Latin/numeric isolates | Preserve originals in preparation, anchors and highlights. Exhaustive short-fixture range/offset tests include RLM, Latin/numeric LRI pairs, emoji, repeated text and cross-block endpoints. |

`BidiDisplay.kt`, `BidiClipboard.android.kt` and insertion scanners are deleted. `rawAnchor` is now a documented identity operation; highlights use original block equality and original offsets, retaining old raw saved comments. Tests that required generated isolates/stripping were removed because that behavior is intentionally no longer supported, not silently changed to accept corruption.

## Executed RED/GREEN evidence

Evidence directory: `/home/matan/research/hermes-android/apk-review-evidence/`.

- Before production changes, `RtlIntegrityTest` uses the rejected renderer's exact preparation sequence (inline isolation of math-prepared input, then conditional run isolation). Confirmed RED run: **8 tests, 7 failures** with actual string/AST differences; existing inline-link control passes. Initial fixture guards needed the parser's `Markdown:` type prefix handled with `endsWith`; the confirmed run corrected this before fixing code.
- Two new UI anchor tests also fail against the rejected design: authored-control removal and cross-block offset corruption. Confirmed RED UI **17 tests, 2 failures**. Logs `corrections-red-confirmed.log`, saved `red-TEST-*.xml`; no fabricated probe outputs.
- After replacement, regression helper calls the actual production `prepareMarkdown` seam used by `MarkdownText`, rather than a copied scanner. First full GREEN: designsystem **67 tests**, UI **622 tests**, zero failures/errors/skips; **BUILD SUCCESSFUL in 2m 34s**, 1200 MiB heap, one worker, offline, in-process Kotlin, monitor minimum available RAM **1553 MiB**. The count reduction replaces 41 isolation-era tests with 12 style/integrity tests; UI replaces two invalid stripping expectations with two preservation tests.
- `python scripts/verify-rtl-contract.py --revision db7d68aedbfec6a64ec06c536c98fcd8ebf3be9c` fails eight architecture checks; current tree passes all ten. This is a static guard, not a phone/native-menu integration test.

## Exact-head assembly and artifact verification

The source revision is the Git commit containing this document (recorded externally before assembly; an exact self-referential SHA cannot be embedded in its own source document). Final build/test/lint logs, source SHA, remote SHA, APK hash/package/certificate and packaged revision are recorded in `/home/matan/research/hermes-android/RTL-CORRECTIONS.md` and `apk/corrected-verification.json` after execution. Do not infer assembly success from this source report alone.

Reproduce with JDK `/home/matan/tools/jdk-25.0.5+8`, SDK `/home/matan/tools/android-sdk`:

```sh
python scripts/verify-rtl-contract.py
./gradlew --offline --no-daemon --max-workers=1 --console=plain \
  '-Dorg.gradle.jvmargs=-Xmx1800m -XX:MaxMetaspaceSize=512m' \
  -Dorg.gradle.parallel=false -Dorg.gradle.configuration-cache=false \
  -Pkotlin.compiler.execution.strategy=in-process \
  :shared:designsystem:testAndroidHostTest :shared:ui:testAndroidHostTest \
  :androidApp:assembleRtl :androidApp:lintRtl -PappVersion=0.13.0
```

Actual local runs additionally use `apk-review-evidence/bounded-gradle.py`: start-headroom check, process-group timeout, available-memory monitor every two seconds, abort below 700 MiB. No added swap, service change or production access. No workflow modification/scope expansion, upstream PR, voice feature, full-shell UI addition or live gateway test.

## Boundaries and independent re-review

- This subset does **not** promise perfect RTL or LTR run isolation in mixed prose; Latin phrases/punctuation may still need a future rendering-only solution. Ordered-list parser semantics are protected, but a custom RTL ordered-list renderer is not added. The retained majority classifier has its original early-return approximation.
- No emulator/phone native Copy menu, visual layout, caret/undo, en-US/he-IL locale matrix or install/co-install was exercised. Byte/range and parser tests plus Android compilation do not stand in for those results. Independent reviewer must recheck source, binary metadata and the synthetic device matrix from `APK-REVIEW.md`.
- Package remains `dev.herald.android.matanrtl`, label `Herald RTL Test`, release-derived RTL build type with existing local debug signer. Shared `hermes:` deep links and call affinity remain known co-install ambiguities. Manual launch only; no clearing/uninstalling/migrating official app data.
- Do not migrate already-corrupted comments from the rejected candidate by guessing which controls were authored. No history has been changed.
