from http import HTTPStatus

errors = {
    'PARAM_COERCION':
    (2, "type coercion error", "{} does not have the expected type",
     HTTPStatus.INTERNAL_SERVER_ERROR),
    'BID_TOO_SMALL': (102, "Bid too low",
                      "The minimum bid for this message is {} millisatoshis.",
                      HTTPStatus.BAD_REQUEST),
    'ORDER_NOT_FOUND': (104, "Order not found", "UUID {} not found",
                        HTTPStatus.NOT_FOUND),
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
    'SEQUENCE_NUMBER_NOT_FOUND':
    (114, "Sequence number not found",
     "Sent order with sequence number {} not found", HTTPStatus.NOT_FOUND),
    'MESSAGE_FILE_TOO_SMALL': (117, "Message too small",
                               "Minimum message size is {} byte",
                               HTTPStatus.BAD_REQUEST),
    'MESSAGE_FILE_TOO_LARGE': (118, "Message too large",
                               "Message size exceeds max size of {} MB",
                               HTTPStatus.REQUEST_ENTITY_TOO_LARGE),
    'ORDER_CANCELLATION_ERROR': (120, "Cannot cancel order",
                                 "Order already {}", HTTPStatus.BAD_REQUEST),
    'ORDER_BUMP_ERROR': (121, "Cannot bump order", "Order already {}",
                         HTTPStatus.BAD_REQUEST),
    'ORPHANED_INVOICE': (122, "Payment problem", "Orphaned invoice",
                         HTTPStatus.NOT_FOUND),
    'INVOICE_ALREADY_PAID': (123, "Payment problem", "Invoice already paid",
                             HTTPStatus.BAD_REQUEST),
    'MESSAGE_MISSING':
    (126, "Message upload problem",
     "Either a message file or a message parameter is required",
     HTTPStatus.BAD_REQUEST),
    'LIGHTNING_CHARGE_INFO_FAILED':
    (128, "Lightning Charge communication error",
     "Failed to fetch information about the Lightning node",
     HTTPStatus.INTERNAL_SERVER_ERROR),
    'INVOICE_ALREADY_EXPIRED': (129, "Payment problem",
                                "Invoice already expired",
                                HTTPStatus.BAD_REQUEST),
    'ORDER_CHANNEL_UNAUTHORIZED_OP': (130, "Unauthorized channel operation",
                                      "Operation not supported on channel {}",
                                      HTTPStatus.UNAUTHORIZED),
}


def _err_to_dict(key, *args):
    """Translate an error key to the full error response dictionary"""
    assert (key in errors)
    code = errors[key][0]
    title = errors[key][1]
    detail = errors[key][2].format(*args)
    return {
        'message': title,
        'errors': [{
            'title': title,
            'detail': detail,
            'code': code
        }]
    }


def get_http_error_resp(key, *args):
    """Return the HTTP error response

    Returns: Pair with error response dictionary and the HTTP error code. The
        former contains the satellite-specific error code and information.

    """
    return _err_to_dict(key, *args), errors[key][3]


def assert_error(err_data, key):
    """Verify that the error response is as expected for the given error key"""
    assert 'message' in err_data
    assert 'errors' in err_data
    # Check title and code (but not detail, which is set dynamically)
    assert err_data['errors'][0]['title'] == errors[key][1]
    assert err_data['errors'][0]['code'] == errors[key][0]
