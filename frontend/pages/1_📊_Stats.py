import streamlit as st
import json
import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import numpy as np

st.set_page_config(page_title="Stats Dashboard", layout="wide")

# Data directory
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

# ===========================
# GENRE CLASSIFICATION
# ===========================
GENRE_HASHTAGS = {
    "Fashion": ["fashion", "style", "ootd", "outfitoftheday", "fashionista", "fashionblogger", "streetstyle", 
                "fashionstyle", "lookbook", "fashionable", "instafashion", "stylish", "outfit", "dress", "clothing"],
    
    "Beauty": ["beauty", "makeup", "skincare", "cosmetics", "makeupartist", "beautyblogger", "makeuptutorial",
               "beautytips", "makeuplover", "skin", "glam", "lipstick", "eyeshadow", "foundation", "skincareroutine"],
    
    "Fitness": ["fitness", "gym", "workout", "fit", "fitnessmotivation", "training", "bodybuilding", "gymlife",
                "exercise", "health", "muscle", "cardio", "fitfam", "crossfit", "yoga", "running", "weightloss"],
    
    "Food": ["food", "foodie", "foodporn", "instafood", "yummy", "delicious", "cooking", "recipe", "chef",
             "foodblogger", "foodphotography", "foodstagram", "homemade", "dinner", "lunch", "breakfast", "dessert"],
    
    "Travel": ["travel", "travelphotography", "wanderlust", "instatravel", "travelgram", "adventure", "explore",
               "vacation", "trip", "traveling", "tourist", "beach", "nature", "travelblogger", "holiday"],
    
    "Music": ["music", "musician", "song", "singer", "band", "concert", "guitar", "piano", "artist", "musicvideo",
              "musicproducer", "hiphop", "rock", "pop", "jazz", "dj", "rap", "musiclover"],
    
    "Gaming": ["gaming", "gamer", "videogames", "game", "games", "playstation", "xbox", "pc", "twitch", "streamer",
               "esports", "fortnite", "callofduty", "minecraft", "gameplay", "gamingcommunity", "ps5", "nintendo"],
    
    "Sports": ["sports", "football", "soccer", "basketball", "baseball", "nfl", "nba", "sports", "athlete",
               "sportsphotography", "tennis", "golf", "hockey", "cricket", "f1", "boxing", "mma"],
    
    "Entertainment": ["entertainment", "movie", "film", "tv", "actor", "actress", "cinema", "hollywood", "netflix",
                      "comedy", "funny", "memes", "viral", "trending", "celebrity", "drama"],
    
    "Lifestyle": ["lifestyle", "life", "daily", "instagood", "photooftheday", "picoftheday", "happy", "love",
                  "lifestyle blogger", "motivation", "inspiration", "goals", "vibes", "mood"],
    
    "Art": ["art", "artist", "artwork", "drawing", "painting", "illustration", "creative", "design", "sketch",
            "artoftheday", "instaart", "digitalart", "contemporaryart", "fineart", "graphicdesign"],
    
    "Photography": ["photography", "photographer", "photo", "photooftheday", "camera", "portrait", "landscape",
                    "naturephotography", "streetphotography", "photographylovers", "photographyeveryday", "canon", "nikon"],
    
    "Technology": ["technology", "tech", "gadgets", "innovation", "ai", "coding", "programming", "developer",
                   "software", "startup", "entrepreneurship", "business", "digital", "app", "smartphone"],
    
    "Education": ["education", "learning", "study", "student", "teacher", "school", "university", "knowledge",
                  "books", "reading", "science", "history", "educational", "studying", "learn"],
    
    "Pets": ["pets", "dog", "cat", "puppy", "kitten", "dogsofinstagram", "catsofinstagram", "petlover", "animal",
             "cute", "petsofinstagram", "dogstagram", "catstagram", "animals", "petphotography"],
    
    "Selfcare": ["selfcare", "wellness", "mentalhealth", "mindfulness", "meditation", "selflove", "healthylifestyle",
                 "relax", "spa", "beauty", "skincare", "selfcaresunday", "healing", "peace", "gratitude"]
}

