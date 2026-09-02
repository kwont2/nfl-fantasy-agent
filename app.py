import streamlit as st
import requests
import json
import time
from google import genai

# ==========================================
# 1. Page Configuration & Chat History Init
# ==========================================
st.set_page_config(page_title="NFL Fantasy AI Agent Pro", page_icon="🏈", layout="wide")

st.title("🏈 NFL Fantasy Football Interactive AI Agent (Pro Version)")
st.caption("Powered by Sleeper API & Google Gemini (Advanced Deep Grounding)")

# 대화 기록 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []

# ==========================================
# Sleeper 대용량 선수 DB Caching Function (에러 및 속도 방지)
# ==========================================
@st.cache_data(ttl=86400)  # 24시간 동안 메모리에 저장하여 재다운로드 방지
def fetch_all_sleeper_players():
    try:
        response = requests.get("https://api.sleeper.app/v1/players/nfl", timeout=10)
        return response.json()
    except Exception as e:
        st.error(f"Failed to fetch Sleeper players database: {e}")
        return {}

# ==========================================
# 2. Sidebar Settings & Roster Sync
# ==========================================
with st.sidebar:
    st.header("⚙️ Settings")
    gemini_api_key = st.text_input("Google Gemini API Key", type="password")
    sleeper_username = st.text_input("Sleeper Username")
    league_id = st.text_input("Sleeper League ID")
    
    st.markdown("---")
    
    # 1) Sleeper 로스터 동기화 버튼
    if st.button("🔄 Sync Sleeper Roster"):
        if not sleeper_username or not league_id:
            st.error("Please enter both Sleeper Username and League ID.")
        else:
            try:
                # 1. User ID 조회
                user_res = requests.get(f"https://api.sleeper.app/v1/user/{sleeper_username}").json()
                user_id = user_res['user_id']
                
                # 2. League 내 내 로스터 찾기
                rosters = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/rosters").json()
                my_roster = next((r for r in rosters if r.get('owner_id') == user_id), None)
                
                # 3. 캐싱된 대용량 선수 DB 불러오기 (속도 0.01초)
                players = fetch_all_sleeper_players()
                
                my_players = []
                if my_roster and 'players' in my_roster and my_roster['players']:
                    for p_id in my_roster['players']:
                        p_info = players.get(p_id, {})
                        player_name = p_info.get('full_name', p_id)
                        pos = p_info.get('position', 'UNK')
                        team = p_info.get('team', 'FA')
                        # AI 환각 방지를 위한 2026 verification 문구 첨부
                        my_players.append(f"{player_name} ({pos} - Sleeper List: {team})")
                
                st.session_state["my_players"] = my_players
                st.success(f"Roster synced successfully! ({len(my_players)} players)")
            except Exception as e:
                st.error(f"Failed to fetch Sleeper data: {e}")

    # 2) 대화 기록 초기화(Reset) 버튼
    if st.button("🗑️ Clear Chat History"):
        st.session_state.messages = []
        st.rerun()

# ==========================================
# 3. Render Chat Log
# ==========================================
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

from datetime import datetime

