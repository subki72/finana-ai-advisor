import streamlit as st
from chatbot import chatbot

# ── Page config ───────────────────────────────────────
st.set_page_config(
    page_title="Finana — AI Financial Advisor",
    page_icon="$",
    layout="wide",
)

# ── Custom CSS ────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* Global */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* Remove default Streamlit top padding and expand content */
.block-container {
    padding: 1.5rem 2rem 1rem !important;
    max-width: 100% !important;
}

/* Header card — full width, responsive padding */
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

/* Quick prompt buttons — equal sizing */
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

/* Chat message styling */
.stChatMessage {
    border-radius: 0.75rem !important;
}

/* Footer */
.footer {
    text-align: center;
    color: #64748b;
    font-size: 0.78rem;
    padding: 1rem 0 0.5rem;
    border-top: 1px solid rgba(100, 116, 139, 0.2);
    margin-top: 2rem;
}

/* ── Responsive breakpoints ───────────────────────── */

/* Tablet (768px and below) */
@media (max-width: 768px) {
    .block-container {
        padding: 1rem 1rem 1rem !important;
    }
    .header-card {
        padding: 1.5rem 1rem 0.8rem;
    }
    .header-card h1 {
        font-size: 1.4rem;
    }
    .header-card .subtitle {
        font-size: 0.82rem;
    }
    .header-card .features {
        gap: 0.8rem;
    }
    .header-card .features span {
        font-size: 0.72rem;
    }
    div[data-testid="stHorizontalBlock"] .stButton > button {
        font-size: 0.75rem !important;
        height: 3rem !important;
        padding: 0.4rem 0.3rem !important;
    }
}

/* Mobile (480px and below) */
@media (max-width: 480px) {
    .block-container {
        padding: 0.75rem 0.5rem 0.75rem !important;
    }
    .header-card {
        padding: 1.2rem 0.75rem 0.6rem;
        border-radius: 0.75rem;
    }
    .header-card h1 {
        font-size: 1.2rem;
    }
    .header-card .subtitle {
        font-size: 0.75rem;
    }
    .header-card .features {
        gap: 0.5rem 1rem;
    }
    .header-card .features span {
        font-size: 0.68rem;
    }
    div[data-testid="stHorizontalBlock"] .stButton > button {
        font-size: 0.7rem !important;
        height: 2.8rem !important;
        padding: 0.3rem 0.2rem !important;
    }
    .footer {
        font-size: 0.7rem;
    }
}
</style>
""", unsafe_allow_html=True)

# ── Header with About info ────────────────────────────
st.markdown("""
<div class="header-card">
    <h1>Finana Bot</h1>
    <p class="subtitle">Your casual AI-powered Financial Advisor · Powered by Llama 3.3</p>
    <div class="features">
        <span>Budget Planning</span>
        <span>Financial Tips</span>
        <span>Investment Basics</span>
        <span>Expense Management</span>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

# ── Quick prompts ─────────────────────────────────────
QUICK_PROMPTS = [
    "Gaji 5jt, gimana ngaturnya?",
    "Hitung budget 50/30/20",
    "Tips kurangin pengeluaran",
    "Cara mulai investasi?",
    "KPR worth it ga?",
]

if not st.session_state.messages:
    st.markdown("<p style='text-align: center; font-weight: 600;'>Quick prompts:</p>", unsafe_allow_html=True)
    cols = st.columns(len(QUICK_PROMPTS))
    for i, prompt in enumerate(QUICK_PROMPTS):
        if cols[i].button(prompt, key=f"qp_{i}", use_container_width=True):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.spinner("Thinking..."):
                reply = chatbot(prompt, [])
            st.session_state.messages.append({"role": "assistant", "content": reply})
            st.rerun()

# ── Chat history ──────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ── Chat input ────────────────────────────────────────
if user_input := st.chat_input("Ask about finances, budget, salary, investments..."):
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            reply = chatbot(user_input, st.session_state.messages[:-1])
        st.markdown(reply)
    st.session_state.messages.append({"role": "assistant", "content": reply})

# ── Reset button (centered) ──────────────────────────
if st.session_state.messages:
    col_l, col_c, col_r = st.columns([3, 1, 3])
    with col_c:
        if st.button("Reset Chat", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

# ── Footer ────────────────────────────────────────────
st.markdown(
    '<div class="footer">Finana may make mistakes. Always verify financial decisions with a professional.</div>',
    unsafe_allow_html=True,
)
