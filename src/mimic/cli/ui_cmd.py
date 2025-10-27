"""CLI command to start the Mimic web UI server."""

import socket
import threading
import time
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


def wait_for_server(host: str, port: int, timeout: int = 10) -> bool:
    """Wait for server to start accepting connections.

    Args:
        host: Server host
        port: Server port
        timeout: Maximum seconds to wait

    Returns:
        True if server is ready, False if timeout
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex((host, port))
                if result == 0:
                    # Server is accepting connections
                    return True
        except OSError:
            pass
        time.sleep(0.1)  # Wait 100ms before next attempt
    return False


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

    # Check keyring availability before starting server
    from mimic.keyring_health import test_keyring_available

    typer.echo("Checking keyring availability...")
    success, error_msg = test_keyring_available(timeout=3)
    if not success:
        typer.echo()
        typer.echo(
            typer.style(
                "✗ Keyring backend is not available", fg=typer.colors.RED, bold=True
            ),
            err=True,
        )
        typer.echo()
        typer.echo(error_msg, err=True)
        typer.echo()
        typer.echo(
            "The web UI requires a functioning keyring to store credentials securely.",
            err=True,
        )
        typer.echo("Please fix the keyring setup before starting the web UI.", err=True)
        raise typer.Exit(1)

    typer.echo(typer.style("✓ Keyring backend is available", fg=typer.colors.GREEN))
    typer.echo()

    typer.echo(
        f"Starting Mimic Web UI at {typer.style(url, fg=typer.colors.CYAN, bold=True)}"
    )
    typer.echo("Press Ctrl+C to stop the server")
    typer.echo()

    # Import here to avoid slow imports
    from mimic.web.server import app

    # Start uvicorn server in a background thread
    # This allows us to wait for it to be ready before opening the browser
    def run_server():
        """Run uvicorn server in thread."""
        config = uvicorn.Config(
            app,
            host=host,
            port=port,
            log_level="info",
            access_log=True,
        )
        server = uvicorn.Server(config)
        server.run()

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Wait for server to be ready
    typer.echo("Waiting for server to start...")
    if wait_for_server(host, port, timeout=10):
        typer.echo(typer.style("✓ Server is ready", fg=typer.colors.GREEN))
        typer.echo()

        # Open browser after server is ready
        if not no_browser:
            typer.echo(f"Opening browser to {url}...")
            try:
                webbrowser.open(url)
            except Exception as e:
                typer.echo(f"Could not open browser: {e}", err=True)
    else:
        typer.echo(
            typer.style(
                "⚠ Server did not start within 10 seconds, but continuing...",
                fg=typer.colors.YELLOW,
            ),
            err=True,
        )

    # Wait for server thread (handles Ctrl+C properly)
    try:
        server_thread.join()
    except KeyboardInterrupt:
        typer.echo()
        typer.echo("Shutting down server...")
        # Server will handle shutdown via uvicorn's signal handlers
        raise typer.Exit(0) from None
