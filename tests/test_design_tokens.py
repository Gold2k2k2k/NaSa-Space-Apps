"""Independent checks for shipped design artifacts and declared contrast pairs."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def luminance(hex_color):
    channels = [int(hex_color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4 for value in channels]
    return sum(weight * channel for weight, channel in zip((.2126, .7152, .0722), linear))


class TestDesignTokens(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tokens = json.loads((ROOT / "design-tokens.json").read_text(encoding="utf-8"))

    def test_css_and_standalone_preview_use_the_declared_palette(self):
        stylesheet = (ROOT / "app/web/static/tokens.css").read_text(encoding="utf-8")
        properties = dict(re.findall(r"--([\w-]+):\s*([^;]+);", stylesheet))
        for name, value in self.tokens["color"].items():
            self.assertEqual(properties["color-" + name], value)
        for ramp, stops in self.tokens["ramp"].items():
            for index, value in enumerate(stops):
                self.assertEqual(properties[f"ramp-{ramp}-{index}"], value)
        preview = (ROOT / "design-preview.html").read_text(encoding="utf-8")
        embedded = re.search(r'<script type="application/json" id="design-tokens">(.*?)</script>', preview, re.S)
        self.assertIsNotNone(embedded)
        self.assertEqual(json.loads(embedded.group(1)), self.tokens)
        self.assertFalse(re.search(r'<(?:script|link|img)[^>]+(?:src|href)=["\']https?://', preview))

    def test_declared_text_and_control_contrast_meet_their_thresholds(self):
        colors = self.tokens["color"]
        pairs = [("text", "surface", 4.5), ("muted", "surface", 4.5), ("subtle", "raised", 4.5),
                 ("accent-ink", "accent", 4.5), ("critical", "critical-bg", 4.5),
                 ("elevated", "elevated-bg", 4.5), ("nominal", "nominal-bg", 4.5),
                 ("unverified", "unverified-bg", 4.5), ("line-strong", "well", 3)]
        for foreground, background, minimum in pairs:
            with self.subTest(pair=(foreground, background)):
                dark, light = sorted((luminance(colors[foreground]), luminance(colors[background])))
                self.assertGreaterEqual((light + .05) / (dark + .05), minimum)

    def test_css_breakpoints_and_touch_size_match_tokens(self):
        stylesheet = (ROOT / "app/web/static/app.css").read_text(encoding="utf-8")
        # CSS custom properties cannot be used in ordinary media-query conditions.
        for name in ("mobile", "tablet"):
            self.assertIn("@media(max-width:" + self.tokens["breakpoint"][name] + ")", stylesheet)
        self.assertEqual(self.tokens["layout"]["target"], "44px")
        self.assertIn("min-height:var(--layout-target)", stylesheet)


if __name__ == "__main__":
    unittest.main()
