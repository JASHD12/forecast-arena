"""Table of contents for long pages: ids, order, and nothing for short pages."""

from arena.site.toc import MIN_SECTIONS, add_toc

HEAD = '<main><header class="page-head"><h1>T</h1></header>'


def _page(*h2: str, extra: str = "") -> str:
    return HEAD + "".join(f"<section>{h}<p>x</p></section>" for h in h2) + extra + "</main>"


def test_adds_ids_and_a_list_after_the_head_in_order() -> None:
    out = add_toc(_page("<h2>One</h2>", "<h2>Two things</h2>", "<h2>Three</h2>", "<h2>Four</h2>"))
    assert '<h2 id="one">One</h2>' in out and '<h2 id="two-things">Two things</h2>' in out
    toc_at = out.index('class="toc"')
    assert out.index("</header>") < toc_at < out.index("<section>")
    labels = [x for x in ("One", "Two things", "Three", "Four") if f">{x}</a>" in out]
    assert labels == ["One", "Two things", "Three", "Four"]
    assert "4 sections" in out


def test_existing_ids_are_kept_and_duplicates_get_new_ones() -> None:
    out = add_toc(
        _page(
            '<h2 id="start">Start</h2>',
            "<h2>Data</h2>",
            "<h2>Data</h2>",
            "<h2><b>Bold</b> Title</h2>",
        )
    )
    assert 'id="start"' in out and 'href="#start"' in out
    assert 'id="data"' in out and 'id="data-2"' in out
    assert 'href="#bold-title"' in out and ">Bold Title</a>" in out


def test_short_pages_and_pages_without_a_head_are_untouched() -> None:
    short = _page(*[f"<h2>H{i}</h2>" for i in range(MIN_SECTIONS - 1)])
    assert add_toc(short) == short
    no_head = "<main>" + "".join(f"<h2>H{i}</h2>" for i in range(6)) + "</main>"
    assert add_toc(no_head) == no_head
