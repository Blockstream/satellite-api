from http import HTTPStatus
import requests

from error import get_http_error_resp
from flask_restful import Resource
import constants


class InfoResource(Resource):
    def get(self):
        try:
            info_response = requests.get(f"{constants.CHARGE_ROOT}/info",
                                         timeout=(constants.CONNECTION_TIMEOUT,
                                                  constants.RESPONSE_TIMEOUT))
            if info_response.status_code != HTTPStatus.OK:
                return get_http_error_resp('LIGHTNING_CHARGE_INFO_FAILED')
            return info_response.json(), HTTPStatus.OK
        except requests.exceptions.RequestException:
            return get_http_error_resp('LIGHTNING_CHARGE_INFO_FAILED')
