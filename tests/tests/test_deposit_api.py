import logging
import os
import tempfile
import unittest
import warnings
from unittest.mock import Mock

from nextdep_dsp.deposition.deposit_api import DepositApi
from nextdep_dsp.deposition.enum import Country, EMSubType, FileType
from nextdep_dsp.deposition.exceptions import DepositApiException
from nextdep_dsp.deposition.models import (
    Deposit,
    DepositedFile,
    DepositedFilesSet,
    Depositor,
    DepositStatus,
    EmVoxel,
    Experiment,
    PixelSpacing,
)


class MyDepositApi(DepositApi):
    """Wrapper class to provide access to internal rest_adapter"""

    def __init__(
        self,
        hostname: str = "https://example.com",
        api_key: str = "test-api-key",  # non-empty dummy key
        ver: str = "v1",
        ssl_verify: bool = True,
        logger: logging.Logger = None,
    ):
        super().__init__(hostname, api_key, ver, ssl_verify, redirect=False, logger=logger)
        self.rest_adapter = self._rest_adapter


class DepositApiTests(unittest.TestCase):
    def setUp(self):
        self.deposit_api = MyDepositApi()
        self.dep_id = "D_8233000014"
        self.email = "test@ebi.ac.uk"
        self.xray = [Experiment("xray", coordinates=True)]
        self.orcids = ["0009-0005-7979-7466", "0000-0001-6466-8083"]
        self.deposition_mocked_data = {
            "id": self.dep_id,
            "email": self.email,
            "pdb_id": "?",
            "emdb_id": "?",
            "bmrb_id": "?",
            "title": "?",
            "hold_exp_date": None,
            "created": "2023-03-23T14:19:43.850522",
            "last_login": "2023-03-23T14:19:43.850349",
            "site": "PDBe",
            "status": "DEP",
            "site_url": "https://wwwdev.ebi.ac.uk/pdbe-da/deposition",
            "experiments": [{"type": "xray"}],
            "errors": [],
        }
        self.create_deposition_params = {
            "email": self.email,
            "users": self.orcids[:1],
            "country": Country.UK,
            "password": "password",
            "subtype": EMSubType.SPA,
            "related_emdb": "EMD-1234",
            "related_bmrb": "51899",
            "coordinates": True,
        }
        self.create_deposition_methods = {
            "xray": self.deposit_api.create_xray_deposition,
            "fiber": self.deposit_api.create_fiber_deposition,
            "neutron": self.deposit_api.create_neutron_deposition,
            "em": self.deposit_api.create_em_deposition,
            "ec": self.deposit_api.create_ec_deposition,
            "nmr": self.deposit_api.create_nmr_deposition,
            "ssnmr": self.deposit_api.create_ssnmr_deposition,
        }
        self.user = {"id": 1, "orcid": self.orcids[0], "full_name": "Name"}

    def test_create_generic_deposition_success(self):
        # Test a successful deposition creation
        self.deposition_mocked_data["experiments"] = [{"type": "xray"}]
        self.create_deposition_params["experiments"] = self.xray
        self.deposit_api.rest_adapter.post = Mock(return_value=Mock(status_code=200, data=self.deposition_mocked_data))
        deposit = self.deposit_api.create_deposition(**self.create_deposition_params)
        self.assertIsInstance(deposit, Deposit, "Deposition was not created successfully")
        self.assertEqual(deposit.dep_id, self.dep_id, "Deposit ID is not correct")

    def test_create_generic_deposition_failure(self):
        # Test a failed deposition creation
        self.create_deposition_params["experiments"] = self.xray
        self.deposit_api.rest_adapter.post = Mock(side_effect=DepositApiException("Failed to create deposition", 404))
        with self.assertRaises(DepositApiException) as context:
            self.deposit_api.create_deposition(**self.create_deposition_params)
        self.assertEqual(context.exception.status_code, 404)
        self.assertEqual(str(context.exception), "Failed to create deposition", "Exception message is not correct")

    def test_create_each_method_deposition_success(self):
        # Test successful deposition creation for each method
        self.deposition_mocked_data["dep_id"] = self.deposition_mocked_data.pop("id")
        for method, call in self.create_deposition_methods.items():
            if method not in ["xray", "fiber", "neutron"]:
                self.deposition_mocked_data["experiments"] = [{"type": method, "coordinates": False}]
                self.create_deposition_params["coordinates"] = False
            self.deposit_api.create_deposition = Mock(return_value=Deposit(**self.deposition_mocked_data))  # pylint: disable=unexpected-keyword-arg
            deposit = call(**self.create_deposition_params)
            self.assertIsInstance(deposit, Deposit, f"{method} deposition was not created successfully")
            self.assertEqual(deposit.dep_id, self.dep_id, "Deposit ID is not correct")

    def test_create_each_method_deposition_failure(self):
        # Test a failed EM deposition creation
        for _method, call in self.create_deposition_methods.items():
            self.deposit_api.create_deposition = Mock(
                side_effect=DepositApiException("Failed to create deposition", 404)
            )
            with self.assertRaises(DepositApiException) as context:
                call(**self.create_deposition_params)
            self.assertEqual(str(context.exception), "Failed to create deposition", "Exception message is not correct")

    def test_get_deposition_success(self):
        # Test deposition found
        self.deposit_api.rest_adapter.get = Mock(return_value=Mock(status_code=200, data=self.deposition_mocked_data))
        deposit = self.deposit_api.get_deposition(dep_id=self.dep_id)
        self.assertIsInstance(deposit, Deposit, "Deposition was not created successfully")
        self.assertEqual(deposit.dep_id, self.dep_id, "Deposit ID is not correct")

    def test_get_all_depositions_success(self):
        # Test find all depositions_success
        obj1, obj2, obj3 = [self.deposition_mocked_data.copy() for _ in range(3)]
        obj1["id"] = "D_8233000014"
        obj2["id"] = "D_8233000015"
        obj3["id"] = "D_8233000016"
        self.deposit_api.rest_adapter.get = Mock(
            return_value=Mock(status_code=200, data={"total": 3, "items": [obj1, obj2, obj3]})
        )
        depositions = self.deposit_api.get_all_depositions()
        self.assertEqual(len(depositions), 3, "Number of depositions is incorrect")
        self.assertEqual(depositions[0].dep_id, "D_8233000014", "Deposit ID is not correct")
        self.assertEqual(depositions[1].dep_id, "D_8233000015", "Deposit ID is not correct")
        self.assertEqual(depositions[2].dep_id, "D_8233000016", "Deposit ID is not correct")

    def test_add_single_user(self):
        # Test addition of a single user
        self.deposit_api.rest_adapter.post = Mock(return_value=Mock(status_code=200, data=[self.user]))
        users = self.deposit_api.add_user(self.dep_id, self.orcids[0])
        self.assertEqual(len(users), 1, "Number of users is incorrect")
        for user in users:
            self.assertIsInstance(user, Depositor, "User was not added successfully")
            self.assertEqual(user.user_id, self.user["user_id"], "Deposit ID is not correct")
            self.assertEqual(user.orcid, self.orcids[0], "Deposit ID is not correct")

    def test_add_multiple_users(self):
        # Test that passing a list of ORCIDs sends the correct payload and parses both users
        user1 = self.user.copy()
        user2 = self.user.copy()
        user2["id"] = 2
        user2["orcid"] = self.orcids[1]
        mock_post = Mock(return_value=Mock(status_code=200, data=[user1, user2]))
        self.deposit_api.rest_adapter.post = mock_post
        users = self.deposit_api.add_user(self.dep_id, self.orcids)
        # Verify the payload sent to the adapter contains both ORCIDs
        mock_post.assert_called_once()
        call_data = mock_post.call_args.kwargs.get("data") or mock_post.call_args[1].get("data")
        self.assertEqual(call_data, [{"orcid": self.orcids[0]}, {"orcid": self.orcids[1]}])
        # Verify both users are returned and parsed correctly
        self.assertEqual(len(users), 2, "Number of users is incorrect")
        for i, user in enumerate(users):
            self.assertIsInstance(user, Depositor, "User was not added successfully")
            self.assertEqual(user.user_id, i + 1, "User ID is not correct")
            self.assertEqual(user.orcid, self.orcids[i], "ORCID is not correct")

    def test_upload_file_success(self):
        _, file_path = tempfile.mkstemp()
        with open(file_path, "w", encoding="utf-8") as fp:
            fp.write("test file content")

        expected_response = {
            "id": 1,
            "name": "test.mmcif",
            "type": "co-pdb",
            "created": "Thursday, April 21, 2023 14:30:00",
        }
        self.deposit_api.rest_adapter.post = Mock(return_value=Mock(status_code=200, data=expected_response))

        result = self.deposit_api.upload_file(dep_id=self.dep_id, file_path=file_path, file_type=FileType.PDB_COORD)
        self.assertIsInstance(result, DepositedFile, "File upload failed")
        self.assertEqual(result.file_id, 1, "File ID is not correct")
        self.assertEqual(result.name, "test.mmcif")
        self.assertEqual(result._type, FileType.PDB_COORD)  # pylint: disable=protected-access

        os.remove(file_path)

    def test_upload_file_failed(self):
        self.deposit_api.rest_adapter.post = Mock(side_effect=DepositApiException("Invalid file", 404))
        with self.assertRaises(DepositApiException) as context:
            _result = self.deposit_api.upload_file(
                dep_id=self.dep_id, file_path="/not/exists/file.mmcif", file_type=FileType.PDB_COORD
            )  # noqa: F841
        self.assertEqual(context.exception.status_code, 404)
        self.assertEqual(str(context.exception), "Invalid input file", "Invalid input file")

    def test_get_files(self):
        data = {
            "errors": [],
            "warnings": [],
            "files": [
                {"name": "sdasdsa.mcif", "type": "co-pdb", "id": 40, "created": "Friday, April 21, 2023 12:03:58"},
                {"name": "8f2i.cifuwG7AvQT", "type": "co-pdb", "id": 41, "created": "Friday, April 21, 2023 12:06:37"},
            ],
        }
        self.deposit_api.rest_adapter.get = Mock(return_value=Mock(status_code=200, data=data))
        files = self.deposit_api.get_files(self.dep_id)
        self.assertIsInstance(files, DepositedFilesSet)
        self.assertEqual(len(files), 2)
        self.assertEqual(files[0].file_id, 40)
        self.assertEqual(files[1].file_id, 41)

    def test_get_status(self):
        self.deposit_api.rest_adapter.get = Mock(
            return_value=Mock(
                status_code=200,
                data={
                    "step": "upload",
                    "action": "submit",
                    "details": "Upload type processed",
                    "date": "2023-04-17T14:57:37.774921",
                    "status": "running",
                },
            )
        )
        status = self.deposit_api.get_status(self.dep_id)
        self.assertIsInstance(status, DepositStatus)
        self.assertEqual(status.status, "running")

    def test_process(self):
        self.deposit_api.rest_adapter.post = Mock(
            return_value=Mock(
                status_code=200,
                data={
                    "step": "upload",
                    "action": "submit",
                    "details": "Upload type processed",
                    "date": "2023-04-17T14:57:37.774921",
                    "status": "running",
                },
            )
        )
        status = self.deposit_api.process(self.dep_id)
        self.assertIsInstance(status, DepositStatus)
        self.assertEqual(status.status, "running")


