"""Render the implemented runtime boundaries as a standalone SVG; no external renderer."""

from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    boxes = [
        (65, 105, 250, 76, "PHONE / DESKTOP", "React · record / type / review", "#e8eee0"),
        (395, 105, 250, 76, "FASTAPI", "Authenticate · upload · accept", "#e8eee0"),
        (725, 105, 250, 76, "DURABLE WORKER", "Lease jobs · recover · retry", "#e8eee0"),
        (725, 255, 250, 76, "LOCAL SPEECH", "FFmpeg → Whisper small.en", "#f0ebdd"),
        (395, 255, 250, 76, "DIALOGUE ORCHESTRATOR", "Bounded calls · clarification", "#e8eee0"),
        (65, 255, 250, 76, "LOCAL LLM", "Qwen 4B Q4_K_M · llama.cpp", "#f0ebdd"),
        (395, 405, 250, 76, "PRIVATE MCP · STDIO", "Read + propose tools only", "#e8eee0"),
        (65, 405, 250, 76, "CALENDAR SERVICE", "Validate · preview · version", "#e8eee0"),
        (725, 405, 250, 76, "APPROVED EXECUTOR", "Exact accepted operations", "#e8eee0"),
        (
            65,
            575,
            580,
            85,
            "SQLITE · PRIVATE STORAGE",
            "Events · conversations · jobs · proposals · audit",
            "#dce7d7",
        ),
        (725, 575, 250, 85, "CALENDAR ADAPTERS", "Local SQLite / optional Google", "#e8eee0"),
        (725, 770, 250, 76, "GOOGLE CALENDAR API", "Minimal fields · OAuth · etags", "#f3e7db"),
        (395, 770, 250, 76, "APPLE CALENDAR", "Displays the Google account", "#f3e7db"),
    ]
    lines = [
        (315, 143, 395, 143),
        (645, 143, 725, 143),
        (850, 181, 850, 255),
        (725, 293, 645, 293),
        (395, 293, 315, 293),
        (520, 331, 520, 405),
        (395, 443, 315, 443),
        (190, 481, 190, 575),
        (850, 181, 1010, 181),
        (1010, 181, 1010, 443),
        (1010, 443, 975, 443),
        (850, 481, 850, 575),
        (725, 615, 645, 615),
        (850, 660, 850, 770),
        (725, 808, 645, 808),
    ]
    svg = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="920" viewBox="0 0 1080 920" role="img" aria-labelledby="title desc">',
        '<title id="title">Jarvis V1 runtime architecture</title>',
        '<desc id="desc">A browser sends requests to FastAPI and a durable worker. Local speech and Qwen interpret requests through private MCP tools. CalendarService stages changes in SQLite. Only accepted operations reach local or Google calendar adapters.</desc>',
        '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8Z" fill="#7d9278"/></marker></defs>',
        '<rect width="1080" height="920" fill="#f7f7f0"/>',
        '<text x="65" y="49" font-family="Georgia,serif" font-size="30" fill="#294632">Jarvis · voice to calendar</text>',
        '<text x="65" y="75" font-family="Arial,sans-serif" font-size="12" fill="#78846d">V1 IMPLEMENTED RUNTIME · LOCAL DEVELOPMENT / PORTABLE CPU HOST</text>',
        '<rect x="40" y="90" width="1000" height="620" rx="18" fill="none" stroke="#cbd7bf" stroke-dasharray="6 5"/>',
        '<text x="65" y="696" font-family="Arial,sans-serif" font-size="11" fill="#7d896f">OWNED HARDWARE IN DEVELOPMENT · INFERENCE AND PERSONAL CONTEXT STAY HERE</text>',
    ]
    for x1, y1, x2, y2 in lines:
        svg.append(
            f'<path d="M{x1} {y1} L{x2} {y2}" stroke="#7d9278" stroke-width="2" marker-end="url(#arrow)" fill="none"/>'
        )
    svg.append(
        '<path d="M520 181 L355 181 L355 575" stroke="#7d9278" stroke-width="2" marker-end="url(#arrow)" fill="none"/>'
    )
    svg.append(
        '<path d="M645 635 L690 635 L690 143 L725 143" stroke="#7d9278" stroke-width="2" marker-end="url(#arrow)" fill="none"/>'
    )
    for x, y, w, h, title, subtitle, fill in boxes:
        svg.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" fill="{fill}" stroke="#c7d4be"/>'
        )
        svg.append(
            f'<text x="{x + 18}" y="{y + 30}" font-family="Arial,sans-serif" font-size="12" font-weight="bold" fill="#35523b">{escape(title)}</text>'
        )
        svg.append(
            f'<text x="{x + 18}" y="{y + 53}" font-family="Arial,sans-serif" font-size="12" fill="#66785d">{escape(subtitle)}</text>'
        )
    svg.append(
        '<text x="65" y="880" font-family="Arial,sans-serif" font-size="12" fill="#78846d">Model calls can only read or propose. Approval is an authenticated UI action. Optimization is deferred.</text></svg>'
    )
    output = ROOT / "docs" / "architecture" / "runtime.svg"
    output.write_text("\n".join(svg) + "\n")
    print(output.relative_to(ROOT))


if __name__ == "__main__":
    main()
