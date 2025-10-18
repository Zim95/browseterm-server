from abc import ABC, abstractmethod
from typing import TypeVar, Dict, Any
from pydantic import BaseModel


T = TypeVar('T', bound=BaseModel)


class InputDataTransformer(ABC):
    '''
    Transform external data (API responses, etc.) to internal DTOs
    '''
    @classmethod
    @abstractmethod
    def transform(cls, input_data: Dict[str, Any]) -> T:
        '''
        Transform external data to internal DTO
        '''
        pass


class OutputDataTransformer(ABC):
    '''
    Transform internal DTOs to external format
    '''
    @classmethod
    @abstractmethod
    def transform(cls, output_data: T) -> Dict[str, Any]:
        '''
        Transform internal DTO to external format
        '''
        pass
