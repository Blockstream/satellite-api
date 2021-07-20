from http import HTTPStatus
import requests

from flask_restful import Resource
import constants


class InfoResource(Resource):
    def get(self):
        try:
            info_response = requests.get(f"{constants.CHARGE_ROOT}/info",
                                         timeout=(constants.CONNECTION_TIMEOUT,
                                                  constants.RESPONSE_TIMEOUT))
            if info_response.status_code != HTTPStatus.OK:
                return 'Failed to fetch info', info_response.status_code
            return info_response.json(), HTTPStatus.OK
        except requests.exceptions.RequestException:
            return 'Failed to fetch info', HTTPStatus.INTERNAL_SERVER_ERROR
