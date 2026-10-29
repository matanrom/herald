package dev.hermeskotlin.designsystem.components

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.style.TextDirection
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue

class BidiDisplayTest {

    private val lri = Bidi.LRI
    private val pdi = Bidi.PDI

    private fun isolated(markdown: String): String {
        val parsed = Bidi.isolateInlineCode(markdown)
        return if (Bidi.prefersRightToLeft(markdown)) Bidi.isolateLtrRuns(parsed) else parsed
    }

    // MARK: what was drawn goes back to what was written

    @Test
    fun theDrawnTextGoesBackToTheWrittenOne() {
        val fixtures = listOf(
            "شغّل `hermes update` بعد النسخ الاحتياطي.",
            "הפעל את hermes update ואז בדוק /root/.hermes/config.yaml",
            "התאריך 2026-11-20, גרסה v0.14.0, 25$",
            "בדוק את auto_prune תחת checkpoints (7 ימים) — זה שונה",
            "أكتوبر ما زال في متناوله حتى 2026-11-20: لو دفع الـ25$ قبله",
            "المسار هو `/root/.hermes/config.yaml` والنسخة `v0.22.5`.",
            "قبل:\n```bash\nhermes sessions prune\n```\nوبعد `x`",
            "    hermes sessions prune\nسطر `y`",
            "`one` و `two` و `three`",
            "שלום 🙂 עולם `git status` 🙂 סוף",
            "",
            "plain English with `code` and no isolates",
        )
        for (fixture in fixtures) {
            val shown = isolated(fixture)
            assertEquals(fixture, BidiDisplay.of(shown).raw, "round trip of: $fixture")
        }
    }

    @Test
    fun aStringWithoutIsolatesIsItsOwnRawText() {
        val text = "התאריך 2026-11-20"
        val shown = BidiDisplay.of(text)
        assertEquals(text, shown.raw)
        assertEquals(text.length, shown.text.length)
        for (i in 0..text.length) assertEquals(i, shown.rawIndex(i))
    }

    @Test
    fun theAnchorsOwnControlCharactersAreKept() {
        val text = "\u200Fשלום\u200E hello \u202Bمرحبا\u202C ${lri}مرحبا بك$pdi"
        assertEquals(text, BidiText.withoutInsertedIsolation(text))
    }

    // MARK: offsets, in both directions

    @Test
    fun aWrittenOffsetFindsTheCharactersDrawn() {
        // "שלום `hermes update` סוף": the span is drawn with an isolate inside the backticks.
        val text = "שלום `${lri}hermes update$pdi` סוף"
        val shown = BidiDisplay.of(text)
        val raw = "שלום `hermes update` סוף"
        assertEquals(raw, shown.raw)

        val open = raw.indexOf("hermes")
        val close = open + "hermes update".length
        assertEquals(open, shown.displayStart(open))
        assertEquals(close + 2, shown.displayEnd(close))
        assertEquals(text.substring(shown.displayStart(open), shown.displayEnd(close)), "${lri}hermes update$pdi")

        // A drawn offset maps past every isolate before it: the boundary before 'h' is drawn one further on.
        assertEquals(open, shown.rawIndex(open + 1))
        assertEquals(close, shown.rawIndex(close + 2))
    }

    @Test
    fun offsetsOutsideIsolatesAreUnchanged() {
        val text = "أكتوبر ${lri}2026-11-20$pdi: لو دفع"
        val shown = BidiDisplay.of(text)
        assertEquals("أكتوبر 2026-11-20: لو دفع", shown.raw)
        assertEquals(0, shown.rawIndex(0))
        assertEquals(7, shown.rawIndex(7))
        assertEquals(7, shown.displayStart(7))
    }

    @Test
    fun emojiCountAsTwoUnitsOnBothSides() {
        val text = "שלום 🙂 ${lri}state.db$pdi 🙂 סוף"
        val shown = BidiDisplay.of(text)
        val raw = "שלום 🙂 state.db 🙂 סוף"
        assertEquals(raw, shown.raw)
        val start = raw.indexOf("state.db")
        val end = start + "state.db".length
        assertEquals(start, shown.rawIndex(shown.displayStart(start)))
        assertEquals(end, shown.rawIndex(shown.displayEnd(end)))
        assertEquals("${lri}state.db$pdi", text.substring(shown.displayStart(start), shown.displayEnd(end)))
    }

