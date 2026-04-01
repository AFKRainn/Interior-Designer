"""
Architecture Agent — Main Streamlit Application

This is the entry point for the Streamlit UI.
Provides a multi-page interface for the full design pipeline.
"""
import json
import sys
from pathlib import Path

# Add project root to Python path so imports work
PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from config import APP_TITLE, APP_ICON, APP_LAYOUT, DATA_DIR
from app.ui.styles import MAIN_CSS
from app.ui.components import (
    render_header,
    render_info_card,
    render_status_badge,
    render_dsd_display,
    render_council_progress,
    render_project_card,
    render_image_gallery,
)
from app.services.project_store import ProjectStore
from app.services.image_service import ImageService
from app.models.project import Project, ProjectStatus, InputData

# ---------------------------------------------------------------------------
# Page Config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout=APP_LAYOUT,
    initial_sidebar_state="expanded",
)

# Inject custom CSS
st.markdown(MAIN_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session Persistence Helpers
# ---------------------------------------------------------------------------
_SESSION_FILE = DATA_DIR / ".last_session.json"


def _save_session():
    """Save current session info to disk for persistence across reloads."""
    try:
        _SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "project_id": st.session_state.get("current_project_id"),
            "page": st.session_state.get("current_page", "new_project"),
        }
        _SESSION_FILE.write_text(json.dumps(data), encoding="utf-8")
    except Exception:
        pass  # Non-critical — silent fail


def _restore_session():
    """Restore session info from disk on fresh page load."""
    if _SESSION_FILE.exists():
        try:
            data = json.loads(_SESSION_FILE.read_text(encoding="utf-8"))
            pid = data.get("project_id")
            page = data.get("page", "new_project")

            if pid:
                store = st.session_state.store
                project = store.load_project(pid)
                if project:
                    st.session_state.current_project_id = pid
                    # Restore DSD
                    dsd = store.load_dsd(pid)
                    if dsd:
                        st.session_state.current_dsd = dsd
                    # Determine best page based on project status
                    status = project.status.value
                    if status == "complete":
                        st.session_state.current_page = "gallery"
                    elif status == "quality_review":
                        st.session_state.current_page = "gallery"
                    elif status == "drawings_review":
                        st.session_state.current_page = "drawings_review"
                    elif status == "generating_render":
                        st.session_state.current_page = "generating_render"
                    elif status == "awaiting_confirmation":
                        st.session_state.current_page = "review_dsd"
                    elif status == "consulting":
                        st.session_state.current_page = "consulting"
                    elif status == "council_review":
                        # Stuck project — send to council page for re-run
                        if dsd:
                            st.session_state.current_page = "review_dsd"
                        else:
                            st.session_state.current_page = "council"
                    elif page in (
                        "gallery", "review_dsd",
                        "drawings_review", "generating_render",
                        "council", "generating", "refine",
                        "consulting",
                    ):
                        st.session_state.current_page = page
        except Exception:
            pass  # Non-critical — silent fail


# ---------------------------------------------------------------------------
# Session State Initialization
# ---------------------------------------------------------------------------
if "store" not in st.session_state:
    st.session_state.store = ProjectStore()

if "current_project_id" not in st.session_state:
    st.session_state.current_project_id = None

if "current_page" not in st.session_state:
    st.session_state.current_page = "new_project"

if "council_state" not in st.session_state:
    st.session_state.council_state = None

if "current_dsd" not in st.session_state:
    st.session_state.current_dsd = None

if "council_messages" not in st.session_state:
    st.session_state.council_messages = []

if "generation_done" not in st.session_state:
    st.session_state.generation_done = False

if "generation_messages" not in st.session_state:
    st.session_state.generation_messages = []

if "consultant_history" not in st.session_state:
    st.session_state.consultant_history = []

if "consultant_brief" not in st.session_state:
    st.session_state.consultant_brief = None

if "images_data" not in st.session_state:
    st.session_state.images_data = []

if "element_selections" not in st.session_state:
    from app.models.elements import ElementSelections
    st.session_state.element_selections = ElementSelections()

if "render_done" not in st.session_state:
    st.session_state.render_done = False

# (review_done / review_results / review_messages removed — quality review step removed)

# Restore session from disk on first load
if "session_restored" not in st.session_state:
    _restore_session()
    st.session_state.session_restored = True


# ---------------------------------------------------------------------------
# Pipeline Progress Indicator (defined before sidebar so it's available)
# ---------------------------------------------------------------------------
_PIPELINE_STEPS = [
    ("consulting", "Design Consultation"),
    ("council_review", "Council Deliberation"),
    ("awaiting_confirmation", "DSD Review"),
    ("generating", "Technical Drawings"),
    ("drawings_review", "Drawings Review"),
    ("generating_render", "Realistic Render"),
    ("complete", "Complete"),
]

_STATUS_TO_STEP = {
    "draft": -1,
    "consulting": 0,
    "council_review": 1,
    "awaiting_confirmation": 2,
    "generating": 3,
    "drawings_review": 4,
    "generating_render": 5,
    "complete": 6,
    "refining": 6,
    "quality_review": 6,  # Legacy status — treated as complete
}


def _render_pipeline_progress(status: ProjectStatus):
    """Render a compact pipeline progress indicator in the sidebar."""
    current_idx = _STATUS_TO_STEP.get(status.value, -1)

    for idx, (_, label) in enumerate(_PIPELINE_STEPS):
        if idx < current_idx:
            icon = "✅"
        elif idx == current_idx:
            icon = "▶️" if status.value != "complete" else "✅"
        else:
            icon = "⬜"
        st.caption(f"{icon} {label}")


