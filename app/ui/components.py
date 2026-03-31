"""
Reusable UI components for the Architecture Agent Streamlit app.
"""
import streamlit as st
from pathlib import Path
from typing import Optional


def render_header():
    """Render the main application header."""
    st.markdown('<p class="main-header">🏛️ Architecture Agent</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sub-header">Multi-agent design system — sketch to professional architectural plans</p>',
        unsafe_allow_html=True,
    )


def render_status_badge(status: str) -> str:
    """Return HTML for a status badge."""
    status_map = {
        "draft": ("Draft", "status-draft"),
        "council_review": ("Council Review", "status-council"),
        "awaiting_confirmation": ("Awaiting Confirmation", "status-council"),
        "generating": ("Generating", "status-generating"),
        "quality_review": ("Quality Review", "status-generating"),
        "complete": ("Complete", "status-complete"),
        "refining": ("Refining", "status-refining"),
    }
    label, css_class = status_map.get(status, (status.title(), "status-draft"))
    return f'<span class="status-badge {css_class}">{label}</span>'


def render_info_card(title: str, text: str):
    """Render an info card with gradient background."""
    st.markdown(
        f"""
        <div class="info-card">
            <h3>{title}</h3>
            <p>{text}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_dsd_section(title: str, content: str):
    """Render a section of the DSD in a styled card."""
    st.markdown(
        f"""
        <div class="dsd-section">
            <h4>{title}</h4>
            <p>{content}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_dsd_display(dsd):
    """Render the full DSD in a readable format."""
    st.subheader(f"📋 {dsd.name}")
    st.markdown(f"**Type:** {dsd.type.value.title()} | **Version:** {dsd.version}")
    st.markdown(f"**Description:** {dsd.description}")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**📐 Dimensions**")
        if dsd.dimensions.width:
            st.markdown(f"- Width: {dsd.dimensions.width}")
        if dsd.dimensions.height:
            st.markdown(f"- Height: {dsd.dimensions.height}")
        if dsd.dimensions.depth:
            st.markdown(f"- Depth: {dsd.dimensions.depth}")
        if dsd.dimensions.notes:
            st.markdown(f"- Notes: {dsd.dimensions.notes}")

        st.markdown("**🎨 Style**")
        if dsd.style.aesthetic:
            st.markdown(f"- Aesthetic: {dsd.style.aesthetic}")
        if dsd.style.era:
            st.markdown(f"- Era: {dsd.style.era}")
        if dsd.style.influences:
            st.markdown(f"- Influences: {', '.join(dsd.style.influences)}")

    with col2:
        st.markdown("**🪵 Materials**")
        for mat in dsd.materials:
            st.markdown(f"- {mat.name}: {mat.usage} ({mat.finish})")

        st.markdown("**🎨 Colors**")
        if dsd.colors.primary:
            st.markdown(f"- Primary: {dsd.colors.primary}")
        if dsd.colors.secondary:
            st.markdown(f"- Secondary: {dsd.colors.secondary}")
        if dsd.colors.accent:
            st.markdown(f"- Accent: {dsd.colors.accent}")

    st.markdown("**🧱 Structural Elements**")
    for elem in dsd.structural_elements:
        count_str = f" (×{elem.count})" if elem.count > 1 else ""
        st.markdown(f"- **{elem.name}**{count_str}: {elem.description}")
        if elem.material:
            st.markdown(f"  Material: {elem.material}")
        if elem.position:
            st.markdown(f"  Position: {elem.position}")

    if dsd.spatial_layout:
        st.markdown(f"**📍 Spatial Layout:** {dsd.spatial_layout}")

    if dsd.context.placement or dsd.context.surroundings:
        st.markdown("**🏠 Context**")
        if dsd.context.placement:
            st.markdown(f"- Placement: {dsd.context.placement}")
        if dsd.context.surroundings:
            st.markdown(f"- Surroundings: {dsd.context.surroundings}")

    if dsd.views_to_generate:
        st.markdown("**🖼️ Views to Generate**")
        for view in dsd.views_to_generate:
            st.markdown(f"- **{view.label}** ({view.type})")

    if dsd.generation_notes:
        st.markdown(f"**📝 Generation Notes:** {dsd.generation_notes}")


def render_council_progress(state):
    """Render the council deliberation progress."""
    if state is None:
        return

    for rnd in state.rounds:
        status_icon = "✅" if rnd.completed_at else "⏳"
        round_name = rnd.round_type.replace("_", " ").title()

        with st.expander(f"{status_icon} Round {rnd.round_number}: {round_name}", expanded=not rnd.completed_at):
            for resp in rnd.responses:
                if resp.error:
                    st.error(f"❌ {resp.member_id}: {resp.error}")
                else:
                    with st.container():
                        st.markdown(f"**{resp.member_id.upper()}** ({resp.model_id})")
                        # Show truncated response
                        preview = resp.response_text[:500]
                        if len(resp.response_text) > 500:
                            preview += "..."
                        st.code(preview, language="json")

    # Consensus status
    if state.consensus_status:
        status_icons = {
            "pending": "⏳",
            "in_progress": "🔄",
            "reached": "✅",
            "forced": "⚠️",
            "failed": "❌",
        }
        icon = status_icons.get(state.consensus_status.value, "❓")
        st.markdown(f"**Consensus:** {icon} {state.consensus_status.value.title()}")
        if state.consensus_summary:
            st.markdown(f"*{state.consensus_summary}*")


def render_project_card(project_meta: dict):
    """Render a project card for the project list."""
    name = project_meta.get("name", "Untitled")
    status = project_meta.get("status", "unknown")
    created = project_meta.get("created_at", "")[:10]

    badge_html = render_status_badge(status)

    st.markdown(
        f"""
        **{name}** {badge_html}
        <br><small>Created: {created}</small>
        """,
        unsafe_allow_html=True,
    )


def render_image_gallery(images: list, images_dir: Path | None = None):
    """
    Render a gallery of generated images.

    Args:
        images: List of GeneratedImage objects
        images_dir: Base directory where images are stored
    """
    if not images:
        st.info("No images generated yet.")
        return

    # Group by view type
    cols_per_row = 2
    rows = [images[i : i + cols_per_row] for i in range(0, len(images), cols_per_row)]

    for row in rows:
        cols = st.columns(cols_per_row)
        for col, img in zip(cols, row):
            with col:
                view_name = img.display_label
                st.markdown(f"**{view_name}**")

                img_path = Path(img.file_path) if img.file_path else None
                if img_path and img_path.exists():
                    st.image(str(img_path), use_container_width=True)

                    # Download button
                    img_bytes = img_path.read_bytes()
                    st.download_button(
                        label=f"Download {view_name}",
                        data=img_bytes,
                        file_name=img_path.name,
                        mime=f"image/{img_path.suffix.lstrip('.')}",
                        key=f"dl_{img.id}",
                        use_container_width=True,
                    )
                else:
                    st.warning(f"Image file not found: {img.file_path}")

                # Metadata
                meta_parts = []
                if img.dsd_version:
                    meta_parts.append(f"DSD v{img.dsd_version}")
                if img.generated_at:
                    # Show a short timestamp
                    ts = img.generated_at[:16].replace("T", " ")
                    meta_parts.append(ts)
                if meta_parts:
                    st.caption(" · ".join(meta_parts))

                if img.quality_score is not None:
                    score_color = "🟢" if img.quality_score >= 7 else "🟡" if img.quality_score >= 5 else "🔴"
                    st.markdown(f"Quality: {score_color} {img.quality_score:.1f}/10")

                if img.approved:
                    st.markdown("✅ Approved")
