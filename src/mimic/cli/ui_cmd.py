"""CLI command to start the Mimic web UI server."""

import socket
import webbrowser

import typer
import uvicorn

ui_app = typer.Typer(help="Web UI server commands")


def find_available_port(start_port: int = 8080) -> int:
    """Find an available port starting from start_port.

    Args:
        start_port: Port to start searching from

    Returns:
        First available port number
    """
    port = start_port
    while port < start_port + 100:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
            port += 1
    raise RuntimeError("No available ports found in range")


@ui_app.callback(invoke_without_command=True)
def start_ui(
    ctx: typer.Context,
    port: int = typer.Option(
        None, help="Port to run on (auto-detect if not specified)"
    ),
    no_browser: bool = typer.Option(False, help="Don't open browser automatically"),
    host: str = typer.Option("127.0.0.1", help="Host to bind to (default: 127.0.0.1)"),
):
    """Start the Mimic web UI server.

    The web UI provides a user-friendly interface for managing scenarios,
    environments, and configurations. It runs locally on your machine with
    the same security model as the CLI.

    Examples:
        mimic ui                    # Start on auto-detected port
        mimic ui --port 8000        # Start on specific port
        mimic ui --no-browser       # Start without opening browser
    """
    # Don't execute if a subcommand was invoked
    if ctx.invoked_subcommand is not None:
        return

    # Find available port if not specified
    if port is None:
        try:
            port = find_available_port()
        except RuntimeError as e:
            typer.echo(f"Error: {e}", err=True)
            raise typer.Exit(1) from e

    url = f"http://{host}:{port}"

    typer.echo(
        f"Starting Mimic Web UI at {typer.style(url, fg=typer.colors.CYAN, bold=True)}"
    )
    typer.echo("Press Ctrl+C to stop the server")
    typer.echo()

    # Open browser if requested
    if not no_browser:
        typer.echo(f"Opening browser to {url}...")
        try:
            webbrowser.open(url)
        except Exception as e:
            typer.echo(f"Could not open browser: {e}", err=True)

    # Import here to avoid slow imports
    from mimic.web.server import app

    # Run uvicorn server
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=True,
    )
