#!/usr/bin/env python3
"""Architectural guard for the style-only subset; optionally inspect a historical Git revision."""
import argparse
from pathlib import Path
import re
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--revision')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]

def read(path):
    if args.revision:
        result = subprocess.run(['git', 'show', f'{args.revision}:{path}'], cwd=root, text=True, capture_output=True)
        return result.stdout if result.returncode == 0 else ''
    file = root / path
    return file.read_text() if file.exists() else ''

ds = 'shared/designsystem/src/commonMain/kotlin/dev/hermeskotlin/designsystem/components/'
ui = 'shared/ui/src/'
checks = {
    'renderer uses shared preparation seam': 'val prepared = remember(text) { prepareMarkdown(text) }' in read(ds + 'MarkdownText.kt'),
    'only pre-existing math prepares source': 'internal fun prepareMarkdown(text: String): String = MathMarkup.prepare(text)' in read(ds + 'BidiText.kt'),
    'no insertion scanner': not re.search(r'fun isolate(?:InlineCode|LtrRuns)', read(ds + 'Bidi.kt')),
    'no guessed display provenance': not read(ds + 'BidiDisplay.kt'),
    'no rewriting clipboard wrapper': not read(ui + 'androidMain/kotlin/dev/hermeskotlin/ui/chat/BidiClipboard.android.kt'),
    'native selection uses ambient clipboard': 'LocalClipboard' not in read(ui + 'androidMain/kotlin/dev/hermeskotlin/ui/chat/CommentSelection.android.kt'),
    'anchors keep exact original blocks and offsets': 'SelectionAnchor(blocks, startBlock, start, endBlock, end)' in read(ui + 'commonMain/kotlin/dev/hermeskotlin/ui/chat/ReviewComments.kt'),
    'highlights compare original text': 'it.block == text' in read(ds + 'TextHighlight.kt') and 'BidiDisplay' not in read(ds + 'TextHighlight.kt'),
    'file preview shares renderer': 'MarkdownText(' in read(ui + 'commonMain/kotlin/dev/hermeskotlin/ui/chat/FileViewer.kt'),
    'journey shares renderer': 'MarkdownText(' in read(ui + 'commonMain/kotlin/dev/hermeskotlin/ui/journey/JourneySheet.kt'),
}
for name, ok in checks.items():
    print(('PASS' if ok else 'FAIL') + ' ' + name)
raise SystemExit(0 if all(checks.values()) else 1)
