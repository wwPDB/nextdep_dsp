import pytest
from nextdep_dsp.validation.support.filecompliance import FileCompliance


@pytest.fixture(scope="module")
def inputs_pass():
    return [
        ("xray", ["co-cif", "xs-cif"], None),
        ("xray", ["co-cif", "xs-cif", "xa-top", "xa-mat", "xa-par"], None),
        ("em", ["vo-map", "img-emdb"], "tomography"),
        ("em", ["vo-map", "img-emdb", "half-map", "half-map"], "single"),
    ]


@pytest.fixture(scope="module")
def inputs_fail():
    return [
        ("xray", ["co-cif"], None),
        ("xray", ["xs-cif"], None),
        ("xray", ["co-pdb", "xs-mtz"], None),
        ("xray", ["co-cif", "xs-cif", "co-cif"], None),
        ("xray", ["co-cif", "xs-cif", "xs-cif"], None),
        ("em", ["vo-map"], "tomography"),
        ("em", ["img-emdb"], "tomography"),
        ("em", ["vo-map", "img-emdb"], "single"),
        ("em", ["vo-map", "img-emdb", "half-map"], "single"),
        ("em", ["vo-map", "img-emdb", "half-map", "half-map", "half-map"], "single"),
    ]


@pytest.fixture(scope="module")
def inputs_exception():
    return [("xray", [], None), ("em", [], "tomography"), ("em", ["vo-map", "img-emdb"], None)]


def test_required_files_pass(inputs_pass):
    filec = FileCompliance()
    for exptype, filetype, subtype in inputs_pass:
        assert filec.inspect_params(exptype, filetype, subtype), f"Validation failed for {exptype} {filetype} {subtype}"


def test_required_files_fail(inputs_fail):
    filec = FileCompliance()
    for exptype, filetype, subtype in inputs_fail:
        assert not filec.inspect_params(exptype, filetype, subtype), (
            f"Validation should fail for {exptype} {filetype} {subtype}"
        )


def test_required_files_exception(inputs_exception):
    filec = FileCompliance()
    for exptype, filetype, subtype in inputs_exception:
        with pytest.raises(ValueError):
            filec.inspect_params(exptype, filetype, subtype)
