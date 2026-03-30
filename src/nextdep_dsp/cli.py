"""Console script for nextdep_dsp."""

import time
from typing import Annotated, Optional
import typer
from rich.console import Console
import re
from nextdep_dsp.deposition.deposit_api import DepositApi
from nextdep_dsp.deposition.enum import EMSubType, ExperimentType, Country, FileType

app = typer.Typer()
console = Console()


def verify_exp_type(exptype:str) -> bool:
    """Verify experiment type"""
    exptypes = []
    for e in ExperimentType:
        exptypes.append(e.value)
    if exptype not in exptypes:
        raise ValueError("Invalid experiment type, options are: " + ", ".join([exptype for exptype in exptypes]))
    return True

def verify_orcid(orcid:str) -> bool:
    """Verify ORCID format"""
    if not re.match(r"^\d{4}-\d{4}-\d{4}-\d{3}[0-9X]$", orcid):
        raise ValueError(f"Invalid ORCID format: {orcid}")
    return True

def get_country_enum(country_string: str):
    """Get Country enum from string"""
    for country in Country:
        if country.value == country_string:
            return country
    raise ValueError("Invalid country, options are: " + ", ".join([country.value for country in Country]))

def get_subtype_enum(subtype_string: str):
    """Get EMSubType enum from string"""
    for subtype in EMSubType:
        if subtype.value == subtype_string:
            return subtype
    raise ValueError("Invalid subtype, options are: " + ", ".join([subtype.value for subtype in EMSubType]))

def get_file_type_enum(file_type_string: str):
    """Get FileType enum from string"""
    for file_type in FileType:
        if file_type.value == file_type_string:
            return file_type
    raise ValueError("Invalid file type, options are: " + ", ".join([file_type.value for file_type in FileType]))

@app.command()
def create(exptype:str, email:str, user:Annotated[list[str], typer.Option()], country:str, subtype:Optional[str]=None, coords:Optional[bool]=None, related:Optional[str]=None, password:Optional[str]=None, sf_only:Optional[bool]=None):
    api = DepositApi()
    verify_exp_type(exptype)
    for u in user:
        verify_orcid(u)
    countryEnum = get_country_enum(country)
    if exptype == "em":
        if subtype is None:
            raise ValueError("subtype is required for EM deposition")
        if coords is None:
            raise ValueError("coordinates (true/false) is required for EM deposition")
        subtypeEnum = get_subtype_enum(subtype)
    elif exptype == "ec":
        if sf_only is None:
            raise ValueError("sf_only (true/false) is required for EC deposition")
    deposition = None
    if exptype == "xray":
        deposition = api.create_xray_deposition(email=email, users=user, country=countryEnum, password=password)
    elif exptype == "em":
        deposition = api.create_em_deposition(email=email, users=user, country=countryEnum, subtype=subtypeEnum, coordinates=coords, related_emdb=related, password=password)
    elif exptype == "nmr":
        deposition = api.create_nmr_deposition(email=email, users=user, country=countryEnum, password=password, coordinates=coords, related_bmrb=related)
    elif exptype == "ssnmr":
        deposition = api.create_ssnmr_deposition(email=email, users=user, country=countryEnum, password=password, coordinates=coords, related_bmrb=related)
    elif exptype == "ec":
        deposition = api.create_ec_deposition(email=email, users=user, country=countryEnum, password=password, coordinates=coords, sf_only=sf_only, related_emdb=related)
    elif exptype == "fiber":
        deposition = api.create_fiber_deposition(email=email, users=user, country=countryEnum, password=password)
    elif exptype == "neutron":
        deposition = api.create_neutron_deposition(email=email, users=user, country=countryEnum, password=password)
    if not deposition:
        raise ValueError("Failed to create deposition")
    dep_id = deposition.dep_id
    console.print(deposition)

@app.command()
def upload(file:str):
    pass

def examples() -> None:
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
