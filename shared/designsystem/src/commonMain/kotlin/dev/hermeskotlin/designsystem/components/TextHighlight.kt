package dev.hermeskotlin.designsystem.components

import androidx.compose.runtime.compositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString

/**
 * Characters [start] until [end] of the piece of shown text that reads exactly [block]: one paragraph, list
 * item or code block of a reply, or a whole output. Marked with a highlighter so what a comment is about stays visible.
 *
 * Offsets are into the text as it was written, which is what a comment saves; [withHighlights] maps them onto
 * the characters drawn, which carry the isolate characters a right-to-left reply is shown with.
 */
data class TextHighlight(val block: String, val start: Int, val end: Int)

/** The highlights for the text drawn under it; [MarkdownText] marks each paragraph and code block they match. */
val LocalTextHighlights = compositionLocalOf<List<TextHighlight>> { emptyList() }

/** [this] with a [color] background under every highlight whose block it is, in the text as it was written. */
fun AnnotatedString.withHighlights(highlights: List<TextHighlight>, color: Color): AnnotatedString {
    if (highlights.isEmpty()) return this
    val shown = BidiDisplay.of(text)
    val ranges = highlights
        .filter { it.block == shown.raw && it.start < it.end && it.end <= shown.raw.length }
        .map { shown.displayStart(it.start) to shown.displayEnd(it.end) }
        .filter { (start, end) -> start < end && end <= text.length }
    if (ranges.isEmpty()) return this
    return buildAnnotatedString {
        append(this@withHighlights)
        ranges.forEach { (start, end) -> addStyle(SpanStyle(background = color), start, end) }
    }
}
