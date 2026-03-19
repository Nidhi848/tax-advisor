#!/usr/bin/env python3
"""FastAPI backend for Personal Tax Advisor."""

import json
from typing import Any, List, Optional

from dotenv import load_dotenv

load_dotenv()

import anthropic
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from tax_calculator import calculate_federal_tax, get_standard_deduction, get_tax_brackets
from document_parser import (
    get_gross_income,
    get_federal_withheld,
    parse_manual_document,
    parse_pdf_bytes,
)
from user_profile import load_profile, save_profile, update_profile_field
from chat_history import (
    save_conversation,
    load_conversation,
    list_conversations,
    delete_conversation,
    new_conversation_id,
)
from scenario_modeler import (
    model_str,
    model_cost_segregation,
    model_capital_gains_harvesting,
    model_401k_ira,
)
from scenario_comparator import compare_scenarios

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

client = anthropic.Anthropic()

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="Personal Tax Advisor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CalculateRequest(BaseModel):
    income: Optional[float] = Field(
        None,
        description="Gross income in dollars; if omitted, falls back to profile annual_income",
    )
    filing_status: Optional[str] = Field(
        None,
        description="single, married_jointly, or head_of_household; falls back to profile filing_status",
    )
    deductions: Optional[float] = Field(
        None,
        description="Custom deductions; if omitted, uses standard deduction",
    )


class W2ManualRequest(BaseModel):
    box_1_wages: float
    box_2_federal_withheld: float
    box_16_state_wages: float
    box_17_state_withheld: float
    employer_name: Optional[str] = ""


class Form1099ManualRequest(BaseModel):
    total_income: float
    federal_withheld: float = 0
    payer_name: Optional[str] = ""


class DocumentManualRequest(BaseModel):
    model_config = {"populate_by_name": True}
    document_type: str = Field(..., description="w2 or 1099")
    w2: Optional[W2ManualRequest] = None
    form_1099: Optional[Form1099ManualRequest] = Field(None, alias="1099")


class ChatRequest(BaseModel):
    message: str
    conversation_history: List[dict] = Field(default_factory=list)
    conversation_id: Optional[str] = Field(None, description="If provided, load this conversation and append; if not, start new and return id in response.")


class ProfileUpdate(BaseModel):
    filing_status: Optional[str] = None
    state: Optional[str] = None
    dependents: Optional[int] = None
    annual_income: Optional[float] = None
    additional_income: Optional[float] = None
    w2_data: Optional[dict] = None
    ten99_data: Optional[dict] = None
    notes: Optional[list] = None
    age: Optional[int] = None
    self_employment_income: Optional[float] = None


class STRScenarioRequest(BaseModel):
    property_purchase_price: Optional[float] = None
    gross_rental_income: Optional[float] = None
    w2_income: Optional[float] = None
    average_stay_days: Optional[float] = None
    material_participation_hours: Optional[float] = None
    annual_expenses: Optional[float] = None
    filing_status: Optional[str] = None


class CostSegScenarioRequest(BaseModel):
    property_value: Optional[float] = None
    land_value: Optional[float] = None
    marginal_tax_rate_pct: Optional[float] = None
    filing_status: Optional[str] = None


class CapitalGainsScenarioRequest(BaseModel):
    gains: Optional[float] = None
    losses: Optional[float] = None
    income: Optional[float] = None
    filing_status: Optional[str] = None


class RetirementScenarioRequest(BaseModel):
    income: Optional[float] = None
    filing_status: Optional[str] = None
    age: Optional[int] = None
    self_employment_income: Optional[float] = None


class CompareScenariosRequest(BaseModel):
    scenarios: List[dict] = Field(
        ...,
        description="List of { name, modeler, params } to run and compare",
    )


