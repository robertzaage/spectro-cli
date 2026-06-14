"""Spectro CLI — control Variable colour measurement devices."""

from __future__ import annotations

import asyncio
import logging

import typer
from bleak.backends.device import BLEDevice
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from . import __version__
from .ble.device import ScanResult, SpectroDevice
from .ble.scanner import Scanner
from .color import (
    Illuminant,
    Observer,
    SpectralCurve,
    srgb_to_cmyk,
    srgb_to_hex,
    srgb_to_hsv,
    xyz_to_adobergb,
    xyz_to_srgb,
)
from .config import CONFIG
from .products import ProductIndex

logger = logging.getLogger(__name__)

app = typer.Typer(
    name="spectro",
    help="CLI for Variable Spectro colour measurement devices",
    no_args_is_help=True,
)
console = Console(emoji=False)
err = Console(stderr=True, emoji=False)

_devices: dict[str, SpectroDevice] = {}


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(rich_tracebacks=True)],
    )


@app.callback()
def main(verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output")) -> None:
    _setup_logging(verbose)


# ---------------------------------------------------------------------------
# shared helpers
# ---------------------------------------------------------------------------


async def _pick_device(address: str | None = None, timeout: float = 5.0) -> tuple[SpectroDevice, str]:
    """Find and connect to a device. Returns (device, address)."""
    scanner = Scanner()

    if address:
        console.print(f"[yellow]Looking for {address}...[/]")
        target = await scanner.find_device(address, timeout=timeout)
        if not target:
            console.print("[yellow]Trying direct connection...[/]")
            dev_path = f"/org/bluez/hci0/dev_{address.replace(':', '_')}"
            ble_dev = BLEDevice(address, "Spectro", {"path": dev_path, "props": {}}, -100)
            dev = SpectroDevice(ble_dev, device_type="spectro")
            try:
                await dev.connect()
            except Exception as e:
                err.print(f"[red]Cannot reach {address}. Is it awake and paired?[/]")
                raise typer.Exit(1) from e
            _devices[address] = dev
            console.print(f"[green]Connected to {dev.serial}[/]")
            return dev, address
        addr = target.address
    else:
        console.print("[yellow]Scanning for devices...[/]")
        devices = await scanner.scan(timeout=timeout)
        if not devices:
            err.print("[red]No Variable devices found.[/]")
            raise typer.Exit(1)
        if len(devices) == 1:
            target = devices[0]
            addr = target.address
        else:
            table = Table(title="Select a device")
            table.add_column("#", style="cyan")
            table.add_column("Name", style="green")
            table.add_column("Address", style="white")
            table.add_column("RSSI", style="magenta")
            for i, d in enumerate(devices, 1):
                table.add_row(str(i), d.name, d.address, str(d.rssi))
            console.print(table)
            choice = typer.prompt("Device number", type=int, default=1)
            if choice < 1 or choice > len(devices):
                err.print("[red]Invalid choice.[/]")
                raise typer.Exit(1)
            target = devices[choice - 1]
            addr = target.address

    if addr in _devices and _devices[addr].is_connected:
        return _devices[addr], addr

    console.print(f"[yellow]Connecting to {target.name}...[/]")
    dev = SpectroDevice(target.ble_device, device_type=target.device_type or "spectro")
    await dev.connect()
    _devices[addr] = dev
    console.print(f"[green]Connected to {dev.serial}[/]")
    return dev, addr


def _display_scan(console: Console, result: ScanResult, dev: SpectroDevice) -> None:
    """Display scan results with all colour formats."""
    console.print(f"[green]Scan — {result.serial}[/]")
    console.print(f"  Model:      {result.model}")
    console.print(f"  Batch:      {result.batch}")
    console.print(f"  Scan #:     {result.scan_count}  (since cal: {result.cal_scan_count})")
    console.print(f"  Calibrated: {'Yes' if result.is_calibrated else 'No'}")

    data = result.corrected_values or result.sense_values
    if result.corrected_values:
        try:
            import json

            info_path = CONFIG.data_dir / "models" / result.serial / "info_v2.json"
            if info_path.exists():
                info = json.loads(info_path.read_text())
                model_name = info.get("model_name", result.serial)
                console.print(f"  ML model:   {model_name} (640K params, {result.ml_inference_ms:.1f}ms)")
            else:
                console.print(f"  Correction: ML pipeline ({result.ml_inference_ms:.1f}ms)")
        except Exception:
            console.print(f"  Correction: ML pipeline ({result.ml_inference_ms:.1f}ms)")
    else:
        n = len(result.correction_factors or [])
        console.print(f"  Correction: {n} device factors applied")

    if not data:
        console.print("[dim]No spectral data.[/]")
        return

    curve = SpectralCurve(data, illuminant=Illuminant.D65, observer=Observer.TEN_DEGREE)
    xyz_d65 = curve.to_xyz()
    lab_d65 = xyz_d65.to_lab(Illuminant.D65, Observer.TEN_DEGREE)
    lab_d50 = xyz_d65.to_lab(Illuminant.D50, Observer.TWO_DEGREE)

    r_srgb, g_srgb, b_srgb = xyz_to_srgb(xyz_d65.X, xyz_d65.Y, xyz_d65.Z)
    hex_colour = srgb_to_hex(r_srgb, g_srgb, b_srgb)
    r_adobe, g_adobe, b_adobe = xyz_to_adobergb(xyz_d65.X, xyz_d65.Y, xyz_d65.Z)
    h, s, v = srgb_to_hsv(r_srgb, g_srgb, b_srgb)
    c, m, y, k = srgb_to_cmyk(r_srgb, g_srgb, b_srgb)

    console.print()
    console.print("  [bold underline]Colour[/]")
    console.print(f"  CIE Lab (D65/10°)   {lab_d65.L:5.1f}  {lab_d65.a:+6.1f}  {lab_d65.b:+6.1f}")
    console.print(f"  CIE Lab (D50/2°)    {lab_d50.L:5.1f}  {lab_d50.a:+6.1f}  {lab_d50.b:+6.1f}")
    console.print(f"  CIE XYZ (D65)       {xyz_d65.X:6.2f}  {xyz_d65.Y:6.2f}  {xyz_d65.Z:6.2f}")
    console.print(
        f"  sRGB / Hex          {r_srgb:3d} {g_srgb:3d} {b_srgb:3d}  [on {hex_colour}]    [/] {hex_colour}"
    )
    console.print(f"  Adobe RGB           {r_adobe:3d} {g_adobe:3d} {b_adobe:3d}")
    console.print(f"  HSV                 {h:.0f}°  {s:.1f}%  {v:.1f}%")
    console.print(f"  CMYK                {c:.1f}%  {m:.1f}%  {y:.1f}%  {k:.1f}%")

    # Nearest product colours
    try:
        nearest = _find_nearest_colors(lab_d65.L, lab_d65.a, lab_d65.b)
        if nearest:
            console.print()
            console.print("  [bold underline]Nearest product colours[/]")
            for i, p in enumerate(nearest, 1):
                h = p.get("hex_color", "")
                if not h.startswith("#"):
                    h = f"#{h}"
                console.print(f"  {i}. [on {h}]    [/] {h}  {p['name']}")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# version
# ---------------------------------------------------------------------------
@app.command()
def version() -> None:
    """Print version."""
    console.print(f"Spectro [bold cyan]v{__version__}[/]")


# ---------------------------------------------------------------------------
# scan-devices
# ---------------------------------------------------------------------------
# scan-devices
# ---------------------------------------------------------------------------
@app.command()
def scan_devices(timeout: float = typer.Option(10.0, "--timeout", "-t", help="Scan duration (s)")) -> None:
    """Discover nearby Spectro BLE devices."""

    async def _run() -> None:
        scanner = Scanner()
        console.print(f"[yellow]Scanning ({timeout}s)...[/]")
        devices = await scanner.scan(timeout=timeout)
        if not devices:
            console.print("[red]No Variable devices found.[/]")
            return
        table = Table(title="Discovered Devices")
        table.add_column("Address", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Type", style="yellow")
        table.add_column("RSSI", style="magenta")
        for d in devices:
            table.add_row(d.address, d.name, d.device_type or "?", str(d.rssi))
        console.print(table)

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# connect
# ---------------------------------------------------------------------------
@app.command()
def connect(
    address: str | None = typer.Argument(None, help="BLE MAC address (optional — auto-detected if omitted)"),
    keep: bool = typer.Option(False, "--keep", "-k", help="Stay connected after showing info"),
    timeout: float = typer.Option(5.0, "--timeout", "-t", help="Scan timeout (s)"),
) -> None:
    """Connect to a device and show identity info."""

    async def _run() -> None:
        dev, addr = await _pick_device(address, timeout)
        info = await dev.get_device_info()

        table = Table(title=f"Device {info.serial}")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("Serial", info.serial)
        table.add_row("Firmware", info.firmware)
        table.add_row("Model", info.model)
        table.add_row("Batch", info.batch)
        if info.battery:
            table.add_row("Battery", f"{info.battery.level}% ({info.battery.voltage:.3f}V)")
            table.add_row("Charging", "Yes" if info.battery.is_charging else "No")
        table.add_row("Scan count", str(info.scan_count))
        table.add_row("Since cal", str(info.cal_scan_count))
        table.add_row("Calibrated", "Yes" if info.is_calibrated else "No")
        if info.temperature is not None:
            table.add_row("Temperature", f"{info.temperature:.1f}°C")
        console.print(table)

        if keep:
            input("Press Enter to disconnect...")
        await dev.disconnect()
        _devices.pop(addr, None)

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# scan
# ---------------------------------------------------------------------------
@app.command()
def scan(
    address: str | None = typer.Argument(None, help="BLE MAC address (optional)"),
    keep: bool = typer.Option(False, "--keep", "-k", help="Keep connection open after scan"),
    timeout: float = typer.Option(5.0, "--timeout", "-t", help="Scan timeout (s)"),
) -> None:
    """Perform a colour measurement and display results."""

    async def _run() -> None:
        dev, addr = await _pick_device(address, timeout)
        while True:
            console.print("[yellow]Measuring...[/]")
            try:
                result = await dev.scan()
            except Exception as e:
                err.print(f"[red]Scan failed: {e}[/]")
                break

            _display_scan(console, result, dev)

            if not keep:
                break
            if not typer.confirm("\nScan again?", default=True):
                break

        await dev.disconnect()
        _devices.pop(addr, None)

    asyncio.run(_run())


def _find_nearest_colors(lab_l: float, lab_a: float, lab_b: float, limit: int = 3) -> list[dict[str, str]]:
    """Find nearest product colours by Lab distance."""
    index = ProductIndex()
    try:
        if not index.is_built():
            return []
        # Get all products with Lab values from their hex colors
        all_products = index.search(limit=100000)
        if not all_products:
            return []

        # Compute delta-E for each product
        scored = []
        for p in all_products:
            h = p.get("hex_color", "").lstrip("#")
            if len(h) != 6:
                continue
            try:
                pr = int(h[0:2], 16) / 255.0
                pg = int(h[2:4], 16) / 255.0
                pb = int(h[4:6], 16) / 255.0
            except ValueError:
                continue

            # Simple sRGB → approximate Lab via linear sRGB → XYZ → Lab
            # (This is a coarse approximation for delta-E sorting)
            rl = _srgb_to_linear(pr)
            gl = _srgb_to_linear(pg)
            bl = _srgb_to_linear(pb)
            x = 0.4124 * rl + 0.3576 * gl + 0.1805 * bl
            y = 0.2126 * rl + 0.7152 * gl + 0.0722 * bl
            z = 0.0193 * rl + 0.1192 * gl + 0.9505 * bl
            xn, yn, zn = 0.95047, 1.0, 1.08883
            fx = _lab_f(x / xn)
            fy = _lab_f(y / yn)
            fz = _lab_f(z / zn)
            pl = 116.0 * fy - 16.0
            pa = 500.0 * (fx - fy)
            pb2 = 200.0 * (fy - fz)

            de = ((lab_l - pl) ** 2 + (lab_a - pa) ** 2 + (lab_b - pb2) ** 2) ** 0.5
            scored.append((de, p))

        scored.sort(key=lambda x: x[0])
        return [p for _, p in scored[:limit]]
    finally:
        index.close()


def _srgb_to_linear(c: float) -> float:
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def _lab_f(t: float) -> float:
    delta = 6.0 / 29.0
    if t > delta**3:
        return t ** (1.0 / 3.0)
    return t / (3.0 * delta**2) + 4.0 / 29.0


# ---------------------------------------------------------------------------
# battery
# ---------------------------------------------------------------------------
@app.command()
def battery(
    address: str | None = typer.Argument(None, help="BLE MAC address (optional)"),
    timeout: float = typer.Option(5.0, "--timeout", "-t", help="Scan timeout (s)"),
) -> None:
    """Read battery status from a device."""

    async def _run() -> None:
        dev, addr = await _pick_device(address, timeout)
        info = await dev.get_battery()
        console.print(f"[green]Battery:[/] {info.level}% ({info.voltage:.3f}V)")
        console.print(f"  Charging: {'Yes' if info.is_charging else 'No'}")
        await dev.disconnect()
        _devices.pop(addr, None)

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# disconnect
# ---------------------------------------------------------------------------
@app.command()
def disconnect(
    address: str | None = typer.Argument(None, help="BLE MAC address (disconnects all if omitted)"),
) -> None:
    """Disconnect from one or all devices."""

    async def _run() -> None:
        if address:
            dev = _devices.pop(address, None)
            if dev:
                await dev.disconnect()
                console.print(f"[green]Disconnected from {address}.[/]")
            else:
                err.print(f"[yellow]Device {address} not in session.[/]")
        else:
            count = 0
            for _addr, dev in list(_devices.items()):
                try:
                    await dev.disconnect()
                    count += 1
                except Exception:
                    pass
            _devices.clear()
            console.print(f"[green]Disconnected {count} device(s).[/]")

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# download
# ---------------------------------------------------------------------------
download_app = typer.Typer(help="Download models and product databases", no_args_is_help=True)
app.add_typer(download_app, name="download")


@download_app.command()
def models(
    serial: str = typer.Option("", "--serial", "-s", help="Device serial number"),
    scan: bool = typer.Option(False, "--scan", help="Scan for nearby devices and download all"),
    timeout: float = typer.Option(10.0, "--timeout", "-t", help="Scan timeout in seconds"),
) -> None:
    """Download ML colour-correction models for a device."""
    serials: list[str] = []

    if scan:

        async def _scan() -> list[str]:
            scanner = Scanner()
            console.print(f"[yellow]Scanning for devices ({timeout}s)...[/]")
            devices = await scanner.scan(timeout=timeout)
            return [d.address for d in devices]

        addresses = asyncio.run(_scan())
        if not addresses:
            err.print("[red]No devices found.[/]")
            raise typer.Exit(1)

        async def _read_serials() -> list[str]:
            result = []
            for addr in addresses:
                try:
                    scanner = Scanner()
                    devs = await scanner.scan(timeout=3.0)
                    tgt = next((d for d in devs if d.address.lower() == addr.lower()), None)
                    if not tgt:
                        continue
                    dev = SpectroDevice(tgt.ble_device, device_type=tgt.device_type or "spectro")
                    await dev.connect()
                    if dev.serial:
                        result.append(dev.serial)
                    await dev.disconnect()
                except Exception:
                    pass
            return result

        serials = asyncio.run(_read_serials())
        if not serials:
            err.print("[red]Could not read serials. Use --serial instead.[/]")
            raise typer.Exit(1)
    elif serial:
        serials = [serial.upper()]
    else:
        err.print("[red]Specify --serial or --scan.[/]")
        raise typer.Exit(1)

    total_size = 0
    for s in serials:
        console.print(f"[yellow]Downloading model for {s}...[/]")
        try:
            from .models import _download_model

            dest = CONFIG.data_dir / "models" / s
            size = _download_model(s, dest)
            console.print(f"  [green]{s}[/] → {dest} ({_fmt_size(size)})")
            total_size += size
        except Exception as e:
            console.print(f"  [red]{s} failed: {e}[/]")

    if total_size:
        console.print(f"\n[green]Downloaded {_fmt_size(total_size)} total to {CONFIG.data_dir / 'models'}[/]")


@download_app.command()
def products(
    package_id: int = typer.Option(0, "--package-id", "-p", help="Package ID (0 = Basic Access)"),
) -> None:
    """Download the Variable product colour database for offline search.

    The Basic Access package (ID 0) is publicly accessible — no account needed.
    """
    url = f"https://d2s9pnfn2sxp4v.cloudfront.net/variable-product-db-zips/v1/vp-dbs-{package_id}.zip"
    dest = CONFIG.data_dir / "products" / f"vp-dbs-{package_id}.zip"
    dest.parent.mkdir(parents=True, exist_ok=True)

    console.print(f"[yellow]Downloading product database (package {package_id})...[/]")
    try:
        import httpx

        with (
            httpx.Client(timeout=httpx.Timeout(300)) as client,
            client.stream("GET", url) as resp,
        ):
            resp.raise_for_status()
            downloaded = 0
            with open(dest, "wb") as f:
                for chunk in resp.iter_bytes(8192):
                    f.write(chunk)
                    downloaded += len(chunk)
            console.print(f"  [green]{_fmt_size(downloaded)}[/] → {dest}")
    except Exception as e:
        err.print(f"[red]Download failed: {e}[/]")
        raise typer.Exit(1) from e


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------
search_app = typer.Typer(help="Search the product colour database", no_args_is_help=True)
app.add_typer(search_app, name="search")


@search_app.command()
def offline(
    query: str = typer.Argument("", help="Search query (name or hex colour)"),
    limit: int = typer.Option(50, "--limit", "-l", help="Max results"),
    rebuild: bool = typer.Option(False, "--rebuild", help="Rebuild the search index"),
) -> None:
    """Search the downloaded product database (no internet required)."""
    index = ProductIndex()
    try:
        if rebuild or not index.is_built():
            console.print("[yellow]Building product index...[/]")
            count = index.build()
            console.print(f"  [green]Indexed {count} products[/]")

        results = index.search(query=query, limit=limit)
        if not results:
            console.print("[yellow]No results found.[/]")
            return

        table = Table(title=f"Found {len(results)} results (of {index.count()} indexed)")
        table.add_column("Name", style="green")
        table.add_column("Hex", style="cyan")
        has_vendor = any(r.get("vendor") for r in results)
        if has_vendor:
            table.add_column("Vendor", style="yellow")
        for r in results:
            h = r["hex_color"]
            if not h.startswith("#"):
                h = f"#{h}"
            row = [r["name"], f"[on {h}]    [/] {h}" if h else "-"]
            if has_vendor:
                row.append(r.get("vendor", ""))
            table.add_row(*row)
        console.print(table)
    finally:
        index.close()


def _fmt_size(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f} MB"
    if n >= 1_000:
        return f"{n / 1_000:.1f} KB"
    return f"{n} B"


# ---------------------------------------------------------------------------
# api — BridgeKit JSONL TCP server
# ---------------------------------------------------------------------------


@app.command()
def api(
    host: str = typer.Option("localhost", "--host", "-h", help="Listen address"),
    port: int = typer.Option(9100, "--port", "-p", help="Listen port"),
) -> None:
    """Start a BridgeKit-compatible JSONL API server.

    Implements the Bridge by Variable protocol over TCP (direct BLE, no dongle).

        curl -s localhost:9100 -d '{"command":"GetDongle"}' | jq .
        curl -s localhost:9100 -d '{"command":"Scan","parameters":{"serial":"DEVICE123"}}' | jq .
    """
    from .api_server import run_api_server

    console.print(f"[green]BridgeKit API server starting on {host}:{port}[/]")
    console.print("[dim]Press Ctrl+C to stop[/]")
    try:
        asyncio.run(run_api_server(host, port))
    except KeyboardInterrupt:
        console.print("\n[yellow]Server stopped.[/]")


# ---------------------------------------------------------------------------
# calibrate
# ---------------------------------------------------------------------------


@app.command()
def calibrate(
    address: str | None = typer.Argument(None, help="BLE MAC address (optional)"),
    timeout: float = typer.Option(5.0, "--timeout", "-t", help="Scan timeout (s)"),
) -> None:
    """Calibrate a Spectro device using the white/green/blue tile flow.

    Follow the on-screen prompts to scan each calibration tile.
    Results are verified against manufacturer reference data and
    written back to the device.
    """

    async def _run() -> None:
        from .calibrate import calibrate_spectro_1

        dev, addr = await _pick_device(address, timeout)

        if not dev.is_calibrated:
            console.print("[yellow]Device is not currently calibrated.[/]")
        else:
            console.print(
                f"[dim]Device is calibrated (scan #{dev.scan_count}, since cal: {dev.cal_scan_count})[/]"
            )

        if not typer.confirm("\nProceed with calibration? Requires white, green, and blue tiles."):
            console.print("[yellow]Cancelled.[/]")
            await dev.disconnect()
            _devices.pop(addr, None)
            return

        console.print("\n[bold]Calibration started[/]")
        result = await calibrate_spectro_1(dev, on_prompt=console.print)

        if result.get("success"):
            console.print("\n[green]Calibration successful![/]")
            if "verification" in result:
                v = result["verification"]
                console.print(f"  White ΔE: {v['white_de']}")
                console.print(f"  Green ΔE: {v['green_de']}")
                console.print(f"  Blue ΔE:  {v['blue_de']}")
        else:
            err.print(f"\n[red]Calibration failed: {result.get('error', 'unknown')}[/]")

        await dev.disconnect()
        _devices.pop(addr, None)

    asyncio.run(_run())
