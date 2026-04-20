import atexit
import json
import logging
import os
import sys
import tempfile
from typing import Optional

from nextdep_dsp.deposition.enum import EMSubType, ExperimentType, FileType
from nextdep_dsp.validation.support.schemacompliance import SchemaCompliance

logging.basicConfig(level=logging.INFO)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__file__)
logger.addHandler(handler)


class FileCompliance(SchemaCompliance):
    """validation logic for required files"""

    schemafile: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "schema", "files.json")

    def __init__(self):
        super().__init__(None, FileCompliance.schemafile, False)
        self.datafile = None
        self.schemafile = FileCompliance.schemafile
        if not os.path.exists(self.schemafile):
            raise FileNotFoundError("error - schema file not found")
        self.keyword_extension = False

    def inspect_params(self, exptype: str, filetype: list[str], subtype: Optional[str] = None) -> bool:
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
        self.datafile = datafile
        return self.validate_required_files()

    def inspect_files(self, datafile: str) -> bool:
        """entry point for file check with prebuilt json file

        Args:
            datafile (str): path to datafile
            schemafile (str): path to schemafile
        Returns:
            bool: True or False
        """
        self.datafile = datafile
        return self.validate_required_files()

    def verify_params(self, exptype: str, filetypes: list[str], subtype: Optional[str] = None) -> bool:
        """verify parameters for file check"""
        explist = []
        filelist = []
        sublist = []
        for e in ExperimentType:
            explist.append(e.value)
        for f in FileType:
            filelist.append(f.value)
        for s in EMSubType:
            sublist.append(s.value)
        if exptype not in explist:
            logger.error("invalid experiment type")
            return False
        if len(filetypes) == 0:
            logger.error("filetypes list cannot be empty")
            return False
        if not all(f in filelist for f in filetypes):
            logger.error("invalid file type")
            return False
        if exptype == ExperimentType.EM.value and subtype is None:
            logger.error("subtype is required for EM experiments")
            return False
        if exptype == ExperimentType.EM.value and subtype not in sublist:
            logger.error("invalid subtype")
            return False
        return True

    def generate_data_file(self, exptype: str, filetypes: list, subtype: Optional[str] = None) -> str:
        """generate json file dynamically from parameters

        Args:
            exptype (str): type of experiment
            filetypes (list): list of file types
            subtype (str): subtype for em experiment
        Returns:
            str: path to generated json file
        """
        if not self.verify_params(exptype, filetypes, subtype):
            raise ValueError("invalid parameters")
        d = {"method": exptype, "files": filetypes}
        if subtype is not None and subtype != "":
            d.update({"subtype": subtype})
        jsonstring = json.dumps(d)
        tmp = tempfile.NamedTemporaryFile(mode="w", delete=False)
        tmp.write(jsonstring)
        tmp.close()
        logger.info(f"generated temporary file: {tmp.name}")
        atexit.register(lambda: os.remove(tmp.name))
        return tmp.name

    def validate_required_files(self) -> bool:
        """forward parameters to support library

        Args:
            datafile (str): path to datafile
            schemafile (str): path to schemafile
            keyword_extension (bool, optional): keyword extension for validation. Defaults to False.
        Returns:
            bool: True or False
        """
        v = self.validate()
        valid = v.valid.value
        return valid
