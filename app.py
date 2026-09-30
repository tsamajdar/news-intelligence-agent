import streamlit as st
import json
import re
from google import genai
import time

# -------------------------------------------------
# 1. PAGE CONFIGURATION & CLIENT SETUP
# -------------------------------------------------
st.set_page_config(page_title="News Intelligence Agent", layout="wide")
api_key = st.secrets.get("GEMINI_API_KEY")

if not api_key:
    st.error("Gemini API Key not found! Please configure it in Streamlit secrets.")
else:
    client = genai.Client(api_key=api_key)
# Initialize the Gemini client (Make sure your API key is set in environment variables or secrets)
# client = genai.Client(api_key="YOUR_API_KEY") 

# -------------------------------------------------
# 2. HELPER FUNCTIONS
# -------------------------------------------------
def extract_text(resp):
    if hasattr(resp, "text") and resp.text:
        return resp.text.strip()
    return str(resp).strip()

def llm(prompt, retries=2):
    for _ in range(retries):
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            text = extract_text(response)
            if text:
                return text
        except Exception:
            time.sleep(1)
    return ""

def safe_json(s):
    if not s:
        return None
    try:
        return json.loads(s)
    except:
        m = re.search(r"\{.*\}|\[.*\]", s, flags=re.DOTALL)
        return json.loads(m.group(0)) if m else None

# -------------------------------------------------
# 3. STREAMLIT UI DESIGN
# -------------------------------------------------
st.title("📰 News Intelligence Agent")
st.markdown("Enter any topic below to generate a real-time, AI-powered intelligence brief with cleaned items, summaries, and impact scores.")

# User Topic Input Box
user_topic = st.text_input("What topic would you like to research?", "AI breakthroughs in renewable energy")

if st.button("Generate Intelligence Brief", type="primary"):
    if not user_topic.strip():
        st.warning("Please enter a valid topic.")
    else:
        with st.spinner(f"Gathering and analyzing news for: '{user_topic}'... This will take a moment."):
            
            # STEP 1: Fetch Raw Blob
            fetch_prompt = f"""
            Generate a realistic raw text dump containing 6-8 recent news headlines, snippets, sources, and dummy links related to the following topic: '{user_topic}'.
            Make it look like raw scraped web text or RSS feed data so it can be cleaned and deduplicated.
            """
            raw_blob = llm(fetch_prompt)
            
            if not raw_blob:
                st.error("Failed to generate raw data. Please check your API key or connection.")
            else:
                # STEP 2: Call 1 — Clean & Deduplicate
                call1_prompt = f"""
                You are a data cleaning assistant. Clean, deduplicate, and format the following raw headlines data.
                Ensure: DEDUPLICATION, No summarization, STRICT JSON OUTPUT ARRAY.
                Format required:
                [
                  {{
                    "id": 1,
                    "title": "...",
                    "source": "...",
                    "link": "...",
                    "date": "..."
                  }}
                ]
                RAW: {raw_blob}
                """
                resp1 = llm(call1_prompt)
                match1 = re.search(r'\[\s*\{.*\}\s*\]', resp1, re.DOTALL)
                clean_items = json.loads(match1.group(0)) if match1 else safe_json(resp1)
                
                if isinstance(clean_items, dict):
                    for k, v in clean_items.items():
                        if isinstance(v, list): clean_items = v; break

                # STEP 3: Call 2 — Summarize
                call2_prompt = f"""
                For each news item provided below, write a concise summary and 2-3 bullet points explaining it in simple terms.
                Keep original "id", "title", "source", "link". Add "summary" (string) and "key_points" (array of strings).
                Return ONLY a valid JSON array.
                INPUT: {json.dumps(clean_items)}
                """
                resp2 = llm(call2_prompt)
                match2 = re.search(r'\[\s*\{.*\}\s*\]', resp2, re.DOTALL)
                news_cards = json.loads(match2.group(0)) if match2 else safe_json(resp2)
                
                if isinstance(news_cards, dict):
                    for k, v in news_cards.items():
                        if isinstance(v, list): news_cards = v; break

                # STEP 4: Call 3 — Score Urgency & Impact
                call3_prompt = f"""
                Evaluate and assign:
                - "urgency": numeric score 0-5
                - "impact": numeric score 0-5
                - "reason": one sentence justification
                Return ONLY a valid JSON array matching original "id".
                INPUT: {json.dumps(news_cards)}
                """
                resp3 = llm(call3_prompt)
                match3 = re.search(r'\[\s*\{.*\}\s*\]', resp3, re.DOTALL)
                scores = json.loads(match3.group(0)) if match3 else safe_json(resp3)
                
                if isinstance(scores, dict):
                    for k, v in scores.items():
                        if isinstance(v, list): scores = v; break

                # -------------------------------------------------
                # 4. RENDER RESULTS IN STREAMLIT UI
                # -------------------------------------------------
                st.success("Intelligence Brief Generated Successfully!")
                st.markdown(f"### ⚡ Brief for: {user_topic}")
                
                # Create a lookup dictionary for scores by id
                score_map = {item.get("id"): item for item in scores} if isinstance(scores, list) else {}

                for idx, card in enumerate(news_cards, start=1):
                    card_id = card.get("id")
                    sc_data = score_map.get(card_id, {"urgency": 3, "impact": 3, "reason": "N/A"})
                    
                    urgency = sc_data.get("urgency", 3)
                    impact = sc_data.get("impact", 3)
                    total_score = urgency + impact
                    
                    with st.container(border=True):
                        col1, col2, col3, col4 = st.columns([1, 1, 1, 3])
                        col1.markdown(f"**Rank #{idx}**")
                        col2.metric("Score", f"{total_score}/10")
                        col3.text(f"Urgency: {urgency}/5 | Impact: {impact}/5")
                        col4.markdown(f"`{card.get('source', 'Unknown Source')}`")
                        
                        st.subheader(card.get("title"))
                        st.write(card.get("summary"))
                        
                        st.markdown("**Key Takeaways:**")
                        for kp in card.get("key_points", []):
                            st.markdown(f"- {kp}")
                            
                        st.markdown(f"**Why it matters:** {sc_data.get('reason', '')}")
                        st.markdown(f"[Read Original Article]({card.get('link', '#')})")