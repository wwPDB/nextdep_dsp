import os
import json
from jsonschema import validate, RefResolver, validators, ValidationError
from dataclasses import dataclass
from pathlib import Path
from enum import Enum
from nextdep_dsp.validation.support.keywords import Keywords
import logging
logger = logging.getLogger(__name__)

@dataclass
class ValidationObject:
    """validation object"""
    method:str = None
    filetypes:list[str] = None
    schema:str = None
    valid:'ValidationObject.ValidationResult' = None
    subtype:str = ""
    errors:list[str] = None
    keyword_extension:bool = False
    class ValidationResult(Enum):
        """validation result"""
        THUMBS_UP = True
        THUMBS_DOWN = False

class SchemaCompliance:
    """validation logic for schema compliance"""

    spec = validators.Draft202012Validator

    def __init__(self, datafile:str, schemafile:str, keyword_extension:bool=False):
        self.datafile = datafile
        self.schemafile = schemafile
        self.keyword_extension = keyword_extension
        if not os.path.exists(datafile) or not os.path.exists(schemafile):
            raise FileNotFoundError("error - file not found")
        if not self.keyword_extension:
            self.validator = getattr(SchemaCompliance, "spec")
        else:
            self.keywords = Keywords()
            self.keywords = Keywords.registry()
            self.validator = validators.extend(getattr(SchemaCompliance, "spec"), self.keywords)
        self.resolvepath = Path(self.schemafile).resolve().as_uri()

    def validate(self) -> ValidationObject:
        """validate a json file with schema
        use RefResolver to resolve file paths to uri for online installations
        external schema file paths are resolved on-the-fly
        returns:
            ValidationObject
        raises:
            ValidationError: if data file is not valid according to the schema
        """
        v = ValidationObject()
        try:

            with open(self.datafile) as f:
                data = json.load(f)
                v.method = data.get("method")
                v.subtype = data.get("subtype", "")
                v.filetypes = data.get("files")

            with open(self.schemafile) as f:
                schema = json.load(f)
                v.schema = self.schemafile

            resolver = RefResolver(self.resolvepath, schema)

            self.validator(resolver=resolver, schema=schema).validate(data)

            v.valid = v.ValidationResult.THUMBS_UP

        except (ValidationError, Exception) as e:
            msg = getattr(e, 'message', str(e))
            logger.error("an exception occurred: %s" % msg)
            v.valid = v.ValidationResult.THUMBS_DOWN
            v.errors = [msg]

        return v
