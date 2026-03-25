import json
from jsonschema import validate, RefResolver, validators, ValidationError
from pathlib import Path
from nextdep_dsp.validation.support.keywords import Keywords
import logging
logger = logging.getLogger(__name__)

class SchemaCompliance:
    """validation logic for schema compliance"""

    spec = validators.Draft202012Validator

    def __init__(self, datafile:str, schemafile:str, keyword_extension:bool=False):
        self.datafile = datafile
        self.schemafile = schemafile
        self.keyword_extension = keyword_extension
        if not self.keyword_extension:
            self.validator = getattr(SchemaCompliance, "spec")
        else:
            self.keywords = Keywords()
            self.keywords = Keywords.registry()
            self.validator = validators.extend(getattr(SchemaCompliance, "spec"), self.keywords)
        self.resolvepath = Path(self.schemafile).resolve().as_uri()

    def validate(self) -> bool:
        """validate a json file with schema
        use RefResolver to resolve file paths to uri for online installations
        external schema file paths are resolved on-the-fly
        returns:
            true or false
        raises:
            ValidationError: if data file is not valid according to the schema
        """
        try:

            with open(self.datafile) as f:
                data = json.load(f)

            with open(self.schemafile) as f:
                schema = json.load(f)

            resolver = RefResolver(self.resolvepath, schema)

            self.validator(resolver=resolver, schema=schema).validate(data)

        except (ValidationError, Exception) as e:
            msg = getattr(e, 'message', str(e))
            logger.error("an exception occurred: %s" % msg)
            return False

        return True
