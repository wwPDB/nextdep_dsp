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
    schema:str = None
    datafile:str = None
    keyword_extension:bool = False
    valid:'ValidationObject.ValidationResult' = None
    errors:list[str] = None
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
        print("schema file %s" % schemafile)
        if not schemafile:
            raise FileNotFoundError("error - schema file is required")
        elif not os.path.exists(schemafile):
            raise FileNotFoundError("error - schema file not found")
        if datafile is not None and not os.path.exists(datafile):
            raise FileNotFoundError("error - data file not found")
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
        result = ValidationObject()
        try:

            with open(self.datafile) as f:
                data = json.load(f)
                result.datafile = self.datafile

            with open(self.schemafile) as f:
                schema = json.load(f)
                result.schema = self.schemafile

            resolver = RefResolver(self.resolvepath, schema)

            self.validator(resolver=resolver, schema=schema).validate(data)

            result.valid = result.ValidationResult.THUMBS_UP

        except (ValidationError, Exception) as e:
            msg = getattr(e, 'message', str(e))
            logger.error("an exception occurred: %s" % msg)
            result.valid = result.ValidationResult.THUMBS_DOWN
            result.errors = [msg]

        return result
