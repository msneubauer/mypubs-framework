#!/usr/bin/env python3
"""Normalize publication data and split it into journal, proceedings, and preprints."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path


UNICODE_REPLACEMENTS = {
    "\u2212": "-",
    "\u202f": " ",
    "\u00b1": r"\pm",
    "\u03b3": r"{\ensuremath{\gamma}}",
    "\u03c4": r"{\ensuremath{\tau}}",
    "\u03bc": r"{\ensuremath{\mu}}",
    "\u03bd": r"{\ensuremath{\nu}}",
    "\u03c8": r"{\ensuremath{\psi}}",
    "\u039b": r"{\ensuremath{\Lambda}}",
    "\u204e": r"\ast",
    "\u2217": r"\ast",
}


def load_config(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def replace_fragile_latex(value: str) -> str:
    text = value or ""
    for old, new in UNICODE_REPLACEMENTS.items():
        text = text.replace(old, new)
    text = text.replace(r"\varvec{W}", "W")
    text = text.replace(r"\varvec{pp}", "pp")
    text = text.replace(r"\varvec{\sqrt{s}}", r"\sqrt{s}")
    return text


def latex_escape_text(value: str) -> str:
    text = replace_fragile_latex(value)
    text = re.sub(r"[ \t]+", " ", text).strip()
    return text


def first_author_display(raw: str) -> str:
    raw = re.sub(r"\s+and\s+others\s*$", "", raw.strip(), flags=re.I)
    raw = raw.strip("{}")
    if "," in raw:
        last, rest = raw.split(",", 1)
        parts = [p for p in rest.strip().split() if p]
    else:
        bits = raw.split()
        last = bits[-1] if bits else raw
        parts = bits[:-1]
    initials = []
    for part in parts:
        if re.fullmatch(r"[A-Za-z]\.?", part):
            initials.append(part[0] + ".")
        else:
            initials.append(part[0] + ".")
    return " ".join(initials + [last.strip()]).strip()


def collab_label(collab: str | None) -> str:
    if not collab:
        return ""
    noun = "Collaborations" if "," in collab or " and " in collab else "Collaboration"
    return f" [{collab} {noun}]"


def normalize_author(author: str, collab: str | None) -> str:
    if " and others" in author:
        return f"{{{first_author_display(author)} {{\\em et al.}}{collab_label(collab)}}}"
    return latex_escape_text(author)


def split_bib_entries(text: str) -> list[str]:
    return [m.group(0).strip() for m in re.finditer(r"(?ms)@\w+\s*[({].*?(?=\n@\w+\s*[({]|\Z)", text)]


def bib_type(entry: str) -> str:
    match = re.search(r"@(\w+)\s*[({]", entry)
    return match.group(1).lower() if match else ""


def bib_key(entry: str) -> str:
    match = re.search(r"@\w+\s*[({]\s*([^,]+)", entry)
    return match.group(1).strip() if match else ""


def bib_field(entry: str, name: str) -> str | None:
    match = re.search(
        r"(?im)^\s*" + re.escape(name) + r"\s*=\s*(?:\"([^\"]*)\"|\{([^}]*)\})\s*,?\s*$",
        entry,
    )
    if not match:
        return None
    return (match.group(1) if match.group(1) is not None else match.group(2)).strip()


def set_or_add_field(entry: str, name: str, value: str) -> str:
    line = f'    {name} = "{value}",'
    pattern = re.compile(r"(?im)^\s*" + re.escape(name) + r"\s*=\s*(?:\"[^\"]*\"|\{[^}]*\})\s*,?\s*$")
    if pattern.search(entry):
        return pattern.sub(lambda _: line, entry)
    insert_before = entry.rfind("\n}")
    if insert_before == -1:
        insert_before = entry.rfind("}")
    if insert_before == -1:
        return entry.rstrip() + "\n" + line
    prefix = entry[:insert_before].rstrip()
    suffix = entry[insert_before:]
    if prefix and not prefix.endswith((",", "{")):
        prefix += ","
    return prefix + "\n" + line + "\n" + suffix.lstrip()


def normalize_bib_entry(entry: str) -> str:
    collab = bib_field(entry, "collaboration")
    author = bib_field(entry, "author")
    if author:
        entry = set_or_add_field(entry, "author", normalize_author(author, collab))
    for field in ("title", "journal", "booktitle", "note"):
        value = bib_field(entry, field)
        if value is not None:
            entry = set_or_add_field(entry, field, "{" + latex_escape_text(value).strip("{}") + "}")
    eprint = bib_field(entry, "eprint")
    archive = bib_field(entry, "archivePrefix")
    primary = bib_field(entry, "primaryClass")
    journal = bib_field(entry, "journal")
    is_preprint = archive == "arXiv" and bool(eprint) and not journal
    if is_preprint:
        note = f"{{arXiv:{eprint}" + (f" [{primary}]" if primary else "") + "}"
        entry = set_or_add_field(entry, "note", note)
        entry = set_or_add_field(entry, "keywords", "{preprint}")
    return replace_fragile_latex(entry)


def records_from_raw_json(raw_dir: Path) -> list[dict]:
    records: list[dict] = []
    for path in sorted(raw_dir.glob("inspire-*.json"), reverse=True):
        data = json.loads(path.read_text(encoding="utf-8"))
        records.extend(data.get("hits", {}).get("hits", []))
    return records


def first(values: list[dict], key: str) -> str:
    if not values:
        return ""
    return str(values[0].get(key, "") or "")


def entry_from_record(record: dict) -> str:
    meta = record.get("metadata", {})
    key = first(meta.get("texkeys", []), "value") if isinstance(meta.get("texkeys"), list) else ""
    if not key:
        key = meta.get("texkeys", [""])[0] if meta.get("texkeys") else f"inspire-{record.get('id')}"
    title = first(meta.get("titles", []), "title")
    authors = meta.get("authors", [])
    raw_author = " and ".join(a.get("full_name", "") for a in authors if a.get("full_name"))
    collaborations = meta.get("collaborations", [])
    collab = ", ".join(c.get("value", "") for c in collaborations if c.get("value")) or None
    if len(authors) > 25 and authors:
        raw_author = authors[0].get("full_name", "") + " and others"
    author = normalize_author(raw_author, collab)
    arxiv = (meta.get("arxiv_eprints") or [{}])[0]
    pub = (meta.get("publication_info") or [{}])[0]
    doi = first(meta.get("dois", []), "value")
    report = ", ".join(r.get("value", "") for r in meta.get("report_numbers", []) if r.get("value"))
    year = str(pub.get("year") or meta.get("earliest_date", "")[:4] or meta.get("preprint_date", "")[:4])
    fields = OrderedDict()
    fields["author"] = author
    if collab:
        fields["collaboration"] = collab
    fields["title"] = "{" + latex_escape_text(title).strip("{}") + "}"
    if arxiv.get("value"):
        fields["eprint"] = arxiv["value"]
        fields["archivePrefix"] = "arXiv"
        if arxiv.get("categories"):
            fields["primaryClass"] = arxiv["categories"][0]
    if report:
        fields["reportNumber"] = report
    if doi:
        fields["doi"] = doi
    if pub.get("journal_title"):
        fields["journal"] = pub["journal_title"]
    if pub.get("journal_volume"):
        fields["volume"] = str(pub["journal_volume"])
    if pub.get("artid") or pub.get("page_start"):
        fields["pages"] = str(pub.get("artid") or pub.get("page_start"))
    if year:
        fields["year"] = year
    lines = [f"@article{{{key},"]
    for name, value in fields.items():
        lines.append(f'    {name} = "{latex_escape_text(str(value))}",')
    lines[-1] = lines[-1].rstrip(",")
    lines.append("}")
    return normalize_bib_entry("\n".join(lines))


def is_preprint(entry: str) -> bool:
    eprint = bib_field(entry, "eprint")
    archive = bib_field(entry, "archivePrefix")
    journal = bib_field(entry, "journal")
    return archive == "arXiv" and bool(eprint) and not journal


def is_proceeding(entry: str) -> bool:
    return bib_type(entry) in {"inproceedings", "conference", "proceedings"} or bool(bib_field(entry, "booktitle"))


def split_entry_groups(entries: list[str]) -> tuple[list[str], list[str], list[str]]:
    unique: OrderedDict[str, str] = OrderedDict()
    for entry in entries:
        key = bib_key(entry)
        if key and key not in unique:
            unique[key] = normalize_bib_entry(entry)

    journal: list[str] = []
    proceedings: list[str] = []
    preprints: list[str] = []
    for entry in unique.values():
        if is_preprint(entry):
            preprints.append(entry)
        elif is_proceeding(entry):
            proceedings.append(entry)
        else:
            journal.append(entry)
    return journal, proceedings, preprints


def write_split(entries: list[str], journal_path: Path, proceedings_path: Path, preprints_path: Path) -> None:
    journal, proceedings, preprints = split_entry_groups(entries)
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    journal_path.write_text("\n\n".join(journal) + ("\n" if journal else ""), encoding="utf-8")
    proceedings_path.write_text("\n\n".join(proceedings) + ("\n" if proceedings else ""), encoding="utf-8")
    preprints_path.write_text("\n\n".join(preprints) + ("\n" if preprints else ""), encoding="utf-8")
    print(f"journal entries: {len(journal)} -> {journal_path}")
    print(f"proceedings entries: {len(proceedings)} -> {proceedings_path}")
    print(f"preprint entries: {len(preprints)} -> {preprints_path}")


def validate(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    entries = split_bib_entries(text)
    keys = [bib_key(entry) for entry in entries]
    dupes = sorted(k for k in set(keys) if keys.count(k) > 1)
    non_ascii = sum(1 for ch in text if ord(ch) > 127)
    print(f"{path}: entries={len(entries)} unique={len(set(keys))} non_ascii={non_ascii}")
    if dupes:
        raise SystemExit(f"duplicate keys in {path}: {dupes[:10]}")
    if non_ascii:
        raise SystemExit(f"non-ASCII characters remain in {path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--from-bib", nargs="*", help="normalize existing BibTeX files instead of raw JSON")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    root = Path.cwd()
    cfg = load_config(root / args.config)
    journal_path = root / cfg["output_dir"] / cfg["journal_bib"]
    proceedings_path = root / cfg["output_dir"] / cfg["proceedings_bib"]
    preprints_path = root / cfg["output_dir"] / cfg["preprints_bib"]

    if args.validate_only:
        validate(journal_path)
        validate(proceedings_path)
        validate(preprints_path)
        return 0

    if args.from_bib:
        entries: list[str] = []
        for filename in args.from_bib:
            entries.extend(split_bib_entries(Path(filename).read_text(encoding="utf-8")))
    else:
        records = records_from_raw_json(root / cfg["raw_dir"])
        if not records:
            raise SystemExit("No raw JSON records found. Run make fetch or pass --from-bib.")
        entries = [entry_from_record(record) for record in records]

    write_split(entries, journal_path, proceedings_path, preprints_path)
    validate(journal_path)
    validate(proceedings_path)
    validate(preprints_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
