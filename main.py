#!/usr/bin/env python3
"""Personal Tax Advisor — Claude-powered terminal chatbot using 2025 US tax data."""

import json
import re
from typing import Optional, Tuple
from dotenv import load_dotenv
load_dotenv()
import os
import anthropic
from tax_calculator import calculate_federal_tax, get_standard_deduction, get_tax_brackets
from document_parser import (
    manual_entry_w2,
    manual_entry_1099,
    pdf_upload_w2,
    pdf_upload_1099,
    get_gross_income,
    get_federal_withheld,
    format_document_summary,
)

client = anthropic.Anthropic()
api_key = os.getenv("ANTHROPIC_API_KEY")

# ---------------------------------------------------------------------------
# Tool definitions exposed to Claude
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "calculate_tax_owed",
        "description": (
            "Calculate estimated 2025 US federal income tax for a given gross income "
            "and filing status. Applies the standard deduction, then runs the income "
            "through progressive brackets. Returns taxable income, total tax owed, "
            "effective rate, marginal rate, and a bracket-by-bracket breakdown."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "gross_income": {
                    "type": "number",
                    "description": "Annual gross income in dollars (before any deductions).",
                },
                "filing_status": {
                    "type": "string",
                    "enum": ["single", "married_jointly", "head_of_household"],
                    "description": (
                        "Filing status: 'single', 'married_jointly', or 'head_of_household'."
                    ),
                },
            },
            "required": ["gross_income", "filing_status"],
        },
    },
    {
        "name": "get_standard_deduction",
        "description": "Return the 2025 standard deduction amount for a given filing status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filing_status": {
                    "type": "string",
                    "enum": ["single", "married_jointly", "head_of_household"],
                    "description": "Filing status.",
                },
            },
            "required": ["filing_status"],
        },
    },
    {
        "name": "get_tax_brackets",
        "description": (
            "Return the full list of 2025 federal income tax brackets (rates and "
            "thresholds) for a given filing status."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "filing_status": {
                    "type": "string",
                    "enum": ["single", "married_jointly", "head_of_household"],
                    "description": "Filing status.",
                },
            },
            "required": ["filing_status"],
        },
    },
]

SYSTEM_PROMPT = """\
You are a knowledgeable personal tax advisor specializing in 2025 US federal income taxes.

Guidelines:
- Always call the appropriate tool to compute accurate figures; never estimate from memory.
- When presenting a tax calculation, show: gross income, standard deduction, taxable income,
  tax owed, effective rate, marginal rate, and the bracket breakdown.
- Use plain language and format dollar amounts with commas (e.g., $10,314.00).
- Remind users that your advice is educational and not a substitute for a licensed tax professional.

Document entry:
- Users can enter W-2 or 1099 data via manual entry ("enter my W-2", "add my 1099") or PDF upload
  ("upload my W-2", "upload my 1099", "parse PDF"). When you receive a document summary in the
  conversation, confirm what was entered, show the estimated federal tax using calculate_tax_owed,
  and clearly state whether the user is likely due a refund (withheld > tax owed) or owes more
  (tax owed > withheld).
"""

# ---------------------------------------------------------------------------
# Tool executor
# ---------------------------------------------------------------------------

def execute_tool(name: str, tool_input: dict) -> str:
    try:
        if name == "calculate_tax_owed":
            result = calculate_federal_tax(
                tool_input["gross_income"], tool_input["filing_status"]
            )
        elif name == "get_standard_deduction":
            amount = get_standard_deduction(tool_input["filing_status"])
            result = {"filing_status": tool_input["filing_status"], "standard_deduction": amount}
        elif name == "get_tax_brackets":
            brackets = get_tax_brackets(tool_input["filing_status"])
            result = {"filing_status": tool_input["filing_status"], "brackets": brackets}
        else:
            result = {"error": f"Unknown tool: {name}"}
    except Exception as exc:
        result = {"error": str(exc)}

    return json.dumps(result, indent=2)

# ---------------------------------------------------------------------------
# Agentic loop (one user turn → stream + tool use until end_turn)
# ---------------------------------------------------------------------------

def run_turn(messages: list) -> None:
    """
    Stream Claude's response for the latest user message, executing any tool
    calls along the way, until Claude reaches end_turn.
    """
    print("\nAdvisor: ", end="", flush=True)

    while True:
        with client.messages.stream(
            model="claude-opus-4-6",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        ) as stream:
            # Stream text tokens as they arrive
            for text in stream.text_stream:
                print(text, end="", flush=True)

            response = stream.get_final_message()

        # Append assistant turn (preserves tool_use blocks for tool_result pairing)
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            print()  # final newline
            break

        # Execute every tool Claude requested and collect results
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result_str = execute_tool(block.name, block.input)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_str,
                    }
                )

        messages.append({"role": "user", "content": tool_results})
        # Loop: Claude will now respond with the tool results in context

# ---------------------------------------------------------------------------
# Document entry triggers (natural language)
# ---------------------------------------------------------------------------

