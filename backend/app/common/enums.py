from enum import Enum


class SortOrder(str, Enum):
    LATEST = "latest"
    OLDEST = "oldest"
    A_TO_Z = "a_to_z"
    Z_TO_A = "z_to_a"
