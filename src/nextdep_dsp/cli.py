"""Console script for nextdep_dsp."""

import os
import time
from typing import Annotated, Optional
import typer
from rich.console import Console
import re
import functools
from nextdep_dsp.deposition.deposit_api import DepositApi
from nextdep_dsp.deposition.enum import EMSubType, ExperimentType, Country, FileType

app = typer.Typer()
console = Console()


def sigma(func) -> bool:
    """Preprocess inputs for deposition creation"""
    @functools.wraps(func)
    def s(*args, **kwargs):
        exptype:str = kwargs.get("exptype")
        email:str = kwargs.get("email")
        user:list[str] = kwargs.get("user")
        country:str = kwargs.get("country")
        subtype:Optional[str] = kwargs.get("subtype")
        coords:Optional[bool] = kwargs.get("coords")
        related_id:Optional[str] = kwargs.get("related_id")
        password:Optional[str] = kwargs.get("password")
        sf_only:Optional[bool] = kwargs.get("sf_only")

        v = verify_exp_type(exptype)
        v &= verify_email(email)
        if len(user) == 0:
            raise ValueError("At least one user is required")
        for u in user:
            v &= verify_orcid(u)
        v &= verify_country(country)
        if exptype == "em":
            if subtype is None:
                raise ValueError("subtype is required for EM deposition")
            if coords is None:
                raise ValueError("coords/no-coords is required for EM deposition")
            v &= verify_subtype(subtype)
        elif exptype == "ec":
            if sf_only is None:
                raise ValueError("sf-only/no-sf-only is required for EC deposition")
        if (
            coords is not None
            and coords == False
            and exptype in ["xray", "fiber", "neutron"]
        ):
            raise ValueError(
                "coordinates are required for xray, fiber, and neutron diffraction"
            )
        if sf_only is not None and exptype != "ec":
            raise ValueError("sf-only is only valid for EC deposition")
        if related_id is not None:
            if exptype in ["em", "ec"]:
                v &= verify_emdb_id(related_id)
            elif exptype in ["nmr", "ssnmr"]:
                v &= verify_bmrb_id(related_id)
            else:
                raise ValueError(
                    "related-id is only valid for EM, EC, NMR, or SS-NMR deposition"
                )
        v ^ func(*args, **kwargs)
    return s


def verify_exp_type(exptype: str) -> bool:
    """Verify experiment type"""
    exptypes = []
    for e in ExperimentType:
        exptypes.append(e.value)
    if exptype not in exptypes:
        raise ValueError(
            "Invalid experiment type, options are: "
            + ", ".join([exptype for exptype in exptypes])
        )
    return True


def verify_email(email: str) -> bool:
    """Verify email format"""
    if not re.match(r"^[\w.-]+@[\w.-]+\.\w+$", email):
        raise ValueError(f"Invalid email format: {email}")
    return True


def verify_orcid(orcid: str) -> bool:
    """Verify ORCID format"""
    if not re.match(r"^\d{4}-\d{4}-\d{4}-\d{3}[0-9X]$", orcid):
        raise ValueError(f"Invalid ORCID format: {orcid}")
    return True


def verify_emdb_id(emdb_id: str) -> bool:
    """Verify EMDB ID format"""
    if not re.match(r"^EMD-\d{4,6}$", emdb_id):
        raise ValueError(f"Invalid EMDB ID format: {emdb_id}")
    return True


def verify_bmrb_id(bmrb_id: str) -> bool:
    """Verify BMRB ID format"""
    if not re.match(r"^\d+$", bmrb_id):
        raise ValueError(f"Invalid BMRB ID format: {bmrb_id}")
    return True


def verify_country(country: str) -> bool:
    """Verify country format"""
    countries = []
    for c in Country:
        countries.append(c.value)
    if country not in countries:
        raise ValueError(
            "Invalid country, options are: "
            + ", ".join([country for country in countries])
        )
    return True


def verify_subtype(subtype: str) -> bool:
    """Verify EM subtype format"""
    subtypes = []
    for s in EMSubType:
        subtypes.append(s.value)
    if subtype not in subtypes:
        raise ValueError(
            "Invalid subtype, options are: "
            + ", ".join([subtype for subtype in subtypes])
        )
    return True


def get_country_enum(country_string: str) -> str:
    """Get Country enum from string"""
    for country in Country:
        if country.value == country_string:
            return country
    raise ValueError(
        "Invalid country, options are: "
        + ", ".join([country.value for country in Country])
    )


def get_subtype_enum(subtype_string: str) -> str:
    """Get EMSubType enum from string"""
    for subtype in EMSubType:
        if subtype.value == subtype_string:
            return subtype
    raise ValueError(
        "Invalid subtype, options are: "
        + ", ".join([subtype.value for subtype in EMSubType])
    )


def get_file_type_enum(file_type_string: str) -> str:
    """Get FileType enum from string"""
    for file_type in FileType:
        if file_type.value == file_type_string:
            return file_type
    raise ValueError(
        "Invalid file type, options are: "
        + ", ".join([file_type.value for file_type in FileType])
    )


def verify_dep_id(dep_id: str) -> bool:
    """Check deposition ID"""
    match = re.match(r"^D_\d+$", dep_id)
    if not match:
        return False
    return True


