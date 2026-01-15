import re
from urllib.parse import urlparse
from datetime import datetime
from typing import Any, Dict, List, Tuple

import numpy as np
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

import os

# ✅ IMPORTANT: absolute path so uvicorn working dir doesn't break session loading
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSION_DIR = os.path.join(BASE_DIR, "pw_ig_session")


# ---------------------------
# URL + auth helpers
# ---------------------------
def extract_username(profile_url: str) -> str:
    u = urlparse(profile_url)
    parts = [p for p in u.path.split("/") if p]
    if not parts:
        raise ValueError("No username found in URL.")
    username = parts[0].strip()
    if username.lower() in {"p", "reel", "stories", "explore", "accounts"}:
        raise ValueError("That URL doesn't look like a profile URL.")
    return username


def ensure_logged_in_or_raise(current_url: str):
    if "accounts/login" in current_url or "/login" in current_url:
        raise RuntimeError("Not logged in. Run ig_login.py once to save session.")


# ---------------------------
# JSON fetch (reliable counts/posts)
# ---------------------------
async def fetch_web_profile_info(context, username: str) -> Dict[str, Any]:
    """
    Instagram internal JSON endpoint for profile counts and recent posts.
    Works best with logged-in session.
    """
    url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
    headers = {
        "Accept": "application/json",
        "Referer": f"https://www.instagram.com/{username}/",
        "X-IG-App-ID": "936619743392459",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    resp = await context.request.get(url, headers=headers)
    if resp.status != 200:
        body = await resp.text()
        raise RuntimeError(f"web_profile_info failed HTTP {resp.status}: {body[:250]}")
    return await resp.json()


def parse_profile_from_webjson(web_json: Dict[str, Any]) -> Tuple[int, int, int, List[str]]:
    user = (web_json.get("data") or {}).get("user") or {}

    followers = int(((user.get("edge_followed_by") or {}).get("count")) or 0)
    following = int(((user.get("edge_follow") or {}).get("count")) or 0)
    posts_count = int(((user.get("edge_owner_to_timeline_media") or {}).get("count")) or 0)

    edges = ((user.get("edge_owner_to_timeline_media") or {}).get("edges")) or []
    shortcodes: List[str] = []
    for e in edges:
        node = (e or {}).get("node") or {}
        sc = node.get("shortcode")
        if sc:
            shortcodes.append(sc)

    return followers, following, posts_count, shortcodes


def parse_counts(web_json: Dict[str, Any]) -> Dict[str, int]:
    followers, following, posts_count, _ = parse_profile_from_webjson(web_json)
    return {"followers": followers, "following": following, "posts_count": posts_count}


# ---------------------------
# Comment + metrics scoring
# ---------------------------
def is_generic_comment(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t or len(t) <= 2:
        return True

    generic_phrases = {
        "nice", "nice pic", "nice post", "cool", "wow", "amazing", "great", "love this",
        "so nice", "beautiful", "awesome", "great pic", "lovely", "perfect"
    }
    if t in generic_phrases:
        return True

    letters = sum(ch.isalpha() for ch in t)
    if letters <= 3 and len(t) <= 12:
        return True

    if re.fullmatch(r"[\W_]+", t):
        return True

    return False


def compute_profile_metrics(profile: Dict[str, Any]) -> Dict[str, Any]:
    followers = int(profile.get("followers", 0) or 0)
    posts = profile.get("posts", [])

    likes = np.array([p.get("likes", 0) for p in posts], dtype=float) if posts else np.array([])
    comcnt = np.array([p.get("comments_count", 0) for p in posts], dtype=float) if posts else np.array([])

    avg_likes = float(likes.mean()) if likes.size else 0.0
    med_likes = float(np.median(likes)) if likes.size else 0.0
    avg_comments = float(comcnt.mean()) if comcnt.size else 0.0
    med_comments = float(np.median(comcnt)) if comcnt.size else 0.0

    er_avg = float((avg_likes + avg_comments) / followers) if followers > 0 else 0.0
    er_med = float((med_likes + med_comments) / followers) if followers > 0 else 0.0

    like_cv = float(likes.std() / likes.mean()) if likes.size and likes.mean() > 0 else 0.0
    comment_cv = float(comcnt.std() / comcnt.mean()) if comcnt.size and comcnt.mean() > 0 else 0.0

    all_comments: List[Dict[str, str]] = []
    for p in posts:
        all_comments.extend(p.get("comments", []))

    total_comments = len(all_comments)
    generic = sum(1 for c in all_comments if is_generic_comment(c.get("text", "")))
    generic_pct = (generic / total_comments) * 100.0 if total_comments else 0.0

    texts = [c.get("text", "").strip().lower() for c in all_comments if c.get("text")]
    dup_pct = 0.0
    if texts:
        unique = len(set(texts))
        dup_pct = (1 - unique / len(texts)) * 100.0

    commenters = [c.get("username", "").strip().lower() for c in all_comments if c.get("username")]
    repeat_commenters_pct = 0.0
    if commenters:
        unique_c = len(set(commenters))
        repeat_commenters_pct = (1 - unique_c / len(commenters)) * 100.0

    risk = 0.0
    if followers < 10_000:
        if er_avg < 0.01:
            risk += 25
    elif followers < 100_000:
        if er_avg < 0.007:
            risk += 25
    else:
        if er_avg < 0.003:
            risk += 25

    if generic_pct > 40:
        risk += 20
    elif generic_pct > 25:
        risk += 12

    if dup_pct > 20:
        risk += 15
    elif dup_pct > 10:
        risk += 8

    if repeat_commenters_pct > 30:
        risk += 10
    elif repeat_commenters_pct > 15:
        risk += 5

    if likes.size >= 10 and like_cv < 0.15:
        risk += 10
    if comcnt.size >= 10 and comment_cv < 0.20:
        risk += 5

    risk = float(max(0.0, min(100.0, risk)))

    return {
        "avg_likes": round(avg_likes, 2),
        "median_likes": round(med_likes, 2),
        "avg_comments": round(avg_comments, 2),
        "median_comments": round(med_comments, 2),
        "er_avg": round(er_avg * 100, 3),
        "er_median": round(er_med * 100, 3),
        "like_cv": round(like_cv, 3),
        "comment_cv": round(comment_cv, 3),
        "generic_comments_pct": round(generic_pct, 2),
        "duplicate_comments_pct": round(dup_pct, 2),
        "repeat_commenters_pct": round(repeat_commenters_pct, 2),
        "risk_score": round(risk, 1),
    }


# ---------------------------
# Post comments (best-effort)
# ---------------------------
async def scrape_post_comments(page, shortcode: str, max_comments: int = 30) -> List[Dict[str, str]]:
    url = f"https://www.instagram.com/p/{shortcode}/"
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        ensure_logged_in_or_raise(page.url)
        await page.wait_for_timeout(1200)
    except PlaywrightTimeoutError:
        return []

    comments: List[Dict[str, str]] = []
    candidates = await page.query_selector_all("article ul li")

    for li in candidates:
        if len(comments) >= max_comments:
            break
        user_el = await li.query_selector("a")
        text_el = await li.query_selector("span")
        if not user_el or not text_el:
            continue

        username = (await user_el.inner_text() or "").strip()
        text = (await text_el.inner_text() or "").strip()
        if not username or not text:
            continue
        if "liked by" in text.lower():
            continue

        comments.append({"username": username, "text": text})

    # de-dup
    seen = set()
    out = []
    for c in comments:
        key = (c["username"].lower(), c["text"].lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


# ---------------------------
# ✅ profile_basic (fast counts only)
# ---------------------------
async def profile_basic(profile_url: str) -> Dict[str, Any]:
    username = extract_username(profile_url)

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=True,
        )
        page = await context.new_page()

        await page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=30_000)
        ensure_logged_in_or_raise(page.url)

        web_json = await fetch_web_profile_info(context, username)
        counts = parse_counts(web_json)

        await context.close()

    return {
        "username": username,
        "profile_url": f"https://www.instagram.com/{username}/",
        **counts,
        "scraped_at": datetime.utcnow().isoformat() + "Z",
    }


# ---------------------------
# ✅ profile_audit (counts + posts + comments metrics)
# ---------------------------
async def profile_audit(profile_url: str, n_posts: int = 30, comments_per_post: int = 30) -> Dict[str, Any]:
    username = extract_username(profile_url)
    n_posts = max(5, min(int(n_posts), 60))
    comments_per_post = max(0, min(int(comments_per_post), 80))

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=True,
        )
        page = await context.new_page()

        await page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=30_000)
        ensure_logged_in_or_raise(page.url)

        web_json = await fetch_web_profile_info(context, username)
        followers, following, posts_count, shortcodes = parse_profile_from_webjson(web_json)
        shortcodes = shortcodes[:n_posts]

        posts: List[Dict[str, Any]] = []
        for sc in shortcodes:
            post_url = f"https://www.instagram.com/p/{sc}/"
            try:
                await page.goto(post_url, wait_until="domcontentloaded", timeout=30_000)
                ensure_logged_in_or_raise(page.url)
                await page.wait_for_timeout(1200)
            except PlaywrightTimeoutError:
                continue

            post_date_iso = None
            time_el = await page.query_selector("time")
            if time_el:
                dt = await time_el.get_attribute("datetime")
                if dt:
                    post_date_iso = dt

            post_type = "post"
            canonical = await page.query_selector('link[rel="canonical"]')
            if canonical:
                canon_href = await canonical.get_attribute("href") or ""
                if "/reel/" in canon_href:
                    post_type = "reel"

            likes_count = 0
            comments_count = 0
            try:
                body_text = await page.inner_text("body")
            except Exception:
                body_text = ""

            mlikes = re.search(r"([\d,]+)\s+likes", body_text, re.IGNORECASE)
            if mlikes:
                likes_count = int(mlikes.group(1).replace(",", ""))

            mcom = re.search(r"View all\s+([\d,]+)\s+comments", body_text, re.IGNORECASE)
            if mcom:
                comments_count = int(mcom.group(1).replace(",", ""))
            else:
                lis = await page.query_selector_all("article ul li")
                if lis:
                    comments_count = max(0, len(lis) - 1)

            comments = await scrape_post_comments(page, sc, max_comments=comments_per_post)

            posts.append({
                "shortcode": sc,
                "url": post_url,
                "date": post_date_iso,
                "type": post_type,
                "likes": likes_count,
                "comments_count": comments_count,
                "comments": comments,
            })

            await page.wait_for_timeout(600)

        await context.close()

    profile = {
        "username": username,
        "profile_url": f"https://www.instagram.com/{username}/",
        "followers": followers,
        "following": following,
        "posts_count": posts_count,
        "scraped_at": datetime.utcnow().isoformat() + "Z",
        "posts": posts,
    }
    profile["metrics"] = compute_profile_metrics(profile)
    return profile


