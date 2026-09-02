import streamlit as st
import requests
import json
import time
from datetime import datetime
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
# 2. Sleeper 대용량 선수 DB Caching Function
# ==========================================
@st.cache_data(ttl=86400)
def fetch_all_sleeper_players():
    try:
        response = requests.get("https://api.sleeper.app/v1/players/nfl", timeout=10)
        return response.json()
    except Exception as e:
        st.error(f"Failed to fetch Sleeper players database: {e}")
        return {}

# ==========================================
# 3. Sidebar Settings & Roster Sync
# ==========================================
with st.sidebar:
    st.header("⚙️ Settings")
    gemini_api_key = st.text_input("Google Gemini API Key", type="password")
    sleeper_username = st.text_input("Sleeper Username")
    sleeper_league_id = st.text_input("Sleeper League ID (Optional)")
    
    st.markdown("---")
    
    # 캐시 초기화 버튼
    if st.button("🔄 Refresh Player Database Cache"):
        st.cache_data.clear()
        st.success("Player DB cache cleared!")

    # 대화 기록 초기화 버튼
    if st.button("🗑️ Clear Chat History"):
        st.session_state.messages = []
        st.rerun()

    st.markdown("---")
    
    # Sleeper 로스터 연동 (League ID 또는 Username)
    if sleeper_username or sleeper_league_id:
        with st.spinner("Fetching Sleeper Roster..."):
            try:
                target_league_id = sleeper_league_id.strip() if sleeper_league_id else None
                user_id = None

                if sleeper_username:
                    user_res = requests.get(f"https://api.sleeper.app/v1/user/{sleeper_username}").json()
                    if user_res and "user_id" in user_res:
                        user_id = user_res["user_id"]

                # League ID를 직접 입력하지 않은 경우 Username 기반으로 2026/2025 리그 조회
                if not target_league_id and user_id:
                    leagues = requests.get(f"https://api.sleeper.app/v1/user/{user_id}/leagues/nfl/2026").json()
                    if not leagues:
                        leagues = requests.get(f"https://api.sleeper.app/v1/user/{user_id}/leagues/nfl/2025").json()
                    if leagues:
                        target_league_id = leagues[0]["league_id"]

                if target_league_id:
                    rosters = requests.get(f"https://api.sleeper.app/v1/league/{target_league_id}/rosters").json()
                    
                    user_roster = None
                    if user_id:
                        user_roster = next((r for r in rosters if r.get("owner_id") == user_id), None)
                    if not user_roster and rosters:
                        user_roster = rosters[0]

                    if user_roster and user_roster.get("players"):
                        all_players = fetch_all_sleeper_players()
                        player_names = []
                        for pid in user_roster["players"]:
                            p_info = all_players.get(pid, {})
                            name = p_info.get("full_name", pid)
                            pos = p_info.get("position", "")
                            team = p_info.get("team", "FA")
                            player_names.append(f"{name} ({pos} - {team})")

                        st.session_state["my_players"] = player_names
                        st.success(f"Loaded {len(player_names)} players (League ID: {target_league_id})")
                        with st.expander("View My Roster"):
                            for p in player_names:
                                st.write(f"- {p}")
                    else:
                        st.info("No active players found in roster.")
                else:
                    st.warning("No active leagues found for this user/ID.")
            except Exception as e:
                st.error(f"Error fetching Sleeper data: {e}")

# 기존 대화 출력
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ==========================================
# 4. User Prompt & Deep Search Gemini AI
# ==========================================
if user_prompt := st.chat_input("Ask about 2026 Draft ADPs, Sleeper Picks, Matchups, CB vs WR, O-Line injuries, or Weather..."):
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

        try:
            client = genai.Client(api_key=gemini_api_key)
        except Exception as e:
            status_placeholder.error(f"Client Init Error: {e}")
            st.stop()

        roster_data = st.session_state.get("my_players", [])

        if len(roster_data) > 0:
            current_mode = "WEEK_TO_WEEK_MATCHUP_MODE"
            mode_context = f"Active User Roster ({len(roster_data)} players): {json.dumps(roster_data)}"
        else:
            current_mode = "PRE_DRAFT_STRATEGY_MODE"
            mode_context = "User status: Pre-Draft (No roster synced yet)."

        today_str = datetime.now().strftime("%B %d, %Y")

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
1. Rely 100% on live Google Search results anchored around {today_str}. Never use outdated internal memory.
2. Strictly verify 2026 Free Agency and Trade moves before confirming player teams.
3. Ignore 2025 or older roster configurations unless explicitly requested.

1. PRE-DRAFT ANALYSIS REQUIREMENTS (If PRE_DRAFT_STRATEGY_MODE):
   - **2026 ADP & Value Check:** Cross-reference current 2026 Superflex PPR ADPs.
   - **O-Line Unit Rankings:** Search latest PFF/PFR 2026 Offensive Line rankings and critical starter injuries.
   - **Strength of Schedule (SOS):** Analyze season-long schedule difficulty.
   - **Bust & Sleeper Targets:** Highlight injury red flags and high-upside late-round sleepers.

2. WEEK-TO-WEEK MATCHUP ANALYSIS REQUIREMENTS (If WEEK_TO_WEEK_MATCHUP_MODE):
   - **All-Position Defensive Matchups & Coverage:** 
     * WRs: Search CB vs WR shadow coverage and slot/outside vulnerability.
     * RBs: Search OL vs DL win rates, stacked box percentage, and run defense DVOA/DvP.
     * TEs: Search Linebacker/Safety coverage efficiency and Defense vs TE rankings.
     * QBs: Search opponent pressure rates, blitz frequency, and pass-rush match-ups.
   - **Game-Day Stadium & Weather Impact:** 
     * Check if Dome or Retractable Roof. If INDOORS/DOME, state weather is a NON-FACTOR (0% impact).
     * If OUTDOORS, search forecasts (wind >15mph, heavy rain/snow) and evaluate impact.
   - **Start / Sit & Waiver Wire:** Provide Start/Sit recommendations with confidence percentages.
   - **O-Line Injury Ripple Effect:** Assess impact on QB time-to-throw and RB yards before contact.

3. OUTPUT FORMAT:
   - Structured, bulleted analysis with clear data points.
   - ALWAYS RESPOND FULLY IN ENGLISH.
"""

        try:
            response = client.models.generate_content(
                model="gemini-3.5-flash",
                contents=user_prompt,
                config={
                    "system_instruction": system_instruction,
                    "tools": [{"google_search": {}}],
                    "temperature": 0.1
                }
            )
            response_text = response.text
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                status_placeholder.markdown("⚠️ *Quota limit reached. Retrying in 3 seconds...*")
                time.sleep(3)
                try:
                    response = client.models.generate_content(
                        model="gemini-3.5-flash",
                        contents=user_prompt,
                        config={
                            "system_instruction": system_instruction,
                            "temperature": 0.1
                        }
                    )
                    response_text = response.text
                except Exception as fallback_err:
                    status_placeholder.error(f"❌ Error: {fallback_err}")
            else:
                status_placeholder.error(f"❌ Error: {e}")

        if response_text:
            status_placeholder.empty()
            st.markdown(response_text)
            st.session_state.messages.append({"role": "assistant", "content": response_text})
