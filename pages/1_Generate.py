import os
import threading
from pathlib import Path

import streamlit as st

from core.orchestrator import Orchestrator
from intelligence_page import show_live_counter


st.title("AI Social Content Factory")

with st.sidebar:
    st.header("Generation Inputs")
    topic = st.text_input("Topic", value="AI marketing workflows")
    platforms = st.multiselect(
        "Platform",
        options=["Instagram", "TikTok", "LinkedIn", "Twitter/X", "Facebook"],
        default=["Instagram", "LinkedIn"],
    )
    content_type_ui = st.radio("Content Type", ["Static Post", "Video Prompt"], index=0)
    _goal = st.selectbox("Goal", ["Engagement", "Awareness", "Sales"], index=0)
    language = st.selectbox("Language", ["English", "Arabic", "Egyptian Arabic"], index=0)
    number_idea = st.slider("Number of ideas", min_value=1, max_value=5, value=3)

    with st.expander("Brand"):
        color = st.color_picker("Brand color", value="#3B82F6")
        brand_logo = st.file_uploader("Brand logo", type=["png", "jpg", "jpeg"])

    with st.expander("Competitor"):
        urls_text = st.text_area("Competitor URLs (one per line)", value="")

content_type = "video" if content_type_ui == "Video Prompt" else "static"
competitor_urls = [u.strip() for u in urls_text.splitlines() if u.strip()]
brand_logo_path = None
if brand_logo is not None:
    tmp_dir = Path("/tmp/content_factory_uploads")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    brand_logo_path = str(tmp_dir / brand_logo.name)
    with open(brand_logo_path, "wb") as file_obj:
        file_obj.write(brand_logo.getbuffer())

if st.button("Generate", type="primary"):
    result_box = {"value": None}

    def _runner():
        orch = Orchestrator()
        result_box["value"] = orch.run(
            topic=topic,
            platforms=platforms,
            content_type=content_type,
            language=language,
            brand_color=[color],
            brand_img=brand_logo_path,
            number_idea=number_idea,
            competitor_urls=competitor_urls,
            niche="tech" if "AI" in topic.upper() else "marketing",
            output_dir="output_posts",
            image_url="",
        )

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()

    show_live_counter(stage1_duration=20, stage2_duration=40, stage3_duration=20)
    thread.join()

    result = result_box.get("value") or {}
    ideas = result.get("ideas", [])
    media_results = result.get("results", [])

    if not ideas:
        st.error("No ideas generated. Check API keys and try again.")
    else:
        tabs = st.tabs([f"Idea {i + 1}" for i in range(len(ideas))])
        for i, tab in enumerate(tabs):
            idea = ideas[i]
            media_obj = media_results[i] if i < len(media_results) else None

            with tab:
                if content_type == "static":
                    col1, col2 = st.columns([1, 1])
                    image_path = getattr(media_obj, "image_path", None)

                    with col1:
                        if image_path and os.path.exists(image_path):
                            st.image(image_path, use_container_width=True)
                        else:
                            st.info("Image preview unavailable")

                    with col2:
                        st.markdown("**Hook**")
                        st.write(idea.get("hook", ""))
                        st.markdown("**Caption**")
                        caption = idea.get("post_copy", "")
                        st.write(caption)
                        st.markdown("**Hashtags**")
                        tags = idea.get("hashtags", [])
                        st.write(" ".join(f"#{str(tag).lstrip('#')}" for tag in tags))

                        col_a, col_b = st.columns(2)
                        with col_a:
                            if st.button("📋 Copy Caption", key=f"copy_caption_{i}"):
                                st.toast("Caption ready to copy")
                        with col_b:
                            if image_path and os.path.exists(image_path):
                                with open(image_path, "rb") as file_obj:
                                    st.download_button(
                                        "⬇ Download Image",
                                        data=file_obj.read(),
                                        file_name=os.path.basename(image_path),
                                        key=f"download_{i}",
                                    )
                else:
                    st.markdown("**Hook**")
                    hook = idea.get("hook", {})
                    if isinstance(hook, dict):
                        st.write(hook.get("text", ""))
                    else:
                        st.write(str(hook))

                    st.markdown("**Veo 3 Prompt -- Scene by Scene**")
                    for scene in idea.get("script", []):
                        scene_no = scene.get("scene", "?")
                        dur = scene.get("duration_seconds", 0)
                        with st.expander(f"Scene {scene_no} ({dur}s)"):
                            st.write("**Visuals:**", scene.get("visuals", ""))
                            st.write("**Voiceover:**", scene.get("voiceover", ""))

                    st.markdown("**Caption**")
                    st.write(idea.get("caption", ""))
                    st.markdown("**Hashtags**")
                    st.write(" ".join(idea.get("hashtags", [])))
                    if st.button("📋 Copy Full Prompt", key=f"copy_prompt_{i}"):
                        st.toast("Prompt ready to copy")
