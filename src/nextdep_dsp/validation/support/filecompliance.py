import os
import json
import sys
import tempfile
import atexit
import logging
from nextdep_dsp.validation.support.schemacompliance import SchemaCompliance

logging.basicConfig(level=logging.INFO)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__file__)
logger.addHandler(handler)


class FileCompliance:
    def __init__(self, schemafile:str):
        self.schemafile = schemafile

    def inspect_params(self, schemafile:str, exptype:str, filetype:list[str], subtype:str="") -> bool:
        """entry point for file check with parameters

        Args:
            schemafile (str): path to schema file
            exptype (str): type of experiment
            filetype (list): list of file types
            subtype (str): subtype for em experiment
        Returns:
            bool: True or False
        """
        datafile = self.generate_data_file(exptype, filetype, subtype)
        return self.validate_required_files(datafile, schemafile)

    def inspect_files(self, datafile:str, schemafile:str) -> bool:
        """entry point for file check with prebuilt json file

        Args:
            datafile (str): path to datafile
            schemafile (str): path to schemafile
        Returns:
            bool: True or False
        """
        return self.validate_required_files(datafile, schemafile)

    def generate_data_file(self, exptype:str, filetypes:list, subtype:str="") -> str:
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
        logger.info(f"generated temporary file: {tmp.name}")
        atexit.register(lambda: os.remove(tmp.name))
        return tmp.name

    def validate_required_files(self, datafile, schemafile, keyword_extension=False) -> bool:
        """forward parameters to support module

        Args:
            datafile (str): path to datafile
            schemafile (str): path to schemafile
            keyword_extension (bool, optional): keyword extension for validation. Defaults to False.
        Returns:
            bool: True or False
        """
        schemac = SchemaCompliance(datafile, schemafile, keyword_extension)
        v = schemac.validate()
        valid = v.valid.value
        assert isinstance(valid, bool), "error - result is not a boolean"
        return valid