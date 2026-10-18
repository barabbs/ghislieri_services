"""Printing PDFs sent to the bot, through CUPS `lp`."""

import asyncio
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from .settings import Settings

log = logging.getLogger(__name__)

MAX_FILE_SIZE = 20 * 1024 * 1024  # also the Bot API download limit
MAX_COPIES = 20
SIDES = {
    "one-sided": "Solo fronte",
    "two-sided-long-edge": "Fronte retro (lato lungo)",
    "two-sided-short-edge": "Fronte retro (lato corto)",
}
NUMBER_UP = (1, 2, 4, 6, 9, 16)
TIMEOUT = 60  # seconds

# "1,3-5,16". ASCII digits only: \d would also accept other scripts' digits.
_PAGE_LIST = re.compile(r"[0-9]{1,5}(-[0-9]{1,5})?(,[0-9]{1,5}(-[0-9]{1,5})?)*")


class PrintError(Exception):
    pass


@dataclass(frozen=True)
class PrintOptions:
    copies: int = 1
    sides: str = "two-sided-long-edge"
    number_up: int = 1
    pages: str | None = None  # None: all pages


def parse_page_list(text: str) -> str:
    """Normalise and validate a page list typed by the user ("1, 3-5" -> "1,3-5"). Raises ValueError."""
    value = text.replace(" ", "")
    if len(value) > 100 or not _PAGE_LIST.fullmatch(value):
        raise ValueError(text)
    for part in value.split(","):
        first, _, last = part.partition("-")
        if int(first) < 1 or (last and int(last) < int(first)):
            raise ValueError(text)
    return value


def build_lp_args(path: Path | str, options: PrintOptions, printer: str | None = None) -> list[str]:
    """The `lp` command line for one job. Every option is validated again: this goes to a subprocess."""
    if not 1 <= options.copies <= MAX_COPIES:
        raise ValueError(f"copies out of range: {options.copies}")
    if options.sides not in SIDES or options.number_up not in NUMBER_UP:
        raise ValueError(f"bad options: {options}")
    args = ["lp"]
    if printer:
        args += ["-d", printer]
    args += ["-n", str(options.copies), "-o", f"sides={options.sides}"]
    if options.number_up != 1:
        args += ["-o", f"number-up={options.number_up}"]
    if options.pages is not None:
        args += ["-P", parse_page_list(options.pages)]
    return [*args, "-t", "Ghislieri Bot", "--", str(path)]


def is_pdf(path: Path) -> bool:
    """The client only claims the MIME type; check the file header too."""
    with path.open("rb") as f:
        return f.read(5) == b"%PDF-"


async def print_pdf(settings: Settings, path: Path, options: PrintOptions) -> None:
    """Send the file to the printer. Raises PrintError with a short reason on failure."""
    args = build_lp_args(path, options, settings.printer)
    if not settings.is_prod:
        log.info("[dev] Not printing: %s", args)
        return
    try:
        proc = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
    except OSError as e:
        raise PrintError(f"lp non disponibile: {e}") from e
    try:
        _, stderr = await asyncio.wait_for(proc.communicate(), TIMEOUT)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        raise PrintError("la stampante non risponde") from None
    if proc.returncode != 0:
        raise PrintError(stderr.decode(errors="replace").strip()[:300] or f"lp exit code {proc.returncode}")
    log.info("Print job sent (%s copies, %s)", options.copies, options.sides)
