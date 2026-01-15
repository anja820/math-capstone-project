from db import init_db
from auth_local import create_user, login_user

from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

import numpy as np
import re
import networkx as nx

from ig_tools import profile_basic, profile_audit, follower_audit

app = FastAPI(title="InsightPro Backend")

init_db()

HASHTAG_RE = re.compile(r"#([A-Za-z0-9_]+)")


# -------------------------
# Models (input/output)
# -------------------------
class AnalyzeRequest(BaseModel):
    username_or_url: str
    followers: Optional[int] = 0
    following: Optional[int] = 0
    posts: Optional[int] = 0
    avg_likes: Optional[int] = 0
    avg_comments: Optional[int] = 0
    bio_text: Optional[str] = ""
    recent_captions: Optional[List[str]] = None


class IgProfileBasicRequest(BaseModel):
    profile_url: str


class IgProfileAuditRequest(BaseModel):
    profile_url: str
    n_posts: Optional[int] = 30
    comments_per_post: Optional[int] = 30


class IgFollowerAuditRequest(BaseModel):
    profile_url: str
    sample_size: Optional[int] = 200  # 50–500
    delay_ms: Optional[int] = 700     # 300–2000


class SignupRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


# -------------------------
# Helper: normalize username
# -------------------------
def normalize_username(s: str) -> str:
    s = s.strip()
    m = re.search(r"instagram\.com/([A-Za-z0-9._]+)/?", s)
    if m:
        return m.group(1)
    if s.startswith("@"):
        s = s[1:]
    return s


# -------------------------
# Math: Discrete probability
# -------------------------
def authenticity_estimate(data: Dict[str, Any]) -> Dict[str, Any]:
    followers = max(int(data.get("followers") or 0), 1)
    following = max(int(data.get("following") or 0), 1)
    posts = max(int(data.get("posts") or 0), 0)
    avg_likes = max(int(data.get("avg_likes") or 0), 0)
    avg_comments = max(int(data.get("avg_comments") or 0), 0)

    xs = np.arange(0, 101)

    er = (avg_likes + 3 * avg_comments) / followers

    if er < 0.005:
        mu, sigma = 35, 18
        reason = "Very low engagement rate → possible fake/low-quality followers."
    elif er < 0.02:
        mu, sigma = 60, 15
        reason = "Moderate-low engagement rate."
    elif er < 0.06:
        mu, sigma = 75, 12
        reason = "Healthy engagement rate."
    else:
        mu, sigma = 65, 20
        reason = "Very high engagement rate → could be viral/small-account effect (uncertainty)."

    L1 = np.exp(-0.5 * ((xs - mu) / sigma) ** 2) + 1e-12

    ratio = followers / following
    if ratio < 0.5:
        mu2, sigma2 = 55, 18
        reason2 = "Followers lower than following → early-stage or follow-back behavior."
    elif ratio < 2:
        mu2, sigma2 = 65, 14
        reason2 = "Balanced follower/following ratio."
    else:
        mu2, sigma2 = 70, 14
        reason2 = "High follower/following ratio."

    L2 = np.exp(-0.5 * ((xs - mu2) / sigma2) ** 2) + 1e-12

    if posts < 10:
        mu3, sigma3 = 55, 20
        reason3 = "Few posts → higher uncertainty."
    elif posts < 50:
        mu3, sigma3 = 65, 16
        reason3 = "Moderate number of posts."
    else:
        mu3, sigma3 = 70, 14
        reason3 = "Many posts → more stable estimate."

    L3 = np.exp(-0.5 * ((xs - mu3) / sigma3) ** 2) + 1e-12

    posterior = (L1 * L2 * L3)
    posterior = posterior / posterior.sum()

    EX = float(np.sum(xs * posterior))
    VarX = float(np.sum((xs - EX) ** 2 * posterior))

    fake_pct = float(max(0.0, min(100.0, 100.0 - EX)))
    real_pct = 100.0 - fake_pct

    if VarX < 120:
        confidence = "High"
    elif VarX < 250:
        confidence = "Medium"
    else:
        confidence = "Low"

    return {
        "fake_pct": round(fake_pct, 2),
        "real_pct": round(real_pct, 2),
        "expected_authenticity": round(EX, 2),
        "variance_authenticity": round(VarX, 2),
        "confidence": confidence,
        "reasons": [reason, reason2, reason3],
    }