# ==========================================
# 4. User Prompt & Deep Search Gemini AI
# ==========================================
if user_prompt := st.chat_input("Ask about 2026 Draft ADPs, Sleeper Picks, Match`up`s, CB vs WR, O-Line injuries, or Weather..."):
    if not gemini_api_key:
        st.error("⚠️ Please enter your Gemini API Key in the sidebar first!")
        st.stop()

    st.session_state.messages.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_prompt)

    with st.chat_message("assistant"):
        response_text = None
        status_placeholder = st.empty()
        status_placeholder.markdown("🧠 *Executing Deep 2026 Live Search (FantasyPros, PFF, Rotoworld, Athletic, Weather, Matchups)...*")
        
        client = genai.Client(api_key=gemini_api_key)
        roster_data = st.session_state.get("my_players", [])
        
        # Determine current mode automatically based on roster length
        if len(roster_data) > 0:
            current_mode = "WEEK_TO_WEEK_MATCHUP_MODE"
            mode_context = f"Active User Roster ({len(roster_data)} players): {json.dumps(roster_data)}"
        else:
            current_mode = "PRE_DRAFT_STRATEGY_MODE"
            mode_context = "User status: Pre-Draft (No roster synced yet)."

        # 오늘 날짜 동적 생성 (최신 정보 검색 기준)
        today_str = datetime.now().strftime("%B %d, %Y")

        # Advanced System Instruction with Granular Analytics & Media Sources
        system_instruction = f"""
You are an elite, world-class NFL Chief Analytics Officer and Fantasy Football AI Strategist.
Today's Date: {today_str} (Use this date as your primary benchmark for live news and 2026 season context).
Current Operating Mode: {current_mode}
{mode_context}

CRITICAL DATA SOURCES TO QUERY (LIVE SEARCH GROUNDING):
Search live breaking news, metrics, and expert consensus from top sources including:
- Expert Ratings & ADPs: FantasyPros, CBS Sports, ESPN Fantasy, Yahoo Fantasy, PlayerProfiler, Fantasy Alarm
- Deep Metrics & Film/Projections: PFF (Pro Football Focus), Sharp Football Analysis, Establish The Run, RotoViz, Football Outsiders/FTN
- Breaking News & Beat Reports: Rotoworld (NBC Sports EDGE), The Athletic, Bleacher Report, Field Level Media, Reddit r/fantasyfootball

STRICT FACT-CHECKING & HALLUCINATION PREVENTION:
1. Rely 100% on live Google Search results anchored around {today_str}. Never use outdated internal memory for rosters, trades, or injuries.
2. Strictly verify 2026 Free Agency and Trade moves before confirming player teams (e.g., Kenneth Walker III is on KC, Travis Etienne Jr. is on NO).
3. Ignore 2025 or older roster configurations unless explicitly requested.

1. PRE-DRAFT ANALYSIS REQUIREMENTS (If PRE_DRAFT_STRATEGY_MODE):
   - **2026 ADP & Value Check:** Cross-reference current 2026 Superflex PPR ADPs to flag reaching vs value picks.
   - **O-Line Unit Rankings:** Search latest PFF/PFR 2026 Offensive Line rankings and critical starter injuries.
   - **Strength of Schedule (SOS):** Analyze season-long schedule difficulty for QBs, RBs, WRs, and TEs.
   - **Bust & Sleeper Targets:** Highlight injury red flags, roster depth chart battles, and high-upside late-round sleepers/handcuffs.

2. WEEK-TO-WEEK MATCHUP ANALYSIS REQUIREMENTS (If WEEK_TO_WEEK_MATCHUP_MODE):
   - **All-Position Defensive Matchups & Coverage:** 
     * WRs: Search CB vs WR shadow coverage, slot vs outside vulnerability, and target match-up ratings.
     * RBs: Search OL vs DL win rates, opponent stacked box percentage (8+ in box), and run defense DVOA/DvP.
     * TEs: Search opponent Linebacker/Safety coverage efficiency and Defense vs TE rankings.
     * QBs: Search opponent pressure rates, blitz frequency, and pass-rush match-ups.
   - **Game-Day Stadium & Weather Impact:** 
     * Check if the game is played in a Dome or Retractable Roof stadium. If INDOORS/DOME, explicitly state weather is a NON-FACTOR (0% impact).
     * If OUTDOORS, search exact forecasts (wind speed >15mph, heavy rain/snow/extreme cold) and evaluate impact on passing/kicking.
   - **Start / Sit & Waiver Wire:** Provide definitive Start/Sit recommendations with confidence percentages and current waiver wire targets.
   - **O-Line Injury Ripple Effect:** Assess how O-Line injuries affect QB time-to-throw, pressure rates, and RB yards before contact (YBC).

3. OUTPUT FORMAT:
   - Provide highly detailed, structured, bulleted analysis with clear data points.
   - Maintain a professional, sharp, expert analyst tone.
   - ALWAYS RESPOND FULLY IN ENGLISH.
"""

        # API Execution with Google Search Tool & Low Temperature Enabled
        try:
            response = client.models.generate_content(
                model="gemini-3.7-flash",
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    temperature=0.1
                )
            )
            response_text = response.text
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                status_placeholder.markdown("⚠️ *Quota limit reached. Retrying without live search...*")
                time.sleep(3)
                try:
                    response = client.models.generate_content(
                        model="gemini-3.7-flash",
                        contents=system_instruction + "\nUser Question: " + user_prompt,
                        config=types.GenerateContentConfig(
                            temperature=0.1
                        )
                    )
                    response_text = response.text
                except Exception as fallback_err:
                    status_placeholder.error(f"❌ Error: {fallback_err}")
            else:
                status_placeholder.error(f"❌ Error: {e}")

        if response_text:
            status_placeholder.empty()
            st.markdown(response_text)
            st.session_state.messages.append({"role": "assistant", "content": response_text})``