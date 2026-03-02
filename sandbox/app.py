"""Streamlit app: Business Trip NL→SQL chatbot."""

import streamlit as st

from db import get_schema, load_db, run_query
from llm import clarify, generate_report, interpret, nl_to_sql, route

st.set_page_config(
    page_title="출장 데이터 조회",
    page_icon="✈️",
    layout="wide",
)

st.title("✈️ 출장 승인/비용 조회 챗봇")
st.caption("자연어로 출장 및 비용 청구 데이터를 조회하세요.")

# Initialize DB on startup
load_db()

# Session state for chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Sidebar: schema reference
with st.sidebar:
    st.header("📋 데이터 스키마")
    st.code(get_schema(), language="text")

    st.header("💡 예시 질문")
    examples = [
        "김철수의 승인된 출장 목록 보여줘",
        "이번달 교통비 청구 합계는?",
        "부서별 승인된 출장 건수를 알려줘",
        "가장 많은 비용을 청구한 직원은?",
        "전체 출장 현황 리포트 만들어줘",
        "부서별 비용 현황 분석 보고서",
        "2월 출장 비용 요약해줘",
    ]
    for ex in examples:
        if st.button(ex, use_container_width=True):
            st.session_state["prefill"] = ex

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("dataframe") is not None:
            st.dataframe(msg["dataframe"], use_container_width=True)
        if msg.get("sql"):
            with st.expander("생성된 SQL 보기"):
                st.code(msg["sql"], language="sql")

# Handle prefill from sidebar button
prefill = st.session_state.pop("prefill", None)

# Chat input
question = st.chat_input("출장 데이터에 대해 질문하세요...") or prefill

if question:
    # Show user message
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    # Build conversation history (user questions + assistant responses)
    history = []
    for msg in st.session_state.messages[:-1]:  # exclude current question
        if msg["role"] == "user":
            history.append({"role": "user", "content": msg["content"]})
        elif msg["role"] == "assistant":
            # Include SQL and/or dataframe summary so interpreter has full context
            content = msg["content"]
            if msg.get("sql"):
                content += f"\n\nGenerated SQL:\n```sql\n{msg['sql']}\n```"
            if msg.get("dataframe") is not None:
                content += f"\n\nResult data (first 20 rows):\n{msg['dataframe'].head(20).to_string(index=False)}"
            history.append({"role": "assistant", "content": content})

    # Generate response
    with st.chat_message("assistant"):
        with st.spinner("판단 중..."):
            try:
                decision = route(question, history=history)
            except Exception as e:
                decision = "sql"  # fallback to sql on router failure

        if decision == "clarify":
            with st.spinner("질문 생성 중..."):
                try:
                    question_text = clarify(question, history=history)
                except Exception as e:
                    question_text = "어떤 범위의 리포트를 원하시나요? (예: 전체 기간 / 특정 월 / 특정 부서)"
            st.markdown(question_text)
            st.session_state.messages.append({"role": "assistant", "content": question_text})

        elif decision == "interpret":
            with st.spinner("답변 생성 중..."):
                try:
                    answer = interpret(question, history=history)
                except Exception as e:
                    answer = f"⚠️ 오류: {e}"
            st.markdown(answer)
            st.session_state.messages.append({"role": "assistant", "content": answer})

        elif decision == "report":
            with st.spinner("데이터 조회 중..."):
                try:
                    sql = nl_to_sql(question, get_schema(), history=history)
                except Exception as e:
                    st.error(f"⚠️ SQL 생성 실패: {e}")
                    st.session_state.messages.append({"role": "assistant", "content": f"⚠️ SQL 생성 실패: {e}"})
                    st.stop()

            df, error = run_query(sql)

            if error:
                msg = f"⚠️ 쿼리 실행 오류:\n```\n{error}\n```"
                st.markdown(msg)
                st.session_state.messages.append({"role": "assistant", "content": msg})
            elif df is None or df.empty:
                msg = "리포트를 생성할 데이터가 없습니다."
                st.markdown(msg)
                st.session_state.messages.append({"role": "assistant", "content": msg})
            else:
                with st.spinner("리포트 생성 중..."):
                    report = generate_report(question, df.to_string(index=False), history=history)

                st.markdown(report)
                with st.expander("원본 데이터 보기"):
                    st.dataframe(df, use_container_width=True)
                with st.expander("생성된 SQL 보기"):
                    st.code(sql, language="sql")
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": report,
                        "dataframe": df,
                        "sql": sql,
                    }
                )

        else:
            with st.spinner("SQL 생성 중..."):
                try:
                    sql = nl_to_sql(question, get_schema(), history=history)
                except Exception as e:
                    error_msg = f"⚠️ SQL 생성 실패: {e}"
                    st.error(error_msg)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": error_msg}
                    )
                    st.stop()

            with st.spinner("쿼리 실행 중..."):
                df, error = run_query(sql)

            if error:
                msg = f"⚠️ 쿼리 실행 오류:\n```\n{error}\n```\n\n생성된 SQL:\n```sql\n{sql}\n```"
                st.markdown(msg)
                st.session_state.messages.append({"role": "assistant", "content": msg})
            elif df is not None and df.empty:
                msg = "결과가 없습니다."
                st.markdown(msg)
                with st.expander("생성된 SQL 보기"):
                    st.code(sql, language="sql")
                st.session_state.messages.append(
                    {"role": "assistant", "content": msg, "sql": sql}
                )
            else:
                row_count = len(df)
                summary = f"**{row_count}개** 결과를 찾았습니다."
                st.markdown(summary)
                st.dataframe(df, use_container_width=True)
                with st.expander("생성된 SQL 보기"):
                    st.code(sql, language="sql")
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": summary,
                        "dataframe": df,
                        "sql": sql,
                    }
                )
