from google.protobuf.message import Message
from typing import TypeVar
from abc import ABC, abstractmethod
from pydantic import BaseModel


T = TypeVar('T', bound=BaseModel)


class InputDataTransformer(ABC):
    '''
    Transform pydantic BaseModel to protobuf message
    '''
    @classmethod
    @abstractmethod
    def transform(cls, input_data: T) -> Message:
        '''
        Transform pydantic BaseModel to protobuf message
        '''
        pass


class OutputDataTransformer(ABC):
    '''
    Transform protobuf message to pydantic BaseModel
    '''
    @classmethod
    @abstractmethod
    def transform(cls, output_data: Message) -> T:
        '''
        Transform protobuf message to pydantic BaseModel
        '''
        pass
