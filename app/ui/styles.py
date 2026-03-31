"""
Custom CSS styling for the Architecture Agent Streamlit app.
"""

MAIN_CSS = """
<style>
/* ---- Global ---- */
.stApp {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}

/* ---- Header ---- */
.main-header {
    font-size: 2.2rem;
    font-weight: 700;
    color: #1a1a2e;
    margin-bottom: 0.2rem;
}

.sub-header {
    font-size: 1.0rem;
    color: #6c757d;
    margin-bottom: 2rem;
}

/* ---- Cards ---- */
.info-card {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 12px;
    padding: 1.5rem;
    color: white;
    margin-bottom: 1rem;
}

.info-card h3 {
    margin: 0 0 0.5rem 0;
    font-size: 1.1rem;
}

.info-card p {
    margin: 0;
    font-size: 0.9rem;
    opacity: 0.9;
}

/* ---- Status badges ---- */
.status-badge {
    display: inline-block;
    padding: 0.25rem 0.75rem;
    border-radius: 20px;
    font-size: 0.8rem;
    font-weight: 600;
}

.status-draft { background: #e9ecef; color: #495057; }
.status-council { background: #fff3cd; color: #856404; }
.status-generating { background: #cce5ff; color: #004085; }
.status-complete { background: #d4edda; color: #155724; }
.status-refining { background: #f8d7da; color: #721c24; }

/* ---- Council progress ---- */
.council-round {
    background: #f8f9fa;
    border-left: 4px solid #667eea;
    padding: 1rem;
    margin-bottom: 0.5rem;
    border-radius: 0 8px 8px 0;
}

.council-round.active {
    border-left-color: #28a745;
    background: #f0fff4;
}

.council-round.completed {
    border-left-color: #28a745;
}

/* ---- DSD display ---- */
.dsd-section {
    background: #f8f9fa;
    border-radius: 8px;
    padding: 1rem;
    margin-bottom: 0.75rem;
}

.dsd-section h4 {
    color: #1a1a2e;
    margin: 0 0 0.5rem 0;
    font-size: 1rem;
}

/* ---- Image gallery ---- */
.gallery-image {
    border-radius: 8px;
    border: 2px solid #e9ecef;
    transition: border-color 0.2s;
}

.gallery-image:hover {
    border-color: #667eea;
}

/* ---- Sidebar ---- */
section[data-testid="stSidebar"] {
    background: #1a1a2e;
}

section[data-testid="stSidebar"] .stMarkdown {
    color: #e9ecef;
}

/* ---- Progress indicators ---- */
.layer-indicator {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 0;
}

.layer-dot {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: #dee2e6;
}

.layer-dot.active {
    background: #667eea;
    box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.3);
}

.layer-dot.complete {
    background: #28a745;
}

/* ---- Pipeline steps ---- */
.pipeline-step {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.6rem 1rem;
    background: #f8f9fa;
    border-radius: 8px;
    margin-bottom: 0.4rem;
    border-left: 4px solid #dee2e6;
}

.pipeline-step.active {
    border-left-color: #667eea;
    background: #eef0ff;
}

.pipeline-step.done {
    border-left-color: #28a745;
}

/* ---- Quality review ---- */
.review-card {
    background: #f8f9fa;
    border-radius: 10px;
    padding: 1rem;
    margin-bottom: 0.75rem;
    border: 1px solid #e9ecef;
}

.review-card.approved {
    border-left: 4px solid #28a745;
}

.review-card.needs-work {
    border-left: 4px solid #ffc107;
}

.score-pill {
    display: inline-block;
    padding: 0.15rem 0.5rem;
    border-radius: 12px;
    font-size: 0.8rem;
    font-weight: 600;
    margin-right: 0.3rem;
}

.score-high { background: #d4edda; color: #155724; }
.score-mid  { background: #fff3cd; color: #856404; }
.score-low  { background: #f8d7da; color: #721c24; }

/* ---- Better tab styling ---- */
button[data-baseweb="tab"] {
    font-size: 0.95rem;
    font-weight: 600;
}

/* ---- Smooth transitions ---- */
.stImage img {
    border-radius: 8px;
    transition: transform 0.2s;
}

.stImage img:hover {
    transform: scale(1.01);
}
</style>
"""
