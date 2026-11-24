"""Streamlit web UI entrypoint for Finana AI Financial Advisor."""

from __future__ import annotations

import logging

import streamlit as st

try:
    from src.calculators import calculate_budget_50_30_20
    from src.chatbot import chatbot
    from src.config import configure_logging
except ModuleNotFoundError:  # pragma: no cover - supports `streamlit run` from inside src/
    from calculators import calculate_budget_50_30_20
    from chatbot import chatbot
    from config import configure_logging

logger = logging.getLogger(__name__)

QUICK_PROMPTS: tuple[str, ...] = (
    "Gaji 5jt, gimana ngaturnya?",
    "Hitung budget 50/30/20",
    "Tips kurangin pengeluaran",
    "Cara mulai investasi?",
    "KPR worth it ga?",
)

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.block-container {
    padding: 1.5rem 2rem 1rem !important;
    max-width: 100% !important;
}

.header-card {
    text-align: center;
    padding: 2rem 1.5rem 1rem;
    border-radius: 1rem;
    margin-bottom: 1.5rem;
    background: linear-gradient(135deg, #064e3b 0%, #1e3a5f 100%);
    border: 1px solid rgba(16, 185, 129, 0.35);
    box-shadow: 0 4px 24px rgba(16, 185, 129, 0.1);
}
.header-card h1 {
    margin: 0;
    font-size: 1.75rem;
    font-weight: 700;
    background: linear-gradient(90deg, #10b981, #34d399);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
.header-card .subtitle {
    margin: 0.4rem 0 0;
    color: #94a3b8;
    font-size: 0.9rem;
}
.header-card .features {
    display: flex;
    justify-content: center;
    gap: 1.5rem;
    flex-wrap: wrap;
    margin-top: 1rem;
    padding-top: 0.8rem;
    border-top: 1px solid rgba(148, 163, 184, 0.15);
}
.header-card .features span {
    color: #cbd5e1;
    font-size: 0.8rem;
    font-weight: 400;
}

div[data-testid="stHorizontalBlock"] .stButton > button {
    border-radius: 0.5rem !important;
    font-size: 0.82rem !important;
    padding: 0.55rem 0.5rem !important;
    transition: all 0.2s ease !important;
    height: 3.2rem !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    text-align: center !important;
    line-height: 1.3 !important;
}

.stChatMessage {
    border-radius: 0.75rem !important;
}

.footer {
    text-align: center;
    color: #64748b;
    font-size: 0.78rem;
    padding: 1rem 0 0.5rem;
    border-top: 1px solid rgba(100, 116, 139, 0.2);
    margin-top: 2rem;
}

@media (max-width: 768px) {
    .block-container { padding: 1rem 1rem 1rem !important; }
    .header-card { padding: 1.5rem 1rem 0.8rem; }
    .header-card h1 { font-size: 1.4rem; }
    .header-card .subtitle { font-size: 0.82rem; }
    .header-card .features { gap: 0.8rem; }
    .header-card .features span { font-size: 0.72rem; }
    div[data-testid="stHorizontalBlock"] .stButton > button {
        font-size: 0.75rem !important;
        height: 3rem !important;
        padding: 0.4rem 0.3rem !important;
    }
}

@media (max-width: 480px) {
    .block-container { padding: 0.75rem 0.5rem 0.75rem !important; }
    .header-card { padding: 1.2rem 0.75rem 0.6rem; border-radius: 0.75rem; }
    .header-card h1 { font-size: 1.2rem; }
    .header-card .subtitle { font-size: 0.75rem; }
    .header-card .features { gap: 0.5rem 1rem; }
    .header-card .features span { font-size: 0.68rem; }
    div[data-testid="stHorizontalBlock"] .stButton > button {
        font-size: 0.7rem !important;
        height: 2.8rem !important;
        padding: 0.3rem 0.2rem !important;
    }
    .footer { font-size: 0.7rem; }
}
</style>
"""

HEADER_HTML = """
<div class="header-card">
    <h1>Finana Bot</h1>
    <p class="subtitle">Your casual AI-powered Financial Advisor - Powered by Llama 3.3</p>
    <div class="features">
        <span>Budget Planning</span>
        <span>Financial Tips</span>
        <span>Investment Basics</span>
        <span>Expense Management</span>
    </div>
</div>
"""


def render_sidebar_calculator() -> None:
    """Render deterministic 50/30/20 budget helper inside the Streamlit sidebar."""
    with st.sidebar:
        st.subheader("Quick 50/30/20 Calculator")
        monthly_income = st.number_input(
            "Monthly Net Income",
            min_value=100_000.0,
            value=5_000_000.0,
            step=500_000.0,
            format="%.0f",
        )
        allocation = calculate_budget_50_30_20(monthly_income)
        st.metric("Needs (50%)", f"{allocation.needs:,.0f}")
        st.metric("Wants (30%)", f"{allocation.wants:,.0f}")
        st.metric("Savings & Invest (20%)", f"{allocation.savings:,.0f}")


def render_quick_prompts(prompts: tuple[str, ...]) -> None:
    """Render starter prompt buttons when conversation history is empty."""
    st.markdown(
        "<p style='text-align: center; font-weight: 600;'>Quick prompts:</p>",
        unsafe_allow_html=True,
    )
    cols = st.columns(len(prompts))
    for index, prompt in enumerate(prompts):
        if cols[index].button(prompt, key=f"qp_{index}", use_container_width=True):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.spinner("Thinking..."):
                reply = chatbot(prompt, [])
            st.session_state.messages.append({"role": "assistant", "content": reply})
            st.rerun()


def render_chat_history(messages: list[dict[str, str]]) -> None:
    """Display persisted chat turns in chronological order."""
    for message in messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])


def handle_chat_input() -> None:
    """Capture user chat input, invoke advisor, and append turn to session state."""
    user_input = st.chat_input("Ask about finances, budget, salary, investments...")
    if not user_input or not user_input.strip():
        return

    cleaned_input = user_input.strip()
    st.session_state.messages.append({"role": "user", "content": cleaned_input})
    with st.chat_message("user"):
        st.markdown(cleaned_input)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            history = st.session_state.messages[:-1]
            reply = chatbot(cleaned_input, history)
        st.markdown(reply)
    st.session_state.messages.append({"role": "assistant", "content": reply})


def main() -> None:
    """Configure page layout and run the Finana Streamlit UI loop."""
    configure_logging()
    st.set_page_config(
        page_title="Finana - AI Financial Advisor",
        page_icon="$",
        layout="wide",
    )
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    st.markdown(HEADER_HTML, unsafe_allow_html=True)
    render_sidebar_calculator()

    if "messages" not in st.session_state:
        st.session_state.messages = []

    if not st.session_state.messages:
        render_quick_prompts(QUICK_PROMPTS)

    render_chat_history(st.session_state.messages)
    handle_chat_input()

    if st.session_state.messages:
        _, col_center, _ = st.columns([3, 1, 3])
        with col_center:
            if st.button("Reset Chat", use_container_width=True):
                st.session_state.messages = []
                logger.info("Cleared chat session history")
                st.rerun()

    st.markdown(
        '<div class="footer">Finana may make mistakes. Always verify financial decisions with a professional.</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
