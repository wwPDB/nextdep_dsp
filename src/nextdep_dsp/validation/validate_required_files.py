import typer
from typing import Annotated
from rich.console import Console
import os
import json
from nextdep_dsp.validation.support.schemacompliance import SchemaCompliance
import tempfile
import atexit

app = typer.Typer()
console = Console()

@app.command()
def params(schemafile:str, exptype:str, filetype:Annotated[list[str], typer.Option()], subtype:str="") -> None:
    """command line entry point

    Args:
        schemafile (str): path to schema file
        exptype (str): type of experiment
        filetype (list): list of file types
        subtype (str): subtype for em experiment
    """
    legit = inspect_params(schemafile, exptype, filetype, subtype)
    if legit:
        console.print("validated correctly")
    else:
        console.print("validation failed")

@app.command()
def files(datafile:str, schemafile:str) -> None:
    """command line entry point

    Args:
        datafile (str): path to datafile
        schemafile (str): path to schemafile
    """
    legit = inspect_files(datafile, schemafile)
    if legit:
        console.print("validated correctly")
    else:
        console.print("validation failed")

def inspect_params(schemafile:str, exptype:str, filetype:list[str], subtype:str="") -> bool:
    """api entry point

    Args:
        schemafile (str): path to schema file
        exptype (str): type of experiment
        filetype (list): list of file types
        subtype (str): subtype for em experiment
    Returns:
        bool: True or False
    """
    datafile = generate_data_file(exptype, filetype, subtype)
    return validate_required_files(datafile, schemafile)

def inspect_files(datafile:str, schemafile:str) -> bool:
    """api entry point

    Args:
        datafile (str): path to datafile
        schemafile (str): path to schemafile
    Returns:
        bool: True or False
    """
    return validate_required_files(datafile, schemafile)

def generate_data_file(exptype:str, filetypes:list, subtype:str="") -> str:
    """generate json file dynamically from parameters

    Args:
        exptype (str): type of experiment
        filetypes (list): list of file types
        subtype (str): subtype for em experiment
    Returns:
        str: path to generated json file
    """
    d = {
        "method": exptype,
        "files": filetypes
    }
    if subtype is not None and subtype != "":
        d.update({"subtype": subtype})
    jsonstring = json.dumps(d)
    tmp = tempfile.NamedTemporaryFile(mode="w", delete=False)
    tmp.write(jsonstring)
    tmp.close()
    console.print(f"generated temporary file: {tmp.name}")
    atexit.register(lambda: os.remove(tmp.name))
    return tmp.name

def validate_required_files(datafile, schemafile, keyword_extension=False) -> bool:
    """forward parameters to support library

    Args:
        datafile (str): path to datafile
        schemafile (str): path to schemafile
        keyword_extension (bool, optional): keyword extension for validation. Defaults to False.
    Returns:
        bool: True or False
    """
    schemac = SchemaCompliance(datafile, schemafile, keyword_extension)
    return schemac.validate()

if __name__ == "__main__":
    app()