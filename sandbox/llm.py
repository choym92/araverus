"""LLM module: NL→SQL with router + interpreter agents (Gemini backend)."""

import os
import re

from google import genai
from google.genai import types

_client: genai.Client | None = None

MODEL = "gemini-2.5-flash"

# --- Prompts ---

ROUTER_PROMPT = """You are a routing agent. Decide how to handle the user's question.

Reply with ONLY one word:
- "sql"       → a DB query is needed to fetch new data
- "interpret" → the question can be answered from already-retrieved data (yes/no, comparison, confirmation)
- "report"    → the user wants a report AND the request is specific enough (scope, period, or target is clear)
- "clarify"   → the user wants a report BUT the request is too vague (no period, no target, no scope specified)

Examples:
- "김철수 출장 목록 보여줘" → sql
- "마케팅팀이 제일 적게했어?" → interpret
- "부서별 출장 건수 알려줘" → sql
- "이번달 영업팀 출장 비용 리포트" → report
- "2월 출장 현황 요약해줘" → report
- "리포트 만들어줘" → clarify
- "출장 현황 분석해줘" → clarify
- "보고서 보여줘" → clarify
- After clarification answer in history → report
"""

CLARIFY_PROMPT = """You are a report requirements assistant. The user wants a report but hasn't specified enough details.

Ask ONE concise question in Korean to clarify what they need. Cover the most important missing info in a single question.

Focus on:
- 기간 (이번달? 특정 월? 전체 기간?)
- 대상 (특정 부서? 특정 직원? 전체?)
- 내용 (출장 건수? 비용? 승인 현황? 전체?)

Format: Ask naturally in 1~2 sentences. Provide 2~4 example options in parentheses to guide the user.

Example output:
어떤 범위의 리포트를 원하시나요? (예: 전체 기간 / 2월만 / 특정 부서별 / 특정 직원)
"""

SQL_PROMPT = """You are an expert SQL assistant. Given a database schema and a conversation history, generate a valid SQLite SQL query for the latest question.

Rules:
- Return ONLY the SQL query inside a ```sql code block. No explanation.
- Use table/column names exactly as defined in the schema.
- For Korean names or values, use LIKE '%keyword%' for flexible matching.
- Always use JOINs when data spans multiple tables.
- Limit results to 100 rows unless the question asks for aggregation.
- When asked for "most" or "least" (제일 많은, 제일 적은, 가장 많은, 가장 적은), do NOT use LIMIT 1. Instead use a subquery or HAVING to return all tied rows.
- For date comparisons, use strftime() or direct string comparison (YYYY-MM-DD format).
- Never use DROP, DELETE, INSERT, UPDATE, or any DDL/DML — SELECT only.
- Use the conversation history to understand follow-up questions (e.g. "그다음은?", "이중에서", "거기서").

Schema:
{schema}
"""

INTERPRET_PROMPT = """You are a helpful data assistant. Answer the user's question based on the conversation history and the data that has already been retrieved.

Rules:
- Answer in Korean.
- Be concise and direct.
- Do NOT generate SQL. Just answer naturally from the context.
- If you cannot answer from the available context, say "이전 조회 결과만으로는 알 수 없어요. 다시 조회해볼까요?"
"""

REPORT_PROMPT = """You are a business data analyst. Generate a well-structured Korean markdown report based on the provided data.

Report format:
## 📊 [적절한 제목]

### 핵심 요약
- 3~5개 bullet point로 주요 인사이트

### 상세 분석
데이터를 기반으로 항목별 분석 (표, 수치 포함)

### 주요 발견사항
눈에 띄는 패턴, 이상치, 특이사항

### 권고사항 (해당되는 경우)
데이터 기반의 실용적인 제안

Rules:
- 반드시 한국어로 작성
- 숫자는 구체적으로 언급 (금액은 원 단위 표시, 예: 120,000원)
- 데이터에 없는 내용은 추측하지 말 것
- 마크다운 형식 사용 (헤더, 볼드, 테이블 등)
"""


# --- Helpers ---

def _get_client() -> genai.Client:
    global _client
    if _client is not None:
        return _client

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY environment variable is required. "
            "Set it to your Gemini API key."
        )

    _client = genai.Client(api_key=api_key)
    return _client


def _build_contents(history: list[dict] | None, question: str) -> list[types.Content]:
    contents: list[types.Content] = []
    for turn in (history or []):
        role = "user" if turn["role"] == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part(text=turn["content"])]))
    contents.append(types.Content(role="user", parts=[types.Part(text=question)]))
    return contents


def _extract_sql(raw: str) -> str:
    match = re.search(r"```sql\s*(.*?)\s*```", raw, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match = re.search(r"```\s*(.*?)\s*```", raw, re.DOTALL)
    if match:
        return match.group(1).strip()
    return raw.strip()


def _chat(system: str, history: list[dict] | None, question: str) -> str:
    client = _get_client()
    contents = _build_contents(history, question)
    response = client.models.generate_content(
        model=MODEL,
        contents=contents,
        config=types.GenerateContentConfig(system_instruction=system),
    )
    return response.text.strip()


# --- Public API ---

def route(question: str, history: list[dict] | None = None) -> str:
    """Return 'sql', 'interpret', 'report', or 'clarify'."""
    result = _chat(ROUTER_PROMPT, history, question).lower()
    if "interpret" in result:
        return "interpret"
    if "clarify" in result:
        return "clarify"
    if "report" in result:
        return "report"
    return "sql"


def clarify(question: str, history: list[dict] | None = None) -> str:
    """Generate a single clarifying question for a vague report request."""
    return _chat(CLARIFY_PROMPT, history, question)


def nl_to_sql(question: str, schema_str: str, history: list[dict] | None = None) -> str:
    """Convert a natural language question to a SQL query."""
    raw = _chat(SQL_PROMPT.format(schema=schema_str), history, question)
    return _extract_sql(raw)


def interpret(question: str, history: list[dict] | None = None) -> str:
    """Answer a question from conversation context without querying the DB."""
    return _chat(INTERPRET_PROMPT, history, question)


def generate_report(question: str, df_str: str, history: list[dict] | None = None) -> str:
    """Generate a formatted markdown report from query results."""
    prompt = f"{question}\n\nData:\n{df_str}"
    return _chat(REPORT_PROMPT, history, prompt)
