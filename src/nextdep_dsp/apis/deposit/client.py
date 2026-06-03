from __future__ import annotations

import logging
import mimetypes
import os
from json import JSONDecodeError
from typing import Union

import requests
import urllib3

from nextdep_dsp.apis.deposit.models import (
    WwPDBDeposition,
    DepositedFile,
    DepositError,
    DepositStatus,
    Experiment,
)
from nextdep_dsp.auths.types import AuthProvider
from nextdep_dsp.config import DepositConfig
from nextdep_dsp.enums import Country, FileType
from nextdep_dsp.exceptions import ApiError


class HttpApiClient:
    def __init__(
        self,
        config: DepositConfig,
        auth_provider: AuthProvider | None = None,
        ver: str = "v1",
        logger: logging.Logger | None = None,
    ) -> None:
        self._config = config
        self._auth_provider = auth_provider
        self._ver = ver
        self._logger = logger or logging.getLogger(__name__)
        self._base_url = f"{config.hostname}/api/{ver}/"
        if not config.ssl_verify:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self._session = requests.Session()
        self._session.verify = config.ssl_verify

    def _refresh_auth_header(self) -> None:
        if self._auth_provider is not None:
            token = self._auth_provider.get_access_token()
        else:
            token = self._config.access_token or ""
        self._session.headers["Authorization"] = f"Bearer {token}"

    def _do(
        self,
        http_method: str,
        endpoint: str,
        params: dict | None = None,
        data: Union[dict, list, None] = None,
        files: dict | None = None,
        content_type: str = "application/json",
    ) -> dict:
        full_url = self._base_url + endpoint
        headers = {}
        if content_type:
            headers["Content-Type"] = content_type

        self._refresh_auth_header()

        try:
            self._logger.debug("method=%s url=%s", http_method, full_url)
            response = self._session.request(
                method=http_method,
                url=full_url,
                headers=headers,
                params=params,
                json=data if content_type == "application/json" else None,
                data=data if content_type != "application/json" else None,
                files=files,
                timeout=300,
            )
        except requests.exceptions.RequestException as e:
            self._logger.error(str(e))
            raise ApiError("Failed to access the API", 403) from e

        if response.status_code == 204:
            return {}

        if not (200 <= response.status_code <= 299):
            self._logger.error("status=%s reason=%s", response.status_code, response.reason)
            raise ApiError(response.reason, response.status_code)

        try:
            data_out = response.json()
        except (ValueError, JSONDecodeError) as e:
            raise ApiError("Bad JSON in response", 502) from e

        if (
            isinstance(data_out, dict)
            and data_out.get("code") == "invalid_location"
            and "base_url" in data_out.get("extras", {})
        ):
            new_base = data_out["extras"]["base_url"]
            self._logger.warning("Invalid deposit site, redirecting to %s", new_base)
            if not self._config.redirect:
                raise ApiError(f"Invalid deposit site; correct site is {new_base}", 400)
            self._base_url = f"{new_base}/api/{self._ver}/"
            full_url = self._base_url + endpoint
            try:
                response = self._session.request(
                    method=http_method,
                    url=full_url,
                    headers=headers,
                    params=params,
                    json=data if content_type == "application/json" else None,
                    data=data if content_type != "application/json" else None,
                    files=files,
                    timeout=300,
                )
            except requests.exceptions.RequestException as e:
                raise ApiError("Retry after redirect failed", 503) from e
            if response.status_code == 204:
                return {}
            if not (200 <= response.status_code <= 299):
                raise ApiError(response.reason, response.status_code)
            try:
                data_out = response.json()
            except (ValueError, JSONDecodeError) as e:
                raise ApiError("Bad JSON in response after redirect", 502) from e

        return data_out

    def _get(self, endpoint: str, params: dict | None = None) -> dict:
        return self._do("GET", endpoint, params=params)

    def _post(
        self,
        endpoint: str,
        data: Union[dict, list, None] = None,
        files: dict | None = None,
        content_type: str = "application/json",
    ) -> dict:
        return self._do("POST", endpoint, data=data, files=files, content_type=content_type)

    def _delete(self, endpoint: str) -> None:
        self._do("DELETE", endpoint)

    # --- ApiClient Protocol implementation ---

    def create_deposition(
        self,
        email: str,
        users: list[str],
        country: Country,
        experiments: list[Experiment],
        password: str = "",
    ) -> WwPDBDeposition:
        body: dict = {
            "email": email,
            "users": users,
            "country": country.value,
            "experiments": [exp.to_dict() for exp in experiments],
        }
        if password:
            body["password"] = password
        data = self._post("depositions/new", data=body)
        data["dep_id"] = data.pop("id")
        return WwPDBDeposition(**data)

    def get_deposition(self, dep_id: str) -> WwPDBDeposition:
        data = self._get(f"depositions/{dep_id}")
        data["dep_id"] = data.pop("id")
        return WwPDBDeposition(**data)

    def get_all_depositions(self) -> list[WwPDBDeposition]:
        data = self._get("depositions/")
        depositions = []
        for item in data.get("items", []):
            item["dep_id"] = item.pop("id")
            depositions.append(WwPDBDeposition(**item))
        return depositions

    def upload_file(
        self,
        dep_id: str,
        file_path: str,
        file_type: FileType,
        overwrite: bool = False,
    ) -> DepositedFile:
        if not os.path.exists(file_path):
            raise ApiError("Invalid input file", 404)
        file_type_str = file_type.value if isinstance(file_type, FileType) else file_type
        mime_type, _ = mimetypes.guess_type(file_path)
        file_name = os.path.basename(file_path)
        form = {"name": file_name, "type": file_type_str}
        if overwrite:
            for existing_file in self.get_files(dep_id):
                if existing_file.file_type.value == file_type_str:
                    self.remove_file(dep_id, existing_file.file_id)
        with open(file_path, "rb") as fp:
            files = {"file": (file_name, fp, mime_type)}
            data = self._post(f"depositions/{dep_id}/files/", data=form, files=files, content_type="")
        data["file_type"] = data.pop("type")
        data["file_id"] = data.pop("id")
        return DepositedFile(**data)

    def update_metadata(
        self,
        dep_id: str,
        file_id: int,
        spacing_x: float,
        spacing_y: float,
        spacing_z: float,
        contour: float,
        description: str,
    ) -> DepositedFile:
        body = {
            "voxel": {
                "spacing": {"x": spacing_x, "y": spacing_y, "z": spacing_z},
                "contour": contour,
            },
            "description": description,
        }
        data = self._post(f"depositions/{dep_id}/files/{file_id}/metadata", data=body)
        data["file_type"] = data.pop("type")
        data["file_id"] = data.pop("id")
        return DepositedFile(**data)

    def get_files(self, dep_id: str) -> list[DepositedFile]:
        data = self._get(f"depositions/{dep_id}/files/")
        result = []
        for f in data.get("files", []):
            f = dict(f)
            f["file_type"] = f.pop("type", f.get("file_type"))
            f["file_id"] = f.pop("id", f.get("file_id"))
            result.append(DepositedFile(**f))
        return result

    def remove_file(self, dep_id: str, file_id: int) -> bool:
        self._delete(f"depositions/{dep_id}/files/{file_id}")
        return True

    def get_status(self, dep_id: str) -> Union[DepositStatus, DepositError]:
        data = self._get(f"depositions/{dep_id}/status")
        if "action" in data:
            return DepositStatus(**data)
        return DepositError(**data)

    def process(self, dep_id: str) -> Union[DepositStatus, DepositError]:
        data = self._post(f"depositions/{dep_id}/process", data={})
        if "action" in data:
            return DepositStatus(**data)
        return DepositError(**data)
