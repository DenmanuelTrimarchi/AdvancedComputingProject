#!/usr/bin/env python3
"""Audit comment style, source attribution and JSON validity across the repository.

Enforces the project's comment conventions without rewriting anything:

* only ``#`` comments in formats that support them;
* concise academic British English in comments;
* attribution headers that carry all four required fields;
* no invented or vague provenance statements;
* no private path or personal email address inside a comment;
* every tracked JSON file still parses.

Comment extraction is deliberately syntax-aware rather than a naive text
scan: Python is tokenised, and shell/YAML/TOML lines have their quoted
strings removed first. That is what keeps URLs, glob patterns and floor
division from being reported as violations.

Exit status is non-zero only when a real violation is found.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from face_verification.privacy import default_forbidden_path_substrings  # noqa: E402

HASH_COMMENT_SUFFIXES = {".py", ".sh", ".yml", ".yaml", ".toml"}
HASH_COMMENT_NAMES = {".env.example", ".gitignore"}

# Generated or binary outputs are never hand-commented, so they are not audited.
EXCLUDED_DIRECTORY_PARTS = {"results", ".git", "__pycache__", ".venv", "htmlcov"}

# British spellings expected in comment prose. Identifiers, API names and
# filenames are never rewritten, so only comment text is inspected.
AMERICAN_SPELLINGS: Dict[str, str] = {
    "analyze": "analyse",
    "authorization": "authorisation",
    "authorize": "authorise",
    "behavior": "behaviour",
    "behaviors": "behaviours",
    "canceled": "cancelled",
    "catalog": "catalogue",
    "categorize": "categorise",
    "centered": "centred",
    "customization": "customisation",
    "customize": "customise",
    "defense": "defence",
    "dialog": "dialogue",
    "favor": "favour",
    "generalize": "generalise",
    "initialization": "initialisation",
    "initialize": "initialise",
    "initialized": "initialised",
    "labeled": "labelled",
    "labeling": "labelling",
    "maximize": "maximise",
    "minimize": "minimise",
    "modeled": "modelled",
    "modeling": "modelling",
    "normalization": "normalisation",
    "normalize": "normalise",
    "normalized": "normalised",
    "offense": "offence",
    "optimization": "optimisation",
    "optimize": "optimise",
    "optimized": "optimised",
    "organize": "organise",
    "randomize": "randomise",
    "recognize": "recognise",
    "recognized": "recognised",
    "serialization": "serialisation",
    "serialize": "serialise",
    "standardize": "standardise",
    "summarize": "summarise",
    "synthesize": "synthesise",
    "tokenize": "tokenise",
    "utilize": "utilise",
    "visualize": "visualise",
}

# "artifact" is this project's own identifier — it names artifacts.py, the
# artifact_type JSON key and threshold_artifact_sha256. Rewriting the prose
# would desynchronise comments from the code they describe, so the American
# spelling is retained deliberately for this one term.
SPELLING_EXCEPTIONS = {"artifact", "artifacts"}

MAX_COMMENT_LENGTH = 100

ATTRIBUTION_FENCE = "##############"
ATTRIBUTION_FIELDS = ("Title", "Author", "Date", "Availability")

# Provenance statements that assert nothing verifiable.
VAGUE_PROVENANCE = re.compile(
    r"(?:author|date|availability|source)\s*:\s*"
    r"(?:unknown|n/?a|internet|the internet|google|stack\s*overflow|chatgpt|ai[\s-]generated|various)\b",
    re.IGNORECASE,
)

STABLE_AVAILABILITY = re.compile(r"^(?:https?://\S+|doi:\S+|10\.\d{4,}/\S+)$", re.IGNORECASE)

EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")

# Comment openers that these formats do not support. `//` is matched only at
# the start of a line so that URLs and POSIX paths are not misreported.
PROHIBITED_PATTERNS: Sequence[Tuple[str, re.Pattern[str]]] = (
    ("C++-style '//' comment", re.compile(r"^\s*//")),
    ("C-style '/*' comment", re.compile(r"(?:^|\s)/\*")),
    ("C-style '*/' terminator", re.compile(r"\*/\s*$")),
    ("HTML-style '<!--' comment", re.compile(r"(?:^|\s)<!--")),
    ("HTML-style '-->' terminator", re.compile(r"-->\s*$")),
)


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    rule: str
    detail: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: [{self.rule}] {self.detail}"


@dataclass(frozen=True)
class Comment:
    path: str
    line: int
    text: str


def tracked_files(root: Path) -> List[Path]:
    """Tracked files only, so untracked scratch work is never audited."""
    output = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [root / name for name in output.split("\0") if name]


def is_auditable(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    if EXCLUDED_DIRECTORY_PARTS.intersection(relative.parts[:-1]):
        return False
    return path.suffix.lower() in HASH_COMMENT_SUFFIXES or path.name in HASH_COMMENT_NAMES


def strip_quoted_strings(line: str) -> str:
    """Blank out quoted spans so their contents cannot trigger a match.

    Quotes are replaced by spaces rather than deleted, which preserves column
    positions and stops two separate literals from being joined into a token
    that never existed in the source.
    """
    result: List[str] = []
    quote: str | None = None
    escaped = False
    for character in line:
        if quote:
            result.append(" ")
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = None
            continue
        if character in "\"'":
            quote = character
            result.append(" ")
            continue
        result.append(character)
    return "".join(result)


def python_comments(path: Path, relative: str) -> Tuple[List[Comment], List[Violation]]:
    """Comments from a tokenised Python file.

    Tokenising is itself the check for prohibited syntax: `//` or `/* */` used
    as a comment is a Python syntax error, so a file that tokenises cannot
    contain one, and `value // 2` is an operator token rather than a comment.
    """
    comments: List[Comment] = []
    try:
        tokens = tokenize.generate_tokens(io.StringIO(path.read_text(encoding="utf-8")).readline)
        for token in tokens:
            if token.type == tokenize.COMMENT:
                comments.append(Comment(relative, token.start[0], token.string))
    except (tokenize.TokenError, SyntaxError, UnicodeDecodeError) as exc:
        return [], [Violation(relative, 1, "unparseable", f"cannot tokenise: {exc}")]
    return comments, []


def hash_format_comments(path: Path, relative: str) -> Tuple[List[Comment], List[Violation]]:
    """Comments and prohibited-syntax violations for shell, YAML and TOML."""
    comments: List[Comment] = []
    violations: List[Violation] = []
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        without_strings = strip_quoted_strings(raw)
        hash_index = without_strings.find("#")
        code = without_strings if hash_index == -1 else without_strings[:hash_index]
        if hash_index != -1:
            comments.append(Comment(relative, number, raw[hash_index:]))
        for rule, pattern in PROHIBITED_PATTERNS:
            if pattern.search(code):
                violations.append(
                    Violation(relative, number, "prohibited-comment-syntax", f"{rule}; use '#' instead")
                )
    return comments, violations


def collect_comments(path: Path, relative: str) -> Tuple[List[Comment], List[Violation]]:
    if path.suffix.lower() == ".py":
        return python_comments(path, relative)
    return hash_format_comments(path, relative)


def comment_body(text: str) -> str:
    """Comment text without its leading '#' markers."""
    return text.lstrip("#").strip()


# Code references inside prose: backticked spans, snake_case or dotted names,
# paths, and anything followed by '('. These are identifiers and must never be
# rewritten for spelling, so they are removed before the prose is inspected.
CODE_REFERENCE = re.compile(
    r"`[^`]*`"
    r"|\b\w+(?:[_./]\w+)+\b"
    r"|\b\w+(?=\()"
)


def prose_only(body: str) -> str:
    """Comment prose with code references blanked out, preserving offsets."""
    return CODE_REFERENCE.sub(lambda m: " " * len(m.group(0)), body)


def check_length(comment: Comment) -> List[Violation]:
    stripped = comment.text.strip()
    if stripped.startswith("#!") or "noqa" in stripped or "pragma" in stripped:
        return []
    if stripped.startswith(ATTRIBUTION_FENCE) or len(stripped) <= MAX_COMMENT_LENGTH:
        return []
    return [
        Violation(
            comment.path,
            comment.line,
            "comment-too-long",
            f"{len(stripped)} characters, limit is {MAX_COMMENT_LENGTH}",
        )
    ]


def check_spelling(comment: Comment) -> List[Violation]:
    violations: List[Violation] = []
    for word in re.findall(r"[A-Za-z]+", prose_only(comment_body(comment.text))):
        lowered = word.lower()
        if lowered in SPELLING_EXCEPTIONS:
            continue
        british = AMERICAN_SPELLINGS.get(lowered)
        if british:
            violations.append(
                Violation(
                    comment.path,
                    comment.line,
                    "american-spelling",
                    f"'{word}' should be '{british}'",
                )
            )
    return violations


def check_privacy(comment: Comment, forbidden: Sequence[str]) -> List[Violation]:
    violations: List[Violation] = []
    body = comment_body(comment.text)
    for substring in forbidden:
        if substring in body:
            violations.append(
                Violation(comment.path, comment.line, "private-path", f"comment contains '{substring}'")
            )
    for address in EMAIL.findall(body):
        violations.append(
            Violation(comment.path, comment.line, "personal-email", f"comment contains '{address}'")
        )
    return violations


def check_provenance(comment: Comment) -> List[Violation]:
    match = VAGUE_PROVENANCE.search(comment_body(comment.text))
    if not match:
        return []
    return [
        Violation(
            comment.path,
            comment.line,
            "vague-provenance",
            f"unverifiable source statement: '{match.group(0).strip()}'",
        )
    ]


def check_attribution_blocks(comments: Sequence[Comment], relative: str) -> List[Violation]:
    """Every attribution header must carry all four fields and a stable location.

    An incomplete header is worse than none at all: it implies provenance was
    recorded when it was not.
    """
    violations: List[Violation] = []
    fence_lines = [c.line for c in comments if comment_body(c.text) == "" and c.text.strip().startswith(ATTRIBUTION_FENCE)]
    if not fence_lines:
        return []

    by_line = {c.line: c for c in comments}
    for index in range(0, len(fence_lines) - 1, 2):
        start, end = fence_lines[index], fence_lines[index + 1]
        fields: Dict[str, str] = {}
        for line in range(start + 1, end):
            comment = by_line.get(line)
            if not comment:
                continue
            field_match = re.match(r"(\w+)\s*:\s*(.*)", comment_body(comment.text))
            if field_match:
                fields[field_match.group(1).title()] = field_match.group(2).strip()

        for required in ATTRIBUTION_FIELDS:
            if not fields.get(required):
                violations.append(
                    Violation(relative, start, "incomplete-attribution", f"missing '{required}' field")
                )

        availability = fields.get("Availability", "")
        if availability and not STABLE_AVAILABILITY.match(availability):
            violations.append(
                Violation(
                    relative,
                    start,
                    "unstable-availability",
                    f"'{availability}' is not a stable URL, DOI or repository location",
                )
            )

    if len(fence_lines) % 2 != 0:
        violations.append(
            Violation(relative, fence_lines[-1], "incomplete-attribution", "unterminated attribution block")
        )
    return violations


def check_json_files(paths: Iterable[Path], root: Path) -> List[Violation]:
    """JSON must stay machine-readable; a '#' comment would silently break it."""
    violations: List[Violation] = []
    for path in paths:
        if path.suffix.lower() != ".json":
            continue
        relative = str(path.relative_to(root))
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            violations.append(Violation(relative, 1, "invalid-json", str(exc)))
    return violations


def audit(root: Path) -> List[Violation]:
    files = tracked_files(root)
    forbidden = default_forbidden_path_substrings()
    violations: List[Violation] = list(check_json_files(files, root))

    for path in files:
        if not is_auditable(path, root) or not path.is_file():
            continue
        relative = str(path.relative_to(root))
        comments, file_violations = collect_comments(path, relative)
        violations.extend(file_violations)
        for comment in comments:
            violations.extend(check_length(comment))
            violations.extend(check_spelling(comment))
            violations.extend(check_privacy(comment, forbidden))
            violations.extend(check_provenance(comment))
        violations.extend(check_attribution_blocks(comments, relative))

    return sorted(violations, key=lambda v: (v.path, v.line, v.rule))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    args = parser.parse_args(argv)

    root = args.root.resolve()
    violations = audit(root)

    if violations:
        print(f"Comment-style audit FAILED with {len(violations)} violation(s):\n")
        for violation in violations:
            print(f"  {violation}")
        return 1

    print("Comment-style audit passed: no violations found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
