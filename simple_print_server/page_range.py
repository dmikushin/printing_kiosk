"""Page-range parser for the kiosk's print form.

Accepts a CUPS-/system-print-dialog style spec and returns a sorted list of
unique 1-indexed page numbers within ``[1, total_pages]``.

Supported syntax (case-insensitive, whitespace-tolerant):

    ""           -> None  (means: print all pages, no filtering)
    "5"          -> [5]
    "1,3,5"      -> [1, 3, 5]
    "1-3"        -> [1, 2, 3]
    "1-end"      -> [1, 2, ..., total_pages]
    "7-"         -> [7, ..., total_pages]   (open end == "-end")
    "-5"         -> [1, ..., 5]             (open start == "1-")
    "end"        -> [total_pages]
    "1-3,5,9-end"-> combination

Raises :class:`PageRangeError` on any syntax or out-of-range issue. The error
message is intentionally short and user-facing — it's flashed back to the
kiosk user verbatim.
"""

class PageRangeError(ValueError):
    """Bad page-range spec from the user."""


def parse_page_range(spec, total_pages):
    """Parse ``spec`` against a document with ``total_pages`` pages.

    Returns ``None`` for an empty/whitespace spec (meaning "print all"),
    otherwise a sorted list of unique 1-indexed page numbers.
    """
    if spec is None:
        return None
    spec = spec.strip()
    if not spec:
        return None
    if not isinstance(total_pages, int) or total_pages < 1:
        raise PageRangeError("document has no pages")

    def resolve(token, default):
        token = token.strip().lower()
        if token == "":
            return default
        if token == "end":
            return total_pages
        if not token.isdigit():
            raise PageRangeError("not a page number: {!r}".format(token))
        n = int(token)
        if n < 1 or n > total_pages:
            raise PageRangeError(
                "page {} out of range (document has {} page{})".format(
                    n, total_pages, "" if total_pages == 1 else "s"))
        return n

    pages = set()
    for raw_entry in spec.split(","):
        entry = raw_entry.strip()
        if not entry:
            raise PageRangeError("empty range entry in {!r}".format(spec))

        if "-" in entry:
            # Range. Allow open start ("-5") and open end ("7-" or "7-end").
            lo_s, hi_s = entry.split("-", 1)
            if "-" in hi_s:
                raise PageRangeError("bad range: {!r}".format(entry))
            lo = resolve(lo_s, 1)
            hi = resolve(hi_s, total_pages)
            if lo > hi:
                raise PageRangeError(
                    "range start > end: {!r}".format(entry))
            pages.update(range(lo, hi + 1))
        else:
            pages.add(resolve(entry, None))

    return sorted(pages)


def format_page_list(pages):
    """Render a list of pages back as a compact range string for display.

    [1,2,3,5,7,8] -> "1-3, 5, 7-8"
    """
    if not pages:
        return ""
    pages = sorted(set(pages))
    out = []
    run_start = pages[0]
    prev = pages[0]
    for p in pages[1:]:
        if p == prev + 1:
            prev = p
            continue
        if run_start == prev:
            out.append(str(run_start))
        else:
            out.append("{}-{}".format(run_start, prev))
        run_start = p
        prev = p
    if run_start == prev:
        out.append(str(run_start))
    else:
        out.append("{}-{}".format(run_start, prev))
    return ", ".join(out)