@app.command()
@sigma
def create(
    exptype: str,
    email: str,
    user: Annotated[list[str], typer.Option()],
    country: str,
    subtype: Optional[str] = None,
    coords: Optional[bool] = None,
    related_id: Optional[str] = None,
    password: Optional[str] = None,
    sf_only: Optional[bool] = None,
) -> bool:
    api = DepositApi()
    countryEnum = get_country_enum(country)
    if exptype == "xray":
        deposition = api.create_xray_deposition(
            email=email, users=user, country=countryEnum, password=password
        )
    elif exptype == "em":
        subtypeEnum = get_subtype_enum(subtype)
        deposition = api.create_em_deposition(
            email=email,
            users=user,
            country=countryEnum,
            subtype=subtypeEnum,
            coordinates=coords,
            related_emdb=related_id,
            password=password,
        )
    elif exptype == "nmr":
        deposition = api.create_nmr_deposition(
            email=email,
            users=user,
            country=countryEnum,
            password=password,
            coordinates=coords,
            related_bmrb=related_id,
        )
    elif exptype == "ssnmr":
        deposition = api.create_ssnmr_deposition(
            email=email,
            users=user,
            country=countryEnum,
            password=password,
            coordinates=coords,
            related_bmrb=related_id,
        )
    elif exptype == "ec":
        deposition = api.create_ec_deposition(
            email=email,
            users=user,
            country=countryEnum,
            password=password,
            coordinates=coords,
            sf_only=sf_only,
            related_emdb=related_id,
        )
    elif exptype == "fiber":
        deposition = api.create_fiber_deposition(
            email=email, users=user, country=countryEnum, password=password
        )
    elif exptype == "neutron":
        deposition = api.create_neutron_deposition(
            email=email, users=user, country=countryEnum, password=password
        )
    if not deposition:
        raise ValueError("Failed to create deposition")
    dep_id = deposition.dep_id
    console.print(dep_id)
    return True


@app.command()
def upload(dep_id: str, file_path: str, file_type: str, overwrite: bool = False) -> bool:
    if not verify_dep_id(dep_id):
        raise ValueError(f"Invalid deposition ID format: {dep_id}")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    file_type = get_file_type_enum(file_type)
    api = DepositApi()
    file = api.upload_file(dep_id, file_path, file_type, overwrite)
    file_id = file.file_id
    console.print(f"Uploaded file: {file_id}")
    return True


@app.command()
def status(dep_id: str) -> bool:
    if not verify_dep_id(dep_id):
        raise ValueError(f"Invalid deposition ID format: {dep_id}")
    api = DepositApi()
    status = api.get_status(dep_id)
    console.print(f"Status: {status}")
    return True


@app.command()
def remove_file(dep_id: str, file_id: int) -> bool:
    if not verify_dep_id(dep_id):
        raise ValueError(f"Invalid deposition ID format: {dep_id}")
    api = DepositApi()
    file_removed = api.remove_file(dep_id, file_id)
    if file_removed:
        console.print(f"File {file_id} was removed from the deposition {dep_id}.")
        return True
    else:
        console.print(f"Failed to remove file {file_id} from the deposition {dep_id}.")
    return False


def examples() -> None:
    """Console script for nextdep_dsp."""
    api = DepositApi()
    # deposition = api.create_xray_deposition(email="wbueno@ebi.ac.uk", users=["0000-0001-6872-1814"], country=Country.USA)
    deposition = api.create_xray_deposition(
        email="wbueno@ebi.ac.uk", users=["0000-0002-5109-8728"], country=Country.USA
    )
    print(deposition)

    dep_id = deposition.dep_id
    # dep_id = "D_800268"
    print(
        api.upload_file(
            dep_id=dep_id,
            file_path="/home/wbueno/repos/test_files/xray/2gc2.cif",
            file_type=FileType.MMCIF_COORD,
        )
    )
    print(
        api.upload_file(
            dep_id=dep_id,
            file_path="/home/wbueno/repos/test_files/xray/2gc2-sf.cif",
            file_type=FileType.CRYSTAL_STRUC_FACTORS,
        )
    )
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
        coordinates=True,
    )
    dep_id = deposition.dep_id

    api.upload_file(
        dep_id=dep_id,
        file_path="/home/wbueno/repos/test_files/em/emd_33233.cif",
        file_type=FileType.MMCIF_COORD,
    )
    api.upload_file(
        dep_id=dep_id,
        file_path="/home/wbueno/repos/test_files/em/emd_33233.map.gz",
        file_type=FileType.EM_MAP,
    )
    api.upload_file(
        dep_id=dep_id,
        file_path="/home/wbueno/repos/test_files/em/emd_33233_half_map_1.map.gz",
        file_type=FileType.EM_HALF_MAP,
    )
    api.upload_file(
        dep_id=dep_id,
        file_path="/home/wbueno/repos/test_files/em/emd_33233_half_map_2.map.gz",
        file_type=FileType.EM_HALF_MAP,
    )
    api.upload_file(
        dep_id=dep_id,
        file_path="/home/wbueno/repos/test_files/em/emd_33233.png",
        file_type=FileType.ENTRY_IMAGE,
    )


if __name__ == "__main__":
    app()
