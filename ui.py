# ──────────────────────────────────────────────
# ELLA-WCD v2.0 — Terminal UI & Aesthetics Engine
# Rich Markdown, Adaptive Color Grading, and ChatGPT-style Typography
# ──────────────────────────────────────────────

import re
from typing import Optional, Iterable, Tuple, Any
from rich.console import Console, ConsoleOptions, RenderResult
from rich.segment import Segment
from rich.text import Text
from rich.markdown import (
    Markdown, Paragraph, Heading, TableElement, BlockQuote,
    ListItem, ListElement
)
from rich.table import Table
from rich.panel import Panel
from rich.theme import Theme
from rich import box

# ── Vibrant Point Palette ──────────────────────
# Alternating, high-contrast colors so list items never visually blend together:
# 1. Vibrant Orange / Amber (Point 1)
# 2. Neon / Nylon Cyan-Blue (Point 2)
# 3. Vivid Red / Coral (Point 3)
# 4. Bright Neon Green (Point 4)
# 5. Vivid Magenta / Violet (Point 5)
# 6. Bright Electric Gold / Yellow (Point 6)

POINT_PALETTE = [
    {"style": "bold dark_orange", "badge_style": "bold black on dark_orange", "bullet": "✦", "name": "Orange"},
    {"style": "bold bright_cyan", "badge_style": "bold black on bright_cyan", "bullet": "✦", "name": "Nylon Cyan"},
    {"style": "bold bright_red", "badge_style": "bold black on bright_red", "bullet": "✦", "name": "Vivid Red"},
    {"style": "bold bright_green", "badge_style": "bold black on bright_green", "bullet": "✦", "name": "Neon Green"},
    {"style": "bold bright_magenta", "badge_style": "bold black on bright_magenta", "bullet": "✦", "name": "Magenta"},
    {"style": "bold bright_yellow", "badge_style": "bold black on bright_yellow", "bullet": "✦", "name": "Gold Yellow"},
]


def loop_first(values: Iterable[Any]) -> Iterable[Tuple[bool, Any]]:
    """Iterate and yield (is_first, value)."""
    iter_values = iter(values)
    try:
        first = next(iter_values)
    except StopIteration:
        return
    yield True, first
    for value in iter_values:
        yield False, value


# ── Dynamic Word Highlighting ──────────────────

def highlight_keywords(text_obj: Text) -> None:
    """
    Highlights critical, dangerous, and operational keywords in Rich Text objects:
    - Errors / Fatal / Bugs / Crashes: Bold Bright Red
    - Danger / Critical / Alerts: Bold Bright Red
    - Warnings / Caution / Risks: Bold Bright Yellow
    - Success / Verified / Optimal: Bold Bright Green
    - Important / Notes / Tips: Bold Bright Cyan
    """
    if not hasattr(text_obj, "highlight_regex"):
        return

    # 1. Dangerous & Error Keywords (RED)
    text_obj.highlight_regex(
        r"(?i)\b(error|errors|failed|failure|failing|exception|crash|crashed|fatal|broken|bug|bugs)\b",
        "bold bright_red"
    )
    # 2. Danger & Critical Keywords (RED)
    text_obj.highlight_regex(
        r"(?i)\b(danger|dangerous|critical|fatal|alert)\b",
        "bold bright_red"
    )
    # 3. Warnings & Risks (YELLOW)
    text_obj.highlight_regex(
        r"(?i)\b(warning|warnings|caution|caveat|risk|risks|unverified)\b",
        "bold bright_yellow"
    )
    # 4. Success & Positive Outcomes (GREEN)
    text_obj.highlight_regex(
        r"(?i)\b(success|succeeded|successful|passed|verified|healthy|completed|optimal|resolved|ready)\b",
        "bold bright_green"
    )
    # 5. Important & Guidance (CYAN)
    text_obj.highlight_regex(
        r"(?i)\b(important|note|tip|recommended|recommendation|advice|best pick|verdict)\b",
        "bold bright_cyan"
    )


def style_item_text(text_obj: Text, color_style: str) -> None:
    """
    Colorize the title or label of a list item (e.g. 'GPT-3 -' or 'Qwen:' or '**Claude**')
    with that item's distinct color from POINT_PALETTE.
    """
    raw = text_obj.plain
    # Match pattern before separator like 'GPT-3 -' or '**Qwen**:' or 'Point 1:'
    match = re.match(r"^(\s*\*?\*?[^:\-–—\n]+?\*?\*?)([:\-–—]\s*)", raw)
    if match:
        label_len = len(match.group(1)) + len(match.group(2))
        text_obj.stylize(color_style, 0, label_len)
    else:
        words = raw.split()
        if words:
            lead_len = min(len(raw), len(" ".join(words[:4])))
            text_obj.stylize(color_style, 0, lead_len)
    highlight_keywords(text_obj)


