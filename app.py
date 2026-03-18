import streamlit as st
from pathlib import Path

st.set_page_config(
    page_title="Content Factory",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("Content Factory")
st.caption("AI Social Media Content Factory + Competitor Intelligence")

st.markdown(
    """
### Workflow
1. Go to **Generate** page and enter topic/platform settings.
2. Optionally add competitor URLs for live intelligence.
3. Run generation and review output ideas/assets in tabs.

Use **Intelligence Engine** page for trust and methodology view.
"""
)

zip_path = Path("dist/content_factory_full_code.zip")
if zip_path.exists():
    with zip_path.open("rb") as file_obj:
        st.download_button(
            "⬇ Download Full Source Code (ZIP)",
            data=file_obj.read(),
            file_name=zip_path.name,
            mime="application/zip",
        )
