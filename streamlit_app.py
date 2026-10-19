"""Local chat UI; all provider access stays in the Python server."""

import streamlit as st
from pydantic import ValidationError
from urllib3.exceptions import MaxRetryError, NewConnectionError

from quantum_primer.config import Settings
from quantum_primer.models import Question
from quantum_primer.service import create_graph


def show_response(response):
    if response["status"] == "insufficient_context":
        st.info(response["answer"])
    else:
        st.markdown(response["answer"])
    if response["citations"]:
        with st.expander("Sources"):
            for citation in response["citations"]:
                st.write(f'[{citation["id"]}] {citation["title"]}')
                st.caption(f'{citation["author"]} — {citation["locator"]}')


st.set_page_config(page_title="Quantum Primer", page_icon="📚")
st.title("Quantum Primer")
st.caption("Ask about your library. Answers cite the author and page.")
st.caption("Each question is answered independently; include any context it needs.")

if st.sidebar.button("Clear conversation"):
    st.session_state.messages = []
st.session_state.setdefault("messages", [])

try:
    if "graph" not in st.session_state:
        with st.spinner("Connecting to your library…"):
            settings = Settings()
            st.session_state.graph = create_graph(settings)
            st.session_state.mode = settings.mode
except Exception as exc:
    if isinstance(exc, (MaxRetryError, NewConnectionError, ConnectionError)):
        st.error(
            "Could not connect to Pinecone to open your library. Check internet access "
            "and firewall settings. If this server was launched by a coding agent, "
            "restart it from a normal PowerShell terminal using .\\start-chat.ps1 "
            "so it can access the network."
        )
    else:
        st.error(
            "Could not open the library. Check the local .env settings, provider access, "
            "and data/index.json, then reload this page."
        )
    if st.button("Retry connection"):
        st.rerun()
    st.stop()

st.sidebar.caption(f'Mode: {st.session_state.mode}')
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "user":
            st.write(message["text"])
        elif "error" in message:
            st.error(message["error"])
        else:
            show_response(message["response"])

if prompt := st.chat_input("How does the author describe DHA?", max_chars=2000):
    try:
        question = Question(question=prompt).question
    except ValidationError:
        st.warning("Please ask a question of 3–2000 characters.")
        st.stop()
    st.session_state.messages.append({"role": "user", "text": question})
    with st.chat_message("user"):
        st.write(question)
    with st.chat_message("assistant"):
        try:
            with st.spinner("Searching sources and preparing an answer…"):
                response = st.session_state.graph.invoke({"question": question})["response"]
            message = {"role": "assistant", "response": response.model_dump()}
            show_response(message["response"])
        except Exception:
            message = {
                "role": "assistant",
                "error": "The answer could not be completed. Check your connection and provider "
                "access, then submit the question again. Provider details are kept private.",
            }
            st.error(message["error"])
        st.session_state.messages.append(message)