def classify_genre(posts):
    """
    Classify account genre based on hashtags from posts
    Returns: dict with genre scores and top genre
    """
    if not posts:
        return {"top_genre": "Unknown", "scores": {}, "confidence": 0}
    
    # Collect all hashtags (lowercase for matching)
    all_hashtags = []
    for post in posts:
        hashtags = [tag.lower() for tag in post.get('hashtags', [])]
        all_hashtags.extend(hashtags)
    
    if not all_hashtags:
        return {"top_genre": "Unknown", "scores": {}, "confidence": 0}
    
    # Count matches for each genre
    genre_scores = {}
    for genre, keywords in GENRE_HASHTAGS.items():
        score = sum(1 for tag in all_hashtags if any(kw in tag for kw in keywords))
        genre_scores[genre] = score
    
    # Find top genre
    if not any(genre_scores.values()):
        return {"top_genre": "Unknown", "scores": genre_scores, "confidence": 0}
    
    top_genre = max(genre_scores.items(), key=lambda x: x[1])
    total_matches = sum(genre_scores.values())
    confidence = (top_genre[1] / total_matches * 100) if total_matches > 0 else 0
    
    # Get top 3 genres
    sorted_genres = sorted(genre_scores.items(), key=lambda x: x[1], reverse=True)[:3]
    
    return {
        "top_genre": top_genre[0],
        "top_genres": sorted_genres,
        "scores": genre_scores,
        "confidence": round(confidence, 1),
        "total_hashtags": len(all_hashtags),
        "total_matches": total_matches
    }

st.title("📊 Analytics Dashboard")

# Check if data directory exists
if not os.path.exists(DATA_DIR):
    st.error("No data directory found. Run some scans first!")
    st.stop()

# Get all JSON files
profile_files = sorted([f for f in os.listdir(DATA_DIR) if f.startswith("profile_audit_")], reverse=True)
follower_files = sorted([f for f in os.listdir(DATA_DIR) if f.startswith("follower_audit_")], reverse=True)

if not profile_files and not follower_files:
    st.warning("No saved data found. Run Profile Audit or Follower Audit first!")
    st.stop()

# Sidebar - File selection
st.sidebar.header("Select Data")

selected_profile = None
selected_follower = None

if profile_files:
    st.sidebar.subheader("Profile Audits")
    profile_choice = st.sidebar.selectbox(
        "Select profile scan",
        profile_files,
        format_func=lambda x: x.replace("profile_audit_", "").replace(".json", "")
    )
    if profile_choice:
        with open(os.path.join(DATA_DIR, profile_choice), 'r') as f:
            selected_profile = json.load(f)

if follower_files:
    st.sidebar.subheader("Follower Audits")
    follower_choice = st.sidebar.selectbox(
        "Select follower scan",
        follower_files,
        format_func=lambda x: x.replace("follower_audit_", "").replace(".json", "")
    )
    if follower_choice:
        with open(os.path.join(DATA_DIR, follower_choice), 'r') as f:
            selected_follower = json.load(f)


