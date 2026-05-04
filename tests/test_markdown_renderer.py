from __future__ import annotations

import unittest

from anki_ai.markdown_renderer import render_markdown_to_anki_html


class MarkdownRendererTest(unittest.TestCase):
    def test_renders_common_markdown(self) -> None:
        html = render_markdown_to_anki_html(
            "**Important**\n\n- one\n- two\n\n```python\nprint('x')\n```"
        )

        self.assertIn("<strong>Important</strong>", html)
        self.assertIn("<ul>", html)
        self.assertIn("<li>one</li>", html)
        self.assertIn("<pre><code", html)
        self.assertIn("print('x')", html)

    def test_normalizes_dollar_math_to_anki_mathjax_delimiters(self) -> None:
        html = render_markdown_to_anki_html(
            "Euler: $E=mc^2$\n\n$$\n\\int_a^b f(x)\\,dx\n$$"
        )

        self.assertIn("\\(E=mc^2\\)", html)
        self.assertIn("\\[\\int_a^b f(x)\\,dx\\]", html)
        self.assertNotIn("<eq>", html)
        self.assertNotIn("<eqn>", html)

    def test_preserves_bracket_math_as_anki_mathjax_delimiters(self) -> None:
        html = render_markdown_to_anki_html(
            "Inline \\(a+b\\), then display:\n\n\\[\na^2+b^2=c^2\n\\]"
        )

        self.assertIn("\\(a+b\\)", html)
        self.assertIn("\\[a^2+b^2=c^2\\]", html)

    def test_does_not_parse_math_inside_code(self) -> None:
        html = render_markdown_to_anki_html("Use `$x$` literally.")

        self.assertIn("<code>$x$</code>", html)
        self.assertNotIn("\\(x\\)", html)

    def test_sanitizes_unsafe_html(self) -> None:
        html = render_markdown_to_anki_html(
            '<script>alert("x")</script><a href="javascript:alert(1)" onclick="x()">bad</a>'
        )

        self.assertNotIn("<script", html)
        self.assertNotIn("javascript:", html)
        self.assertNotIn("onclick", html)
        self.assertIn(">bad</a>", html)


if __name__ == "__main__":
    unittest.main()
