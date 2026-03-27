import typer
from typing import Annotated
from rich.console import Console
from nextdep_dsp.validation.support.schemacompliance import SchemaCompliance
from nextdep_dsp.validation.support.filecompliance import FileCompliance

app = typer.Typer()
console = Console()


@app.command()
def filecheck(schemafile:str, exptype:str, filetype:Annotated[list[str], typer.Option()], subtype:str="") -> None:
    """required files command line entry point

    Args:
        schemafile (str): path to schema file
        exptype (str): type of experiment
        filetype (list): list of file types
        subtype (str): subtype for em experiment
    """
    filec = FileCompliance(schemafile)
    legit = filec.inspect_params(exptype, filetype, subtype)
    if legit:
        console.print("validated correctly")
    else:
        console.print("validation failed")

@app.command()
def datafile(datafile:str, schemafile:str, keyword_extension:bool = False) -> None:
    """generalized command line entry point

    Args:
        datafile (str): path to datafile
        schemafile (str): path to schemafile
    """
    schemac = SchemaCompliance(datafile, schemafile, keyword_extension)
    v = schemac.validate()
    legit = v.valid.value
    if legit:
        console.print("validated correctly")
    else:
        console.print("validation failed")


if __name__ == "__main__":
    app()