# ---------------------------------------------------------------------------
# Tools (for Claude)
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "calculate_tax_owed",
        "description": (
            "Calculate estimated 2025 US federal income tax for a given gross income "
            "and filing status. Applies the standard deduction (or custom deductions), "
            "then runs the income through progressive brackets."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "gross_income": {"type": "number", "description": "Annual gross income in dollars."},
                "filing_status": {
                    "type": "string",
                    "enum": ["single", "married_jointly", "head_of_household"],
                    "description": "Filing status.",
                },
                "deductions": {
                    "type": "number",
                    "description": "Optional custom deductions; omit to use standard deduction.",
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
                },
            },
            "required": ["filing_status"],
        },
    },
    {
        "name": "get_tax_brackets",
        "description": "Return the 2025 federal income tax brackets for a given filing status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filing_status": {
                    "type": "string",
                    "enum": ["single", "married_jointly", "head_of_household"],
                },
            },
            "required": ["filing_status"],
        },
    },
    {
        "name": "update_profile",
        "description": (
            "Update a single field in the user's tax profile. "
            "Use this when the user mentions life changes like marriage, children, moving states, "
            "or updated income. Always confirm the change back to the user in natural language."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "field": {
                    "type": "string",
                    "enum": [
                        "filing_status",
                        "state",
                        "dependents",
                        "annual_income",
                        "additional_income",
                        "w2_data",
                        "ten99_data",
                        "notes",
                        "age",
                        "self_employment_income",
                    ],
                    "description": "Profile field to update.",
                },
                "value": {
                    "description": "New value for the field.",
                },
            },
            "required": ["field", "value"],
        },
    },
    {
        "name": "model_str_scenario",
        "description": (
            "Model a short-term rental (STR) tax scenario: depreciation, net rental income/loss, "
            "STR loophole eligibility (avg stay < 7 days AND 750+ hours material participation), "
            "passive loss rules, MAGI $150k phaseout. Use when the user asks about buying an STR, "
            "rental property tax impact, or STR loophole."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "property_purchase_price": {"type": "number", "description": "Property purchase price in dollars."},
                "gross_rental_income": {"type": "number", "description": "Expected annual gross rental income."},
                "w2_income": {"type": "number", "description": "Current W-2 income (omit to use profile)."},
                "average_stay_days": {"type": "number", "description": "Average guest stay in days (under 7 for STR)."},
                "material_participation_hours": {"type": "number", "description": "Hours per year (750+ to qualify)."},
                "annual_expenses": {"type": "number", "description": "Annual rental expenses."},
                "filing_status": {"type": "string", "enum": ["single", "married_jointly", "head_of_household"]},
            },
        },
    },
    {
        "name": "model_cost_segregation_scenario",
        "description": (
            "Model cost segregation: reclassify building value to 5/7/15-year property, "
            "apply 60% bonus depreciation (2024), show Year 1 deduction vs straight-line and tax savings. "
            "Use when the user asks about cost seg or accelerated depreciation on real estate."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "property_value": {"type": "number", "description": "Total property value."},
                "land_value": {"type": "number", "description": "Land value (not depreciable)."},
                "marginal_tax_rate_pct": {"type": "number", "description": "Optional marginal rate percent."},
                "filing_status": {"type": "string", "enum": ["single", "married_jointly", "head_of_household"]},
            },
        },
    },
    {
        "name": "model_capital_gains_scenario",
        "description": (
            "Model capital gains harvesting: LTCG rate (0/15/20%), net gain/loss, "
            "$3,000 ordinary income offset, carryforward. Use when the user asks about harvesting "
            "gains or losses, or tax impact of selling investments."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "gains": {"type": "number", "description": "Long-term capital gains in dollars."},
                "losses": {"type": "number", "description": "Long-term capital losses in dollars."},
                "income": {"type": "number", "description": "Ordinary income (omit to use profile)."},
                "filing_status": {"type": "string", "enum": ["single", "married_jointly", "head_of_household"]},
            },
        },
    },
    {
        "name": "model_401k_ira_scenario",
        "description": (
            "Model 401k/IRA: tax savings at $5k, $10k, $23k (2024), catch-up if 50+; "
            "Roth eligibility (MAGI limits 2024); backdoor Roth if over limit; SEP-IRA if self-employed. "
            "Use when the user asks about 401k, IRA, Roth, or retirement contribution tax savings."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "income": {"type": "number", "description": "Annual income (omit to use profile)."},
                "filing_status": {"type": "string", "enum": ["single", "married_jointly", "head_of_household"]},
                "age": {"type": "integer", "description": "Age (50+ for catch-up; omit to use profile)."},
                "self_employment_income": {"type": "number", "description": "Self-employment income for SEP-IRA."},
            },
        },
    },
    {
        "name": "compare_scenarios",
        "description": (
            "Compare multiple tax scenarios side by side vs baseline (current situation). "
            "Input is a list of scenarios, each with name, modeler (str|cost_seg|capital_gains|401k), and params. "
            "Returns a table: scenario name, gross income, deductions, taxable income, tax, effective rate, "
            "net take-home, tax savings vs baseline. Use when the user wants to compare two or more options."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "scenarios": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "modeler": {"type": "string", "enum": ["str", "cost_seg", "capital_gains", "401k"]},
                            "params": {"type": "object"},
                        },
                    },
                    "description": "List of scenario configs to run and compare.",
                },
            },
            "required": ["scenarios"],
        },
    },
]

