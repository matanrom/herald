package dev.hermeskotlin.ui.chat

import android.content.ClipData
import androidx.compose.ui.platform.ClipEntry
import androidx.compose.ui.platform.Clipboard
import dev.hermeskotlin.designsystem.components.BidiText

/**
 * [delegate], with text going in stripped of the isolate characters a reply is only drawn with.
 *
 * A right-to-left reply carries LRI…PDI around its inline code and its left-to-right runs so the lines read in
 * order. Selection Copy is the platform's own menu item and would put those zero-width characters on the
 * clipboard; this is the one place it passes through. Nothing else about an entry changes: non-text items, and
 * text that only has the author's own control characters, go through as they are.
 */
internal fun bidiSafeClipboard(delegate: Clipboard): Clipboard = object : Clipboard by delegate {
    override suspend fun setClipEntry(clipEntry: ClipEntry?) {
        delegate.setClipEntry(clipEntry?.withoutInsertedIsolation())
    }
}

/** [this] with every text item as the agent wrote it. */
private fun ClipEntry.withoutInsertedIsolation(): ClipEntry {
    val source = clipData
    if (source.itemCount == 0) return this
    var changed = false
    val items = (0 until source.itemCount).map { index ->
        val item = source.getItemAt(index)
        val text = item.text?.toString() ?: return@map item
        val written = BidiText.withoutInsertedIsolation(text)
        if (written == text) item else {
            changed = true
            ClipData.Item(written)
        }
    }
    if (!changed) return this
    val description = source.description
    val mimeTypes = description.mimeTypeArray ?: arrayOf("text/plain")
    return ClipEntry(
        ClipData(description.label ?: "text", mimeTypes, items.first()).also { rebuilt ->
            items.drop(1).forEach(rebuilt::addItem)
        },
    )
}
