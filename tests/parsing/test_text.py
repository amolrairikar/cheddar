"""HTML conversion. Parser cases hold already-converted text, so markup is tested here.

When real markup breaks conversion, reduce it to a few made-up lines and add it.
"""

import pytest
from email_parser.parsing.text import MAX_CHARS, email_text, html_to_text


def test_cells_become_lines_and_scripts_dropped():
    html = "<head><title>t</title></head><style>x{}</style><table><tr><td>A  b</td><td>&amp;c</td></tr></table>"
    assert html_to_text(html) == "A b\n&c"


@pytest.mark.parametrize("html, text", [
    pytest.param(
        "<table><tr><td><table><tbody><tr><td>Merchant</td></tr></tbody></table></td>"
        "<td><table><tr><td>SHOP</td></tr></table></td></tr></table>",
        "Merchant\nSHOP", id="nested-tables"),
    pytest.param("<td><span>$1,2</span><b>34</b><span>.56</span><sup>*</sup></td>",
                 "$1,234.56*", id="inline-tags-do-not-split-values"),
    pytest.param("<td>\n    You made a\n\t$0.02 transaction\n</td>",
                 "You made a\n$0.02 transaction", id="source-newlines-split-lines"),
    pytest.param("<td>Account&nbsp;Ending:&#32;12345</td><td>AT&amp;T &#36;5.00</td>",
                 "Account Ending: 12345\nAT&T $5.00", id="entities"),
    pytest.param("<p>a<br>b<br/>c</p><div>d</div><ul><li>e</li></ul><h2>f</h2>g",
                 "a\nb\nc\nd\ne\nf\ng", id="block-tags"),
    pytest.param("<div>&zwnj;&nbsp;&zwnj;</div><div>x</div>",
                 "‌ ‌\nx", id="zero-width-padding-is-kept"),
    pytest.param("<head><style>a{}</style></head><body><!-- hidden --><script>var x = '<td>';</script>"
                 "<style>b{}</style>shown</body>", "shown", id="non-content-dropped"),
    pytest.param('<a href="https://example.com/t?token=abc"><img src="x.png" alt="logo">Review</a>',
                 "Review", id="attributes-dropped"),
    pytest.param("<table><tr><td>unclosed<td>cells", "unclosed\ncells", id="unclosed-tags"),
])
def test_html_to_text(html, text):
    assert html_to_text(html) == text


def test_output_is_truncated():
    assert len(html_to_text("a" * (MAX_CHARS + 1))) == MAX_CHARS


def test_html_preferred_over_plain(make_email):
    assert email_text(make_email("x", plain="plain", html="<p>html</p>")) == "html"


def test_plain_used_when_html_has_no_text(make_email):
    assert email_text(make_email("x", plain="plain", html="<img src='x'>")) == "plain"