# ── Custom Markdown Elements ───────────────────

class StyledParagraph(Paragraph):
    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        highlight_keywords(self.text)
        yield self.text


class StyledHeading(Heading):
    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        highlight_keywords(self.text)
        for item in super().__rich_console__(console, options):
            yield item


class StyledTableElement(TableElement):
    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        table = Table(
            box=box.ROUNDED,
            pad_edge=False,
            style="markdown.table.border",
            show_edge=True,
            collapse_padding=False,
            header_style="bold bright_cyan",
        )

        if self.header is not None and self.header.row is not None:
            for column in self.header.row.cells:
                heading = column.content.copy()
                heading.stylize("markdown.table.header")
                highlight_keywords(heading)
                table.add_column(heading)

        if self.body is not None:
            for row in self.body.rows:
                row_content = []
                for element in row.cells:
                    cell_text = element.content.copy()
                    highlight_keywords(cell_text)
                    row_content.append(cell_text)
                table.add_row(*row_content)

        yield table


class StyledListItem(ListItem):
    """
    Renders list items with individual color identity, high-contrast badges,
    and a clean 2-line vertical gap between points.
    """
    color_index: int = 0

    def render_bullet(self, console: Console, options: ConsoleOptions) -> RenderResult:
        c_entry = POINT_PALETTE[self.color_index % len(POINT_PALETTE)]
        c_style = c_entry["style"]
        bullet_icon = c_entry["bullet"]
        bullet_style = console.get_style(c_style, default="bold cyan")

        for el in self.elements:
            if hasattr(el, "text"):
                style_item_text(el.text, c_style)

        render_options = options.update(width=options.max_width - 4)
        lines = console.render_lines(self.elements, render_options, style=self.style)

        bullet = Segment(f" {bullet_icon} ", bullet_style)
        padding = Segment("   ", bullet_style)
        new_line = Segment("\n")
        for first, line in loop_first(lines):
            yield bullet if first else padding
            yield from line
            yield new_line

    def render_number(
        self, console: Console, options: ConsoleOptions, number: int, last_number: int
    ) -> RenderResult:
        c_entry = POINT_PALETTE[(number - 1) % len(POINT_PALETTE)]
        c_style = c_entry["style"]
        badge_style = console.get_style(c_entry.get("badge_style", "bold black on dark_orange"))

        for el in self.elements:
            if hasattr(el, "text"):
                style_item_text(el.text, c_style)

        # Render high-contrast badge e.g. " 1. " with colored background
        badge_str = f" {number}. "
        badge_len = len(badge_str) + 1
        render_options = options.update(width=options.max_width - badge_len)
        lines = console.render_lines(self.elements, render_options, style=self.style)

        new_line = Segment("\n")
        badge_segment = Segment(badge_str, badge_style)
        space_segment = Segment(" ")
        padding = Segment(" " * badge_len)

        for first, line in loop_first(lines):
            if first:
                yield badge_segment
                yield space_segment
            else:
                yield padding
            yield from line
            yield new_line

        # Exactly 1 clean blank line between numbered points for compact readability
        yield Segment("\n")


class StyledListElement(ListElement):
    """
    Distributes color indexes across ordered and unordered list items.
    """
    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        if self.list_type == "bullet_list_open":
            for idx, item in enumerate(self.items):
                if isinstance(item, StyledListItem):
                    item.color_index = idx
                yield from item.render_bullet(console, options)
        else:
            number = 1 if self.list_start is None else self.list_start
            last_number = number + len(self.items)
            for index, item in enumerate(self.items):
                if isinstance(item, StyledListItem):
                    item.color_index = index
                yield from item.render_number(
                    console, options, number + index, last_number
                )