class ModelBugRegressionTests(unittest.TestCase):
    """Regression tests for bugs fixed in models.py"""

    def test_em_voxel_contour_property_no_recursion(self):
        # EmVoxel.contour previously returned self.contour (infinite recursion)
        spacing = PixelSpacing(x=1.0, y=1.0, z=1.0)
        voxel = EmVoxel(spacing=spacing, contour=2.5)
        self.assertEqual(voxel.contour, 2.5)

    def test_deposited_files_set_warnings_not_discarded_when_errors_empty(self):
        # DepositedFilesSet._warnings previously used `if errors` as its guard,
        # so warnings were silently dropped whenever errors was empty/None.
        data = {"files": [], "errors": [], "warnings": [{"code": "w1", "message": "test warning"}]}
        file_set = DepositedFilesSet(**data)
        self.assertEqual(len(file_set.warnings), 1)
        self.assertEqual(file_set.warnings[0].code, "w1")

    def test_deposited_files_set_warnings_none_errors_none(self):
        # Both absent should produce empty lists without error
        file_set = DepositedFilesSet(files=[], errors=None, warnings=None)
        self.assertEqual(len(file_set.errors), 0)
        self.assertEqual(len(file_set.warnings), 0)

    def test_experiment_json_emits_sf_only_when_refln_only_true(self):
        # Public API uses refln_only (clearer name); the OneDep server
        # (per upstream wwPDB/py-onedep_deposition) expects sf_only on the
        # JSON wire. Experiment.json() bridges the two.
        wire = Experiment(exp_type="ec", coordinates=True, refln_only=True).json()
        self.assertEqual(wire.get("sf_only"), True)
        self.assertNotIn("refln_only", wire)

    def test_experiment_json_emits_sf_only_when_refln_only_false(self):
        # The dict-comprehension in Experiment.json() filters by `is not None`,
        # not by truthiness — so refln_only=False survives and must still
        # be remapped to sf_only=False on the wire.
        wire = Experiment(exp_type="ec", coordinates=True, refln_only=False).json()
        self.assertEqual(wire.get("sf_only"), False)
        self.assertNotIn("refln_only", wire)