# ---------------------------
# follower audit
# ---------------------------
def looks_botty_username(u: str) -> bool:
    if not u:
        return True
    digits = sum(ch.isdigit() for ch in u)
    if digits >= max(5, int(len(u) * 0.4)):
        return True
    if re.search(r"^[a-z]{2,6}\d{4,}$", u, re.IGNORECASE):
        return True
    return False


def classify_likely_fake(f: Dict[str, Any]) -> Tuple[bool, List[str]]:
    reasons = []
    posts = f.get("posts", 0)
    followers = f.get("followers", 0)
    following = f.get("following", 0)
    has_bio = f.get("has_bio", False)
    is_private = f.get("is_private", False)
    username = f.get("username", "")

    if not is_private and posts == 0:
        reasons.append("0 posts (public)")
    if not is_private and not has_bio:
        reasons.append("no bio (public)")
    if following >= 1500 and followers <= 50:
        reasons.append("following very high, followers very low")
    if following >= 3000:
        reasons.append("following extremely high")
    if looks_botty_username(username):
        reasons.append("bot-like username pattern")

    score = 0
    for r in reasons:
        if "following very high" in r:
            score += 3
        elif "0 posts" in r:
            score += 2
        elif "bot-like username" in r:
            score += 2
        else:
            score += 1

    if is_private:
        score = max(0, score - 1)

    return (score >= 4), reasons