MANUAL_W2_PATTERNS = (r"enter\s+my\s+w-?2", r"add\s+my\s+w-?2", r"manual\s+w-?2")
MANUAL_1099_PATTERNS = (r"add\s+my\s+1099", r"enter\s+my\s+1099", r"manual\s+1099")
PDF_W2_PATTERNS = (r"upload\s+my\s+w-?2", r"parse\s+my\s+w-?2", r"upload\s+w-?2")
PDF_1099_PATTERNS = (r"upload\s+my\s+1099", r"parse\s+my\s+1099", r"upload\s+1099")
PDF_GENERIC_PATTERNS = (r"parse\s+pdf", r"upload\s+pdf", r"parse\s+my\s+pdf")


def _matches(text: str, patterns: Tuple[str, ...]) -> bool:
    lower = text.lower().strip()
    return any(re.search(p, lower, re.IGNORECASE) for p in patterns)


def _handle_document_entry(user_input: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Detect document entry triggers and run the appropriate flow.
    Returns (synthesized_message, None) if handled, or (None, user_input) to pass through.
    """
    # Manual entry (default)
    if _matches(user_input, MANUAL_W2_PATTERNS):
        doc = manual_entry_w2()
        return _build_document_message(doc), None
    if _matches(user_input, MANUAL_1099_PATTERNS):
        doc = manual_entry_1099()
        return _build_document_message(doc), None

    # PDF upload (opt-in)
    if _matches(user_input, PDF_W2_PATTERNS):
        path = input("Path to your W-2 PDF file: ").strip().strip('"\'')
        if not path:
            print("No path provided. Skipping.")
            return None, None
        try:
            doc = pdf_upload_w2(client, path)
            if doc:
                return _build_document_message(doc), None
        except FileNotFoundError as e:
            print(f"Error: {e}")
        return None, None
    if _matches(user_input, PDF_1099_PATTERNS):
        path = input("Path to your 1099 PDF file: ").strip().strip('"\'')
        if not path:
            print("No path provided. Skipping.")
            return None, None
        try:
            doc = pdf_upload_1099(client, path)
            if doc:
                return _build_document_message(doc), None
        except FileNotFoundError as e:
            print(f"Error: {e}")
        return None, None
    if _matches(user_input, PDF_GENERIC_PATTERNS):
        path = input("Path to your PDF file: ").strip().strip('"\'')
        if not path:
            print("No path provided. Skipping.")
            return None, None
        form = input("Form type (w2 or 1099): ").strip().lower()
        if form in ("w2", "w-2"):
            try:
                doc = pdf_upload_w2(client, path)
                if doc:
                    return _build_document_message(doc), None
            except FileNotFoundError as e:
                print(f"Error: {e}")
        elif form == "1099":
            try:
                doc = pdf_upload_1099(client, path)
                if doc:
                    return _build_document_message(doc), None
            except FileNotFoundError as e:
                print(f"Error: {e}")
        else:
            print("Unknown form type. Use 'w2' or '1099'.")
        return None, None

    return None, user_input


def _build_document_message(doc: dict) -> str:
    """Build a message for the agent with document summary and filing status prompt."""
    gross = get_gross_income(doc)
    withheld = get_federal_withheld(doc)
    # Local display (includes employer/payer)
    print("\nEntered document:")
    print(format_document_summary(doc, for_api=False))
    filing = input(
        "\nYour filing status (single / married_jointly / head_of_household): "
    ).strip().lower()
    if filing not in ("single", "married_jointly", "head_of_household"):
        filing = "single"
    calc = calculate_federal_tax(gross, filing)
    tax_owed = calc["tax_owed"]
    refund = withheld - tax_owed
    # Summary for API excludes employer/payer (never send to API)
    summary = format_document_summary(doc, for_api=True)
    outcome = (
        f"Refund: ~${refund:,.2f}" if refund > 0 else f"Amount owed: ~${-refund:,.2f}"
    )
    return (
        f"I've entered my tax document. Here's the summary:\n\n{summary}\n\n"
        f"Filing status: {filing}. "
        f"Please confirm what was entered, show the estimated federal tax, and note: {outcome}. "
        f"Tax calculation data: {json.dumps(calc)}"
    )


# ---------------------------------------------------------------------------
# Main REPL
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 55)
    print("   Personal Tax Advisor  —  2025 US Federal Taxes")
    print("=" * 55)
    print("Ask anything about your federal taxes.")
    print("Examples:")
    print("  • How much tax do I owe if I earn $85,000 as a single filer?")
    print("  • What are the 2025 tax brackets for married filing jointly?")
    print("  • Enter my W-2  (manual entry)")
    print("  • Add my 1099   (manual entry)")
    print("  • Upload my W-2 (PDF — opt-in)")
    print("\nType 'quit' or 'exit' to quit.\n")

    messages: list = []

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break

        # Check for document entry triggers
        doc_message, pass_through = _handle_document_entry(user_input)
        if doc_message is not None:
            messages.append({"role": "user", "content": doc_message})
        elif pass_through is not None:
            messages.append({"role": "user", "content": pass_through})
        else:
            continue

        run_turn(messages)
        print()


if __name__ == "__main__":
    main()