# ===========================
# AUTHENTICITY SCORE CALCULATOR
# ===========================
def calculate_authenticity_score(profile_data, follower_data=None):
    """
    Calculate a comprehensive authenticity score (0-100)
    Higher score = more authentic
    """
    score = 100.0
    reasons = []
    
    if profile_data:
        metrics = profile_data.get("metrics", {})
        followers = profile_data.get("followers", 0)
        following = profile_data.get("following", 0)
        posts_count = profile_data.get("posts_count", 0)
        
        # Factor 1: Engagement Rate
        er_avg = metrics.get("er_avg", 0)
        if followers < 10_000:
            if er_avg < 1.0:
                score -= 20
                reasons.append("Low engagement rate for account size")
        elif followers < 100_000:
            if er_avg < 0.7:
                score -= 20
                reasons.append("Low engagement rate for account size")
        else:
            if er_avg < 0.3:
                score -= 20
                reasons.append("Low engagement rate for large account")
        
        # Factor 2: Generic Comments
        generic_pct = metrics.get("generic_comments_pct", 0)
        if generic_pct > 50:
            score -= 15
            reasons.append(f"Very high generic comments ({generic_pct}%)")
        elif generic_pct > 30:
            score -= 8
            reasons.append(f"High generic comments ({generic_pct}%)")
        
        # Factor 3: Duplicate Comments
        dup_pct = metrics.get("duplicate_comments_pct", 0)
        if dup_pct > 25:
            score -= 15
            reasons.append(f"High duplicate comments ({dup_pct}%)")
        elif dup_pct > 15:
            score -= 8
            reasons.append(f"Moderate duplicate comments ({dup_pct}%)")
        
        # Factor 4: Follower/Following Ratio
        if following > 0:
            ratio = followers / following
            if ratio < 0.3:
                score -= 15
                reasons.append("Following significantly more than followers")
            elif ratio < 0.8:
                score -= 5
                reasons.append("Following more than followers")
        
        # Factor 5: Post Consistency (CV)
        like_cv = metrics.get("like_cv", 0)
        if like_cv < 0.15 and len(profile_data.get("posts", [])) >= 10:
            score -= 10
            reasons.append("Suspiciously consistent like counts")
        
        # Factor 6: Risk Score from backend
        risk_score = metrics.get("risk_score", 0)
        score -= (risk_score * 0.3)  # Use 30% of backend risk score
    
    if follower_data:
        bot_pct = follower_data.get("likely_bot_like_pct", 0)
        if bot_pct > 40:
            score -= 25
            reasons.append(f"Very high bot-like followers ({bot_pct}%)")
        elif bot_pct > 25:
            score -= 15
            reasons.append(f"High bot-like followers ({bot_pct}%)")
        elif bot_pct > 15:
            score -= 8
            reasons.append(f"Moderate bot-like followers ({bot_pct}%)")
    
    score = max(0, min(100, score))
    
    if score >= 80:
        status = "✅ Highly Authentic"
        color = "green"
    elif score >= 60:
        status = "⚠️ Moderately Authentic"
        color = "orange"
    elif score >= 40:
        status = "🚨 Questionable"
        color = "orange"
    else:
        status = "❌ Likely Inauthentic"
        color = "red"
    
    return {
        "score": round(score, 1),
        "fake_percentage": round(100 - score, 1),
        "status": status,
        "color": color,
        "reasons": reasons
    }


# ===========================
# MAIN DASHBOARD
# ===========================

# Calculate Authenticity Score
auth_result = calculate_authenticity_score(selected_profile, selected_follower)

# Calculate Genre Classification
genre_result = None
if selected_profile:
    posts = selected_profile.get('posts', [])
    genre_result = classify_genre(posts)

# Hero Metrics
st.header("🎯 Authenticity Analysis")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Authenticity Score",
        f"{auth_result['score']}/100",
        delta=f"{auth_result['status']}"
    )

with col2:
    st.metric(
        "Estimated Fake %",
        f"{auth_result['fake_percentage']}%",
        delta="Lower is better",
        delta_color="inverse"
    )

with col3:
    if selected_follower:
        st.metric(
            "Bot-like Followers",
            f"{selected_follower.get('likely_bot_like_pct', 0)}%"
        )
with col3:
    if selected_follower:
        st.metric(
            "Bot-like Followers",
            f"{selected_follower.get('likely_bot_like_pct', 0)}%"
        )
    else:
        st.info("Run Follower Audit for bot analysis")

with col4:
    if genre_result:
        st.metric(
            "Account Genre",
            genre_result['top_genre'],
            delta=f"{genre_result['confidence']}% confidence"
        )

# Gauge Chart for Authenticity
fig_gauge = go.Figure(go.Indicator(
    mode="gauge+number",
    value=auth_result['score'],
    title={'text': "Authenticity Score"},
    gauge={
        'axis': {'range': [0, 100]},
        'bar': {'color': auth_result['color']},
        'steps': [
            {'range': [0, 40], 'color': "lightcoral"},
            {'range': [40, 60], 'color': "lightyellow"},
            {'range': [60, 80], 'color': "lightblue"},
            {'range': [80, 100], 'color': "lightgreen"}
        ],
        'threshold': {
            'line': {'color': "red", 'width': 4},
            'thickness': 0.75,
            'value': 50
        }
    }
))
fig_gauge.update_layout(height=300)
st.plotly_chart(fig_gauge, use_container_width=True)

