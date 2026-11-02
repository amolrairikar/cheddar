from email_parser.parsing.text import html_to_text


def test_cells_become_lines_and_scripts_dropped():
    html = "<head><title>t</title></head><style>x{}</style><table><tr><td>A  b</td><td>&amp;c</td></tr></table>"
    assert html_to_text(html) == "A b\n&c"