# ---------------------------------------------------------------------------
# Sidebar Navigation
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 🏛️ Architecture Agent")
    st.markdown("---")

    # Navigation buttons
    if st.button("➕ New Project", use_container_width=True):
        st.session_state.current_page = "new_project"
        st.rerun()

    if st.button("📂 My Projects", use_container_width=True):
        st.session_state.current_page = "projects"
        st.rerun()

    st.markdown("---")

    # Show current project info if one is active
    if st.session_state.current_project_id:
        project = st.session_state.store.load_project(
            st.session_state.current_project_id
        )
        if project:
            st.markdown(f"**Active:** {project.name or 'Untitled'}")
            st.markdown(
                render_status_badge(project.status.value),
                unsafe_allow_html=True,
            )

            # Pipeline progress indicator
            _render_pipeline_progress(project.status)

            st.markdown("---")

            # Context-sensitive navigation based on project status
            if project.status == ProjectStatus.CONSULTING:
                if st.button("💬 Consultation", use_container_width=True):
                    st.session_state.current_page = "consulting"
                    st.rerun()

            if project.status in (
                ProjectStatus.COUNCIL_REVIEW,
                ProjectStatus.AWAITING_CONFIRMATION,
            ):
                if st.button("🔍 Council View", use_container_width=True):
                    st.session_state.current_page = "council"
                    st.rerun()

            if project.status == ProjectStatus.AWAITING_CONFIRMATION:
                if st.button("📋 Review DSD", use_container_width=True):
                    st.session_state.current_page = "review_dsd"
                    st.rerun()

            if project.status == ProjectStatus.GENERATING:
                if st.button("⚙️ Generation Progress", use_container_width=True):
                    st.session_state.current_page = "generating"
                    st.rerun()

            if project.status == ProjectStatus.DRAWINGS_REVIEW:
                if st.button("📐 Review Drawings", use_container_width=True):
                    st.session_state.current_page = "drawings_review"
                    st.rerun()

            if project.status == ProjectStatus.GENERATING_RENDER:
                if st.button("🎨 Render Progress", use_container_width=True):
                    st.session_state.current_page = "generating_render"
                    st.rerun()

            if project.status == ProjectStatus.COMPLETE:
                if st.button("🖼️ Gallery", use_container_width=True):
                    st.session_state.current_page = "gallery"
                    st.rerun()

            if project.status == ProjectStatus.COMPLETE:
                if st.button("✏️ Request Changes", use_container_width=True):
                    st.session_state.current_page = "refine"
                    st.rerun()

    st.markdown("---")
    # API usage display
    try:
        from app.services.openrouter import CostTracker
        tracker = CostTracker()
        if tracker.call_count > 0:
            st.markdown("---")
            st.caption(
                f"📊 API: {tracker.call_count} calls · "
                f"{tracker.total_tokens:,} tokens"
            )
            if tracker.total_cost > 0:
                st.caption(f"💰 Cost: ${tracker.total_cost:.4f}")
    except Exception:
        pass

    st.markdown(
        "<small>Powered by OpenRouter<br>"
        "Claude · GPT · Gemini<br>"
        "Nano Banana 🍌</small>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Page: New Project
# ---------------------------------------------------------------------------
def page_new_project():
    render_header()

    render_info_card(
        "How it works",
        "Describe your design (and/or upload sketches) → "
        "A design consultant refines your brief → "
        "The Council (3 AI architects) deliberates → "
        "You review technical drawings → A realistic render is generated.",
    )

    st.markdown("### Start a New Design")

    # Project name
    project_name = st.text_input(
        "Project Name",
        placeholder="e.g., Modern Oak Bookshelf, Living Room Layout",
    )

    # --- Single unified input ---
    st.markdown("#### Describe Your Design")
    text_input = st.text_area(
        "What do you want designed?",
        height=200,
        placeholder=(
            "Describe what you want designed — be as detailed or as brief "
            "as you like.  A design consultant will help clarify anything "
            "that's unclear.\n\n"
            "Examples:\n"
            "• A modern minimalist bookshelf, light oak with black metal frame\n"
            "• Give me a kitchen design — L-shaped, modern, white marble\n"
            "• A wardrobe similar to the attached sketch but in walnut"
        ),
        key="input_text",
    )

    st.markdown("#### Reference Images *(optional)*")
    st.caption(
        "Upload sketches, reference photos, inspiration images — "
        "anything that helps describe what you want."
    )
    uploaded_files = st.file_uploader(
        "Upload images",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        key="input_images",
    )

    # Show uploaded images
    if uploaded_files:
        cols = st.columns(min(len(uploaded_files), 4))
        for i, f in enumerate(uploaded_files):
            with cols[i % len(cols)]:
                st.image(f, caption=f.name, use_container_width=True)

    # --- Element Library Selector ---
    from app.models.elements import (
        ELEMENT_LIBRARY,
        ElementSelections,
        get_category_display_name,
        get_default,
    )

    use_element_selector = st.toggle(
        "Select Construction Elements manually",
        value=False,
        help=(
            "Enable to pick specific construction details (handles, shelves, "
            "finishes, etc.) from a library. Leave off if your description "
            "already includes them or you want the council to decide."
        ),
    )

    element_selections = ElementSelections()

    if use_element_selector:
        with st.expander("🧩 Construction Elements", expanded=True):
            st.caption(
                "Select specific construction details. Everything defaults "
                "to plain/standard — only change what you need."
            )

            for cat_key, options in ELEMENT_LIBRARY.items():
                display_name = get_category_display_name(cat_key)
                default_opt = get_default(cat_key)
                default_idx = 0
                if default_opt:
                    for i, opt in enumerate(options):
                        if opt.id == default_opt.id:
                            default_idx = i
                            break

                selected = st.selectbox(
                    display_name,
                    options,
                    index=default_idx,
                    format_func=lambda opt: f"{opt.name} — {opt.description}",
                    key=f"element_{cat_key}",
                )
                if selected and not selected.is_default:
                    element_selections.set_selection(cat_key, selected.id)

            if element_selections.selections:
                st.markdown("**Your selections:**")
                st.markdown(element_selections.to_description())

    # Start button
    st.markdown("---")
    if st.button("🚀 Start Design", type="primary", use_container_width=True):
        if text_input.strip() or uploaded_files:
            _start_project(
                project_name,
                text_input=text_input.strip() if text_input.strip() else None,
                uploaded_files=uploaded_files or [],
                element_selections=element_selections,
            )
        else:
            st.warning("Please provide at least a description or an image.")


def _start_project(
    name: str,
    text_input: str | None = None,
    uploaded_files: list | None = None,
    element_selections=None,
):
    """Create a new project and start the design consultation."""
    from app.models.elements import ElementSelections

    store: ProjectStore = st.session_state.store

    if element_selections is None:
        element_selections = ElementSelections()

    has_text = bool(text_input and text_input.strip())
    has_images = bool(uploaded_files)

    if not has_text and not has_images:
        st.error("Please provide at least a text description or an image.")
        return

    input_type = (
        "mixed" if (has_text and has_images) else
        ("image" if has_images else "text")
    )

    # Create project
    project = Project(
        name=name or "Untitled Design",
        input_data=InputData(
            text_description=text_input,
            input_type=input_type,
        ),
    )

    # Save all uploaded images
    images_data = []  # list of (b64, mime) tuples for API calls
    for uploaded_file in (uploaded_files or []):
        file_bytes = uploaded_file.read()
        saved_path = store.save_uploaded_image(
            project.id, file_bytes, uploaded_file.name
        )
        project.input_data.image_paths.append(str(saved_path))

        # Encode for API
        b64, mime = ImageService.encode_uploaded_bytes(
            file_bytes, uploaded_file.name
        )
        images_data.append({"data": b64, "mime_type": mime})

    # Update status and save
    project.update_status(ProjectStatus.CONSULTING)
    store.save_project(project)

    # Store in session
    st.session_state.current_project_id = project.id
    st.session_state.consultant_history = []
    st.session_state.consultant_brief = None
    st.session_state.images_data = images_data
    st.session_state.element_selections = element_selections

    # Run the consultant assessment
    _run_consultant_assessment(project, images_data, element_selections)


def _format_conversation_for_council(
    user_text: str | None,
    history: list[dict],
    tech_spec: str = "",
) -> str:
    """
    Build the text that the council receives.

    Contains the user's original words plus any answers they gave during
    the consultation.  Nothing is rewritten or summarised.
    """
    parts = []

    if user_text:
        parts.append(f"CLIENT'S DESIGN REQUEST:\n{user_text}")

    # Collect genuine user replies from the conversation (skip the very first
    # assistant greeting, which is not a question-answer exchange)
    user_replies = [m["content"] for m in history if m["role"] == "user"]
    if user_replies:
        combined = "\n\n".join(user_replies)
        parts.append(f"ADDITIONAL DETAILS PROVIDED BY CLIENT:\n{combined}")

    if tech_spec:
        parts.append(f"CONSTRUCTION ELEMENT SPECIFICATIONS:\n{tech_spec}")

    return "\n\n".join(parts) if parts else (user_text or "")


def _run_consultant_assessment(project, images_data, element_selections=None):
    """Assess input completeness and decide whether to chat or proceed."""
    from app.agents.consultant import Consultant
    from app.models.elements import ElementSelections
    from app.services.openrouter import run_async

    if element_selections is None:
        element_selections = ElementSelections()

    elements_desc = element_selections.to_description()

    try:
        consultant = Consultant()
        assessment = run_async(
            consultant.assess_input(
                user_text=project.input_data.text_description,
                image_count=len(images_data),
                element_selections=elements_desc,
            )
        )

        ready_message = assessment.get(
            "ready_message",
            "Your request is clear! Add any extra details below if you like, "
            "then send it to the council.",
        )

        if assessment.get("has_enough"):
            # Enough info — build the council input from the raw text and go
            # to the consulting page so the user can add more or proceed.
            tech_spec = element_selections.to_technical_spec()
            council_input = _format_conversation_for_council(
                project.input_data.text_description,
                [],
                tech_spec=tech_spec,
            )
            st.session_state.consultant_brief = council_input
            st.session_state.consultant_history = [
                {"role": "assistant", "content": ready_message}
            ]
        else:
            # Need to chat — open the consulting page with questions
            questions = assessment.get("clarifying_questions", [])
            intro_msg = "I have a couple of quick questions before we proceed:"
            if questions:
                intro_msg += "\n\n" + "\n".join(f"• {q}" for q in questions)

            st.session_state.consultant_history = [
                {"role": "assistant", "content": intro_msg}
            ]
            st.session_state.consultant_brief = None

        st.session_state.current_page = "consulting"
        st.rerun()

    except Exception as e:
        st.error(f"Consultant error: {e}")
        # Fallback — pass raw input straight to council
        st.session_state.consultant_brief = project.input_data.text_description
        st.session_state.consultant_history = [
            {
                "role": "assistant",
                "content": "Ready to proceed. Click 'Send to Council' below.",
            }
        ]
        st.session_state.current_page = "consulting"
        st.rerun()


def _run_council(
    project_id: str,
    user_text: str | None,
    image_data: str | None,
    image_mime_type: str,
    all_images: list[dict] | None = None,
):
    """Run the council deliberation (called after consultation)."""
    from app.agents.council import Council
    from app.services.openrouter import run_async

    store: ProjectStore = st.session_state.store

    # Progress messages will be collected
    messages = []

    def on_progress(msg: str):
        messages.append(msg)

    try:
        council = Council()
        state, dsd = run_async(
            council.deliberate(
                project_id=project_id,
                user_text=user_text,
                image_data=image_data,
                image_mime_type=image_mime_type,
                on_progress=on_progress,
                all_images=all_images,
            )
        )

        # Save results
        st.session_state.council_state = state
        st.session_state.council_messages = messages

        if dsd:
            store.save_dsd(project_id, dsd)
            st.session_state.current_dsd = dsd

            # Update project
            project = store.load_project(project_id)
            if project:
                project.dsd_id = dsd.project_id
                project.dsd_versions.append(dsd.version)
                project.update_status(ProjectStatus.AWAITING_CONFIRMATION)
                store.save_project(project)

            st.session_state.current_page = "review_dsd"

    except Exception as e:
        st.session_state.council_messages = messages + [f"❌ Error: {e}"]

    st.rerun()


# ---------------------------------------------------------------------------
# Page: Design Consultation (chat with consultant)
# ---------------------------------------------------------------------------
def page_consulting():
    render_header()
    st.markdown("### 💬 Design Consultation")
    st.caption(
        "The design consultant is clarifying your requirements before "
        "sending them to the council."
    )

    project_id = st.session_state.current_project_id
    if not project_id:
        st.warning("No active project.")
        return

    store: ProjectStore = st.session_state.store
    project = store.load_project(project_id)
    if not project:
        st.warning("Project not found.")
        return

    # Show the original input for context
    with st.expander("📎 Your Original Input", expanded=False):
        if project.input_data.text_description:
            st.markdown(project.input_data.text_description)
        for img_path in project.input_data.image_paths:
            p = Path(img_path)
            if p.exists():
                st.image(str(p), width=250)

    st.markdown("---")

    # Display conversation history
    for msg in st.session_state.consultant_history:
        role = msg["role"]
        content = msg["content"]
        if role == "assistant":
            st.markdown(f"**🏛️ Consultant:** {content}")
        else:
            st.markdown(f"**You:** {content}")

    # Ready banner — shown when enough info is available
    if st.session_state.consultant_brief:
        st.success(
            "✅ Ready to send to the council. "
            "You can still add more details below, or click **Send to Council** to proceed."
        )
        if st.button("✅ Send to Council", type="primary", use_container_width=True):
            # Rebuild council input one final time to capture any last additions
            elem_sel = st.session_state.get("element_selections")
            tech_spec = elem_sel.to_technical_spec() if elem_sel else ""
            council_input = _format_conversation_for_council(
                project.input_data.text_description,
                st.session_state.consultant_history,
                tech_spec=tech_spec,
            )

            project.update_status(ProjectStatus.COUNCIL_REVIEW)
            store.save_project(project)

            st.session_state.current_page = "council"
            st.session_state.council_messages = []

            images_data = st.session_state.images_data
            image_data = images_data[0]["data"] if images_data else None
            image_mime = images_data[0]["mime_type"] if images_data else "image/png"

            _run_council(
                project.id,
                council_input,
                image_data,
                image_mime,
                all_images=images_data,
            )

    st.markdown("---")

    # Chat input — always visible so the user can keep adding details
    user_reply = st.text_input(
        "Add more details (optional)",
        placeholder="Anything else you want the council to know...",
        key="consultant_input",
    )

    # Image attachment in chat
    chat_images = st.file_uploader(
        "Attach images *(optional — these will be sent to the council)*",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        key="consultant_chat_images",
    )
    if chat_images:
        cols = st.columns(min(len(chat_images), 4))
        for i, f in enumerate(chat_images):
            with cols[i % len(cols)]:
                st.image(f, caption=f.name, use_container_width=True)

    col_send, col_skip = st.columns([2, 1])

    with col_send:
        if st.button("📨 Send", type="primary", use_container_width=True):
            if user_reply.strip() or chat_images:
                # Process any newly attached images
                if chat_images:
                    _add_chat_images_to_project(project, store, chat_images)

                msg = user_reply.strip()
                if chat_images and msg:
                    msg += f" (attached {len(chat_images)} image(s))"
                elif chat_images:
                    msg = f"(attached {len(chat_images)} image(s))"
                _handle_consultant_reply(project, msg)

    with col_skip:
        if st.button(
            "⏭️ Skip — Send to Council",
            use_container_width=True,
        ):
            # Process any attached images before skipping
            if chat_images:
                _add_chat_images_to_project(project, store, chat_images)

            project.update_status(ProjectStatus.COUNCIL_REVIEW)
            store.save_project(project)

            st.session_state.current_page = "council"
            st.session_state.council_messages = []

            images_data = st.session_state.images_data
            image_data = images_data[0]["data"] if images_data else None
            image_mime = (
                images_data[0]["mime_type"] if images_data else "image/png"
            )

            elem_sel = st.session_state.get("element_selections")
            tech_spec = elem_sel.to_technical_spec() if elem_sel else ""
            council_input = _format_conversation_for_council(
                project.input_data.text_description,
                st.session_state.consultant_history,
                tech_spec=tech_spec,
            )

            _run_council(
                project.id,
                council_input,
                image_data,
                image_mime,
                all_images=images_data,
            )


def _add_chat_images_to_project(project, store: ProjectStore, uploaded_files):
    """Save images attached during consultant chat and add to session data."""
    for uploaded_file in uploaded_files:
        file_bytes = uploaded_file.read()
        saved_path = store.save_uploaded_image(
            project.id, file_bytes, uploaded_file.name
        )
        project.input_data.image_paths.append(str(saved_path))

        b64, mime = ImageService.encode_uploaded_bytes(
            file_bytes, uploaded_file.name
        )
        st.session_state.images_data.append({"data": b64, "mime_type": mime})

    store.save_project(project)


def _handle_consultant_reply(project, user_message: str):
    """Process the user's reply in the consultant chat."""
    from app.agents.consultant import Consultant
    from app.services.openrouter import run_async

    # Add user message to history first so it appears in the conversation
    st.session_state.consultant_history.append(
        {"role": "user", "content": user_message}
    )

    with st.spinner("Consultant is thinking..."):
        try:
            consultant = Consultant()
            result = run_async(
                consultant.continue_conversation(
                    conversation_history=st.session_state.consultant_history,
                    user_message=user_message,
                )
            )

            # Add consultant response to history
            st.session_state.consultant_history.append(
                {"role": "assistant", "content": result["response_text"]}
            )

            # When done, build the council input from the raw conversation
            if result.get("done"):
                elem_sel = st.session_state.get("element_selections")
                tech_spec = elem_sel.to_technical_spec() if elem_sel else ""
                st.session_state.consultant_brief = _format_conversation_for_council(
                    project.input_data.text_description,
                    st.session_state.consultant_history,
                    tech_spec=tech_spec,
                )

        except Exception as e:
            st.session_state.consultant_history.append(
                {
                    "role": "assistant",
                    "content": f"(Error: {e}) — You can proceed with what we have.",
                }
            )
            # On error, pass the raw input through
            st.session_state.consultant_brief = (
                project.input_data.text_description or "Design as described."
            )

    st.rerun()


# ---------------------------------------------------------------------------
# Page: Council View
# ---------------------------------------------------------------------------
def page_council():
    render_header()
    st.markdown("### 🔍 Council Deliberation")

    store: ProjectStore = st.session_state.store
    project_id = st.session_state.current_project_id

    # Show progress messages
    if st.session_state.council_messages:
        for msg in st.session_state.council_messages:
            st.markdown(msg)

    # Show detailed council state
    if st.session_state.council_state:
        st.markdown("---")
        st.markdown("### Deliberation Details")
        render_council_progress(st.session_state.council_state)

    # --- Recovery: no session data but project exists ---
    has_session_data = bool(
        st.session_state.council_messages or st.session_state.council_state
    )

    if not has_session_data and project_id:
        # Check if DSD was saved to disk even though session state was lost
        dsd = store.load_dsd(project_id)
        if dsd:
            st.success(
                "Council deliberation completed previously! "
                "The Design Specification was recovered from disk."
            )
            st.session_state.current_dsd = dsd
            # Also fix the project status if still stuck
            project = store.load_project(project_id)
            if project and project.status == ProjectStatus.COUNCIL_REVIEW:
                project.dsd_id = dsd.project_id
                if dsd.version not in project.dsd_versions:
                    project.dsd_versions.append(dsd.version)
                project.update_status(ProjectStatus.AWAITING_CONFIRMATION)
                store.save_project(project)
        else:
            # DSD never saved — council results were truly lost
            project = store.load_project(project_id)
            if project:
                st.warning(
                    "The council deliberation ran but its results were lost "
                    "due to an earlier error. You can re-run it below — "
                    "your project input is still saved."
                )
                st.markdown(f"**Project:** {project.name}")
                st.markdown(
                    f"**Input:** {project.input_data.text_description or 'Image only'}"
                )

                if st.button("🔄 Re-run Council Deliberation", type="primary"):
                    # Re-load image data if available
                    image_data = None
                    image_mime_type = "image/png"
                    if project.input_data.image_paths:
                        img_path = Path(project.input_data.image_paths[0])
                        if img_path.exists():
                            file_bytes = img_path.read_bytes()
                            b64, mime = ImageService.encode_uploaded_bytes(
                                file_bytes, img_path.name
                            )
                            image_data = b64
                            image_mime_type = mime

                    st.session_state.council_messages = []
                    _run_council(
                        project.id,
                        project.input_data.text_description,
                        image_data,
                        image_mime_type,
                    )
                return  # Don't show navigation below

    # Navigation
    if st.session_state.current_dsd:
        st.markdown(
            "**The council has finished.** Review the full specification on the "
            "next page. If anything is wrong — dimensions, elements, style, "
            "layout — you can correct it before any images are generated."
        )
        if st.button("📋 Review & Correct the Specification →", type="primary"):
            st.session_state.current_page = "review_dsd"
            st.rerun()


# ---------------------------------------------------------------------------
# Page: Review DSD
# ---------------------------------------------------------------------------
def page_review_dsd():
    render_header()
    st.markdown("### 📋 Design Specification Review")

    dsd = st.session_state.current_dsd
    if dsd is None:
        # Try loading from disk
        if st.session_state.current_project_id:
            dsd = st.session_state.store.load_dsd(
                st.session_state.current_project_id
            )
            st.session_state.current_dsd = dsd

    if dsd is None:
        st.warning("No Design Specification found. Please start a new project.")
        return

    # Prominent correction banner — always visible before the tabs
    st.info(
        "**Review the specification below carefully.** "
        "The council analyzed your input and agreed on this — but they may have "
        "gotten something wrong. If dimensions, elements, style, layout, or "
        "anything else is incorrect, use the **'Correct the Council'** tab to "
        "tell them in plain language before generating any images."
    )

    # Tabs: View (read-only) vs Corrections (prominent, second tab) vs Edit
    tab_view, tab_correct, tab_edit = st.tabs([
        "📋 View Specification",
        "🔧 Correct the Council",
        "✏️ Edit Fields Manually",
    ])

    with tab_view:
        st.markdown(
            "The Council has analyzed your input and agreed on this specification. "
            "Review every detail — dimensions, elements, style, and layout."
        )
        render_dsd_display(dsd)

    with tab_correct:
        st.markdown(
            "**Tell the council what they got wrong** — in plain language. "
            "The specification will be updated automatically."
        )
        st.markdown(
            "Examples: *\"The width should be 150cm, not 80cm\"* · "
            "*\"I wanted 4 shelves, not 2\"* · "
            "*\"The style should be industrial, not Scandinavian\"* · "
            "*\"The layout is L-shaped, the council described it as straight\"*"
        )
        _render_dsd_corrections(dsd)

    with tab_edit:
        st.markdown(
            "Directly edit individual fields. Use this for quick number or "
            "text corrections. Use **Correct the Council** for structural changes."
        )
        _render_dsd_editor(dsd)

    # Actions
    st.markdown("---")
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("✅ Approve & Generate Images", type="primary"):
            st.session_state.current_page = "generating"
            st.rerun()

    with col2:
        if st.button("🔍 View Council Details"):
            st.session_state.current_page = "council"
            st.rerun()

    with col3:
        if st.button("🔄 Start Over"):
            st.session_state.current_page = "new_project"
            st.session_state.current_project_id = None
            st.session_state.current_dsd = None
            st.session_state.council_state = None
            st.rerun()


def _render_dsd_editor(dsd):
    """Render editable DSD fields."""
    changed = False

    # Basic info
    new_name = st.text_input("Design Name", value=dsd.name, key="edit_name")
    if new_name != dsd.name:
        dsd.name = new_name
        changed = True

    new_desc = st.text_area(
        "Description", value=dsd.description, height=100, key="edit_desc"
    )
    if new_desc != dsd.description:
        dsd.description = new_desc
        changed = True

    # Dimensions
    st.markdown("**Dimensions**")
    dcol1, dcol2, dcol3 = st.columns(3)
    with dcol1:
        w = st.text_input("Width", value=dsd.dimensions.width or "", key="edit_w")
        if w != (dsd.dimensions.width or ""):
            dsd.dimensions.width = w or None
            changed = True
    with dcol2:
        h = st.text_input("Height", value=dsd.dimensions.height or "", key="edit_h")
        if h != (dsd.dimensions.height or ""):
            dsd.dimensions.height = h or None
            changed = True
    with dcol3:
        d = st.text_input("Depth", value=dsd.dimensions.depth or "", key="edit_d")
        if d != (dsd.dimensions.depth or ""):
            dsd.dimensions.depth = d or None
            changed = True

    # Style
    st.markdown("**Style**")
    new_style = st.text_input(
        "Aesthetic", value=dsd.style.aesthetic, key="edit_aesthetic"
    )
    if new_style != dsd.style.aesthetic:
        dsd.style.aesthetic = new_style
        changed = True

    # Colors
    st.markdown("**Colors**")
    ccol1, ccol2, ccol3 = st.columns(3)
    with ccol1:
        pc = st.text_input(
            "Primary Color", value=dsd.colors.primary or "", key="edit_pc"
        )
        if pc != (dsd.colors.primary or ""):
            dsd.colors.primary = pc or None
            changed = True
    with ccol2:
        sc = st.text_input(
            "Secondary Color", value=dsd.colors.secondary or "", key="edit_sc"
        )
        if sc != (dsd.colors.secondary or ""):
            dsd.colors.secondary = sc or None
            changed = True
    with ccol3:
        ac = st.text_input(
            "Accent Color", value=dsd.colors.accent or "", key="edit_ac"
        )
        if ac != (dsd.colors.accent or ""):
            dsd.colors.accent = ac or None
            changed = True

    # Views to generate (council-decided, show as info)
    st.markdown("**Views to Generate** *(decided by the council)*")
    if dsd.views_to_generate:
        for vs in dsd.views_to_generate:
            st.markdown(f"- **{vs.label}** ({vs.type}): {vs.description}")
    else:
        st.info("No views specified — defaults will be used.")

    # Generation notes
    new_notes = st.text_area(
        "Generation Notes (extra instructions for image generation)",
        value=dsd.generation_notes or "",
        height=80,
        key="edit_notes",
    )
    if new_notes != (dsd.generation_notes or ""):
        dsd.generation_notes = new_notes
        changed = True

    # Save changes
    if changed:
        st.session_state.current_dsd = dsd
        if st.session_state.current_project_id:
            st.session_state.store.save_dsd(
                st.session_state.current_project_id, dsd
            )
        st.caption("Changes saved automatically.")


def _render_dsd_corrections(dsd):
    """Natural-language correction interface for post-council DSD fixes."""
    correction_text = st.text_area(
        "What did the council get wrong?",
        placeholder=(
            "e.g., The dimensions should be 120cm wide, not 80cm.\n"
            "e.g., I wanted 3 shelves, not 2. Also the color should be navy blue.\n"
            "e.g., The layout is L-shaped, the council described it as straight."
        ),
        height=120,
        key="dsd_correction_input",
    )

    correction_images = st.file_uploader(
        "Attach reference images *(optional)*",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        key="dsd_correction_images",
    )
    if correction_images:
        cols = st.columns(min(len(correction_images), 4))
        for i, f in enumerate(correction_images):
            with cols[i % len(cols)]:
                st.image(f, caption=f.name, use_container_width=True)

    if st.button(
        "Apply Corrections",
        type="primary",
        disabled=not correction_text,
        key="apply_dsd_corrections",
    ):
        _apply_dsd_corrections(dsd, correction_text)


def _apply_dsd_corrections(dsd, correction_text: str):
    """Use the refiner to apply natural-language corrections to the DSD."""
    from app.agents.refiner import Refiner
    from app.services.openrouter import run_async

    store: ProjectStore = st.session_state.store
    project_id = st.session_state.current_project_id

    with st.spinner("Applying corrections to the specification..."):
        try:
            refiner = Refiner()
            updated_dsd = run_async(
                refiner.apply_change(
                    change_request=correction_text,
                    dsd=dsd,
                )
            )

            # Save the updated DSD
            store.save_dsd(project_id, updated_dsd)
            st.session_state.current_dsd = updated_dsd

            st.success(
                f"Specification updated to v{updated_dsd.version}. "
                "Review the changes in the View tab."
            )
            st.rerun()

        except Exception as e:
            st.error(f"Failed to apply corrections: {e}")


# ---------------------------------------------------------------------------
# Technical drawing view types (generated in Stage 1)
# ---------------------------------------------------------------------------
_TECHNICAL_VIEWS = {"floor_plan", "front_elevation", "side_elevation", "rear_elevation"}


# ---------------------------------------------------------------------------
# Page: Generating Technical Drawings (Stage 1)
# ---------------------------------------------------------------------------
def page_generating():
    render_header()
    st.markdown("### ⚙️ Generating Technical Drawings...")

    project_id = st.session_state.current_project_id
    dsd = st.session_state.current_dsd

    if not project_id or not dsd:
        st.warning("No project or DSD found. Please start a new project.")
        return

    from app.models.dsd import ViewSpec

    # Determine which technical views to generate
    all_views = dsd.views_to_generate or dsd.get_applicable_views()
    technical_views = [v for v in all_views if v.type in _TECHNICAL_VIEWS]

    # If the DSD has no technical views, create sensible defaults
    if not technical_views:
        technical_views = [
            ViewSpec(type="floor_plan", label="Floor Plan", description="Top-down layout"),
            ViewSpec(type="front_elevation", label="Front Elevation", description="Frontal view"),
        ]

    # Mandatory: ensure at least 1 floor_plan + 1 front_elevation
    has_floor = any(v.type == "floor_plan" for v in technical_views)
    has_elev = any(v.type == "front_elevation" for v in technical_views)
    if not has_floor:
        technical_views.insert(0, ViewSpec(
            type="floor_plan", label="Floor Plan", description="Top-down layout"
        ))
    if not has_elev:
        technical_views.append(ViewSpec(
            type="front_elevation", label="Front Elevation", description="Frontal view"
        ))

    st.markdown(f"**Design:** {dsd.name}")
    st.markdown(f"**Technical drawings to generate:** {len(technical_views)}")
    for v in technical_views:
        st.markdown(f"- **{v.label}** ({v.type})")
    st.markdown(
        "\n*After reviewing these drawings, a realistic lifestyle render "
        "will be generated in the next step.*"
    )

    st.markdown("---")

    # Check if generation was already run (avoid double-run on rerun)
    if st.session_state.get("generation_done"):
        st.success("Technical drawings complete! Proceeding to review...")
        st.session_state.generation_done = False
        st.session_state.current_page = "drawings_review"
        st.rerun()
        return

    # Run generation
    progress_container = st.container()
    progress_messages = []

    def on_progress(msg: str):
        progress_messages.append(msg)

    from app.agents.generator import Generator
    from app.services.openrouter import run_async

    store: ProjectStore = st.session_state.store

    with st.spinner("Generating technical drawings... This may take a few minutes."):
        try:
            generator = Generator()
            generated_images = run_async(
                generator.generate_all_views(
                    dsd=dsd,
                    project_id=project_id,
                    on_progress=on_progress,
                    view_filter=technical_views,
                )
            )

            # Show progress messages
            with progress_container:
                for msg in progress_messages:
                    st.markdown(msg)

            # Save generated images to the project
            project = store.load_project(project_id)
            if project:
                for img in generated_images:
                    project.add_image(img)
                project.update_status(ProjectStatus.DRAWINGS_REVIEW)
                store.save_project(project)

            st.session_state.generation_messages = progress_messages

            if generated_images:
                st.success(
                    f"Successfully generated {len(generated_images)} drawing(s)! "
                    f"Review them before generating the realistic render."
                )
                st.session_state.generation_done = True
                st.session_state.current_page = "drawings_review"
                st.rerun()
            else:
                st.error("No images were generated. Please try again.")

        except Exception as e:
            with progress_container:
                for msg in progress_messages:
                    st.markdown(msg)
            st.error(f"Generation failed: {e}")
            if st.button("🔄 Retry Generation"):
                st.rerun()
            if st.button("<- Back to DSD Review"):
                st.session_state.current_page = "review_dsd"
                st.rerun()


# ---------------------------------------------------------------------------
# Page: Drawings Review (user approves technical drawings before render)
# ---------------------------------------------------------------------------
def page_drawings_review():
    render_header()
    st.markdown("### 📐 Review Technical Drawings")

    project_id = st.session_state.current_project_id
    dsd = st.session_state.current_dsd

    if not project_id or not dsd:
        st.warning("No project or DSD found. Please start a new project.")
        return

    store: ProjectStore = st.session_state.store
    project = store.load_project(project_id)
    if not project or not project.images:
        st.warning("No drawings found to review.")
        return

    # Only show technical drawings (not any previous renders)
    technical_images = [
        img for img in project.get_latest_images()
        if img.view_type in _TECHNICAL_VIEWS
    ]

    if not technical_images:
        st.warning("No technical drawings found.")
        return

    st.markdown(
        "Review your **technical drawings** below. "
        "If everything looks good, approve them to generate the **realistic lifestyle render**. "
        "If something needs fixing, you can go back and adjust the DSD or regenerate individual views."
    )
    st.markdown("---")

    # Display each technical drawing with its label
    for img in technical_images:
        st.markdown(f"#### {img.display_label}")
        img_path = Path(img.file_path)
        if img_path.exists():
            st.image(str(img_path), use_container_width=True)
        else:
            st.warning(f"Image file not found: {img_path}")
        st.markdown("---")

    # Show original input for reference
    if project.input_data.text_description or project.input_data.image_paths:
        with st.expander("📎 Original Input (for comparison)", expanded=False):
            if project.input_data.text_description:
                st.markdown(
                    f"**Description:** {project.input_data.text_description}"
                )
            for ref_path in project.input_data.image_paths:
                p = Path(ref_path)
                if p.exists():
                    st.image(str(p), caption="Original sketch", width=300)

    # Actions
    st.markdown("---")
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button(
            "✅ Approve & Generate Realistic Render",
            type="primary",
            use_container_width=True,
        ):
            # Lock the baseline — design intent is now frozen
            dsd = st.session_state.current_dsd
            if dsd and not dsd.baseline_locked:
                dsd.lock_baseline()
                store.save_dsd(project.id, dsd)
                st.session_state.current_dsd = dsd

            project.update_status(ProjectStatus.GENERATING_RENDER)
            store.save_project(project)
            st.session_state.current_page = "generating_render"
            st.rerun()

    with col2:
        if st.button("🔄 Regenerate Drawings", use_container_width=True):
            st.session_state.generation_done = False
            st.session_state.current_page = "generating"
            st.rerun()

    with col3:
        if st.button("📋 Edit DSD", use_container_width=True):
            st.session_state.current_page = "review_dsd"
            st.rerun()

    # Individual drawing regeneration
    st.markdown("---")
    st.markdown("#### Regenerate Individual Drawing")
    if technical_images:
        # Build a mapping from display label -> image for selection
        label_to_img = {}
        for img in technical_images:
            label_to_img[img.display_label] = img

        selected_label = st.selectbox(
            "Select drawing to regenerate",
            list(label_to_img.keys()),
            key="drawings_regen_select",
        )
        regen_feedback = st.text_input(
            "Optional feedback",
            placeholder="e.g., Make the dimensions larger, add more detail to shelves",
            key="drawings_regen_feedback",
        )
        if st.button("🔄 Regenerate Selected Drawing"):
            sel_img = label_to_img[selected_label]
            _regenerate_single_view(
                project.id, sel_img.view_type, regen_feedback,
                view_spec_id=sel_img.spec_id,
                view_label=sel_img.display_label,
            )


# ---------------------------------------------------------------------------
# Page: Generating Realistic Render (Stage 2)
# ---------------------------------------------------------------------------
def page_generating_render():
    render_header()
    st.markdown("### 🎨 Generating Realistic Render...")

    project_id = st.session_state.current_project_id
    dsd = st.session_state.current_dsd

    if not project_id or not dsd:
        st.warning("No project or DSD found. Please start a new project.")
        return

    from app.models.dsd import ViewSpec

    st.markdown(f"**Design:** {dsd.name}")
    st.markdown(
        "Generating a **photorealistic lifestyle render** showing your design "
        "in a real-world environment with contextual items and natural lighting."
    )
    st.markdown("---")

    # Check if render was already run (avoid double-run on rerun)
    if st.session_state.get("render_done"):
        st.success("Realistic render complete! Proceeding to gallery...")
        st.session_state.render_done = False
        st.session_state.current_page = "gallery"
        st.rerun()
        return

    # Run generation
    progress_container = st.container()
    progress_messages = []

    def on_progress(msg: str):
        progress_messages.append(msg)

    from app.agents.generator import Generator
    from app.services.openrouter import run_async

    store: ProjectStore = st.session_state.store

    render_view = ViewSpec(
        type="realistic_render",
        label="Realistic Lifestyle Render",
        description=(
            "Photorealistic 3D render showing the design in a real-world "
            "environment with contextual items, props, and natural lighting"
        ),
    )

    with st.spinner(
        "Generating realistic render... This may take a few minutes."
    ):
        try:
            generator = Generator()
            generated_images = run_async(
                generator.generate_all_views(
                    dsd=dsd,
                    project_id=project_id,
                    on_progress=on_progress,
                    view_filter=[render_view],
                )
            )

            # Show progress messages
            with progress_container:
                for msg in progress_messages:
                    st.markdown(msg)

            # Save generated images to the project
            project = store.load_project(project_id)
            if project:
                for img in generated_images:
                    project.add_image(img)
                project.update_status(ProjectStatus.COMPLETE)
                store.save_project(project)

            if generated_images:
                st.success("Realistic render generated! Going to gallery...")
                st.session_state.render_done = True
                st.session_state.current_page = "gallery"
                st.rerun()
            else:
                st.error("Render generation failed. Please try again.")

        except Exception as e:
            with progress_container:
                for msg in progress_messages:
                    st.markdown(msg)
            st.error(f"Render generation failed: {e}")
            if st.button("🔄 Retry Render"):
                st.rerun()
            if st.button("📐 Back to Drawings Review"):
                st.session_state.current_page = "drawings_review"
                st.rerun()


# ---------------------------------------------------------------------------
# Page: Quality Review — REMOVED (user inspects images themselves in gallery)
# This stub exists only to redirect legacy sessions that still carry the
# quality_review status.
# ---------------------------------------------------------------------------
def page_quality_review():
    """Legacy redirect — quality review step has been removed."""
    store: ProjectStore = st.session_state.store
    project_id = st.session_state.current_project_id
    if project_id:
        project = store.load_project(project_id)
        if project:
            project.update_status(ProjectStatus.COMPLETE)
            store.save_project(project)
    st.session_state.current_page = "gallery"
    st.rerun()


# ---------------------------------------------------------------------------
# (Placeholder to keep line reference intact — _show_review_results removed)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Page: Gallery
# ---------------------------------------------------------------------------
def page_gallery():
    render_header()
    st.markdown("### 🖼️ Design Gallery")

    if not st.session_state.current_project_id:
        st.warning("No active project. Please start or select a project.")
        return

    store: ProjectStore = st.session_state.store
    project = store.load_project(st.session_state.current_project_id)

    if not project:
        st.warning("Project not found.")
        return

    if not project.images:
        st.info("No images generated yet.")
        if st.session_state.current_dsd:
            if st.button("🚀 Generate Images Now"):
                st.session_state.current_page = "generating"
                st.rerun()
        return

    # Show project info
    st.markdown(f"**Project:** {project.name}")
    latest_images = project.get_latest_images()
    st.markdown(
        f"**Images:** {len(latest_images)} view(s) "
        f"({len(project.images)} total including history)"
    )

    # Tabs: Gallery vs Comparison
    tab_gallery, tab_compare = st.tabs(["🖼️ Gallery", "🔍 Compare"])

    with tab_gallery:
        # Show original input for reference
        if project.input_data.text_description or project.input_data.image_paths:
            with st.expander("📎 Original Input", expanded=False):
                if project.input_data.text_description:
                    st.markdown(
                        f"**Description:** {project.input_data.text_description}"
                    )
                for img_path in project.input_data.image_paths:
                    p = Path(img_path)
                    if p.exists():
                        st.image(str(p), caption="Original sketch", width=300)

        render_image_gallery(latest_images)

        # Download all images as ZIP
        if len(latest_images) > 1:
            st.markdown("---")
            _render_download_all_zip(project, latest_images)

    with tab_compare:
        _render_comparison_view(project, latest_images)

    # Actions
    st.markdown("---")
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("✏️ Request Changes", use_container_width=True):
            st.session_state.current_page = "refine"
            st.rerun()

    with col2:
        if st.button("🔄 Regenerate All", use_container_width=True):
            st.session_state.current_page = "generating"
            st.rerun()

    with col3:
        if st.button("📋 View DSD", use_container_width=True):
            st.session_state.current_page = "review_dsd"
            st.rerun()

    # Individual image regeneration
    st.markdown("---")
    st.markdown("#### Regenerate Individual View")
    if latest_images:
        label_to_img = {}
        for img in latest_images:
            label_to_img[img.display_label] = img

        selected_label = st.selectbox(
            "Select view to regenerate",
            list(label_to_img.keys()),
        )
        regen_feedback = st.text_input(
            "Optional feedback for regeneration",
            placeholder="e.g., Make the lighting warmer, show more wood grain detail",
        )
        if st.button("🔄 Regenerate Selected View"):
            sel_img = label_to_img[selected_label]
            _regenerate_single_view(
                project.id, sel_img.view_type, regen_feedback,
                view_spec_id=sel_img.spec_id,
                view_label=sel_img.display_label,
            )


def _render_comparison_view(project, images):
    """Side-by-side comparison of generated views."""
    if len(images) < 2:
        st.info("Need at least 2 images for comparison. Generate more views!")
        return

    st.markdown("**Select two views to compare side-by-side:**")

    # Build unique keys for each image (use id since view_type can repeat)
    img_labels = {}
    for img in images:
        img_labels[img.id] = img.display_label

    col_sel1, col_sel2 = st.columns(2)
    with col_sel1:
        left_id = st.selectbox(
            "Left image",
            [img.id for img in images],
            index=0,
            format_func=lambda x: img_labels.get(x, x),
            key="cmp_left",
        )
    with col_sel2:
        right_options = [img.id for img in images if img.id != left_id]
        if not right_options:
            right_options = [img.id for img in images]
        right_id = st.selectbox(
            "Right image",
            right_options,
            index=0,
            format_func=lambda x: img_labels.get(x, x),
            key="cmp_right",
        )

    left_img = next((img for img in images if img.id == left_id), None)
    right_img = next((img for img in images if img.id == right_id), None)

    if left_img and right_img:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**{img_labels.get(left_id, left_id)}**")
            lpath = Path(left_img.file_path)
            if lpath.exists():
                st.image(str(lpath), use_container_width=True)
            if left_img.quality_score is not None:
                st.caption(f"Quality: {left_img.quality_score:.1f}/10")

        with col2:
            st.markdown(f"**{img_labels.get(right_id, right_id)}**")
            rpath = Path(right_img.file_path)
            if rpath.exists():
                st.image(str(rpath), use_container_width=True)
            if right_img.quality_score is not None:
                st.caption(f"Quality: {right_img.quality_score:.1f}/10")

    # Also show DSD summary for reference
    dsd = st.session_state.current_dsd
    if dsd:
        with st.expander("📋 DSD Reference", expanded=False):
            render_dsd_display(dsd)


def _render_download_all_zip(project, images):
    """Offer a 'Download All' ZIP of the latest generated images."""
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for img in images:
            p = Path(img.file_path)
            if p.exists():
                label = img.display_label.replace(" ", "_")
                arcname = f"{project.name}_{label}{p.suffix}"
                zf.write(p, arcname)
    buf.seek(0)

    st.download_button(
        label="📦 Download All Images (ZIP)",
        data=buf,
        file_name=f"{project.name.replace(' ', '_')}_renders.zip",
        mime="application/zip",
        use_container_width=True,
    )


def _regenerate_single_view(
    project_id: str,
    view_type_str: str,
    feedback: str = "",
    view_spec_id: str = "",
    view_label: str = "",
):
    """Regenerate a single view and update the project."""
    from app.agents.generator import Generator
    from app.models.dsd import ViewSpec
    from app.services.openrouter import run_async

    dsd = st.session_state.current_dsd
    if not dsd:
        st.error("No DSD found.")
        return

    # Find the matching ViewSpec from the DSD, or create a basic one
    view_spec = None
    if view_spec_id:
        for vs in (dsd.views_to_generate or []):
            if vs.id == view_spec_id:
                view_spec = vs
                break
    if view_spec is None:
        view_spec = ViewSpec(
            type=view_type_str,
            label=view_label or view_type_str.replace("_", " ").title(),
        )

    display_label = view_spec.label or view_type_str.replace("_", " ").title()
    store: ProjectStore = st.session_state.store

    with st.spinner(f"Regenerating {display_label}..."):
        try:
            generator = Generator()
            new_image = run_async(
                generator.regenerate_view(
                    dsd=dsd,
                    view_spec=view_spec,
                    project_id=project_id,
                    feedback=feedback,
                )
            )

            if new_image:
                project = store.load_project(project_id)
                if project:
                    project.add_image(new_image)
                    store.save_project(project)
                st.success("View regenerated successfully!")
                st.rerun()
            else:
                st.error("Regeneration failed. Please try again.")

        except Exception as e:
            st.error(f"Regeneration error: {e}")


# ---------------------------------------------------------------------------
# Page: Refinement
# ---------------------------------------------------------------------------
def page_refine():
    render_header()
    st.markdown("### ✏️ Request Changes")

    project_id = st.session_state.current_project_id
    dsd = st.session_state.current_dsd

    if not project_id or not dsd:
        st.warning("No active project with a DSD. Please start a project first.")
        return

    store: ProjectStore = st.session_state.store
    project = store.load_project(project_id)
    if not project:
        st.warning("Project not found.")
        return

    # Show current design summary
    st.markdown(f"**Design:** {dsd.name} (v{dsd.version})")
    with st.expander("📋 Current DSD Summary", expanded=False):
        render_dsd_display(dsd)

    # Show current images for reference
    latest_images = project.get_latest_images()
    if latest_images:
        with st.expander("🖼️ Current Images", expanded=False):
            cols = st.columns(min(len(latest_images), 3))
            for i, img in enumerate(latest_images):
                with cols[i % len(cols)]:
                    p = Path(img.file_path)
                    if p.exists():
                        st.image(str(p), caption=img.display_label, use_container_width=True)

    st.markdown("---")
    st.markdown(
        "Describe the change you want. The system will classify it, "
        "update the design specification, and regenerate only the affected views."
    )

    # Change request input
    change_request = st.text_area(
        "Describe the change you want",
        placeholder="e.g., Change the primary color to navy blue\n"
                    "e.g., Add a drawer to the bottom shelf\n"
                    "e.g., Make the overall height 200cm instead of 180cm",
        height=120,
        key="refine_input",
    )

    # Optional reference images for the change
    refine_images = st.file_uploader(
        "Reference images for the change *(optional)*",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        key="refine_images",
    )
    if refine_images:
        cols = st.columns(min(len(refine_images), 4))
        for i, f in enumerate(refine_images):
            with cols[i % len(cols)]:
                st.image(f, caption=f.name, use_container_width=True)

    # Show change history
    if dsd.change_history:
        with st.expander(f"📜 Change History ({len(dsd.change_history)} changes)", expanded=False):
            for ch in reversed(dsd.change_history):
                st.markdown(
                    f"**v{ch.version}** ({ch.change_type.value}) — {ch.description}"
                )

    # Submit button
    if st.button("🚀 Apply Change", type="primary", disabled=not change_request):
        _run_refinement(project_id, dsd, change_request, store)

    # Rollback
    if dsd.version > 1:
        st.markdown("---")
        if st.button("⏪ Rollback to Previous Version"):
            prev_version = dsd.version - 1
            prev_dsd = store.load_dsd(project_id, version=prev_version)
            if prev_dsd:
                st.session_state.current_dsd = prev_dsd
                store.save_dsd(project_id, prev_dsd)
                st.success(f"Rolled back to DSD version {prev_version}")
                st.rerun()
            else:
                st.warning(f"Version {prev_version} not found on disk.")

    # Navigation
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🖼️ Back to Gallery", use_container_width=True):
            st.session_state.current_page = "gallery"
            st.rerun()
    with col2:
        if st.button("📋 View DSD", use_container_width=True):
            st.session_state.current_page = "review_dsd"
            st.rerun()


def _run_refinement(project_id, dsd, change_request, store):
    """Execute the full refinement pipeline with progress."""
    from app.agents.refiner import Refiner
    from app.services.openrouter import run_async

    progress_container = st.container()
    messages = []

    def on_progress(msg: str):
        messages.append(msg)

    with st.spinner("Applying change... This may take a few minutes."):
        try:
            refiner = Refiner()
            updated_dsd, classification, new_images = run_async(
                refiner.refine(
                    change_request=change_request,
                    dsd=dsd,
                    project_id=project_id,
                    on_progress=on_progress,
                )
            )

            # Show progress messages
            with progress_container:
                for msg in messages:
                    st.markdown(msg)

            # Show classification
            change_type = classification.get("change_type", "unknown")
            risk = classification.get("risk_level", "unknown")
            st.info(
                f"Change classified as **{change_type}** (risk: {risk}). "
                f"{len(new_images)} view(s) regenerated."
            )

            # Update session and project
            st.session_state.current_dsd = updated_dsd
            store.save_dsd(project_id, updated_dsd)

            project = store.load_project(project_id)
            if project:
                for img in new_images:
                    project.add_image(img)
                project.dsd_versions.append(updated_dsd.version)
                # Route to drawings_review so user can verify the
                # regenerated technical drawings before realistic render
                project.update_status(ProjectStatus.DRAWINGS_REVIEW)
                store.save_project(project)

            if new_images:
                st.success(
                    f"Change applied! DSD updated to v{updated_dsd.version}. "
                    f"{len(new_images)} technical drawing(s) regenerated. "
                    f"Review them before generating the realistic render."
                )
                if st.button("📐 Review Updated Drawings"):
                    st.session_state.current_page = "drawings_review"
                    st.rerun()
            else:
                st.success(
                    f"DSD updated to v{updated_dsd.version}. "
                    f"No images needed regeneration."
                )
                st.rerun()

        except Exception as e:
            with progress_container:
                for msg in messages:
                    st.markdown(msg)
            st.error(f"Refinement failed: {e}")


# ---------------------------------------------------------------------------
# Page: Projects List
# ---------------------------------------------------------------------------
def page_projects():
    render_header()
    st.markdown("### 📂 My Projects")

    store: ProjectStore = st.session_state.store
    projects = store.list_projects()

    if not projects:
        st.info("No projects yet. Start by creating a new design!")
        if st.button("➕ Create New Project"):
            st.session_state.current_page = "new_project"
            st.rerun()
        return

    for proj_meta in projects:
        with st.container():
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                render_project_card(proj_meta)
            with col2:
                if st.button("Open", key=f"open_{proj_meta['id']}"):
                    st.session_state.current_project_id = proj_meta["id"]
                    # Load DSD if available
                    dsd = store.load_dsd(proj_meta["id"])
                    st.session_state.current_dsd = dsd
                    # Determine page based on status
                    status = proj_meta["status"]
                    if status == "consulting":
                        st.session_state.current_page = "consulting"
                    elif status == "council_review":
                        # Might be stuck — check if DSD exists
                        if dsd:
                            # DSD exists, fix the project status
                            project = store.load_project(proj_meta["id"])
                            if project:
                                project.dsd_id = dsd.project_id
                                if dsd.version not in project.dsd_versions:
                                    project.dsd_versions.append(dsd.version)
                                project.update_status(ProjectStatus.AWAITING_CONFIRMATION)
                                store.save_project(project)
                            st.session_state.current_page = "review_dsd"
                        else:
                            st.session_state.current_page = "council"
                    elif status == "awaiting_confirmation":
                        st.session_state.current_page = "review_dsd" if dsd else "council"
                    elif status == "drawings_review":
                        st.session_state.current_page = "drawings_review"
                    elif status == "generating_render":
                        st.session_state.current_page = "generating_render"
                    elif status == "quality_review":
                        st.session_state.current_page = "gallery"
                    elif status == "complete":
                        st.session_state.current_page = "gallery"
                    else:
                        st.session_state.current_page = "review_dsd" if dsd else "new_project"
                    st.rerun()
            with col3:
                if st.button("🗑️", key=f"del_{proj_meta['id']}"):
                    store.delete_project(proj_meta["id"])
                    if st.session_state.current_project_id == proj_meta["id"]:
                        st.session_state.current_project_id = None
                        st.session_state.current_dsd = None
                    st.rerun()
            st.markdown("---")


# ---------------------------------------------------------------------------
# Page Router
# ---------------------------------------------------------------------------
PAGE_MAP = {
    "new_project": page_new_project,
    "consulting": page_consulting,
    "council": page_council,
    "review_dsd": page_review_dsd,
    "generating": page_generating,
    "drawings_review": page_drawings_review,
    "generating_render": page_generating_render,
    "quality_review": page_quality_review,  # Legacy redirect only
    "gallery": page_gallery,
    "refine": page_refine,
    "projects": page_projects,
}

# Render the current page
current_page = st.session_state.get("current_page", "new_project")
page_fn = PAGE_MAP.get(current_page, page_new_project)
page_fn()

# Persist session state after each render
_save_session()
