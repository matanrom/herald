package dev.hermeskotlin.designsystem.components

import androidx.compose.ui.text.style.TextDirection

/**
 * A string as it is drawn, with the isolate characters [Bidi] adds for layout only.
 *
 * Isolation is what keeps an inline code span or a path whole inside a Hebrew or Arabic sentence, but the
 * characters it adds are invisible ones that aren't in the reply the agent wrote. Anything that leaves the
 * screen — a comment's selection, Copy — has to be the text as written, and a highlight saved against the
 * written text has to be drawn over the right characters. Both directions are answered here.
 */
class BidiDisplay private constructor(
    /** The characters as drawn, isolate characters and all. */
    val text: String,
    private val inserted: BooleanArray,
) {
    /** The characters as written: [text] without the isolates that were added for layout. */
    val raw: String = buildString(text.length) {
        for (i in text.indices) if (!inserted[i]) append(text[i])
    }

    /** How many characters of [raw] come before [displayIndex] characters of [text]. */
    fun rawIndex(displayIndex: Int): Int = kept[displayIndex.coerceIn(0, text.length)]

    /**
     * Where the boundary before [rawIndex] starts in [text], including an isolate that opens the run
     * there, so a highlight covers the whole run rather than all but its first invisible character.
     */
    fun displayStart(rawIndex: Int): Int = kept.indexOfFirst { it >= rawIndex.coerceIn(0, raw.length) }
        .let { if (it < 0) text.length else it }

    /** Where the boundary after [rawIndex] ends in [text], including the isolate that closes the run. */
    fun displayEnd(rawIndex: Int): Int = kept.indexOfLast { it <= rawIndex.coerceIn(0, raw.length) }
        .let { if (it < 0) 0 else it }

    /** Characters of [raw] before each position of [text], plus the end. */
    private val kept: IntArray = IntArray(text.length + 1).also { counts ->
        for (i in text.indices) counts[i + 1] = counts[i] + if (inserted[i]) 0 else 1
    }

    companion object {
        /**
         * [text] with the isolates that [Bidi] would have added recognised, so [raw] is the text it was made
         * from. Isolates the author wrote are left alone: only a pair that wraps a run the isolation pass
         * would wrap — no control characters of its own, and either opening with a left-to-right character or
         * being a run of digits and punctuation — is taken as one of ours.
         */
        fun of(text: String): BidiDisplay {
            if (text.indexOf(Bidi.LRI) < 0) return BidiDisplay(text, BooleanArray(text.length))
            val inserted = BooleanArray(text.length)
            var i = 0
            while (i < text.length) {
                if (text[i] != Bidi.LRI) {
                    i++
                    continue
                }
                val close = text.indexOf(Bidi.PDI, i + 1)
                if (close < 0) break
                if (isAddedRun(text.substring(i + 1, close))) {
                    inserted[i] = true
                    inserted[close] = true
                    i = close + 1
                } else {
                    i++
                }
            }
            return BidiDisplay(text, inserted)
        }

        /** Whether [inner] is a run the isolation pass wraps: a left-to-right opening, or numbers and punctuation. */
        private fun isAddedRun(inner: String): Boolean {
            if (inner.isEmpty()) return false
            if (inner.any { it.isBidiControl() }) return false
            var opensLeftToRight = false
            var opensRightToLeft = false
            for (c in inner) {
                when {
                    Bidi.isRightToLeft(c) -> {
                        opensRightToLeft = true
                        break
                    }
                    Bidi.isLeftToRight(c) -> {
                        opensLeftToRight = true
                        break
                    }
                }
            }
            if (opensLeftToRight) return true
            // No letters at all: a run of digits, punctuation or symbols, which opens with a run character.
            return !opensRightToLeft && inner[0] in '0'..'9'
        }
    }
}

/** Text as the rest of the app sees it: direction for layout, and the written form for everything else. */
object BidiText {

    /**
     * The direction [text] is laid out in: right to left when most of its letters are Hebrew or Arabic, and
     * [TextDirection.Content] otherwise, so each string still follows its own first strong character.
     */
    fun direction(text: String): TextDirection =
        if (Bidi.prefersRightToLeft(text)) TextDirection.Rtl else TextDirection.Content

    /** [text] without the isolates added for layout, keeping any the author wrote. */
    fun withoutInsertedIsolation(text: String): String = BidiDisplay.of(text).raw

    /** [text] as drawn, with the isolates it carries told apart from those the author wrote. */
    fun displayOf(text: String): BidiDisplay = BidiDisplay.of(text)
}

/** The zero-width characters that order text without being seen. */
internal fun Char.isBidiControl(): Boolean = when (this) {
    '\u200E', '\u200F', // LRM, RLM
    '\u202A', '\u202B', '\u202C', '\u202D', '\u202E', // LRE, RLE, PDF, LRO, RLO
    '\u2066', '\u2067', '\u2068', '\u2069', // LRI, RLI, FSI, PDI
    '\u061C', // ALM
    -> true
    else -> false
}
