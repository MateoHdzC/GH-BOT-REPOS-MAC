"""Pre-commit secret scanner preventing credentials and private keys from leaking."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from src.utils.logger import get_logger

logger = get_logger("security")


@dataclass(frozen=True)
class SecretMatch:
    """Represents a discovered secret pattern within scanned contents."""

    rule_name: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    redacted_preview: str = ""


SECRET_RULES: list[tuple[str, re.Pattern]] = [
    (
        "GitHub Personal Access Token (PAT)",
        re.compile(r"(?:ghp|gho|ghu|ghs|ghr)_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9_]{82}"),
    ),
    (
        "AWS Access Key ID",
        re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    ),
    (
        "AWS Secret Access Key",
        re.compile(r"(?i)aws_secret_access_key\s*[:=]\s*['\"]?[a-zA-Z0-9/+=]{40}['\"]?"),
    ),
    (
        "Private Cryptographic Key",
        re.compile(r"-----BEGIN\s+(?:RSA|OPENSSH|DSA|EC|PGP)?\s*PRIVATE KEY-----"),
    ),
    (
        "Slack Token",
        re.compile(r"xox[baprs]-[0-9a-zA-Z]{10,48}"),
    ),
    (
        "Google Cloud / Firebase API Key",
        re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b"),
    ),
    (
        "OpenAI / Anthropic API Key",
        re.compile(r"\b(?:sk-[a-zA-Z0-9]{20,}|sk-ant-[a-zA-Z0-9\-_]{20,})\b"),
    ),
    (
        "Generic Hardcoded Secret/Token",
        re.compile(
            r"(?i)(?:api_key|apikey|secret_key|access_token|private_key|auth_token)\s*[:=]\s*['\"]([a-zA-Z0-9_\-\.]{16,})['\"]"
        ),
    ),
]

SAFE_PLACEHOLDERS: set[str] = {
    "your_api_key",
    "your_secret_key",
    "your_token_here",
    "placeholder",
    "test_token",
    "dummy_key",
    "xxxx",
}


class SecretScanner:
    """Scans staged git diffs and file contents to prevent credential leaks."""

    def __init__(self, custom_rules: Optional[list[tuple[str, re.Pattern]]] = None) -> None:
        self.rules: list[tuple[str, re.Pattern]] = custom_rules or SECRET_RULES

    def is_path_excluded(self, file_path: Optional[str]) -> bool:
        """Checks if the file path is a test fixture, documentation, or scanner definition."""
        if not file_path:
            return False
        normalized = file_path.replace("\\", "/").lower()
        if any(
            normalized.startswith(prefix) or f"/{prefix}" in normalized
            for prefix in ("tests/", "test/", "fixtures/", "docs/")
        ):
            return True
        if normalized.endswith((".md", ".rst", ".markdown")):
            return True
        if "secret_scanner" in normalized or "_test.py" in normalized or normalized.startswith("test_"):
            return True
        return False

    def redact(self, secret_text: str) -> str:
        """Returns a redacted preview of the detected secret."""
        cleaned = secret_text.strip()
        if len(cleaned) <= 6:
            return "***"
        return f"{cleaned[:3]}...{cleaned[-3:]}"

    def scan_diff(self, diff_text: str) -> list[SecretMatch]:
        """Scans added lines in a unified git diff for potential secrets."""
        matches: list[SecretMatch] = []
        current_file: Optional[str] = None
        line_num: int = 0

        for line in diff_text.splitlines():
            if line.startswith("+++ b/"):
                current_file = line[6:].strip()
                line_num = 0
                continue
            elif line.startswith("@@"):
                line_num = 0
                continue

            if not line.startswith("+") or line.startswith("+++"):
                continue

            if current_file and self.is_path_excluded(current_file):
                continue

            line_num += 1
            added_content = line[1:].strip()

            for rule_name, pattern in self.rules:
                found_iter = pattern.finditer(added_content)
                for found in found_iter:
                    matched_str = found.group(0)
                    if any(p in matched_str.lower() for p in SAFE_PLACEHOLDERS):
                        continue

                    match_item = SecretMatch(
                        rule_name=rule_name,
                        file_path=current_file,
                        line_number=line_num,
                        redacted_preview=self.redact(matched_str),
                    )
                    matches.append(match_item)

        return matches

    def scan_content(self, content: str, file_path: Optional[str] = None) -> list[SecretMatch]:
        """Scans arbitrary raw text content for potential secrets."""
        if file_path and self.is_path_excluded(file_path):
            return []

        matches: list[SecretMatch] = []
        for line_idx, line in enumerate(content.splitlines(), start=1):
            for rule_name, pattern in self.rules:
                for found in pattern.finditer(line):
                    matched_str = found.group(0)
                    if any(p in matched_str.lower() for p in SAFE_PLACEHOLDERS):
                        continue
                    matches.append(
                        SecretMatch(
                            rule_name=rule_name,
                            file_path=file_path,
                            line_number=line_idx,
                            redacted_preview=self.redact(matched_str),
                        )
                    )
        return matches
