"""
main.py
───────
Command-line interface entry point.

Commands:
  python main.py list-sections          — show all PDF sections
  python main.py scenario-a             — run cold-start demo
  python main.py scenario-b             — run full 3-iteration evaluation
  python main.py interactive -s 1 -s 2  — answer questions yourself
  python main.py api                    — start REST API server

All evaluation outputs written to outputs/
"""

from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

import config
from config import validate_config
from kb.database import init_db
from utils.logger import get_logger

logger  = get_logger(__name__)
console = Console()


def _startup(load_pdf: bool = True) -> None:
    """Common startup: validate config, init DB, load PDF."""
    # Check config and warn about issues
    warnings = validate_config()
    for w in warnings:
        console.print(f"[bold yellow]⚠  {w}[/bold yellow]")
    if warnings:
        raise SystemExit(1)

    init_db()

    if load_pdf:
        from core.pdf_parser import pdf_parser
        pdf_parser.load()


@click.group()
@click.version_option("1.0.0")
def cli():
    """Adaptive Document Preparation System — SLATEFALL Assessment"""
    pass


# ─── list-sections ────────────────────────────────────────────────

@cli.command("list-sections")
def cmd_list_sections():
    """
    Show all sections detected in the SLATEFALL PDF.

    Run this first to verify PDF parsing worked correctly.
    If sections look wrong, check APPROACH.md for how to adjust regex.
    """
    _startup(load_pdf=True)
    from core.pdf_parser import pdf_parser

    sections = pdf_parser.get_all_sections()

    console.print(f"\n[bold cyan]SLATEFALL PDF — Detected Sections[/bold cyan]\n")

    table = Table(show_header=True, header_style="bold magenta", box=None)
    table.add_column("ID",    justify="right",  style="cyan",   width=4)
    table.add_column("Title", style="white",    width=50)
    table.add_column("Pages", justify="center", style="green",  width=10)
    table.add_column("Words", justify="right",  style="yellow", width=7)

    for s in sections:
        table.add_row(
            str(s.section_id),
            s.title[:50],
            f"p{s.start_page}–{s.end_page}",
            str(s.word_count),
        )

    console.print(table)
    console.print(
        f"\n[dim]Total: {len(sections)} sections detected. "
        f"Use these IDs with other commands.[/dim]\n"
    )


# ─── scenario-a ───────────────────────────────────────────────────

@cli.command("scenario-a")
@click.option(
    "--sections", "-s",
    multiple=True,
    type=int,
    default=[1, 2],
    show_default=True,
    help="Section IDs to study",
)
@click.option(
    "--n-questions", "-n",
    default=config.QUESTIONS_PER_SECTION,
    show_default=True,
    help="Questions per section",
)
@click.option(
    "--simulate/--interactive",
    default=True,
    help="Simulate answers or answer yourself",
)
def cmd_scenario_a(sections, n_questions, simulate):
    """
    Scenario A: Cold-start session (first time studying these sections).

    \b
    Examples:
      python main.py scenario-a
      python main.py scenario-a -s 3 -s 7
      python main.py scenario-a -s 1 -s 2 --interactive
    """
    _startup()
    from core.session_manager import session_manager
    from utils.exporter import export_iteration_outputs

    section_ids = list(sections)

    console.print(Panel(
        f"[bold]Scenario A — Cold Start[/bold]\n"
        f"Sections : {section_ids}\n"
        f"Questions: {n_questions} per section\n"
        f"Mode     : {'Simulated' if simulate else 'Interactive'}",
        style="cyan",
        title="SLATEFALL Prep",
    ))

    result = session_manager.run_session(
        section_ids         = section_ids,
        n_per_section       = n_questions,
        simulate_answers    = simulate,
        simulation_accuracy = 0.6,
        interactive         = not simulate,
    )

    # Display summary
    score_color = "green" if result.score >= 0.7 else "yellow" if result.score >= 0.5 else "red"
    console.print(Panel(
        f"[bold]Session Complete[/bold]\n"
        f"Session ID : {result.session_id}\n"
        f"Score      : [{score_color}]{result.correct_count}/{result.total_count} "
        f"({result.score:.1%})[/{score_color}]\n"
        f"Adaptive   : {result.is_adaptive}",
        style="green",
    ))

    # Export output files
    paths = export_iteration_outputs(
        iteration      = 1,
        scenario       = "scenario_a",
        session_result = result,
    )
    console.print(f"\n[dim]✓ Outputs written to {paths['questions'].parent}[/dim]\n")


# ─── scenario-b ───────────────────────────────────────────────────