async def collect_follower_usernames(page, target_username: str, sample_size: int) -> List[str]:
    profile_url = f"https://www.instagram.com/{target_username}/"
    await page.goto(profile_url, wait_until="domcontentloaded", timeout=30_000)
    ensure_logged_in_or_raise(page.url)
    await page.wait_for_timeout(1200)

    link = await page.query_selector(f'a[href="/{target_username}/followers/"]') or await page.query_selector('a[href$="/followers/"]')
    if not link:
        raise RuntimeError("Could not find followers link (IG UI changed).")

    await link.click()
    await page.wait_for_timeout(1200)

    dialog = await page.query_selector('div[role="dialog"]')
    if not dialog:
        raise RuntimeError("Followers dialog did not open.")

    scroll_box = (
        await dialog.query_selector("div._aano")
        or await dialog.query_selector('div[style*="overflow"]')
        or await dialog.query_selector('div[style*="overflow-y"]')
    )
    if not scroll_box:
        raise RuntimeError("Could not find followers scroll container (IG UI changed).")

    usernames: List[str] = []

    async def harvest():
        anchors = await dialog.query_selector_all('a[href^="/"]')
        for a in anchors:
            href = await a.get_attribute("href")
            if not href:
                continue
            m = re.match(r"^/([A-Za-z0-9._]+)/$", href)
            if m:
                u = m.group(1)
                if u.lower() != target_username.lower():
                    usernames.append(u)

    for _ in range(90):
        await harvest()
        usernames[:] = list(dict.fromkeys(usernames))
        if len(usernames) >= sample_size:
            break
        await scroll_box.evaluate("(el) => { el.scrollTop = el.scrollTop + el.clientHeight * 2; }")
        await page.wait_for_timeout(850)

    return usernames[:sample_size]