# -------------------------
# Graphs: hashtag co-occurrence
# -------------------------
def hashtag_graph_stats(captions: Optional[List[str]]) -> Dict[str, Any]:
    if not captions:
        return {"nodes": 0, "edges": 0, "top_hashtags": []}

    G = nx.Graph()
    for cap in captions:
        tags = [t.lower() for t in HASHTAG_RE.findall(cap or "")]
        tags = list(dict.fromkeys(tags))
        for t in tags:
            G.add_node(t)
        for i in range(len(tags)):
            for j in range(i + 1, len(tags)):
                a, b = tags[i], tags[j]
                if G.has_edge(a, b):
                    G[a][b]["weight"] += 1
                else:
                    G.add_edge(a, b, weight=1)

    top = sorted(G.degree(), key=lambda x: x[1], reverse=True)[:10]
    top_list = [{"hashtag": h, "degree": int(d)} for h, d in top]

    return {"nodes": G.number_of_nodes(), "edges": G.number_of_edges(), "top_hashtags": top_list}


# -------------------------
# Simple content breakdown (text keywords MVP)
# -------------------------
TOPICS = [
    "fashion", "beauty", "fitness", "food", "travel", "technology",
    "business", "lifestyle", "music", "sports", "education"
]

KEYWORDS = {
    "fashion": ["outfit", "style", "fashion", "clothes", "dress"],
    "beauty": ["makeup", "skincare", "beauty"],
    "fitness": ["gym", "workout", "fitness", "training"],
    "food": ["food", "recipe", "restaurant", "cook"],
    "travel": ["travel", "trip", "vacation", "hotel", "flight"],
    "technology": ["tech", "ai", "software", "app", "gadgets"],
    "business": ["business", "startup", "marketing", "brand"],
    "lifestyle": ["life", "daily", "routine", "vlog"],
    "music": ["music", "song", "album"],
    "sports": ["match", "game", "sport", "team"],
    "education": ["learn", "study", "course", "lesson"],
}


def content_breakdown(bio: str, captions: Optional[List[str]]) -> Dict[str, Any]:
    text = (bio or "") + "\n" + "\n".join(captions or [])
    text_l = text.lower()

    counts = {t: 0 for t in TOPICS}
    for topic, kws in KEYWORDS.items():
        for kw in kws:
            counts[topic] += text_l.count(kw)

    total = sum(counts.values())
    if total == 0:
        probs = {t: 0.0 for t in TOPICS}
        probs["lifestyle"] = 1.0
        summary = "Not enough text to classify; defaulted to lifestyle."
    else:
        probs = {t: counts[t] / total for t in TOPICS}
        top3 = sorted(probs.items(), key=lambda x: x[1], reverse=True)[:3]
        summary = f"Main topics: {top3[0][0]}, {top3[1][0]}, {top3[2][0]}."

    topics_pct = {t: round(probs[t] * 100.0, 2) for t in TOPICS}
    return {"topics": topics_pct, "summary": summary}


# -------------------------
# Auth endpoints
# -------------------------
@app.post("/signup")
def signup(req: SignupRequest):
    create_user(req.email, req.password)
    return {"ok": True}


@app.post("/login")
def login(req: LoginRequest):
    user_id = login_user(req.email, req.password)
    return {"ok": True, "user_id": user_id}


# -------------------------
# IG scraping endpoints
# -------------------------
@app.post("/ig/profile-basic")
async def ig_profile_basic(req: IgProfileBasicRequest):
    data = await profile_basic(req.profile_url)
    return {"ok": True, "data": data}


@app.post("/ig/profile-audit")
async def ig_profile_audit(req: IgProfileAuditRequest):
    data = await profile_audit(
        req.profile_url,
        n_posts=max(5, min(int(req.n_posts or 30), 60)),
        comments_per_post=max(0, min(int(req.comments_per_post or 30), 80)),
    )
    return {"ok": True, "data": data}


@app.post("/ig/follower-audit")
async def ig_follower_audit(req: IgFollowerAuditRequest):
    data = await follower_audit(
        req.profile_url,
        sample_size=max(50, min(int(req.sample_size or 200), 500)),
        delay_ms=max(300, min(int(req.delay_ms or 700), 2000)),
    )
    return {"ok": True, "data": data}


# -------------------------
# Advice rotation
# -------------------------
def advice_rotation(username: str) -> List[str]:
    bundles = [
        ["Post 3–4x/week consistently.", "Reply to comments in first hour.", "Use fewer but relevant hashtags."],
        ["Try Reels with a strong hook.", "Ask a question in caption.", "Collaborate with similar creators."],
        ["Focus on your top 2 content pillars.", "Test two posting times.", "Double down on best format."],
    ]
    idx = sum(ord(c) for c in username) % len(bundles)
    return bundles[idx]


# -------------------------
# Predicted /analyze endpoint (math model)
# -------------------------
@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    username = normalize_username(req.username_or_url)

    auth = authenticity_estimate(req.model_dump())
    content = content_breakdown(req.bio_text or "", req.recent_captions)
    gstats = hashtag_graph_stats(req.recent_captions)
    advice = advice_rotation(username)

    return {
        "username": username,
        "authenticity": auth,
        "content": content,
        "graph": gstats,
        "advice": advice,
    }