# Risk Factors
if auth_result['reasons']:
    st.subheader("⚠️ Risk Factors Detected")
    for reason in auth_result['reasons']:
        st.warning(f"• {reason}")
else:
    st.success("✅ No significant risk factors detected!")

st.divider()

# ===========================
# GENRE CLASSIFICATION
# ===========================
if genre_result and genre_result['top_genre'] != "Unknown":
    st.header("🎨 Content Genre Analysis")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Genre scores chart
        genre_df = pd.DataFrame([
            {"Genre": k, "Matches": v} 
            for k, v in genre_result['scores'].items() if v > 0
        ]).sort_values('Matches', ascending=False).head(10)
        
        fig_genre = px.bar(
            genre_df,
            x='Matches',
            y='Genre',
            orientation='h',
            title="Genre Classification (based on hashtags)",
            color='Matches',
            color_continuous_scale='viridis'
        )
        st.plotly_chart(fig_genre, use_container_width=True)
    
    with col2:
        st.subheader("Top Genres")
        for i, (genre, score) in enumerate(genre_result['top_genres'], 1):
            percentage = (score / genre_result['total_matches'] * 100) if genre_result['total_matches'] > 0 else 0
            if i == 1:
                st.success(f"🥇 **{genre}** - {score} matches ({percentage:.1f}%)")
            elif i == 2:
                st.info(f"🥈 {genre} - {score} matches ({percentage:.1f}%)")
            elif i == 3:
                st.info(f"🥉 {genre} - {score} matches ({percentage:.1f}%)")
        
        st.caption(f"Analyzed {genre_result['total_hashtags']} hashtags from posts")

st.divider()

# ===========================
# PROFILE ANALYSIS
# ===========================
if selected_profile:
    st.header(f"📱 Profile: @{selected_profile['username']}")
    
    # Profile Overview
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Followers", f"{selected_profile.get('followers', 0):,}")
    col2.metric("Following", f"{selected_profile.get('following', 0):,}")
    col3.metric("Posts", f"{selected_profile.get('posts_count', 0):,}")
    
    ratio = selected_profile.get('followers', 1) / max(selected_profile.get('following', 1), 1)
    col4.metric("Follower Ratio", f"{ratio:.2f}x")
    
    # Engagement Metrics
    st.subheader("📊 Engagement Metrics")
    metrics = selected_profile.get('metrics', {})
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Avg ER", f"{metrics.get('er_avg', 0)}%")
    col2.metric("Median ER", f"{metrics.get('er_median', 0)}%")
    col3.metric("Avg Likes", f"{metrics.get('avg_likes', 0):,.0f}")
    col4.metric("Avg Comments", f"{metrics.get('avg_comments', 0):,.0f}")
    
    # Comment Quality
    st.subheader("💬 Comment Quality Analysis")
    col1, col2, col3 = st.columns(3)
    col1.metric("Generic Comments", f"{metrics.get('generic_comments_pct', 0)}%")
    col2.metric("Duplicate Comments", f"{metrics.get('duplicate_comments_pct', 0)}%")
    col3.metric("Repeat Commenters", f"{metrics.get('repeat_commenters_pct', 0)}%")
    
    # Posts Analysis
    posts = selected_profile.get('posts', [])
    if posts:
        st.subheader("📸 Posts Performance")
        
        # Create dataframe
        posts_df = pd.DataFrame([{
            'shortcode': p.get('shortcode'),
            'date': p.get('date'),
            'likes': p.get('likes', 0),
            'comments': p.get('comments_count', 0),
            'engagement': p.get('likes', 0) + p.get('comments_count', 0),
            'type': p.get('type', 'post'),
            'hashtags_count': len(p.get('hashtags', []))
        } for p in posts])
        
        # Engagement over time
        fig_engagement = px.line(
            posts_df,
            x=posts_df.index,
            y=['likes', 'comments'],
            title="Likes & Comments per Post",
            labels={'value': 'Count', 'variable': 'Metric', 'index': 'Post #'}
        )
        st.plotly_chart(fig_engagement, use_container_width=True)
        
        # Post type distribution
        col1, col2 = st.columns(2)
        
        with col1:
            type_counts = posts_df['type'].value_counts()
            fig_types = px.pie(
                values=type_counts.values,
                names=type_counts.index,
                title="Post Types"
            )
            st.plotly_chart(fig_types, use_container_width=True)
        
        with col2:
            # Hashtags usage
            fig_hashtags = px.bar(
                posts_df,
                y='hashtags_count',
                title="Hashtags per Post",
                labels={'hashtags_count': 'Number of Hashtags', 'index': 'Post #'}
            )
            st.plotly_chart(fig_hashtags, use_container_width=True)
        
        # Top performing posts
        st.subheader("🏆 Top Performing Posts")
        top_posts = posts_df.nlargest(5, 'engagement')[['shortcode', 'likes', 'comments', 'engagement', 'type']]
        st.dataframe(top_posts, use_container_width=True)
        
        # All hashtags frequency
        all_hashtags = []
        for p in posts:
            all_hashtags.extend(p.get('hashtags', []))
        
        if all_hashtags:
            st.subheader("🏷️ Most Used Hashtags")
            hashtag_counts = pd.Series(all_hashtags).value_counts().head(15)
            fig_hashtag_freq = px.bar(
                x=hashtag_counts.values,
                y=hashtag_counts.index,
                orientation='h',
                title="Top 15 Hashtags",
                labels={'x': 'Frequency', 'y': 'Hashtag'}
            )
            st.plotly_chart(fig_hashtag_freq, use_container_width=True)

