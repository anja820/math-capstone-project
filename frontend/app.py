import streamlit as st
import requests
import pandas as pd
import json
import os
from datetime import datetime

# Backend URL (FastAPI)
BACKEND_URL = "http://127.0.0.1:8001"

# Create data directory if it doesn't exist
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

st.set_page_config(page_title="InsightPro", layout="wide")


# -------------------------
# Sidebar: backend test + logout
# -------------------------
st.sidebar.write("Backend URL:", BACKEND_URL)

if st.sidebar.button("Test backend connection"):
    try:
        requests.get(BACKEND_URL + "/docs", timeout=5)
        st.sidebar.success("Backend reachable ✅")
    except Exception as e:
        st.sidebar.error(f"Backend NOT reachable ❌: {e}")

if "user_id" in st.session_state:
    if st.sidebar.button("Logout"):
        st.session_state.pop("user_id", None)
        st.rerun()


# -------------------------
# Login / Signup UI
# -------------------------
def login_ui():
    st.title("InsightPro — Login")

    tab1, tab2 = st.tabs(["Login", "Sign up"])

    with tab1:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_pw")
        if st.button("Login"):
            try:
                r = requests.post(
                    f"{BACKEND_URL}/login",
                    json={"email": email, "password": password},
                    timeout=10
                )
                if r.status_code == 200:
                    st.session_state["user_id"] = r.json().get("user_id")
                    st.success("Logged in!")
                    st.rerun()
                else:
                    st.error(r.text)
            except Exception as e:
                st.error(f"Request error: {e}")

    with tab2:
        email = st.text_input("Email", key="signup_email")
        password = st.text_input("Password (min 6 chars)", type="password", key="signup_pw")
        if st.button("Create account"):
            try:
                r = requests.post(
                    f"{BACKEND_URL}/signup",
                    json={"email": email, "password": password},
                    timeout=10
                )
                if r.status_code == 200:
                    st.success("Account created! Now login.")
                else:
                    st.error(r.text)
            except Exception as e:
                st.error(f"Request error: {e}")


# If not logged in, show login screen only
if "user_id" not in st.session_state:
    login_ui()
    st.stop()


# -------------------------
# Main app (after login)
# -------------------------
st.title("InsightPro — Instagram Scan (MVP)")
st.caption("Paste an Instagram username/link. You can run quick math estimate OR real scraping (requires backend ig_login.py session).")

username_or_url = st.text_input(
    "Instagram username or profile link",
    placeholder="@username or https://instagram.com/username"
)

# ---- Quick scrape counts (real numbers) ----
colS1, colS2 = st.columns([1, 3])
with colS1:
    fetch_basic = st.button("Fetch REAL profile numbers (scrape)")
with colS2:
    st.write("Uses backend endpoint `/ig/profile-basic` (fast, real followers/following/posts).")

if fetch_basic:
    if not username_or_url.strip():
        st.error("Please enter an Instagram username or link.")
    else:
        try:
            rr = requests.post(
                f"{BACKEND_URL}/ig/profile-basic",
                json={"profile_url": username_or_url.strip()},
                timeout=90
            )
            if rr.status_code != 200:
                st.error(rr.text)
            else:
                pdata = rr.json()["data"]
                st.success(f"Fetched @{pdata['username']}")
                c1, c2, c3 = st.columns(3)
                c1.metric("Followers", pdata["followers"])
                c2.metric("Following", pdata["following"])
                c3.metric("Posts", pdata["posts_count"])
                st.caption(f"Scraped at: {pdata['scraped_at']}")
        except Exception as e:
            st.error(f"Request failed: {e}")

st.divider()

# ---- Math estimate form (/analyze) ----
st.subheader("Predicted estimate (math model)")
with st.form("form_math"):
    st.write("Optional inputs (makes estimate better)")

    c1, c2, c3, c4, c5 = st.columns(5)
    followers = c1.number_input("Followers", min_value=0, value=1000, step=1)
    following = c2.number_input("Following", min_value=0, value=300, step=1)
    posts = c3.number_input("Posts", min_value=0, value=50, step=1)
    avg_likes = c4.number_input("Avg Likes", min_value=0, value=50, step=1)
    avg_comments = c5.number_input("Avg Comments", min_value=0, value=2, step=1)

    bio = st.text_area("Bio (optional)", height=60)
    captions_raw = st.text_area(
        "Recent captions (optional, one per line)",
        height=140,
        placeholder="Caption 1...\nCaption 2...\nCaption 3..."
    )

    submitted = st.form_submit_button("Run predicted estimate")

if submitted:
    if not username_or_url.strip():
        st.error("Please enter an Instagram username or link.")
    else:
        captions = [x.strip() for x in captions_raw.splitlines() if x.strip()] if captions_raw else None

        payload = {
            "username_or_url": username_or_url.strip(),
            "followers": int(followers),
            "following": int(following),
            "posts": int(posts),
            "avg_likes": int(avg_likes),
            "avg_comments": int(avg_comments),
            "bio_text": bio,
            "recent_captions": captions
        }

        try:
            r = requests.post(f"{BACKEND_URL}/analyze", json=payload, timeout=60)
            if r.status_code != 200:
                st.error(r.text)
            else:
                data = r.json()
                st.subheader(f"Predicted results for @{data['username']}")

                a = data["authenticity"]
                c1, c2, c3 = st.columns(3)
                c1.metric("Fake followers (pred.)", f"{a['fake_pct']}%")
                c2.metric("Real followers (pred.)", f"{a['real_pct']}%")
                c3.metric("Confidence", a["confidence"])

                st.caption(
                    f"Expected authenticity E[X]={a['expected_authenticity']} (X in 0..100), "
                    f"Variance Var(X)={a['variance_authenticity']}"
                )

                with st.expander("Reasons (math heuristics)"):
                    for reason in a["reasons"]:
                        st.write("•", reason)

                st.subheader("Content topic breakdown (%) (from text)")
                st.write(data["content"]["summary"])
                topic_df = pd.DataFrame(
                    [{"topic": k, "percent": v} for k, v in data["content"]["topics"].items()]
                ).sort_values("percent", ascending=False)
                st.bar_chart(topic_df.set_index("topic")["percent"])

                st.subheader("Hashtag graph stats")
                g = data["graph"]
                c1, c2 = st.columns(2)
                c1.metric("Nodes (hashtags)", g["nodes"])
                c2.metric("Edges (co-occurrences)", g["edges"])

                if g["top_hashtags"]:
                    st.write("Top hashtags by degree:")
                    st.dataframe(pd.DataFrame(g["top_hashtags"]))
                else:
                    st.info("No hashtags found. Add captions with #hashtags.")

                st.subheader("Engagement improvement tips (simple rotation)")
                for tip in data["advice"]:
                    st.write("•", tip)

        except Exception as e:
            st.error(f"Request error: {e}")