    @Test
    fun aRepeatedWordMapsToTheOccurrenceTheOffsetsName() {
        val text = "הראשון ${lri}auto_prune$pdi ואז ${lri}auto_prune$pdi שוב"
        val shown = BidiDisplay.of(text)
        val raw = "הראשון auto_prune ואז auto_prune שוב"
        assertEquals(raw, shown.raw)
        val second = raw.indexOf("auto_prune", startIndex = raw.indexOf("auto_prune") + 1)
        val drawn = text.substring(shown.displayStart(second), shown.displayEnd(second + "auto_prune".length))
        assertEquals("${lri}auto_prune$pdi", drawn)
    }

    // MARK: direction

    @Test
    fun aHebrewOrArabicTextIsLaidOutRightToLeft() {
        assertEquals(TextDirection.Rtl, BidiText.direction("בדוק כל יום אם auto_prune פעיל"))
        assertEquals(TextDirection.Rtl, BidiText.direction("شكراً على الشرح"))
    }

    @Test
    fun everythingElseFollowsItsOwnFirstStrongCharacter() {
        assertEquals(TextDirection.Content, BidiText.direction("Check auto_prune under checkpoints"))
        assertEquals(TextDirection.Content, BidiText.direction("2026-11-20 25$"))
        assertEquals(TextDirection.Content, BidiText.direction(""))
    }

    // MARK: highlights

    @Test
    fun aHighlightSavedAgainstTheWrittenTextCoversTheCharactersDrawn() {
        val text = "שלום ${lri}hermes update$pdi סוף"
        val annotated = AnnotatedString(text).withHighlights(listOf(TextHighlight("שלום hermes update סוף", 5, 18)), Color.Red)
        val style = annotated.spanStyles.single()
        assertEquals("${lri}hermes update$pdi", annotated.text.substring(style.start, style.end))
    }

    @Test
    fun aHighlightInPlainTextKeepsItsOffsets() {
        val text = "שלום עולם"
        val annotated = AnnotatedString(text).withHighlights(listOf(TextHighlight(text, 5, 9)), Color.Red)
        val style = annotated.spanStyles.single()
        assertEquals(5, style.start)
        assertEquals(9, style.end)
    }

    @Test
    fun aHighlightFromAnotherBlockMarksNothing() {
        val annotated = AnnotatedString("שלום ${lri}hermes$pdi").withHighlights(listOf(TextHighlight("משהו אחר", 0, 4)), Color.Red)
        assertTrue(annotated.spanStyles.isEmpty())
    }

    @Test
    fun aHighlightRunningPastTheEndIsDropped() {
        val text = "שלום עולם"
        val annotated = AnnotatedString(text).withHighlights(listOf(TextHighlight(text, 5, 99)), Color.Red)
        assertTrue(annotated.spanStyles.isEmpty())
    }

    @Test
    fun everyHighlightThatMatchesGetsItsOwnStyle() {
        val text = "${lri}auto_prune$pdi ו-${lri}state.db$pdi"
        val raw = "auto_prune ו-state.db"
        val annotated = AnnotatedString(text).withHighlights(
            listOf(TextHighlight(raw, 0, "auto_prune".length), TextHighlight(raw, raw.indexOf("state.db"), raw.length)),
            Color.Red,
        )
        assertEquals(2, annotated.spanStyles.size)
        assertEquals("${lri}auto_prune$pdi", annotated.text.substring(annotated.spanStyles[0].start, annotated.spanStyles[0].end))
        assertEquals("${lri}state.db$pdi", annotated.text.substring(annotated.spanStyles[1].start, annotated.spanStyles[1].end))
    }

    @Test
    fun noHighlightsMeansTheTextIsUntouched() {
        val text = "שלום ${lri}hermes$pdi"
        val annotated = AnnotatedString(text).withHighlights(emptyList(), Color.Red)
        assertEquals(text, annotated.text)
        assertTrue(annotated.spanStyles.isEmpty())
        assertNull(annotated.spanStyles.firstOrNull())
    }
}