class DeprecationAliasTests(unittest.TestCase):
    """Backward-compat for the v0.1.0 → v0.2.0 'structure factor' → 'reflection data' rename."""

    def test_filetype_struc_factors_alias(self):
        with self.assertWarns(DeprecationWarning):
            got = FileType.CRYSTAL_STRUC_FACTORS  # noqa: PLW2901  - old name
        self.assertIs(got, FileType.CRYSTAL_REFLN_CIF)

    def test_filetype_mtz_alias(self):
        with self.assertWarns(DeprecationWarning):
            got = FileType.CRYSTAL_MTZ  # noqa: PLW2901  - old name
        self.assertIs(got, FileType.CRYSTAL_REFLN_MTZ)

    def test_filetype_unknown_name_still_attribute_errors(self):
        # The metaclass __getattr__ must not swallow real typos.
        with self.assertRaises(AttributeError):
            _ = FileType.CRYSTAL_NONEXISTENT_NAME

    def test_filetype_iteration_excludes_deprecated_aliases(self):
        # Old names are NOT enum members; iteration sees only the canonical set.
        names = {m.name for m in FileType}
        self.assertIn("CRYSTAL_REFLN_CIF", names)
        self.assertIn("CRYSTAL_REFLN_MTZ", names)
        self.assertNotIn("CRYSTAL_STRUC_FACTORS", names)
        self.assertNotIn("CRYSTAL_MTZ", names)

    def test_experiment_sf_only_kwarg_alias(self):
        with self.assertWarns(DeprecationWarning):
            exp = Experiment(exp_type="ec", coordinates=True, sf_only=True)
        # Forwarded to refln_only and emitted on the wire as sf_only.
        wire = exp.json()
        self.assertEqual(wire.get("sf_only"), True)
        self.assertNotIn("refln_only", wire)

    def test_experiment_sf_only_false_does_not_warn(self):
        # sf_only=None (omitted) is the no-op default; only an explicit value
        # triggers the deprecation path.
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            Experiment(exp_type="ec", coordinates=True)
        deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        self.assertEqual(deprecations, [])

    def test_create_ec_deposition_sf_only_kwarg_alias(self):
        api = MyDepositApi()
        api.rest_adapter.post = Mock(
            return_value=Mock(
                status_code=200,
                data={
                    "id": "D_8233000014",
                    "email": "test@example.org",
                    "pdb_id": "?", "emdb_id": "?", "bmrb_id": "?",
                    "title": "?", "hold_exp_date": None,
                    "created": "2026-01-01T00:00:00",
                    "last_login": "2026-01-01T00:00:00",
                    "site": "PDBe", "status": "DEP", "site_url": "https://example.org",
                    "experiments": [{"type": "ec", "coordinates": True, "sf_only": True}],
                    "errors": [],
                },
            )
        )
        with self.assertWarns(DeprecationWarning):
            deposit = api.create_ec_deposition(
                email="test@example.org",
                users=["0000-0001-2345-6789"],
                country=Country.UK,
                coordinates=True,
                sf_only=True,
            )
        # Verify the wire payload sent to the server still uses sf_only:True.
        call_kwargs = api.rest_adapter.post.call_args.kwargs
        sent_experiments = call_kwargs["data"]["experiments"]
        self.assertEqual(sent_experiments[0]["sf_only"], True)
        self.assertNotIn("refln_only", sent_experiments[0])
        self.assertEqual(deposit.dep_id, "D_8233000014")


if __name__ == "__main__":
    unittest.main()