@cli.command("scenario-b")
@click.option(
    "--n-questions", "-n",
    default=config.QUESTIONS_PER_SECTION,
    show_default=True,
    help="Questions per section per iteration",
)
@click.option(
    "--accuracy",
    default=0.6,
    type=float,
    show_default=True,
    help="Simulated answer accuracy 0.0-1.0",
)
def cmd_scenario_b(n_questions, accuracy):
    """
    Scenario B: Three consecutive adaptive iterations.

    \b
    Iter 1: Sections 5, 8       (cold start)
    Iter 2: Sections 6, 8, 9   (adaptive — uses iter 1 history)
    Iter 3: Section 8           (adaptive — uses iter 1+2 history)

    \b
    Outputs written to:
      outputs/scenario_b_iter1/
      outputs/scenario_b_iter2/
      outputs/scenario_b_iter3/

    \b
    Example:
      python main.py scenario-b
      python main.py scenario-b --n-questions 3 --accuracy 0.5
    """
    _startup()
    from core.session_manager import session_manager
    from utils.exporter import export_iteration_outputs

    iterations = [
        (1, [5, 8]),
        (2, [6, 8, 9]),
        (3, [8]),
    ]

    console.print(Panel(
        "[bold]Scenario B — Three Adaptive Iterations[/bold]\n"
        "Iter 1: Sections 5, 8      → cold start\n"
        "Iter 2: Sections 6, 8, 9  → adaptive (uses iter 1 history)\n"
        "Iter 3: Section 8          → adaptive (uses iter 1+2 history)",
        style="cyan",
        title="SLATEFALL Prep",
    ))

    for iteration, section_ids in iterations:
        console.print(
            f"\n[bold yellow]{'═'*55}[/bold yellow]\n"
            f"[bold yellow]  Iteration {iteration} | Sections: {section_ids}[/bold yellow]\n"
            f"[bold yellow]{'═'*55}[/bold yellow]"
        )

        result = session_manager.run_session(
            section_ids         = section_ids,
            n_per_section       = n_questions,
            simulate_answers    = True,
            simulation_accuracy = accuracy,
            interactive         = False,
        )

        # Show iteration summary
        tag = "[bold green]ADAPTIVE[/bold green]" if result.is_adaptive else "[dim]COLD START[/dim]"
        score_color = "green" if result.score >= 0.7 else "yellow" if result.score >= 0.5 else "red"

        console.print(
            f"\n  {tag}  |  "
            f"Score: [{score_color}]{result.correct_count}/{result.total_count} "
            f"({result.score:.1%})[/{score_color}]"
        )

        if result.is_adaptive and result.weak_topics_used:
            console.print("  [dim]Weak topics targeted:[/dim]")
            for wt in result.weak_topics_used[:3]:
                if isinstance(wt, dict):
                    console.print(
                        f"  [dim]  → '{wt.get('topic', wt)}' "
                        f"(wrong {wt.get('wrong_count', '?')}×)[/dim]"
                    )
                else:
                    console.print(f"  [dim]  → {wt}[/dim]")

        # Export files
        paths = export_iteration_outputs(
            iteration      = iteration,
            scenario       = "scenario_b",
            session_result = result,
        )
        console.print(
            f"  [dim]✓ Saved: "
            f"{paths['questions'].name} + "
            f"{paths['kb_snapshot'].name}[/dim]"
        )

    console.print(
        "\n[bold green]✓ Scenario B complete![/bold green]\n"
        "[dim]Check outputs/scenario_b_iter*/ for all output files.[/dim]\n"
    )


# ─── interactive ──────────────────────────────────────────────────

@cli.command("interactive")
@click.option(
    "--sections", "-s",
    multiple=True,
    type=int,
    required=True,
    help="Section IDs to study (required)",
)
@click.option(
    "--n-questions", "-n",
    default=config.QUESTIONS_PER_SECTION,
    show_default=True,
)
def cmd_interactive(sections, n_questions):
    """
    Interactive mode: answer questions yourself.

    \b
    Example:
      python main.py interactive -s 1 -s 2
      python main.py interactive -s 5
    """
    _startup()
    from core.session_manager import session_manager

    section_ids = list(sections)

    console.print(Panel(
        f"[bold]Interactive Prep Session[/bold]\n"
        f"Sections : {section_ids}\n"
        f"Questions: {n_questions} per section\n\n"
        f"Answer each question with A, B, C, or D.",
        style="cyan",
    ))

    result = session_manager.run_session(
        section_ids      = section_ids,
        n_per_section    = n_questions,
        simulate_answers = False,
        interactive      = True,
    )

    score_color = "green" if result.score >= 0.7 else "yellow" if result.score >= 0.5 else "red"
    console.print(Panel(
        f"[bold]Session Complete![/bold]\n"
        f"Score: [{score_color}]{result.correct_count}/{result.total_count} "
        f"({result.score:.1%})[/{score_color}]\n\n"
        f"Your results have been saved.\n"
        f"Next session on these sections will be [bold]adaptive[/bold]!",
        style=score_color,
    ))


# ─── api ──────────────────────────────────────────────────────────

@cli.command("api")
@click.option("--host", default=config.API_HOST, show_default=True)
@click.option("--port", default=config.API_PORT, show_default=True)
def cmd_api(host, port):
    """
    Start the REST API server.

    \b
    Then visit: http://localhost:8000/docs
    """
    import uvicorn

    # Validate config before starting server
    warnings = validate_config()
    for w in warnings:
        console.print(f"[yellow]⚠  {w}[/yellow]")

    init_db()

    console.print(Panel(
        f"[bold]REST API Starting[/bold]\n"
        f"URL  : http://{host}:{port}\n"
        f"Docs : http://localhost:{port}/docs\n"
        f"Press Ctrl+C to stop.",
        style="cyan",
    ))

    uvicorn.run("api.app:app", host=host, port=port, reload=True)


# ─── ui ───────────────────────────────────────────────────────────

@cli.command("ui")
@click.option("--port", default=8501, help="Streamlit port")
def cmd_ui(port):
    """
    Launch the Streamlit web UI.

    \b
    Example:
      python main.py ui
      python main.py ui --port 8502
    """
    import subprocess
    import sys

    console.print(Panel(
        f"[bold]Starting Streamlit UI[/bold]\n"
        f"URL  : http://localhost:{port}\n"
        f"Press Ctrl+C to stop.",
        style="cyan",
    ))

    subprocess.run([
        sys.executable, "-m", "streamlit", "run",
        "streamlit_app.py",
        f"--server.port={port}",
        "--server.headless=false",
        "--theme.base=dark",
        "--theme.primaryColor=#4f8ef7",
        "--theme.backgroundColor=#0e1117",
        "--theme.secondaryBackgroundColor=#1e2130",
    ])


# ─── Entry point ──────────────────────────────────────────────────

if __name__ == "__main__":
    cli()