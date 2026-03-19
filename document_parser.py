"""Tax document data entry — manual entry (default) and PDF upload (opt-in)."""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any, Optional, Union

import anthropic

# ---------------------------------------------------------------------------
# Shared data structures (same for both modes)
# ---------------------------------------------------------------------------

W2_FIELDS = {
    "box_1_wages": "Box 1: Wages, tips, other compensation",
    "box_2_federal_withheld": "Box 2: Federal income tax withheld",
    "box_16_state_wages": "Box 16: State wages",
    "box_17_state_withheld": "Box 17: State income tax withheld",
}

W2_OPTIONAL = {"employer_name"}

FORM_1099_FIELDS = {
    "total_income": "Total income received",
    "federal_withheld": "Federal tax withheld (if any, enter 0 if none)",
}

FORM_1099_OPTIONAL = {"payer_name"}

PDF_WARNING = (
    "Warning: this will send your document contents to Anthropic's API for processing. "
    "For sensitive documents like W-2s, manual entry is recommended. "
    "Type 'continue' to proceed or 'cancel' to use manual entry instead."
)


def _parse_amount(value: str) -> float:
    """Parse a dollar amount from user input, stripping $ and commas."""
    cleaned = re.sub(r"[$,\s]", "", value.strip())
    if not cleaned:
        return 0.0
    try:
        return float(cleaned)
    except ValueError:
        raise ValueError(f"Invalid amount: {value}")


def _prompt_field(prompt: str, optional: bool = False) -> Union[str, float]:
    """Prompt for a single field. Returns str for optional text, float for amounts."""
    raw = input(f"  {prompt}: ").strip()
    if optional and not raw:
        return ""
    if optional and raw:
        return raw
    if not raw:
        raise ValueError("This field is required.")
    return _parse_amount(raw)


# ---------------------------------------------------------------------------
# Mode 1: Manual Entry (default)
# ---------------------------------------------------------------------------

def manual_entry_w2() -> dict[str, Any]:
    """Collect W-2 fields one at a time via terminal prompts."""
    print("\n--- W-2 Manual Entry ---")
    data: dict[str, Any] = {
        "document_type": "w2",
        "source": "manual",
        "employer_name": "",
    }
    for key, label in W2_FIELDS.items():
        while True:
            try:
                data[key] = _prompt_field(label, optional=False)
                break
            except ValueError as e:
                print(f"  Error: {e}")
    # Optional employer name
    employer = input(f"  Employer name (optional, press Enter to skip): ").strip()
    data["employer_name"] = employer
    return data


def manual_entry_1099() -> dict[str, Any]:
    """Collect 1099 fields one at a time via terminal prompts."""
    print("\n--- 1099 Manual Entry ---")
    data: dict[str, Any] = {
        "document_type": "1099",
        "source": "manual",
        "payer_name": "",
    }
    for key, label in FORM_1099_FIELDS.items():
        while True:
            try:
                data[key] = _prompt_field(label, optional=False)
                break
            except ValueError as e:
                print(f"  Error: {e}")
    payer = input(f"  Payer name (optional, press Enter to skip): ").strip()
    data["payer_name"] = payer
    return data


# ---------------------------------------------------------------------------
# Mode 2: PDF Upload (opt-in)
# ---------------------------------------------------------------------------

def _confirm_pdf_upload() -> bool:
    """Print warning and require user to type 'continue' or 'cancel'."""
    print(f"\n{PDF_WARNING}")
    response = input("Your choice: ").strip().lower()
    return response == "continue"


def _extract_w2_from_pdf(client: anthropic.Anthropic, pdf_base64: str) -> dict[str, Any]:
    """Use Claude to extract W-2 fields from a base64-encoded PDF."""
    prompt = """Extract the following fields from this W-2 tax form. Return ONLY valid JSON with these exact keys (use numbers, no currency symbols):
- box_1_wages: Box 1 (Wages, tips, other compensation)
- box_2_federal_withheld: Box 2 (Federal income tax withheld)
- box_16_state_wages: Box 16 (State wages)
- box_17_state_withheld: Box 17 (State income tax withheld)
- employer_name: Employer name (optional, empty string if not found)

Example: {"box_1_wages": 75000, "box_2_federal_withheld": 8500, "box_16_state_wages": 75000, "box_17_state_withheld": 3000, "employer_name": "Acme Corp"}"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_base64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )
    text = message.content[0].text
    # Extract JSON from response (handle markdown code blocks)
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        text = match.group(1).strip()
    parsed = json.loads(text)
    result: dict[str, Any] = {
        "document_type": "w2",
        "source": "pdf",
        "box_1_wages": float(parsed.get("box_1_wages", 0)),
        "box_2_federal_withheld": float(parsed.get("box_2_federal_withheld", 0)),
        "box_16_state_wages": float(parsed.get("box_16_state_wages", 0)),
        "box_17_state_withheld": float(parsed.get("box_17_state_withheld", 0)),
        "employer_name": str(parsed.get("employer_name", "") or ""),
    }
    return result


def _extract_1099_from_pdf(client: anthropic.Anthropic, pdf_base64: str) -> dict[str, Any]:
    """Use Claude to extract 1099 fields from a base64-encoded PDF."""
    prompt = """Extract the following fields from this 1099 tax form. Return ONLY valid JSON with these exact keys (use numbers, no currency symbols):
