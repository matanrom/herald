package dev.hermeskotlin.designsystem.components

import androidx.compose.ui.text.style.TextDirection

/** Style only. Text and selection offsets are always the original rendered block's, including authored controls. */
object BidiText {
    fun direction(text: String): TextDirection =
        if (Bidi.prefersRightToLeft(text)) TextDirection.Rtl else TextDirection.Content
}

/** The existing math pipeline is the only source preparation. Bidi is exclusively a rendering style. */
internal fun prepareMarkdown(text: String): String = MathMarkup.prepare(text)
