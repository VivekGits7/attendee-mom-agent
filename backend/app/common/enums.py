from enum import Enum, IntEnum


class SortOrder(str, Enum):
    LATEST = "latest"
    OLDEST = "oldest"
    A_TO_Z = "a_to_z"
    Z_TO_A = "z_to_a"


class WSCloseCode(IntEnum):
    AUTH_FAILED = 4001
    INVALID_PARAMS = 4002
    SERVER_ERROR = 4003
    NOT_FOUND = 4004