class EllaMarkdown(Markdown):
    """
    Enhanced Markdown renderer with:
    - Auto-sanitizer for repetitive degeneration loops from LLMs
    - Auto-normalization of numbered items without dots (e.g. '1 GPT-3' -> '1. GPT-3')
    - Auto-normalization of 'Point 1:' or 'Step 1:' to markdown numbered lists
    - Point-by-point high-contrast color badges (Orange -> Nylon Cyan -> Red -> Green -> Magenta)
    - 2-line vertical breathing room between points
    - Keyword auto-colorization (Errors in red, warnings in yellow, success in green)
    - Modern rounded tables
    """
    elements = Markdown.elements.copy()
    elements["paragraph_open"] = StyledParagraph
    elements["heading_open"] = StyledHeading
    elements["table_open"] = StyledTableElement
    elements["bullet_list_open"] = StyledListElement
    elements["ordered_list_open"] = StyledListElement
    elements["list_item_open"] = StyledListItem

    def __init__(self, markup: str, **kwargs):
        # 1. Clean repetitive degeneration loops while preserving document structure
        paragraphs = markup.split("\n\n")
        cleaned_paras = []
        for para in paragraphs:
            # Skip code blocks or tables to preserve syntax
            if "|" in para or "```" in para:
                cleaned_paras.append(para)
                continue

            # Remove consecutive repeating phrases (e.g. 'phrase, phrase, phrase')
            cleaned = re.sub(r"(\b[a-zA-Z0-9\s]{12,60}?[\.,;]?\s*)(?:\1){2,}", r"\1", para, flags=re.IGNORECASE)
            
            # Word-level degenerate loop detection
            words = cleaned.split()
            if len(words) > 15:
                truncated = False
                for w_size in range(5, min(20, len(words) // 2)):
                    i = 0
                    while i + w_size * 2 <= len(words):
                        w1 = " ".join(words[i:i+w_size]).lower().strip(" ,.-;:")
                        w2 = " ".join(words[i+w_size:i+w_size*2]).lower().strip(" ,.-;:")
                        if len(w1) > 15 and w1 == w2:
                            count = 2
                            pos = i + w_size * 2
                            while pos + w_size <= len(words):
                                w_next = " ".join(words[pos:pos+w_size]).lower().strip(" ,.-;:")
                                if w_next == w1:
                                    count += 1
                                    pos += w_size
                                else:
                                    break
                            if count >= 3:
                                words = words[:i + w_size]
                                cleaned = " ".join(words) + "."
                                truncated = True
                                break
                        i += 1
                    if truncated:
                        break
            cleaned_paras.append(cleaned)

        text = "\n\n".join(cleaned_paras)

        # 2. Normalize numbered lines that lack a dot (e.g. ' 1 GPT-3' -> ' 1. GPT-3')
        text = re.sub(r"(?m)^(\s*)(\d+)(?![\.\)])\s+", r"\1\2. ", text)

        # 3. Normalize 'Point 1:' or 'Step 1:' to numbered list item
        text = re.sub(r"(?mi)^(\s*)(?:point|step)\s*(\d+)[:\-\s]+", r"\1\2. ", text)

        super().__init__(text, **kwargs)


# ── Curated Color Theme ────────────────────────

ELLA_THEME = Theme({
    "markdown.h1": "bold bright_cyan underline",
    "markdown.h2": "bold bright_magenta",
    "markdown.h3": "bold bright_yellow",
    "markdown.h4": "bold bright_green",
    "markdown.item.bullet": "bold bright_cyan",
    "markdown.item.number": "bold bright_cyan",
    "markdown.strong": "bold bright_white",
    "markdown.emphasis": "italic bright_cyan",
    "markdown.code": "bold bright_yellow on grey15",
    "markdown.code_block": "bright_white on grey11",
    "markdown.block_quote": "italic bright_white",
    "markdown.table.border": "bright_blue",
    "markdown.table.header": "bold bright_cyan",
    "markdown.link": "bright_cyan underline",
})

console = Console(theme=ELLA_THEME)


# ── Public UI Helpers ──────────────────────────

def print_ai_response(
    content: str,
    model_name: str = "Qwen2.5-VL",
    title: Optional[str] = None,
    subtitle: Optional[str] = "Local AI Engine • Privacy First",
    border_style: str = "bright_blue"
) -> None:
    """
    Render a response from ELLA with ChatGPT-style spacing, vibrant typography,
    and automatic keyword colorization.
    """
    md = EllaMarkdown(content)
    header_title = title or f"[bold bright_magenta]✦[/bold bright_magenta] [bold bright_cyan]ELLA AI[/bold bright_cyan] [dim]• {model_name}[/dim]"
    
    panel = Panel(
        md,
        title=header_title,
        subtitle=f"[dim]{subtitle}[/dim]" if subtitle else None,
        subtitle_align="right",
        border_style=border_style,
        box=box.ROUNDED,
        padding=(1, 3)
    )

    console.print()
    console.print(panel)
    console.print()


def print_task_result(
    content: str,
    title: str = "Autonomous Task Result",
    model_name: str = "Qwen2.5-VL",
    border_style: str = "bright_green"
) -> None:
    """
    Render an autonomous browser task synthesis with rich tables, verdicts,
    and clear structured formatting.
    """
    md = EllaMarkdown(content)
    header_title = f"[bold bright_green]✦[/bold bright_green] [bold bright_white]{title}[/bold bright_white] [dim]• {model_name}[/dim]"
    
    panel = Panel(
        md,
        title=header_title,
        subtitle="[dim]Verified Autonomous Browser Execution[/dim]",
        subtitle_align="right",
        border_style=border_style,
        box=box.ROUNDED,
        padding=(1, 3)
    )

    console.print()
    console.print(panel)
    console.print()
