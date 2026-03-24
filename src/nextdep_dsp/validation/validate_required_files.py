import os
import sys
import tempfile
import json
from schemacompliance import SchemaCompliance
import argparse
import atexit
import logging

logging.basicConfig(level=logging.INFO)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__file__)
logger.addHandler(handler)

def generate_data_file(exptype:str, filetypes:list, subtype:str="") -> str:
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
    return tmp.name

def validate_required_files(datafile, schemafile, keyword_extension=False) -> bool:
    schemac = SchemaCompliance(datafile, schemafile, keyword_extension)
    return schemac.validate()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--exptype", help="experiment type")
    parser.add_argument("--subtype", help="em experiment subtype")
    parser.add_argument("--filetype", action="append", help="file type", dest="filetypes")
    parser.add_argument("--datafile", help="optional data file")
    parser.add_argument("--schema", default="schema/files.json", help="schema file", required=True)
    args = parser.parse_args()

    if not os.path.exists(args.schema):
        sys.exit("error - schema file does not exist")

    if args.datafile is not None:
        if not os.path.isfile(args.datafile):
            sys.exit("error - data file does not exist")
        if args.exptype or args.subtype or args.filetypes:
            sys.exit("error - datafile is mutually exclusive with all other options except schemafile")
        result = validate_required_files(args.datafile, args.schema)
    elif args.exptype and args.filetypes:
        files = []
        for arg in args.filetypes:
            files.append(arg)

        if not args.subtype:
            args.subtype = ""

        datafile = generate_data_file(args.exptype, files, args.subtype)
        logger.info(f"generated data file: {datafile}")
        atexit.register(lambda: os.remove(datafile))
        result = validate_required_files(datafile, args.schema)
    else:
        sys.exit("error - require data file or experiment type and file type, use option -h for usage")

    if result:
        sys.exit("validated correctly")
    else:
        sys.exit("validation failed")