BASE_SYSTEM_PROMPT = """\
You are a knowledgeable personal tax advisor specializing in 2025 US federal income taxes.

Guidelines:
- Always call the appropriate tool to compute accurate figures; never estimate from memory.
- When presenting a tax calculation, show: gross income, deduction, taxable income,
  tax owed, effective rate, marginal rate, and the bracket breakdown.
- Use plain language and format dollar amounts with commas (e.g., $10,314.00).
- Remind users that your advice is educational and not a substitute for a licensed tax professional.

Document entry:
- Users can enter W-2 or 1099 data. When you receive a document summary, confirm what was entered,
  show the estimated federal tax, and clearly state whether the user is likely due a refund or owes more.

Profile personalization:
- The user has a persistent tax profile (filing status, state, dependents, income, age, and any W-2/1099 data on file).
- When the user says things like "I got married this year", "I have two kids", or "I moved to Texas",
  call the update_profile tool to keep their profile up to date, then clearly confirm the change.
- Prefer using the profile as default context so the user does not have to repeat their situation each time.

Scenario modeling:
- When the user asks \"what if\" investment or tax scenarios (e.g. \"if I buy a $600k STR in Nashville, how much can I save?\"),
  call the appropriate scenario tool: model_str_scenario, model_cost_segregation_scenario, model_capital_gains_scenario,
  or model_401k_ira_scenario. Present the result inline (inputs used, calculation steps, tax impact, summary) and mention
  they can add it to the comparison table on the Scenarios screen. For STR and cost segregation, always include the disclaimer.
- To compare multiple scenarios side by side, use compare_scenarios with a list of scenario configs.
"""


def execute_tool(name: str, tool_input: dict) -> str:
    try:
        if name == "calculate_tax_owed":
            result = calculate_federal_tax(
                tool_input["gross_income"],
                tool_input["filing_status"],
                tool_input.get("deductions"),
            )
        elif name == "get_standard_deduction":
            amount = get_standard_deduction(tool_input["filing_status"])
            result = {"filing_status": tool_input["filing_status"], "standard_deduction": amount}
        elif name == "get_tax_brackets":
            brackets = get_tax_brackets(tool_input["filing_status"])
            result = {"filing_status": tool_input["filing_status"], "brackets": brackets}
        elif name == "update_profile":
            updated = update_profile_field(tool_input["field"], tool_input.get("value"))
            result = {
                "ok": True,
                "updated_field": tool_input["field"],
                "value": tool_input.get("value"),
                "profile": updated,
            }
        elif name == "model_str_scenario":
            result = model_str(
                property_purchase_price=tool_input.get("property_purchase_price"),
                gross_rental_income=tool_input.get("gross_rental_income"),
                w2_income=tool_input.get("w2_income"),
                average_stay_days=tool_input.get("average_stay_days"),
                material_participation_hours=tool_input.get("material_participation_hours"),
                annual_expenses=tool_input.get("annual_expenses"),
                filing_status=tool_input.get("filing_status"),
            )
        elif name == "model_cost_segregation_scenario":
            result = model_cost_segregation(
                property_value=tool_input.get("property_value"),
                land_value=tool_input.get("land_value"),
                marginal_tax_rate_pct=tool_input.get("marginal_tax_rate_pct"),
                filing_status=tool_input.get("filing_status"),
            )
        elif name == "model_capital_gains_scenario":
            result = model_capital_gains_harvesting(
                gains=tool_input.get("gains"),
                losses=tool_input.get("losses"),
                income=tool_input.get("income"),
                filing_status=tool_input.get("filing_status"),
            )
        elif name == "model_401k_ira_scenario":
            result = model_401k_ira(
                income=tool_input.get("income"),
                filing_status=tool_input.get("filing_status"),
                age=tool_input.get("age"),
                self_employment_income=tool_input.get("self_employment_income"),
            )
        elif name == "compare_scenarios":
            result = compare_scenarios(tool_input.get("scenarios") or [])
        else:
            result = {"error": f"Unknown tool: {name}"}
    except Exception as exc:
        result = {"error": str(exc)}
    return json.dumps(result, indent=2)


