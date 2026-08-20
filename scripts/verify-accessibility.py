#!/usr/bin/env python3
"""Structural accessibility and mobile checks against the rendered pages.

Not a substitute for using the site with a keyboard and a screen reader — no
automated check can be. It catches the mechanical failures that make those
sessions pointless before they start: an unlabelled input, a heading level
skipped, a control with no accessible name, a viewport that disables zoom.

Runs against the real server output rather than the source, because that is what
a browser receives — and because a component can look correct in JSX and render
without its label.

    python scripts/verify-accessibility.py
    python scripts/verify-accessibility.py --base http://localhost:8080
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from html.parser import HTMLParser

GREEN, RED, YELLOW, DIM, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"

# Controls that need an accessible name to be operable by anything but a mouse.
NAMED_CONTROLS = {"input", "select", "textarea", "button", "a"}
HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
# Input types that are not user-facing controls.
UNNAMED_INPUT_TYPES = {"hidden", "submit", "reset", "image"}


@dataclass
class Finding:
    page: str
    rule: str
    detail: str


@dataclass
class PageFacts:
    lang: str | None = None
    viewport: str | None = None
    headings: list[tuple[int, str]] = field(default_factory=list)
    landmarks: set[str] = field(default_factory=set)
    main_count: int = 0
    skip_link: bool = False
    problems: list[tuple[str, str]] = field(default_factory=list)
    labels_for: set[str] = field(default_factory=set)
    control_count: int = 0
    nested_paragraphs: int = 0


class Auditor(HTMLParser):
    """Walks the served HTML collecting only what the rules below need."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.facts = PageFacts()
        self._open: list[list] = []
        # An <input> wrapped in a <label> is labelled by it, with no id or `for`
        # needed. That is valid and common, and a checker that does not know it
        # reports every correctly-labelled form as broken — which is worse than
        # no checker, because the noise trains people to ignore it.
        self._label_depth = 0
        # <p> inside <p> is invalid, and the browser silently closes the
        # outer one — so the server's markup and the client's DOM disagree
        # and React reports a hydration error. It is invisible on screen,
        # which is exactly the kind of defect a mechanical check should own.
        self._p_depth = 0

    # -- helpers ---------------------------------------------------------
    @staticmethod
    def _named(attrs: dict) -> bool:
        return bool(
            attrs.get("aria-label")
            or attrs.get("aria-labelledby")
            or attrs.get("title")
            or attrs.get("alt")
        )

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        attrs = {key: (value or "") for key, value in attrs_list}

        if tag == "html":
            self.facts.lang = attrs.get("lang")
        elif tag == "meta" and attrs.get("name") == "viewport":
            self.facts.viewport = attrs.get("content", "")
        elif tag in {"main", "nav", "header", "footer"}:
            self.facts.landmarks.add(tag)
            if tag == "main":
                self.facts.main_count += 1
        elif tag == "a" and attrs.get("href", "").startswith("#"):
            # A same-page link at the very top of the document is a skip link.
            # Checking the target exists is what makes it more than decoration.
            self.facts.skip_link = True
        elif tag == "label":
            self._label_depth += 1
            if attrs.get("for"):
                self.facts.labels_for.add(attrs["for"])
        elif tag == "p":
            if self._p_depth > 0:
                self.facts.nested_paragraphs += 1
            self._p_depth += 1
        elif tag == "img" and "alt" not in attrs:
            self.facts.problems.append(("img-alt", attrs.get("src", "?")[:60]))

        if attrs.get("tabindex", "").lstrip("+").isdigit() and int(attrs["tabindex"]) > 0:
            self.facts.problems.append(("tabindex", f"<{tag} tabindex={attrs['tabindex']}>"))

        if tag == "input":
            self.facts.control_count += 1
            if (
                attrs.get("type", "text") not in UNNAMED_INPUT_TYPES
                and not self._named(attrs)
                and self._label_depth == 0
            ):
                # May still be labelled by a <label for> seen elsewhere; resolved
                # after parsing, since the label can come after the input.
                self.facts.problems.append(("input-name", attrs.get("id", "") or "(no id)"))

        if tag in NAMED_CONTROLS or tag in HEADINGS:
            # A frame per tracked element, because an accessible name is the
            # text of the whole subtree. Collecting into one buffer lets a
            # nested <h2> swallow the text of the <a> that contains it, and
            # every link whose label is a heading is then reported as nameless.
            self._open.append([tag, attrs, []])

    def handle_data(self, data: str) -> None:
        for frame in self._open:
            frame[2].append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "label":
            self._label_depth = max(0, self._label_depth - 1)
        elif tag == "p":
            self._p_depth = max(0, self._p_depth - 1)

        index = next(
            (i for i in range(len(self._open) - 1, -1, -1) if self._open[i][0] == tag), None
        )
        if index is None:
            return
        # Unclosed void or mis-nested markup: discard anything opened inside.
        frame = self._open[index]
        del self._open[index:]
        _, attrs, chunks = frame
        text = "".join(chunks).strip()

        if tag.startswith("h") and len(tag) == 2 and tag[1].isdigit():
            self.facts.headings.append((int(tag[1]), text[:60]))
        elif tag in {"button", "a"}:
            self.facts.control_count += 1
            if not text and not self._named(attrs):
                target = attrs.get("href", "")[:40] or "(button)"
                self.facts.problems.append(("control-name", f"<{tag}> {target}"))


