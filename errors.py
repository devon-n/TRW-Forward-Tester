import json

from logging_utils import sanitize_dict


def format_allowed_values(enum_cls, formatter=str):
    values = [formatter(member.value) for member in enum_cls]
    if len(values) == 1:
        return values[0]
    if len(values) == 2:
        return f"{values[0]} or {values[1]}"
    return f"{', '.join(values[:-1])}, or {values[-1]}"


class TRWError(Exception):
    code = None
    stage = None
    message = None

    def __init__(self):
        super().__init__(self.message)

    def to_dict(self):
        return {
            "code": self.code,
            "stage": self.stage,
            "message": self.message,
        }

    def log(self, cause=None):
        event = {"failure": self.to_dict()}
        if cause is not None:
            event["exception_type"] = type(cause).__name__
        print(f"Structured failure: {json.dumps(sanitize_dict(event), sort_keys=True)}")


class MissingRequiredFieldError(TRWError):
    code = "missing_required_field"
    stage = "validation"

    def __init__(self, field):
        self.message = f"Missing required webhook field: {field}"
        super().__init__()


class InvalidFieldTypeError(TRWError):
    code = "invalid_field_type"
    stage = "validation"

    def __init__(self, field, expected_type):
        self.message = f"Webhook field must be {expected_type}: {field}"
        super().__init__()


class InvalidFieldValueError(TRWError):
    code = "invalid_field_value"
    stage = "validation"

    def __init__(self, field, expected_value):
        self.message = f"Webhook field has unsupported value; expected {expected_value}: {field}"
        super().__init__()


class InvalidFiniteNumericTypeError(InvalidFieldTypeError):
    def __init__(self, field):
        super().__init__(field, "finite numeric")


class InvalidFiniteNumericValueError(InvalidFieldValueError):
    def __init__(self, field):
        super().__init__(field, "a finite numeric value")


class InvalidPositiveQuantityError(InvalidFieldValueError):
    def __init__(self, field="strategy.order_contracts"):
        super().__init__(field, "a positive finite numeric value")


class InvalidOrderTypeError(InvalidFieldValueError):
    def __init__(self, enum_cls=None):
        if enum_cls is None:
            from trw.types.enums import OrderType
            enum_cls = OrderType
        super().__init__("order_type", format_allowed_values(enum_cls))


class InvalidOrderActionError(InvalidFieldValueError):
    def __init__(self, enum_cls=None):
        if enum_cls is None:
            from trw.types.enums import OrderAction
            enum_cls = OrderAction
        super().__init__("strategy.order_action", format_allowed_values(enum_cls))


class UnsupportedExchangeError(TRWError):
    code = "unsupported_exchange"
    stage = "routing"

    def __init__(self, enum_cls=None):
        if enum_cls is None:
            from trw.types.enums import Exchange
            enum_cls = Exchange
        self.message = f"No exchange value matching {format_allowed_values(enum_cls, str.title)}"
        super().__init__()


class ExchangeSubmissionError(TRWError):
    code = "exchange_submission_failed"
    stage = "exchange_submission"
    message = "Exchange order submission failed"


class PersistenceError(TRWError):
    code = "persistence_failed"
    stage = "persistence"
    message = "Failed to persist trade record"