st.divider()

# ---- Real scraping section (Playwright) ----
st.header("Real scraping audit (requires backend ig_login.py session)")
st.caption("These calls use Playwright inside the backend. Run `python ig_login.py` once in backend folder.")

colA, colB, colC = st.columns(3)
n_posts_scrape = colA.number_input("Scrape last N posts", min_value=1, max_value=60, value=20, step=1)
comments_per_post = colB.number_input("Comments per post", min_value=0, max_value=80, value=20, step=1)
run_profile_scrape = colC.button("Run Profile Scrape")

if run_profile_scrape:
    if not username_or_url.strip():
        st.error("Please enter an Instagram username or link.")
    else:
        with st.spinner("Scraping profile..."):
            rr = requests.post(
                f"{BACKEND_URL}/ig/profile-audit",
                json={
                    "profile_url": username_or_url.strip(),
                    "n_posts": int(n_posts_scrape),
                    "comments_per_post": int(comments_per_post),
                },
                timeout=300
            )
        if rr.status_code != 200:
            st.error(rr.text)
        else:
            pdata = rr.json()["data"]
            
            # Save to JSON file
            username = pdata['username']
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = os.path.join(DATA_DIR, f"profile_audit_{username}_{timestamp}.json")
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(pdata, f, indent=2, ensure_ascii=False)
            
            st.success(f"✅ Data saved to: {filepath}")
            
            st.subheader(f"Scraped profile: @{pdata['username']}")

            c1, c2, c3 = st.columns(3)
            c1.metric("Followers", pdata.get("followers", 0))
            c2.metric("Following", pdata.get("following", 0))
            c3.metric("Posts", pdata.get("posts_count", 0))

            m = pdata["metrics"]
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("ER (avg)", f"{m['er_avg']}%")
            c2.metric("Generic comments", f"{m['generic_comments_pct']}%")
            c3.metric("Dup comments", f"{m['duplicate_comments_pct']}%")
            c4.metric("Risk score", f"{m['risk_score']}/100")

            st.write("### Latest posts")
            rows = []
            for p in pdata["posts"]:
                hashtags_str = ", ".join([f"#{tag}" for tag in p.get("hashtags", [])]) if p.get("hashtags") else ""
                rows.append({
                    "shortcode": p["shortcode"],
                    "date": p.get("date"),
                    "type": p.get("type"),
                    "likes": p.get("likes"),
                    "comments_count": p.get("comments_count"),
                    "hashtags": hashtags_str,
                    "caption": p.get("caption", "")[:100] + "..." if p.get("caption") and len(p.get("caption", "")) > 100 else p.get("caption", ""),
                    "url": p.get("url"),
                })
            st.dataframe(pd.DataFrame(rows))

st.divider()

st.subheader("Follower Sample Audit (1–500 followers)")
col1, col2, col3 = st.columns(3)
sample_size = col1.number_input("Sample size", min_value=1, max_value=500, value=200, step=50)
delay_ms = col2.number_input("Delay per follower (ms)", min_value=300, max_value=2000, value=700, step=50)
run_followers = col3.button("Run Follower Audit")

if run_followers:
    if not username_or_url.strip():
        st.error("Please enter an Instagram username or link.")
    else:
        with st.spinner("Sampling followers (this can take a few minutes)..."):
            rr = requests.post(
                f"{BACKEND_URL}/ig/follower-audit",
                json={
                    "profile_url": username_or_url.strip(),
                    "sample_size": int(sample_size),
                    "delay_ms": int(delay_ms),
                },
                timeout=600
            )
        if rr.status_code != 200:
            st.error(rr.text)
        else:
            fdata = rr.json()["data"]
            
            # Save to JSON file
            username = fdata['target_username']
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = os.path.join(DATA_DIR, f"follower_audit_{username}_{timestamp}.json")
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(fdata, f, indent=2, ensure_ascii=False)
            
            st.success(f"✅ Data saved to: {filepath}")
            st.success("Done.")

            st.metric("Likely bot-like followers (heuristic)", f"{fdata['likely_bot_like_pct']}%")
            st.caption(f"Collected {fdata['sample_size_collected']} followers.")

            st.write("Top reasons (among flagged accounts):")
            if fdata.get("reason_counts"):
                st.dataframe(pd.DataFrame(
                    [{"reason": k, "count": v} for k, v in fdata["reason_counts"].items()]
                ))
            else:
                st.info("No reasons returned (or none flagged).")

            st.write("Follower sample preview (first 30):")
            st.dataframe(pd.DataFrame(fdata.get("followers_sample_preview", [])))