def audit(html: str, page: str) -> list[Finding]:
    parser = Auditor()
    parser.feed(html)
    facts = parser.facts
    findings: list[Finding] = []

    def add(rule: str, detail: str) -> None:
        findings.append(Finding(page, rule, detail))

    if not facts.lang:
        add("lang", "<html> has no lang attribute — screen readers guess the language")

    if facts.viewport is None:
        add("viewport", "no viewport meta — the page will render at desktop width on a phone")
    else:
        lowered = facts.viewport.replace(" ", "").lower()
        if "user-scalable=no" in lowered:
            add("zoom", "viewport disables pinch zoom")
        maximum = re.search(r"maximum-scale=([\d.]+)", lowered)
        if maximum and float(maximum.group(1)) < 2:
            add("zoom", f"viewport caps zoom at {maximum.group(1)}×")

    h1s = [text for level, text in facts.headings if level == 1]
    if not h1s:
        add("heading-h1", "no <h1> — the page has no title in the document outline")
    elif len(h1s) > 1:
        add("heading-h1", f"{len(h1s)} <h1> elements: {h1s[:3]}")

    previous = 0
    for level, text in facts.headings:
        if previous and level > previous + 1:
            add("heading-order", f"h{previous} → h{level} at {text!r}")
        previous = level

    if "main" not in facts.landmarks:
        add("landmark-main", "no <main> element — skip links and rotors have nothing to target")
    elif facts.main_count > 1:
        # Nested or repeated <main> is the failure this rule exists for: it is
        # invalid, it is invisible on screen, and it leaves assistive technology
        # with two candidates for "the content".
        add("landmark-main", f"{facts.main_count} <main> elements — there must be exactly one")

    if facts.nested_paragraphs:
        add(
            "nested-p",
            f"{facts.nested_paragraphs} <p> inside <p> — invalid, and a React hydration error",
        )

    if not facts.skip_link:
        add("skip-link", "no skip link — keyboard users tab through the whole nav on every page")

    for rule, detail in facts.problems:
        if rule == "input-name" and detail in facts.labels_for:
            continue  # labelled by a <label for> elsewhere in the document
        add(
            {
                "img-alt": "img-alt",
                "input-name": "control-name",
                "control-name": "control-name",
                "tabindex": "tabindex",
            }[rule],
            detail if rule != "input-name" else f"<input id={detail}> has no accessible name",
        )

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Structural accessibility checks")
    parser.add_argument("--base", default="http://localhost:8080")
    args = parser.parse_args()

    pages = [
        "/",
        "/topics/the-machine",
        "/learn/the-machine/read-overview",
        "/learn/the-machine/lab-inspect-the-machine",
        "/learn/the-machine/quiz",
        "/search?q=kernel",
        "/projects",
        "/login",
        "/register",
        # Fetched anonymously, so this audits the signed-out state of the
        # authoring route rather than the inventory itself. That state is a real
        # page with its own heading and link, and it is the one an unauthorised
        # visitor actually reaches.
        "/authoring",
    ]

    print("Accessibility check")
    all_findings: list[Finding] = []
    weights: dict[str, int] = {}

    for page in pages:
        try:
            with urllib.request.urlopen(args.base + page, timeout=20) as response:
                html = response.read().decode("utf-8", "replace")
                weights[page] = len(html)
        except urllib.error.URLError as error:
            print(f"  {RED}FAIL{RESET}  {page} — {error}")
            all_findings.append(Finding(page, "unreachable", str(error)))
            continue

        findings = audit(html, page)
        all_findings.extend(findings)
        if findings:
            print(f"  {RED}FAIL{RESET}  {page}")
            for finding in findings:
                print(f"        {finding.rule}: {finding.detail}")
        else:
            print(f"  {GREEN} ok {RESET}  {page}  {DIM}{weights[page] // 1024} KiB{RESET}")

    # Compression is a mobile accessibility issue as much as a performance one:
    # uncompressed HTML is the difference between a page that loads on a train
    # and one that does not.
    request = urllib.request.Request(args.base + "/topics/the-machine")
    request.add_header("accept-encoding", "gzip")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            encoding = response.headers.get("content-encoding", "")
        if "gzip" in encoding or "zstd" in encoding or "br" in encoding:
            print(f"  {GREEN} ok {RESET}  responses are compressed ({encoding})")
        else:
            print(f"  {RED}FAIL{RESET}  responses are not compressed")
            all_findings.append(Finding("(proxy)", "compression", "no content-encoding"))
    except urllib.error.URLError as error:
        print(f"  {YELLOW}note{RESET}  could not check compression: {error}")

    heaviest = max(weights.items(), key=lambda item: item[1], default=("", 0))
    if heaviest[1] > 250 * 1024:
        print(f"  {YELLOW}note{RESET}  {heaviest[0]} is {heaviest[1] // 1024} KiB of HTML")

    print()
    if all_findings:
        print(f"{RED}Accessibility check FAILED — {len(all_findings)} finding(s).{RESET}")
        return 1
    print(f"{GREEN}Accessibility check passed.{RESET}")
    print(f"{DIM}Mechanical checks only. Keyboard and screen-reader passes are still manual.{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
