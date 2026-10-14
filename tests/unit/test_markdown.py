from triagedash.markdown import render


def test_paragraphs_and_line_breaks():
    assert render("one\ntwo\n\nthree") == "<p>one<br>two</p><p>three</p>"


def test_lists_and_rule():
    assert render("1. Open it.\n2. Click.") == "<ol><li>Open it.</li><li>Click.</li></ol>"
    assert render("- a\n- b") == "<ul><li>a</li><li>b</li></ul>"
    assert render("x\n\n---\n\ny") == "<p>x</p><hr><p>y</p>"


def test_inline_marks():
    assert (
        render("**Analysis** in `Foo.cpp`")
        == "<p><strong>Analysis</strong> in <code>Foo.cpp</code></p>"
    )
    assert (
        render("[file](https://searchfox.org/a?b=1)")
        == '<p><a href="https://searchfox.org/a?b=1">file</a></p>'
    )


def test_html_is_escaped_and_only_https_links_render():
    assert render("<script>x</script>") == "<p>&lt;script&gt;x&lt;/script&gt;</p>"
    assert render("[x](javascript:alert(1))") == "<p>[x](javascript:alert(1))</p>"
    assert render('[x](https://a" onerror="b)') == "<p>[x](https://a&quot; onerror=&quot;b)</p>"
