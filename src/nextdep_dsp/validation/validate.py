import os
import sys
from schemacompliance import SchemaCompliance
import argparse
import logging

logging.basicConfig(level=logging.INFO)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__file__)
logger.addHandler(handler)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--datafile", required=True, help="json file")
    parser.add_argument("--schema", required=True, help="schema file")
    parser.add_argument("--keywords", action="store_true", help="enable keywords extension")
    args = parser.parse_args()

    datafile = args.datafile
    schemafile = args.schema
    keyword_extension = False
    if args.keywords:
        keyword_extension = bool(args.keywords)
    if not os.path.exists(datafile):
        sys.exit("error - file %s does not exist" % datafile)
    if not os.path.exists(schemafile):
        sys.exit("error - file %s does not exist" % schemafile)

    schemac = SchemaCompliance(datafile, schemafile, keyword_extension)

    if schemac.validate():
        sys.exit("validated correctly")

    sys.exit("validation failed")