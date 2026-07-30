"""
MN — Python-like markup language.
Indentation-based, no closing tags, no angle brackets.
"""

import re


class Element:
    __slots__ = ("tag", "text", "attrs", "children")

    def __init__(self, tag, text="", attrs=None, children=None):
        self.tag = tag
        self.text = text.strip()
        self.attrs = attrs or {}
        self.children = children or []

    def __repr__(self):
        return f"<{self.tag} {self.attrs!r}>"


def parse(source):
    lines = source.split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        return []
    tree, _ = _block(lines, 0, _indent(lines[0]))
    return tree


def _indent(line):
    return len(line) - len(line.lstrip())


def _block(lines, i, target):
    result = []
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        ind = _indent(line)
        if ind < target:
            break
        if ind > target:
            break
        elem = _parse_line(stripped)
        if i + 1 < len(lines) and _indent(lines[i + 1]) > ind:
            kids, i = _block(lines, i + 1, _indent(lines[i + 1]))
            elem.children = kids
        else:
            i += 1
        result.append(elem)
    return result, i


def _parse_line(s):
    # list item
    if s.startswith("- "):
        return Element("li", s[2:])

    # numbered list item
    m = re.match(r"^\d+\.\s+(.*)", s)
    if m:
        return Element("li", m.group(1))

    # tag(args): content
    m = re.match(r'^(\w+)\(([^)]*)\)\s*:\s*(.*)', s)
    if m:
        tag, args, text = m.groups()
        return Element(tag, text, _attrs(args))

    # tag(args) — no content
    m = re.match(r'^(\w+)\(([^)]*)\)\s*$', s)
    if m:
        tag, args = m.groups()
        return Element(tag, "", _attrs(args))

    # tag: content
    m = re.match(r'^(\w+)\s*:\s*(.*)', s)
    if m:
        return Element(m.group(1), m.group(2))

    # plain text
    return Element("p", s)


def _attrs(raw):
    a = {}
    for p in raw.split(","):
        p = p.strip().strip("\"'")
        if not p:
            continue
        if "=" in p:
            k, v = p.split("=", 1)
            a[k.strip()] = v.strip().strip("\"'")
        else:
            a[f"_{len(a)}"] = p
    return a


# ── helpers ───────────────────────────────────────────────────────

def to_html(elements):
    """Convert MN elements to HTML string."""
    out = []
    for el in elements:
        out.append(_el_to_html(el))
    return "\n".join(out)


def _el_to_html(el):
    t = el.tag.lower()
    attrs_str = " ".join(f'{k}="{v}"' for k, v in el.attrs.items())
    if attrs_str:
        attrs_str = " " + attrs_str

    # void elements
    if t in ("hr", "br", "img", "input"):
        if t == "hr":
            return "<hr>"
        if t == "br":
            return "<br>"
        if t == "img":
            src = el.attrs.get("_0", el.attrs.get("src", ""))
            alt = el.attrs.get("alt", el.text)
            return f'<img src="{src}" alt="{alt}">'
        if t == "input":
            itype = el.attrs.get("type", "text")
            name = el.attrs.get("name", "")
            placeholder = el.attrs.get("placeholder", el.text)
            return f'<input type="{itype}" name="{name}" placeholder="{placeholder}">'

    # tags with children
    children_html = "".join(_el_to_html(ch) for ch in el.children)

    if t == "title":
        return f"<title>{el.text}</title>"
    if t in ("h1", "h2", "h3", "h4", "h5", "h6"):
        return f"<{t}{attrs_str}>{el.text}{children_html}</{t}>"
    if t == "p":
        return f"<p{attrs_str}>{el.text}{children_html}</p>"
    if t == "ul":
        items = "".join(f"<li>{ch.text}</li>" for ch in el.children if ch.tag == "li")
        return f"<ul>{items}</ul>"
    if t == "ol":
        items = "".join(f"<li>{ch.text}</li>" for ch in el.children if ch.tag == "li")
        return f"<ol>{items}</ol>"
    if t == "li":
        return f"<li>{el.text}{children_html}</li>"
    if t == "link":
        url = el.attrs.get("_0", el.attrs.get("href", ""))
        return f'<a href="{url}">{el.text}</a>'
    if t == "bold" or t == "b":
        return f"<b>{el.text}</b>"
    if t == "italic" or t == "i":
        return f"<i>{el.text}</i>"
    if t == "code":
        return f"<code>{el.text}</code>"
    if t == "pre":
        return f"<pre>{el.text}{children_html}</pre>"
    if t == "style":
        return f"<style>{el.text}{children_html}</style>"
    if t == "script":
        return f"<script>{el.text}{children_html}</script>"
    if t == "video":
        src = el.attrs.get("_0", el.attrs.get("src", ""))
        return f'<video src="{src}" controls>{el.text}</video>'
    if t == "audio":
        src = el.attrs.get("_0", el.attrs.get("src", ""))
        return f'<audio src="{src}" controls>{el.text}</audio>'
    if t == "image":
        src = el.attrs.get("_0", el.text)
        return f'<img src="{src}">'
    if t == "table":
        rows = ""
        for ch in el.children:
            if ch.tag == "row":
                cells = "".join(f"<td>{c.text}</td>" for c in ch.children if c.tag == "cell")
                rows += f"<tr>{cells}</tr>"
        return f"<table>{rows}</table>"
    if t == "form":
        action = el.attrs.get("_0", el.attrs.get("action", ""))
        return f'<form action="{action}">{children_html}</form>'
    if t == "button":
        return f"<button>{el.text}</button>"

    # generic
    return f"<{t}{attrs_str}>{el.text}{children_html}</{t}>"
