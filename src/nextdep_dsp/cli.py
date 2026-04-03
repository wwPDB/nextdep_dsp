"""Console script for nextdep_dsp."""

import os
import time
from typing import Annotated, Optional
import typer
from rich.console import Console
import json
import re
import functools
from nextdep_dsp.deposition.deposit_api import DepositApi
from nextdep_dsp.deposition.enum import EMSubType, ExperimentType, Country, FileType
from nextdep_dsp.deposition.models import Deposit, DepositedFile, DepositStatus

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
    """Create deposition"""
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
    """Upload file to deposition"""
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
    """Get status of deposition"""
    if not verify_dep_id(dep_id):
        raise ValueError(f"Invalid deposition ID format: {dep_id}")
    api = DepositApi()
    status = api.get_status(dep_id)
    console.print(f"Status: {status}")
    return True


@app.command()
def remove_file(dep_id: str, file_id: int) -> bool:
    """Remove file from deposition"""
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


@app.command()
def get_files(dep_id: str) -> bool:
    """Get files from deposition"""
    if not verify_dep_id(dep_id):
        raise ValueError(f"Invalid deposition ID format: {dep_id}")
    api = DepositApi()
    files = api.get_files(dep_id)
    for file in files:
        console.print(file)
        console.print("---------------------------------")
    return True


@app.command()
def process(dep_id: str, voxels_json: Optional[str] = None, copy_dep_id: Optional[str] = None, copy_all: bool = False, copy_contact: bool = False, copy_authors: bool = False, copy_citation: bool = False, copy_grant: bool = False, copy_em_exp: bool = False) -> bool:
    """Process deposition

    Args:
        dep_id (str): Deposition ID to process
        voxels_json (Optional[str], optional): Path to voxels JSON file with voxel values in the following format: ([{"file_id": X, "spacing": Y, "contour": Z}, ...])
        copy_dep_id (Optional[str], optional): Deposition ID to copy elements from. Defaults to None.
        copy_all (bool, optional): Copy all elements. Defaults to False.
        copy_contact (bool, optional): Copy contact information. Defaults to False.
        copy_authors (bool, optional): Copy authors. Defaults to False.
        copy_citation (bool, optional): Copy citation. Defaults to False.
        copy_grant (bool, optional): Copy grant information. Defaults to False.
        copy_em_exp (bool, optional): Copy EM experiment data. Defaults to False.
    """
    if not verify_dep_id(dep_id):
        raise ValueError(f"Invalid deposition ID format: {dep_id}")
    voxel = None
    if voxels_json:
        if not os.path.isfile(voxels_json):
            raise FileNotFoundError(f"Voxel file not found: {voxels_json}")
        with open(voxels_json, "r", encoding="utf-8") as f:
            voxel = json.load(f)
    copy_elements = {"copy_contact": False, "copy_authors": False, "copy_citation": False, "copy_grant": False, "copy_em_exp_data": False}
    if copy_dep_id:
        copy_elements = {"copy_contact": copy_contact, "copy_authors": copy_authors, "copy_citation": copy_citation, "copy_grant": copy_grant, "copy_em_exp_data": copy_em_exp}
        if copy_all:
            copy_elements = {"copy_contact": True, "copy_authors": True, "copy_citation": True, "copy_grant": True, "copy_em_exp_data": True}
    api = DepositApi()
    response = api.process(dep_id, voxel=voxel, copy_from_id=copy_dep_id, **copy_elements)
    if isinstance(response, DepositStatus):
        console.print(response.status)
        return True
    else:
        console.print(response)
        return False


@app.command()
def get_deposition(dep_id: str) -> bool:
    """Get deposition from deposition id"""
    if not verify_dep_id(dep_id):
        raise ValueError(f"Invalid deposition ID format: {dep_id}")
    api = DepositApi()
    deposition = api.get_deposition(dep_id)
    console.print(deposition)
    return True


@app.command()
def add_users(dep_id: str, orcid: Annotated[list[str], typer.Option()]) -> bool:
    """Add users to deposition"""
    api = DepositApi()
    users = api.add_user(dep_id, orcid)
    for user in users:
        console.print(user)
        console.print("---------------------------------")
    return True


@app.command()
def get_users(dep_id: str) -> bool:
    """Get users from deposition"""
    if not verify_dep_id(dep_id):
        raise ValueError(f"Invalid deposition ID format: {dep_id}")
    api = DepositApi()
    users = api.get_users(dep_id)
    for user in users:
        console.print(user)
        console.print("---------------------------------")
    return True


@app.command()
def remove_user(dep_id: str, orcid: str) -> bool:
    """Remove user from deposition"""
    api = DepositApi()
    user_removed = api.remove_user(dep_id, orcid)
    if user_removed:
        console.print(f"User {orcid} was removed from the deposition {dep_id}.")
        return True
    else:
        console.print(f"Failed to remove user {orcid} from the deposition {dep_id}.")
        return False


@app.command()
def update(dep_id: str, file_id: int, spacing_x: float, spacing_y: float, spacing_z: float, contour: float, description: str) -> bool:
    """Update metadata for a file in a deposition"""
    if not verify_dep_id(dep_id):
        raise ValueError(f"Invalid deposition ID format: {dep_id}")
    api = DepositApi()
    file = api.update_metadata(dep_id, file_id, spacing_x, spacing_y, spacing_z, contour, description)
    console.print(f"Updated file: {file}")
    return True


if __name__ == "__main__":
    app()