- total_income: Total income received
- federal_withheld: Federal tax withheld (0 if none)
- payer_name: Payer name (optional, empty string if not found)

Example: {"total_income": 12000, "federal_withheld": 0, "payer_name": "Freelance Client Inc"}"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_base64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )
    text = message.content[0].text
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        text = match.group(1).strip()
    parsed = json.loads(text)
    result: dict[str, Any] = {
        "document_type": "1099",
        "source": "pdf",
        "total_income": float(parsed.get("total_income", 0)),
        "federal_withheld": float(parsed.get("federal_withheld", 0)),
        "payer_name": str(parsed.get("payer_name", "") or ""),
    }
    return result


def parse_pdf_bytes(
    client: anthropic.Anthropic,
    pdf_bytes: bytes,
    document_type: str,
) -> dict[str, Any]:
    """
    Parse a PDF from raw bytes. No confirmation prompt.
    document_type: 'w2' or '1099'
    """
    pdf_base64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")
    if document_type == "w2":
        return _extract_w2_from_pdf(client, pdf_base64)
    if document_type == "1099":
        return _extract_1099_from_pdf(client, pdf_base64)
    raise ValueError(f"Unknown document_type: {document_type}")


def parse_manual_document(
    document_type: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    """
    Build document dict from manual entry JSON (e.g. from API).
    Validates and normalizes fields.
    """
    if document_type == "w2":
        return {
            "document_type": "w2",
            "source": "manual",
            "box_1_wages": float(data.get("box_1_wages", 0)),
            "box_2_federal_withheld": float(data.get("box_2_federal_withheld", 0)),
            "box_16_state_wages": float(data.get("box_16_state_wages", 0)),
            "box_17_state_withheld": float(data.get("box_17_state_withheld", 0)),
            "employer_name": str(data.get("employer_name", "") or ""),
        }
    if document_type == "1099":
        return {
            "document_type": "1099",
            "source": "manual",
            "total_income": float(data.get("total_income", 0)),
            "federal_withheld": float(data.get("federal_withheld", 0)),
            "payer_name": str(data.get("payer_name", "") or ""),
        }
    raise ValueError(f"Unknown document_type: {document_type}")


def pdf_upload_w2(client: anthropic.Anthropic, filepath: str) -> Optional[dict[str, Any]]:
    """
    Parse a W-2 PDF after user confirms. Returns document dict or None if cancelled.
    """
    if not _confirm_pdf_upload():
        print("Cancelled. Use manual entry instead (e.g. 'enter my W-2').")
        return None
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    with open(path, "rb") as f:
        pdf_base64 = base64.standard_b64encode(f.read()).decode("utf-8")
    return _extract_w2_from_pdf(client, pdf_base64)


def pdf_upload_1099(client: anthropic.Anthropic, filepath: str) -> Optional[dict[str, Any]]:
    """
    Parse a 1099 PDF after user confirms. Returns document dict or None if cancelled.
    """
    if not _confirm_pdf_upload():
        print("Cancelled. Use manual entry instead (e.g. 'add my 1099').")
        return None
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    with open(path, "rb") as f:
        pdf_base64 = base64.standard_b64encode(f.read()).decode("utf-8")
    return _extract_1099_from_pdf(client, pdf_base64)


# ---------------------------------------------------------------------------
# Helpers for downstream pipeline
# ---------------------------------------------------------------------------

def get_gross_income(doc: dict[str, Any]) -> float:
    """Total wages/income for federal tax calculation."""
    if doc.get("document_type") == "w2":
        return float(doc.get("box_1_wages", 0))
    if doc.get("document_type") == "1099":
        return float(doc.get("total_income", 0))
    return 0.0


def get_federal_withheld(doc: dict[str, Any]) -> float:
    """Federal tax already withheld."""
    if doc.get("document_type") == "w2":
        return float(doc.get("box_2_federal_withheld", 0))
    if doc.get("document_type") == "1099":
        return float(doc.get("federal_withheld", 0))
    return 0.0


def format_document_summary(doc: dict[str, Any], for_api: bool = False) -> str:
    """
    Human-readable summary. When for_api=True, excludes employer/payer names
    (never send those to the API — local display only).
    """
    lines = []
    if doc.get("document_type") == "w2":
        lines.append(f"  Box 1 (Wages): ${doc.get('box_1_wages', 0):,.2f}")
        lines.append(f"  Box 2 (Federal withheld): ${doc.get('box_2_federal_withheld', 0):,.2f}")
        lines.append(f"  Box 16 (State wages): ${doc.get('box_16_state_wages', 0):,.2f}")
        lines.append(f"  Box 17 (State withheld): ${doc.get('box_17_state_withheld', 0):,.2f}")
        if not for_api and doc.get("employer_name"):
            lines.append(f"  Employer: {doc['employer_name']}")
    else:
        lines.append(f"  Total income: ${doc.get('total_income', 0):,.2f}")
        lines.append(f"  Federal withheld: ${doc.get('federal_withheld', 0):,.2f}")
        if not for_api and doc.get("payer_name"):
            lines.append(f"  Payer: {doc['payer_name']}")
    lines.append(f"  Source: {doc.get('source', 'unknown')}")
    return "\n".join(lines)