st.divider()

# ===========================
# FOLLOWER ANALYSIS
# ===========================
if selected_follower:
    st.header(f"👥 Follower Analysis: @{selected_follower['target_username']}")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Sample Size", f"{selected_follower.get('sample_size_collected', 0)}")
    col2.metric("Bot-like %", f"{selected_follower.get('likely_bot_like_pct', 0)}%")
    col3.metric("Authentic %", f"{100 - selected_follower.get('likely_bot_like_pct', 0)}%")
    
    # Bot reasons
    reason_counts = selected_follower.get('reason_counts', {})
    if reason_counts:
        st.subheader("🚩 Bot Indicators")
        
        reasons_df = pd.DataFrame([
            {'Reason': k, 'Count': v} for k, v in reason_counts.items()
        ]).sort_values('Count', ascending=False)
        
        fig_reasons = px.bar(
            reasons_df,
            x='Count',
            y='Reason',
            orientation='h',
            title="Most Common Bot Indicators"
        )
        st.plotly_chart(fig_reasons, use_container_width=True)
    
    # Follower sample preview
    followers_sample = selected_follower.get('followers_sample_preview', [])
    if followers_sample:
        st.subheader("👤 Sample Followers")
        
        sample_df = pd.DataFrame(followers_sample)
        
        # Add color coding
        def color_fake(row):
            if row['likely_fake']:
                return ['background-color: #ffcccc'] * len(row)
            else:
                return ['background-color: #ccffcc'] * len(row)
        
        st.dataframe(
            sample_df[['username', 'followers', 'following', 'posts', 'likely_fake', 'is_private']].head(20),
            use_container_width=True
        )

st.divider()

# Export functionality
st.subheader("💾 Export Data")
col1, col2 = st.columns(2)

if selected_profile and col1.button("Download Profile Data (CSV)"):
    posts_df = pd.DataFrame(selected_profile.get('posts', []))
    csv = posts_df.to_csv(index=False)
    st.download_button(
        "Download CSV",
        csv,
        f"profile_{selected_profile['username']}.csv",
        "text/csv"
    )

if selected_follower and col2.button("Download Follower Data (CSV)"):
    followers_df = pd.DataFrame(selected_follower.get('followers_sample_preview', []))
    csv = followers_df.to_csv(index=False)
    st.download_button(
        "Download CSV",
        csv,
        f"followers_{selected_follower['target_username']}.csv",
        "text/csv"
    )