async def follower_audit(profile_url: str, sample_size: int = 200, delay_ms: int = 700) -> Dict[str, Any]:
    target_username = extract_username(profile_url)
    sample_size = max(50, min(int(sample_size), 500))
    delay_ms = max(300, min(int(delay_ms), 2000))

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=True,
        )
        page = await context.new_page()

        await page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=30_000)
        ensure_logged_in_or_raise(page.url)
        await page.wait_for_timeout(900)

        follower_usernames = await collect_follower_usernames(page, target_username, sample_size)

        followers_data: List[Dict[str, Any]] = []
        fake_flags: List[bool] = []

        for u in follower_usernames:
            try:
                wj = await fetch_web_profile_info(context, u)
                followers, following, posts_count, _ = parse_profile_from_webjson(wj)

                user = (wj.get("data") or {}).get("user") or {}
                is_private = bool(user.get("is_private", False))
                biography = (user.get("biography") or "")
                has_bio = bool(biography.strip())

                stats = {
                    "username": u,
                    "url": f"https://www.instagram.com/{u}/",
                    "followers": followers,
                    "following": following,
                    "posts": posts_count,
                    "is_private": is_private,
                    "has_bio": has_bio,
                }
            except Exception:
                stats = {
                    "username": u,
                    "url": f"https://www.instagram.com/{u}/",
                    "followers": 0,
                    "following": 0,
                    "posts": 0,
                    "is_private": False,
                    "has_bio": False,
                }

            likely_fake, reasons = classify_likely_fake(stats)
            stats["likely_fake"] = likely_fake
            stats["reasons"] = reasons

            followers_data.append(stats)
            fake_flags.append(likely_fake)

            await page.wait_for_timeout(delay_ms)

        await context.close()

    likely_fake_pct = float(np.mean(fake_flags) * 100.0) if fake_flags else 0.0

    reason_counts: Dict[str, int] = {}
    for f in followers_data:
        if f.get("likely_fake"):
            for r in f.get("reasons", []):
                reason_counts[r] = reason_counts.get(r, 0) + 1

    return {
        "target_username": target_username,
        "profile_url": f"https://www.instagram.com/{target_username}/",
        "sample_size_requested": sample_size,
        "sample_size_collected": len(followers_data),
        "likely_bot_like_pct": round(likely_fake_pct, 2),
        "reason_counts": dict(sorted(reason_counts.items(), key=lambda x: x[1], reverse=True)),
        "followers_sample_preview": followers_data[:30],
    }
