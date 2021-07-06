from http import HTTPStatus
import json

errors = {
    'OTHER_ERROR': (1, "", ""),
    'PARAM_COERCION':
    (2, "type coercion error", "{} does not have the expected type",
     HTTPStatus.INTERNAL_SERVER_ERROR),
    'PARAM_MISSING': (3, "", ""),
    'PARAM_BLANK': (4, "", ""),
    'PARAM_NOT_STRING': (5, "", ""),
    'PARAM_FORMAT': (6, "", ""),
    'PARAM_EQUALITY': (7, "", ""),
    'PARAM_OUT_OF_RANGE': (8, "", ""),
    'PARAM_TOO_SMALL': (9, "", ""),
    'PARAM_TOO_LARGE': (10, "", ""),
    'PARAM_TOO_SHORT': (11, "", ""),
    'PARAM_TOO_LONG': (12, "", ""),
    'PARAM_ONE_OF': (13, "", ""),
    'PARAM_ANY_OF': (14, "", ""),
    'LIMIT_TOO_LARGE':
    (101, "limit too large", "limit cannot be larger than {}",
     HTTPStatus.INTERNAL_SERVER_ERROR),
    'BID_TOO_SMALL': (102, "Bid too low",
                      "The minimum bid for this message is {} millisatoshis.",
                      HTTPStatus.BAD_REQUEST),
    'FILE_MISSING': (103, "", ""),
    'ORDER_NOT_FOUND': (104, "Order not found", "UUID {} not found",
                        HTTPStatus.NOT_FOUND),
    'BID_INCREASE_MISSING': (105, "", ""),
    'BID_INCREASE_TOO_SMALL': (106, "", ""),
    'LID_MISSING': (107, "", ""),
    'CHARGED_AUTH_TOKEN_MISSING': (108, "", ""),
    'INVALID_AUTH_TOKEN': (109, "Unauthorized", "Invalid authentication token",
                           HTTPStatus.UNAUTHORIZED),
    'LIGHTNING_CHARGE_INVOICE_ERROR':
    (110, "Invoice Creation Error", "Lightning Charge invoice creation error",
     HTTPStatus.BAD_REQUEST),
    'LIGHTNING_CHARGE_WEBHOOK_REGISTRATION_ERROR':
    (111, "Invoice Creation Error",
     "Lightning Charge webhook registration error", HTTPStatus.BAD_REQUEST),
    'INVOICE_ID_NOT_FOUND_ERROR': (112, "Not found", "Invoice id {} not found",
                                   HTTPStatus.NOT_FOUND),
    'INVALID_DATE':
    (113, "Invalid date", "Couldn't parse date given by before param",
     HTTPStatus.BAD_REQUEST),
    'SEQUENCE_NUMBER_NOT_FOUND':
    (114, "Sequence number not found",
     "Sent order with sequence number {} not found", HTTPStatus.NOT_FOUND),
    'MESSAGE_FILE_MISSING': (115, "", ""),
    'MESSAGE_FILENAME_MISSING': (116, "", ""),
    'MESSAGE_FILE_TOO_SMALL': (117, "Message too small",
                               "Minimum message size is {} byte",
                               HTTPStatus.BAD_REQUEST),
    'MESSAGE_FILE_TOO_LARGE': (118, "Message too large",
                               "Message size exceeds max size of {} MB",
                               HTTPStatus.REQUEST_ENTITY_TOO_LARGE),
    'ORDER_BUMP_ERROR': (119, "", ""),
    'ORDER_CANCELLATION_ERROR': (120, "Cannot cancel order",
                                 "Order already {}", HTTPStatus.BAD_REQUEST),
    'INVOICE_NOT_FOUND': (121, "", ""),
    'ORPHANED_INVOICE': (122, "Payment problem", "Orphaned invoice",
                         HTTPStatus.NOT_FOUND),
    'ORDER_ALREADY_PAID': (123, "Payment problem", "Order already paid",
                           HTTPStatus.BAD_REQUEST),
    'CHANNELS_EQUALITY': (124, "invalid channel",
                          "channel {} is not a valid channel name",
                          HTTPStatus.INTERNAL_SERVER_ERROR),
    'MESSAGE_TOO_LONG': (125, "", ""),
    'MESSAGE_MISSING':
    (126, "Message upload problem",
     "Either a message file or a message parameter is required",
     HTTPStatus.BAD_REQUEST),
    'REGION_NOT_FOUND': (127, "region not found", "region {} not found",
                         HTTPStatus.NOT_FOUND),
    'LIGHTNING_CHARGE_INFO_FAILED':
    (128, "Lightning Charge communication error",
     "Failed to fetch information about the Lightning node",
     HTTPStatus.INTERNAL_SERVER_ERROR)
}


def _err_to_json(key, *args):
    """Translate an error key to the full JSON error response"""
    assert (key in errors)
    code = errors[key][0]
    title = errors[key][1]
    detail = errors[key][2].format(*args)
    return json.dumps({
        'message':
        title,
        'errors': [{
            'title': title,
            'detail': detail,
            'code': code
        }]
    })


def get_http_error_resp(key, *args):
    """Return the HTTP error response

    Returns: Pair with JSON response and the HTTP error code. The JSON response
        contains the satellite-specific error code and information.

    """
    json_resp = _err_to_json(key, *args)
    return json_resp, errors[key][3]


def assert_error(json_resp, key):
    """Verify that the error response is as expected for the given error key"""
    err_data = json.loads(json_resp)
    assert 'message' in err_data
    assert 'errors' in err_data
    # Check title and code (but not detail, which is set dynamically)
    assert err_data['errors'][0]['title'] == errors[key][1]
    assert err_data['errors'][0]['code'] == errors[key][0]
