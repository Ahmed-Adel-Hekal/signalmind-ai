import time

import streamlit as st


def show_live_counter(
    stage1_duration: float = 20,
    stage2_duration: float = 40,
    stage3_duration: float = 20,
):
    """Animated live counter shown during generation."""
    stages = [
        ("Stage 1 - Competitor Intelligence", stage1_duration),
        ("Stage 2 - Trend Intelligence", stage2_duration),
        ("Stage 3 - Content Generation", stage3_duration),
    ]

    status = st.empty()
    prog = st.progress(0)

    total = sum(duration for _, duration in stages) or 1
    elapsed = 0.0

    for title, duration in stages:
        start = time.time()
        while True:
            passed = time.time() - start
            if passed >= duration:
                break
            pct = int(((elapsed + passed) / total) * 100)
            status.info(f"{title} - {int(passed)}s")
            prog.progress(min(pct, 99))
            time.sleep(0.2)
        elapsed += duration

    status.success("Pipeline complete")
    prog.progress(100)


def show_intelligence_page():
    st.title("Intelligence Engine")
    st.markdown(
        """
### How it works
- Live scraping across multiple social/news/dev sources
- Multi-stage trend analysis and ranking
- Competitor pattern extraction
- AI content generation for static posts or video prompts
"""
    )
