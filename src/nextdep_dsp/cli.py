"""Console script for nextdep_dsp."""

import time

import typer
from rich.console import Console

from nextdep_dsp.deposition.deposit_api import DepositApi, Country, FileType
from nextdep_dsp.deposition.enum import EMSubType

app = typer.Typer()
console = Console()


@app.command()
def main() -> None:
    """Console script for nextdep_dsp."""
    api = DepositApi()
    # deposition = api.create_xray_deposition(email="wbueno@ebi.ac.uk", users=["0000-0001-6872-1814"], country=Country.USA)
    deposition = api.create_xray_deposition(email="wbueno@ebi.ac.uk", users=["0000-0002-5109-8728"], country=Country.USA)
    print(deposition)

    dep_id = deposition.dep_id
    # dep_id = "D_800268"
    print(api.upload_file(dep_id=dep_id, file_path="/home/wbueno/repos/test_files/xray/2gc2.cif",
                          file_type=FileType.MMCIF_COORD))
    print(api.upload_file(dep_id=dep_id, file_path="/home/wbueno/repos/test_files/xray/2gc2-sf.cif",
                          file_type=FileType.CRYSTAL_STRUC_FACTORS))
    # print(api.remove_file(dep_id=dep_id, file_id=800))
    print(api.process(dep_id=dep_id))
    status = api.get_status(dep_id=dep_id)
    while status.status != "FINISHED":
        console.print(f"Deposition {dep_id} status: {status.status}")
        time.sleep(15)
        status = api.get_status(dep_id=dep_id)

    deposition = api.create_em_deposition(
        email="wbueno@ebi.ac.uk",
        users=["0000-0001-6872-1814"],
        country=Country.USA,
        subtype=EMSubType.SPA,
        coordinates=True
    )
    dep_id = deposition.dep_id

    api.upload_file(dep_id=dep_id, file_path="/home/wbueno/repos/test_files/em/emd_33233.cif",
                          file_type=FileType.MMCIF_COORD)
    api.upload_file(dep_id=dep_id, file_path="/home/wbueno/repos/test_files/em/emd_33233.map.gz",
                          file_type=FileType.EM_MAP)
    api.upload_file(dep_id=dep_id, file_path="/home/wbueno/repos/test_files/em/emd_33233_half_map_1.map.gz",
                        file_type=FileType.EM_HALF_MAP)
    api.upload_file(dep_id=dep_id, file_path="/home/wbueno/repos/test_files/em/emd_33233_half_map_2.map.gz",
                        file_type=FileType.EM_HALF_MAP)
    api.upload_file(dep_id=dep_id, file_path="/home/wbueno/repos/test_files/em/emd_33233.png",
                        file_type=FileType.ENTRY_IMAGE)


if __name__ == "__main__":
    app()
