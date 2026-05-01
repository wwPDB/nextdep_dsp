import logging
import mimetypes
import os
from typing import Union

from nextdep_dsp.config import DepositConfig
from nextdep_dsp.deposition.decorators import handle_invalid_deposit_site
from nextdep_dsp.deposition.enum import Country, EMSubType, FileType
from nextdep_dsp.deposition.exceptions import DepositApiException
from nextdep_dsp.deposition.models import (
    Deposit,
    DepositedFile,
    DepositedFilesSet,
    DepositError,
    Depositor,
    DepositStatus,
    Experiment,
)
from nextdep_dsp.deposition.rest_adapter import RestAdapter


class DepositApi:
    """Deposit API wrapper"""

    def __init__(
        self,
        hostname: str = None,
        api_key: str = None,
        ver: str = "v1",
        ssl_verify: bool = None,
        redirect: bool = None,
        logger: logging.Logger = None,
    ):
        """
        Constructor method for DepositAPI wrapper
        :param hostname: Site url
        :param api_key: User public API key
        :param ver: version (usually v1)
        :param ssl_verify: Perform a SSL verification? True for production
        :param redirect: Allow site redirects? True for production
        :param logger: Attach a logger
        """
        overrides = {
            k: v
            for k, v in {
                "hostname": hostname,
                "api_key": api_key,
                "ssl_verify": ssl_verify,
                "redirect": redirect,
            }.items()
            if v is not None
        }
        config = DepositConfig.load(**overrides)

        if not config.api_key:
            raise DepositApiException(
                "No API key configured. Set ONEDEP_API_KEY or add api_key to ~/.config/nextdep/config.toml",
                401,
            )

        self._hostname = config.hostname
        self._api_key = config.api_key
        self._ssl_verify = config.ssl_verify
        self._redirect = config.redirect
        self._version = ver
        self._logger = logger or logging.getLogger(__name__)

        self._connect()

    def _connect(self) -> None:
        self._rest_adapter = RestAdapter(
            hostname=self._hostname,
            api_key=self._api_key,
            ver=self._version,
            ssl_verify=self._ssl_verify,
            logger=self._logger,
        )

    @handle_invalid_deposit_site
    def create_deposition(
        self,
        email: str,
        users: list[str],
        country: Country,  # pylint: disable=unused-argument
        experiments: list[Experiment],
        password: str = "",
        **kwargs,
    ) -> Deposit:
        """
        General method to create a deposition passing an Experiment object
        :param email: User e-mail
        :param users: List of ORCID ids that can access this deposition
        :param country: Country from enum list
        :param experiments: List of Experiment objects
        :param password: Password
        :return: Response
        """
        data = {
            "email": email,
            "users": users,
            "country": country.value,
            "experiments": [experiment.json() for experiment in experiments],
        }
        if password:
            data["password"] = password
        response = self._rest_adapter.post("depositions/new", data=data)
        response.data["dep_id"] = response.data.pop("id")
        deposit = Deposit(**response.data)
        return deposit

    def create_em_deposition(
        self,
        email: str,
        users: list[str],
        country: Country,
        coordinates: bool = True,
        subtype: Union[EMSubType, str, None] = None,
        related_emdb: str = None,
        password: str = "",
        **kwargs,
    ) -> Deposit:
        """
        Create an EM deposition
        :param email: User e-mail
        :param users: List of ORCID ids that can access this deposition
        :param country: Country from enum list
        :param subtype: EM sub type, accepts enum or string
        :param coordinates: Depositing coordinates file?
        :param related_emdb: Related EMDB id
        :param password: Password
        :return: Response
        """
        experiment = Experiment(exp_type="em", coordinates=coordinates, subtype=subtype, related_emdb=related_emdb)
        deposit = self.create_deposition(
            email=email, users=users, country=country, experiments=[experiment], password=password
        )
        return deposit

    def create_xray_deposition(
        self, email: str, users: list[str], country: Country, password: str = "", **kwargs
    ) -> Deposit:  # pylint: disable=unused-argument
        """
        Create an XRAY deposition
        :param email: User e-mail
        :param users: List of ORCID ids that can access this deposition
        :param country: Country from enum list
        :param password: Password
        :return: Response
        """
        experiment = Experiment(exp_type="xray", coordinates=True)
        deposit = self.create_deposition(
            email=email, users=users, country=country, experiments=[experiment], password=password
        )
        return deposit

    def create_fiber_deposition(
        self, email: str, users: list[str], country: Country, password: str = "", **kwargs
    ) -> Deposit:  # pylint: disable=unused-argument
        """
        Create a Fiber diffraction deposition
        :param email: User e-mail
        :param users: List of ORCID ids that can access this deposition
        :param country: Country from enum list
        :param password: Password
        :return: Response
        """
        experiment = Experiment(exp_type="fiber", coordinates=True)
        deposit = self.create_deposition(
            email=email, users=users, country=country, experiments=[experiment], password=password
        )
        return deposit

    def create_neutron_deposition(
        self, email: str, users: list[str], country: Country, password: str = "", **kwargs
    ) -> Deposit:  # pylint: disable=unused-argument
        """
        Create a Neutron diffraction deposition
        :param email: User e-mail
        :param users: List of ORCID ids that can access this deposition
        :param country: Country from enum list
        :param password: Password
        :return: Response
        """
        experiment = Experiment(exp_type="neutron", coordinates=True)
        deposit = self.create_deposition(
            email=email, users=users, country=country, experiments=[experiment], password=password
        )
        return deposit

    def create_ec_deposition(
        self,
        email: str,
        users: list[str],
        country: Country,
        coordinates: bool,
        password: str = "",  # pylint: disable=unused-argument
        related_emdb: str = None,
        sf_only: bool = False,
        **kwargs,
    ) -> Deposit:
        """
        Create an Electron crystallography deposition
        :param email: User e-mail
        :param users: List of ORCID ids that can access this deposition
        :param country: Country from enum list
        :param coordinates: Depositing coordinates file?
        :param password: Password
        :param related_emdb: Related EMDB id
        :param sf_only: Structure factor only?
        :return: Response
        """
        experiment = Experiment(exp_type="ec", related_emdb=related_emdb, coordinates=coordinates, sf_only=sf_only)
        deposit = self.create_deposition(
            email=email, users=users, country=country, experiments=[experiment], password=password
        )
        return deposit

    def create_nmr_deposition(
        self,
        email: str,
        users: list[str],
        country: Country,
        coordinates: bool,
        password: str = "",  # pylint: disable=unused-argument
        related_bmrb: str = None,
        **kwargs,
    ) -> Deposit:
        """
        Create a NMR deposition
        :param email: User e-mail
        :param users: List of ORCID ids that can access this deposition
        :param country: Country from enum list
        :param coordinates: Depositing coordinates file?
        :param password: Password
        :param related_bmrb: Related BMRB id
        :return: Response
        """
        experiment = Experiment(exp_type="nmr", related_bmrb=related_bmrb, coordinates=coordinates)
        deposit = self.create_deposition(
            email=email, users=users, country=country, experiments=[experiment], password=password
        )
        return deposit

    def create_ssnmr_deposition(
        self,
        email: str,
        users: list[str],
        country: Country,
        coordinates: bool,
        password: str = "",  # pylint: disable=unused-argument
        related_bmrb: str = None,
        **kwargs,
    ) -> Deposit:
        """
        Create a Solid-state NMR E deposition
        :param email: User e-mail
        :param users: List of ORCID ids that can access this deposition
        :param country: Country from enum list
        :param coordinates: Depositing coordinates file?
        :param password: Password
        :param related_bmrb: Related BMRB id
        :return: Response
        """
        experiment = Experiment(exp_type="ssnmr", related_bmrb=related_bmrb, coordinates=coordinates)
        deposit = self.create_deposition(
            email=email, users=users, country=country, experiments=[experiment], password=password
        )
        return deposit

    @handle_invalid_deposit_site
    def get_deposition(self, dep_id: str) -> Union[Deposit, None]:
        """
        Get deposition from ID
        :param dep_id: Deposition ID
        :return: Deposit
        """
        response = self._rest_adapter.get(f"depositions/{dep_id}")
        response.data["dep_id"] = response.data.pop("id")
        return Deposit(**response.data)

    @handle_invalid_deposit_site
    def get_all_depositions(self) -> list[Deposit]:
        """
        Get all depositions from an user
        :return: list[Deposit]
        """
        depositions = []
        response = self._rest_adapter.get("depositions/")
        for deposition_json in response.data["items"]:
            deposition_json["dep_id"] = deposition_json.pop("id")
            deposition = Deposit(**deposition_json)
            depositions.append(deposition)
        return depositions

    @handle_invalid_deposit_site
    def get_users(self, dep_id: str):
        """
        Get users from deposition
        :param dep_id:
        :return: Depositor
        """
        users = []
        response = self._rest_adapter.get(f"depositions/{dep_id}/users/")
        for user_json in response.data:
            user_json["user_id"] = user_json.pop("id")
            user = Depositor(**user_json)
            users.append(user)
        return users

    @handle_invalid_deposit_site
    def add_user(self, dep_id: str, orcid: Union[list, str]) -> list[Depositor]:
        """
        Grant access from given users to deposition
        :param dep_id: Deposition ID
        :param orcid: Orcid ID or list of Orcid ids
        :return: List of depositors
        """
        users = []
        data = []
        if isinstance(orcid, str):
            data.append({"orcid": orcid})
        elif isinstance(orcid, list):
            for orcid_id in orcid:
                data.append({"orcid": orcid_id})
        response = self._rest_adapter.post(f"depositions/{dep_id}/users/", data=data)
        for user_json in response.data:
            user_json["user_id"] = user_json.pop("id")
            users.append(Depositor(**user_json))

        return users

    @handle_invalid_deposit_site
    def remove_user(self, dep_id: str, orcid: str):
        """
        Remove access from an user to a deposition
        :param dep_id: Deposition id
        :param orcid: Orcid id
        :return: Depositor
        """
        self._rest_adapter.delete(f"depositions/{dep_id}/users/{orcid}")
        return True

    @handle_invalid_deposit_site
    def upload_file(
        self, dep_id: str, file_path: str, file_type: Union[str, FileType], overwrite: bool = False
    ) -> DepositedFile:
        """
        Upload a file in a deposition
        :param dep_id: Deposition id
        :param file_path: File path
        :param file_type: Deposition file type
        :param overwrite: If true, overwrite all previously uploaded file with the same type
        :return: File response
        """
        if not os.path.exists(file_path):
            raise DepositApiException("Invalid input file", 404)

        file_type_str = file_type
        if isinstance(file_type, FileType):
            file_type_str = file_type.value

        mime_type, _encoding = mimetypes.guess_type(file_path)
        file_name = os.path.basename(file_path)

        data = {"name": file_name, "type": file_type_str}

        if overwrite:
            deposited_files = self.get_files(dep_id)
            for file in deposited_files:
                if file.file_type.value == file_type_str:
                    self.remove_file(dep_id, file.file_id)

        endpoint = f"depositions/{dep_id}/files/"

        response = self._rest_adapter.repost(endpoint, data, file_path)
        if not response:
            raise DepositApiException("Error uploading file", 500)
        response.data["file_type"] = response.data.pop("type")
        response.data["file_id"] = response.data.pop("id")
        response.data.pop("uploadedBytes")

        return DepositedFile(**response.data)

    @handle_invalid_deposit_site
    def update_metadata(
        self,
        dep_id: str,
        file_id: int,
        spacing_x: float,
        spacing_y: float,
        spacing_z: float,
        contour: float,
        description: str,
    ) -> Deposit:
        """
        Set metadata in a deposition
        :param dep_id: Deposition ID
        :param file_id: File ID
        :param spacing_x: Pixel spacing X
        :param spacing_y: Pixel spacing Y
        :param spacing_z: Pixel spacing Z
        :param contour: Contour level
        :param description: Description
        :return: Deposit
        """

        data = {
            "voxel": {"spacing": {"x": spacing_x, "y": spacing_y, "z": spacing_z}, "contour": contour},
            "description": description,
        }

        response = self._rest_adapter.post(f"depositions/{dep_id}/files/{file_id}/metadata", data=data)
        response.data["file_type"] = response.data.pop("type")
        response.data["file_id"] = response.data.pop("id")
        return DepositedFile(**response.data)

    @handle_invalid_deposit_site
    def get_files(self, dep_id: str) -> DepositedFilesSet:
        """
        Get all files in deposition
        :param dep_id: Deposition ID
        :return: List of uploaded files
        """
        response = self._rest_adapter.get(f"depositions/{dep_id}/files/")
        return DepositedFilesSet(**response.data)

    @handle_invalid_deposit_site
    def remove_file(self, dep_id: str, file_id: int):
        """
        Remove a file from a deposition
        :param dep_id: Deposition ID
        :param file_id: File ID
        :return: None
        """
        self._rest_adapter.delete(f"depositions/{dep_id}/files/{file_id}")
        return True

    @handle_invalid_deposit_site
    def get_status(self, dep_id: str) -> DepositStatus:
        """
        Return the deposition status
        :param dep_id: Deposition ID
        :return: Status
        """
        response = self._rest_adapter.get(f"depositions/{dep_id}/status")
        try:
            status = DepositStatus(**response.data)
        except TypeError:
            status = DepositError(**response.data)
        return status

    @handle_invalid_deposit_site
    def process(
        self,
        dep_id: str,
        voxel: dict = None,
        copy_from_id: str = None,
        copy_contact: bool = False,
        copy_authors: bool = False,
        copy_citation: bool = False,
        copy_grant: bool = False,
        copy_em_exp_data: bool = False,
    ):
        """
        Trigger file processing
        :param dep_id: Deposition ID
        :param voxel: EM Voxel list
        :param copy_from_id: Copy metadata from another deposition?
        :param copy_contact: Copy contract metadata?
        :param copy_authors: Copy authors?
        :param copy_citation: Copy citation?
        :param copy_grant: Copy grant?
        :param copy_em_exp_data: Copy EM experimental data?
        :return: Status
        """
        copy_elements = []
        data = {}
        if voxel:
            data = voxel

        if copy_from_id:
            copy_elements.append("contact") if copy_contact else None  # pylint: disable=expression-not-assigned
            copy_elements.append("authors") if copy_authors else None  # pylint: disable=expression-not-assigned
            copy_elements.append("citation") if copy_citation else None  # pylint: disable=expression-not-assigned
            copy_elements.append("grant") if copy_grant else None  # pylint: disable=expression-not-assigned
            copy_elements.append("em_exp") if copy_em_exp_data else None  # pylint: disable=expression-not-assigned
            data["related"] = {"id": copy_from_id, "items": copy_elements}

        response = self._rest_adapter.post(f"depositions/{dep_id}/process", data=data)
        try:
            status = DepositStatus(**response.data)
        except TypeError:
            status = DepositError(**response.data)

        return status
