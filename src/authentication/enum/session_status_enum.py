from enum import Enum


class SessionStatus(str, Enum):
    '''
    Session status enumeration
    '''
    ACTIVE: str = 'active'
    EXPIRED: str = 'expired'
    INVALID: str = 'invalid'
    NOT_FOUND: str = 'not_found'