def _build_system_prompt() -> str:
    """Base system prompt with current profile summary injected at the top."""
    profile = load_profile()
    filing_status = profile.get("filing_status") or "unknown"
    state = profile.get("state") or "unspecified"
    dependents = profile.get("dependents")
    annual_income = profile.get("annual_income")
    w2_present = "yes" if profile.get("w2_data") else "no"
    ten99_present = "yes" if profile.get("ten99_data") else "no"
    additional_income = profile.get("additional_income")

    age = profile.get("age")
    self_employment = profile.get("self_employment_income")
    summary_lines = [
        "User tax profile (persisted between turns):",
        f"- Filing status: {filing_status}",
        f"- State: {state}",
        f"- Dependents: {dependents}",
        f"- Annual income: {annual_income if annual_income is not None else 'not set'}",
        f"- Age: {age if age is not None else 'not set'}",
        f"- Self-employment income: {self_employment if self_employment is not None else 'not set'}",
        f"- W-2 data on file: {w2_present}",
        f"- 1099 data on file: {ten99_present}",
        f"- Additional income: {additional_income if additional_income is not None else 'not set'}",
        "",
        "Use this profile as default context. If information seems outdated, politely ask the user to confirm before relying on it.",
        "",
    ]
    return "\n".join(summary_lines) + BASE_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post("/calculate")
