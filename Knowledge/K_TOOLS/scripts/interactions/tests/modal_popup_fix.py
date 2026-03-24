"""
Modal Popup Fix — Embedded Panel Validation
=============================================

Verifies that standalone pages rendered by the index viewer do NOT show
fullscreen modal popups when embedded in center-panel or content-panel.

Tests 6 interface pages (center-panel) and 5 publication pages (content-panel)
to confirm no modal overlay appears on load.

Rerunnable module — invoke via:
    python3 web_test_engine.py --module modal_popup_fix

Or run the full pipeline:
    python3 web_test_engine.py --module modal_popup_fix
    python3 generate_test_report.py --module modal_popup_fix
    python3 persist_test_run.py --module modal_popup_fix
"""

TEST_ID = "modal-popup-fix"
TITLE = "Modal Popup Fix — Embedded Panels"
TITLE_FR = "Correction Popup Modal — Panneaux intégrés"
SLUG = "test-modal-popup-fix"
OUTPUT_DIR = "docs/publications/test-modal-popup-fix"

# Pages that must NOT show modal popups when embedded
INTERFACE_TARGETS = [
    "interfaces/task-workflow/index.md",
    "interfaces/tests/index.md",
    "interfaces/session-review/index.md",
    "interfaces/project-viewer/index.md",
    "interfaces/live-mindmap/index.md",
    "interfaces/claude-interface/index.md",
]

PUBLICATION_TARGETS = [
    "publications/guide-main-navigator/index.md",
    "publications/guide-tests/index.md",
    "publications/guide-session-review/index.md",
    "publications/guide-commands/index.md",
    "publications/success-stories/story-28/index.md",
]

REQUEST = "Modal popup fix — verify no fullscreen prompt on embedded pages"
ORIGINAL_REQUEST = (
    "I have found a new bug that just raised which I want you to test and "
    "to proof it is fixed: now standalone interface or pages when embedded "
    "(displayed) in the central-panel or the content-panel are popping the "
    "modal windows at load for full screen or click here for normal browser "
    "view: this must not happen when a standalone page rendered by index "
    "viewer embedded in panel, this is new from our last changes on the "
    "main interface but be careful not to break the changes that are "
    "approved and running."
)


def get_targets():
    """Return all target pages for web_test_engine."""
    return INTERFACE_TARGETS + PUBLICATION_TARGETS


def get_test_config():
    """Return complete test configuration for the pipeline.

    Used by web_test_engine --module, generate_test_report --module,
    and persist_test_run --module to run the full pipeline with one flag.
    """
    return {
        "test_id": TEST_ID,
        "title": TITLE,
        "title_fr": TITLE_FR,
        "slug": SLUG,
        "output_dir": OUTPUT_DIR,
        "targets": get_targets(),
        "request": REQUEST,
        "original_request": ORIGINAL_REQUEST,
    }
