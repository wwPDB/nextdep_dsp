"""Console script for nextdep_dsp."""

import logging
import time

import typer
from rich.console import Console
from rich.logging import RichHandler

from nextdep_dsp.deposition.deposit_api import DepositApi, Country, FileType
from nextdep_dsp.deposition.enum import EMSubType

app = typer.Typer()
console = Console()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[RichHandler(console=console, show_time=False)],
)
log = logging.getLogger(__name__)


@app.command()
def main() -> None:
    """Console script for nextdep_dsp."""
    api = DepositApi()
    # deposition = api.create_xray_deposition(email="wbueno@ebi.ac.uk", users=["0000-0001-6872-1814"], country=Country.USA)
    deposition = api.create_xray_deposition(email="wbueno@ebi.ac.uk", users=["0000-0002-5109-8728"], country=Country.USA)
    log.info("Created deposition: %s", deposition)

    dep_id = deposition.dep_id
    # dep_id = "D_800268"
    result = api.upload_file(dep_id=dep_id, file_path="/home/wbueno/repos/test_files/xray/2gc2.cif",
                             file_type=FileType.MMCIF_COORD)
    log.info("Uploading coord file: %s", result)
    result = api.upload_file(dep_id=dep_id, file_path="/home/wbueno/repos/test_files/xray/2gc2-sf.cif",
                             file_type=FileType.CRYSTAL_STRUC_FACTORS)
    log.info("Uploading SF file: %s", result)
    # log.info("Remove file: %s", api.remove_file(dep_id=dep_id, file_id=800))
    log.info("Process: %s", api.process(dep_id=dep_id))
    status = api.get_status(dep_id=dep_id)
    while status.status != "FINISHED":
        log.info("Deposition %s status: %s", dep_id, status.status)
        time.sleep(5)
        status = api.get_status(dep_id=dep_id)


if __name__ == "__main__":
    app()