def post_calculate(req: CalculateRequest):
    """Calculate tax breakdown from income, filing status, and optional deductions."""
    try:
        profile = load_profile()
        income = req.income if req.income is not None else profile.get("annual_income")
        filing_status = req.filing_status or profile.get("filing_status")
        if income is None:
            raise HTTPException(status_code=400, detail="Income is required (request body or profile annual_income).")
        if not filing_status:
            raise HTTPException(status_code=400, detail="Filing status is required (request body or profile filing_status).")
        result = calculate_federal_tax(
            income,
            filing_status,
            req.deductions,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/document/manual")
def post_document_manual(req: DocumentManualRequest):
    """Accept W-2 or 1099 fields as JSON; return structured document + estimated tax."""
    doc_type = req.document_type.lower()
    if doc_type == "w2":
        if not req.w2:
            raise HTTPException(status_code=400, detail="w2 fields required for document_type w2")
        data = req.w2.model_dump()
    elif doc_type == "1099":
        if not req.form_1099:
            raise HTTPException(status_code=400, detail="form_1099 fields required for document_type 1099")
        data = req.form_1099.model_dump()
    else:
        raise HTTPException(status_code=400, detail="document_type must be w2 or 1099")

    try:
        doc = parse_manual_document(doc_type, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    profile = load_profile()
    filing_status = profile.get("filing_status", "single")
    gross = get_gross_income(doc)
    withheld = get_federal_withheld(doc)
    calc = calculate_federal_tax(gross, filing_status)
    refund = withheld - calc["tax_owed"]

    # Persist extracted document on profile
    field_name = "w2_data" if doc_type == "w2" else "ten99_data"
    update_profile_field(field_name, doc)

    return {
        "document": doc,
        "tax_calculation": calc,
        "federal_withheld": withheld,
        "refund_or_owed": refund,
        "outcome": "refund" if refund > 0 else "owe",
    }


@app.post("/document/pdf")
async def post_document_pdf(
    file: UploadFile = File(...),
    document_type: str = "w2",
):
    """Upload a PDF; extract W-2 or 1099 fields via Anthropic API."""
    if document_type not in ("w2", "1099"):
        raise HTTPException(status_code=400, detail="document_type must be w2 or 1099")
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    pdf_bytes = await file.read()
    try:
        doc = parse_pdf_bytes(client, pdf_bytes, document_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF parsing failed: {str(e)}")

    profile = load_profile()
    filing_status = profile.get("filing_status", "single")
    gross = get_gross_income(doc)
    withheld = get_federal_withheld(doc)
    calc = calculate_federal_tax(gross, filing_status)
    refund = withheld - calc["tax_owed"]

    # Persist extracted document on profile
    field_name = "w2_data" if document_type == "w2" else "ten99_data"
    update_profile_field(field_name, doc)

    return {
        "document": doc,
        "tax_calculation": calc,
        "federal_withheld": withheld,
        "refund_or_owed": refund,
        "outcome": "refund" if refund > 0 else "owe",
        "warning": "Document contents were sent to Anthropic's API for processing. Use manual entry to keep your data local.",
    }


def _chat_sse_generator(message: str, conversation_history: list, conversation_id: Optional[str] = None):
    """Yield SSE events for streaming chat response. Loads/saves conversation when conversation_id is used."""
    if conversation_id:
        loaded = load_conversation(conversation_id)
        if loaded and loaded.get("messages"):
            conversation_history = loaded["messages"]
    else:
        conversation_id = new_conversation_id()
        yield f"data: {json.dumps({'type': 'conversation_id', 'id': conversation_id})}\n\n"

    # Build Claude API message list (content can be str or list of blocks)
    messages = list(conversation_history)
    messages.append({"role": "user", "content": message})

    assistant_text_parts = []

    while True:
        with client.messages.stream(
            model="claude-opus-4-6",
            max_tokens=4096,
            system=_build_system_prompt(),
            tools=TOOLS,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                yield f"data: {json.dumps({'type': 'text', 'content': text})}\n\n"
                assistant_text_parts.append(text)
            response = stream.get_final_message()

        # Append assistant turn (content for API is the raw response)
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            break

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result_str = execute_tool(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_str,
                })
                if block.name == "update_profile":
                    field = block.input.get("field")
                    value = block.input.get("value")
                    yield f"data: {json.dumps({'type': 'profile_update', 'field': field, 'value': value})}\n\n"
                if block.name in (
                    "model_str_scenario",
                    "model_cost_segregation_scenario",
                    "model_capital_gains_scenario",
                    "model_401k_ira_scenario",
                ):
                    try:
                        payload = json.loads(result_str)
                        scenario_type = block.name.replace("model_", "").replace("_scenario", "")
                        yield f"data: {json.dumps({'type': 'scenario_result', 'scenario_type': scenario_type, 'result': payload})}\n\n"
                    except Exception:
                        pass
        messages.append({"role": "user", "content": tool_results})
        yield f"data: {json.dumps({'type': 'thinking'})}\n\n"

    # Persist: build display-friendly message list for storage
    stored = list(conversation_history)
    stored.append({"role": "user", "content": message})
    stored.append({"role": "assistant", "content": "".join(assistant_text_parts)})
    save_conversation(conversation_id, stored)

    yield f"data: {json.dumps({'type': 'done'})}\n\n"


@app.post("/chat")
def post_chat(req: ChatRequest):
    """Stream Claude's response via SSE. Optional conversation_id to continue a conversation."""
    return StreamingResponse(
        _chat_sse_generator(req.message, req.conversation_history, req.conversation_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/conversations")
def get_conversations_list():
    """List conversations: id, timestamp, preview (first message)."""
    return list_conversations()


@app.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str):
    """Return full message history for a conversation."""
    conv = load_conversation(conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@app.delete("/conversations/{conversation_id}")
def delete_conversation_endpoint(conversation_id: str):
    """Delete a conversation."""
    if not delete_conversation(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Scenario endpoints
# ---------------------------------------------------------------------------


@app.post("/scenario/str")
def post_scenario_str(req: STRScenarioRequest):
    """Run STR (short-term rental) scenario modeler."""
    try:
        return model_str(
            property_purchase_price=req.property_purchase_price,
            gross_rental_income=req.gross_rental_income,
            w2_income=req.w2_income,
            average_stay_days=req.average_stay_days,
            material_participation_hours=req.material_participation_hours,
            annual_expenses=req.annual_expenses,
            filing_status=req.filing_status,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/scenario/cost-seg")
def post_scenario_cost_seg(req: CostSegScenarioRequest):
    """Run cost segregation scenario modeler."""
    try:
        return model_cost_segregation(
            property_value=req.property_value,
            land_value=req.land_value,
            marginal_tax_rate_pct=req.marginal_tax_rate_pct,
            filing_status=req.filing_status,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/scenario/capital-gains")
def post_scenario_capital_gains(req: CapitalGainsScenarioRequest):
    """Run capital gains harvesting scenario modeler."""
    try:
        return model_capital_gains_harvesting(
            gains=req.gains,
            losses=req.losses,
            income=req.income,
            filing_status=req.filing_status,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/scenario/401k")
def post_scenario_401k(req: RetirementScenarioRequest):
    """Run 401k/IRA optimizer scenario modeler."""
    try:
        return model_401k_ira(
            income=req.income,
            filing_status=req.filing_status,
            age=req.age,
            self_employment_income=req.self_employment_income,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/scenario/compare")
def post_scenario_compare(req: CompareScenariosRequest):
    """Run scenario comparator; returns unified table vs baseline."""
    try:
        return compare_scenarios(req.scenarios)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/profile")
def get_profile():
    """Return current user profile from user_profile.json."""
    return load_profile()


@app.post("/profile")
def post_profile(profile: ProfileUpdate):
    """Update user profile."""
    current = load_profile()
    updates = profile.model_dump(exclude_none=True)
    current.update(updates)
    saved = save_profile(current)
    return saved


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
