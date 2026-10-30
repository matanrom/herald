package dev.hermeskotlin.ui.chat

import android.content.ComponentName
import android.graphics.Canvas
import android.graphics.Bitmap
import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.text.BasicText
import androidx.compose.foundation.text.input.TextFieldState
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.semantics.SemanticsNode
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.text.TextRange
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.style.TextDirection
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import android.view.View
import android.view.ViewGroup
import com.composeunstyled.Text
import com.composeunstyled.theme.ColorScheme
import dev.hermeskotlin.designsystem.HermesTheme
import java.io.File
import org.junit.Rule
import org.junit.Test
import org.junit.rules.RuleChain
import org.junit.rules.TestRule
import org.junit.runner.Description
import org.junit.runner.RunWith
import org.junit.runners.model.Statement
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.Shadows
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.test.fail

/**
 * Rendered geometry of the composer's editable field, on the real [ComposerTextInput] the phone draws,
 * hosted by Robolectric with real Compose measurement and real pixels.
 *
 * The defect under test: a short Hebrew draft is a narrow text box, so unless the editor's viewport is
 * full-width *and* its content start is anchored to the right, the text sits at the left of a wide field
 * while its glyphs are ordered right-to-left. These tests assert the visible start edge in root space, not
 * a direction/style enum.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], qualifiers = "w411dp-h891dp-xxhdpi")
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class ComposerRtlLayoutTest {

    private val composeRule = createAndroidComposeRule<ComponentActivity>()

    // The library ships no manifest declaring an activity, so register one before createComposeRule
    // launches its host activity through Robolectric's package manager.
    @get:Rule
    val rules: TestRule = RuleChain.outerRule(RegisterHostActivity()).around(composeRule)

    private val state = TextFieldState()

    private fun show(
        text: String,
        ambient: LayoutDirection = LayoutDirection.Ltr,
    ) {
        state.edit {
            replace(0, length, text)
            selection = TextRange(length)
        }
        composeRule.setContent {
            HermesTheme(ColorScheme.Light) {
                CompositionLocalProvider(LocalLayoutDirection provides ambient) {
                    Box(Modifier.width(FIELD_WIDTH).background(Color.White)) {
                        ComposerTextInput(
                            state = state,
                            modifier = Modifier.fillMaxWidth().heightIn(min = 28.dp).padding(horizontal = INSET),
                            placeholder = { Text("Message Hermes", color = Color.Gray) },
                        )
                    }
                }
            }
        }
        composeRule.waitForIdle()
    }

    // ---- controls: the harness has to show English at the left and known RTL text at the right before any
    // composer assertion means anything.

    @Test
    fun englishDraftStartsAtTheLeftContentEdge() {
        show("I want to add this too")
        val field = measure("english-short")
        val left = field.bounds.left
        record("english-short", field.detail())
        assertTrue(
            field.inkLeft in (left - tolPx())..(left + tolPx()),
            "English draft ink starts at ${field.inkLeft}px, expected the left content edge $left px (${field.detail()})",
        )
    }

    @Test
    fun fullWidthRtlReferenceTextStartsAtTheRightContentEdge() {
        composeRule.setContent {
            HermesTheme(ColorScheme.Light) {
                CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Rtl) {
                    Box(Modifier.width(FIELD_WIDTH).background(Color.White)) {
                        BasicText(
                            "אבגד",
                            modifier = Modifier.fillMaxWidth(),
                            style = TextStyle(textDirection = TextDirection.Rtl),
                        )
                    }
                }
            }
        }
        composeRule.waitForIdle()
        val node = composeRule.onAllNodes(SemanticsMatcher.keyIsDefined(SemanticsActions.GetTextLayoutResult))
            .fetchSemanticsNodes().single()
        val bounds = node.boundsInRoot
        val ink = inkIn(bounds, "control-full-width-rtl") ?: fail("Robolectric rendered no ink for the RTL control")
        record("control-full-width-rtl", "bounds=${bounds.short()} ink=${ink.short()} lines=${lines(node)}")
        assertTrue(
            ink.right >= bounds.right - tolPx(),
            "full-width RTL control ink ends at ${ink.right}px, expected the container edge ${bounds.right}px",
        )
    }

    // ---- the reported case

    @Test
    fun oneHebrewLetterIsAnchoredAtTheRightContentEdge() = assertHebrewDraftIsRightAnchored("א", "one-letter")

    @Test
    fun twoHebrewLettersAreAnchoredAtTheRightContentEdge() = assertHebrewDraftIsRightAnchored("אי", "two-letters")

    @Test
    fun shortHebrewDraftIsAnchoredAtTheRightContentEdge() =
        assertHebrewDraftIsRightAnchored("אני רוצה גם להוסיף", "short-hebrew")

    @Test
    fun englishDraftStaysLeftInAnRtlAmbientContext() {
        show("I want to add this too", ambient = LayoutDirection.Rtl)
        val field = measure("english-in-rtl-ambient")
        val left = field.bounds.left
        record("english-in-rtl-ambient", field.detail())
        assertTrue(
            field.inkLeft in (left - tolPx())..(left + tolPx()),
            "English draft in an RTL ambient context starts at ${field.inkLeft}px, expected the left content " +
                "edge $left px (${field.detail()})",
        )
    }

    @Test
    fun wrappedHebrewLinesShareTheRightContentEdge() {
        show("אני רוצה גם להוסיף את הרשימה הארוכה הזאת לבית ולשלוח אותה למוטי בערב")
        val field = measure("wrapped-hebrew")
        val editor = editables().minByOrNull { it.boundsInRoot.width } ?: fail("no editable node found")
        val layout = layoutOf(editor) ?: fail("no text layout result for the editor")
        val right = field.bounds.right
        record("wrapped-hebrew-lines", "lines=${layout.lineCount} right=$right ${lines(editor)} ${field.detail()}")
        assertTrue(layout.lineCount >= 2, "fixture should wrap, got ${layout.lineCount} line(s)")
        assertTrue(
            field.inkRight in (right - tolPx())..(right + tolPx()),
            "wrapped Hebrew draft ink ends at ${field.inkRight}px, expected the right content edge $right px " +
                "(${field.detail()})",
        )
        // Lines that wrap must not jump: every line ends at the same right content edge.
        val boxRight = field.inkRight
        for (line in 0 until layout.lineCount) {
            val lineRight = boxRight - (layout.size.width - layout.getLineRight(line))
            assertTrue(
                lineRight >= right - tolPx(),
                "line $line ends at ${lineRight}px, expected the same right content edge $right px",
            )
        }
    }

    @Test
    fun theDraftKeepsItsExactBytes() {
        val draft = "שלום abc \u200F ١٢٣"
        show(draft)
        assertEquals(draft, state.text.toString(), "the field must not insert, strip or reorder characters")
        assertTrue(
            state.text.toString().none { it in '\u2066'..'\u2069' },
            "no isolate controls may be added to the draft",
        )
    }

    // ---- helpers ------------------------------------------------------------------------------------

    private fun assertHebrewDraftIsRightAnchored(text: String, label: String) {
        show(text)
        val field = measure(label)
        val right = field.bounds.right
        record(label, field.detail())
        assertTrue(
            field.inkRight in (right - tolPx())..(right + tolPx()),
            "Hebrew draft \"$text\" ink ends at ${field.inkRight}px, expected the right content edge $right px " +
                "(${field.detail()})",
        )
    }

    private class FieldGeometry(
        val bounds: Rect,
        val ink: Rect,
        val editor: Rect?,
        val layoutWidth: Int?,
        val lineSummary: String,
    ) {
        val inkLeft get() = ink.left
        val inkRight get() = ink.right
        fun detail() = "field=${bounds.short()} ink=${ink.short()} editor=${editor?.short()} " +
            "layoutWidth=$layoutWidth lines=$lineSummary"
    }

    private fun measure(label: String): FieldGeometry {
        val nodes = editables()
        val field = nodes.maxByOrNull { it.boundsInRoot.width } ?: fail("no editable node in the composer")
        val bounds = field.boundsInRoot
        val layout = layoutOf(field)
        val ink = inkIn(bounds, label) ?: fail("Robolectric rendered no ink for the draft in $label")
        val editor = nodes.filter { it.boundsInRoot.width < bounds.width - 1f }
            .maxByOrNull { it.boundsInRoot.width }
        return FieldGeometry(
            bounds = bounds,
            ink = ink,
            editor = editor?.boundsInRoot,
            layoutWidth = layout?.size?.width,
            lineSummary = editor?.let { lines(it) } ?: "none",
        )
    }

    private fun editables(): List<SemanticsNode> = composeRule.onAllNodes(Editable, useUnmergedTree = true)
        .fetchSemanticsNodes()

    private fun layoutOf(node: SemanticsNode): TextLayoutResult? {
        val results = mutableListOf<TextLayoutResult>()
        if (!node.config.contains(SemanticsActions.GetTextLayoutResult)) return null
        node.config[SemanticsActions.GetTextLayoutResult].action?.invoke(results)
        return results.firstOrNull()
    }

    private fun lines(node: SemanticsNode): String {
        val layout = layoutOf(node) ?: return "none"
        return (0 until layout.lineCount).joinToString("; ") { line ->
            "L$line[${layout.getLineLeft(line)}..${layout.getLineRight(line)}]"
        }
    }

    /**
     * The compose root drawn through a software canvas. captureToImage() copies the window, so it picks up the
     * activity's title bar and loses the root offset; drawing the compose view keeps root coordinates exact.
     */
    private fun renderRoot(): Bitmap? {
        val view = composeRule.activity.window.decorView.findComposeView() ?: return null
        if (view.width <= 0 || view.height <= 0) return null
        composeRule.waitForIdle()
        val bitmap = Bitmap.createBitmap(view.width, view.height, Bitmap.Config.ARGB_8888)
        view.draw(Canvas(bitmap))
        return bitmap
    }

    /** The darkest pixels drawn inside [bounds]: the rendered text, whatever node the decorator hides it in. */
    private fun inkIn(bounds: Rect, label: String): Rect? {
        val bitmap = renderRoot() ?: return null
        save(bitmap, label)
        val x0 = bounds.left.toInt().coerceIn(0, bitmap.width - 1)
        val x1 = bounds.right.toInt().coerceIn(0, bitmap.width - 1)
        val y0 = bounds.top.toInt().coerceIn(0, bitmap.height - 1)
        val y1 = bounds.bottom.toInt().coerceIn(0, bitmap.height - 1)
        // The field's dominant colour is its background; the drawn glyphs are whatever differs from it, so
        // this works for a light or a dark scheme without assuming either.
        val histogram = HashMap<Int, Int>()
        for (y in y0..y1) for (x in x0..x1) {
            val pixel = bitmap.getPixel(x, y)
            histogram[pixel] = (histogram[pixel] ?: 0) + 1
        }
        val background = histogram.maxByOrNull { it.value }?.key ?: return null
        fun differs(pixel: Int): Boolean =
            Math.abs(android.graphics.Color.red(pixel) - android.graphics.Color.red(background)) +
                Math.abs(android.graphics.Color.green(pixel) - android.graphics.Color.green(background)) +
                Math.abs(android.graphics.Color.blue(pixel) - android.graphics.Color.blue(background)) > 48

        var left = Int.MAX_VALUE
        var top = Int.MAX_VALUE
        var right = -1
        var bottom = -1
        for (y in y0..y1) {
            for (x in x0..x1) {
                val pixel = bitmap.getPixel(x, y)
                if (differs(pixel)) {
                    if (x < left) left = x
                    if (x > right) right = x
                    if (y < top) top = y
                    if (y > bottom) bottom = y
                }
            }
        }
        if (right < 0) return null
        return Rect(left.toFloat(), top.toFloat(), right + 1f, bottom + 1f)
    }

    private fun save(bitmap: Bitmap, label: String) {
        val dir = File("build/rtl-geometry").apply { mkdirs() }
        File(dir, "composer-$label.png").outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
    }

    private fun record(label: String, value: String) {
        println("[rtl-geometry] composer $label: $value")
        val dir = File("build/rtl-geometry").apply { mkdirs() }
        File(dir, "composer-$label.txt").writeText(value + "\n")
    }

    private fun tolPx() = with(composeRule.density) { TOLERANCE.toPx() }

    private class RegisterHostActivity : TestRule {
        override fun apply(base: Statement, description: Description): Statement = object : Statement() {
            override fun evaluate() {
                val app = RuntimeEnvironment.getApplication()
                Shadows.shadowOf(app.packageManager).addActivityIfNotPresent(
                    ComponentName(app.packageName, ComponentActivity::class.java.name),
                )
                base.evaluate()
            }
        }
    }

    private companion object {
        val FIELD_WIDTH = 360.dp
        val INSET = 12.dp

        /** Rasterisation and font advances differ by a pixel or two between hosts; the defect is ~200dp. */
        val TOLERANCE = 4.dp

        val Editable: SemanticsMatcher = SemanticsMatcher.keyIsDefined(SemanticsActions.SetText)
    }
}

/** A layout bound (or ink bound) as whole-pixel root coordinates, for the geometry record. */
private fun Rect.short() = "[${left.toInt()}..${right.toInt()}]x[${top.toInt()}..${bottom.toInt()}]"

/** The Compose root inside a view tree, without depending on Compose's internal class. */
private fun View.findComposeView(): View? {
    if (javaClass.name == "androidx.compose.ui.platform.AndroidComposeView") return this
    val group = this as? ViewGroup ?: return null
    for (index in 0 until group.childCount) {
        group.getChildAt(index).findComposeView()?.let { return it }
    }
    return null
}
