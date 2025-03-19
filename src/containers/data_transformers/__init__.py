from google.protobuf.message import Message
from typing import TypeVar
from abc import ABC, abstractmethod
from dataclasses import dataclass


T = TypeVar('T', bound=dataclass)


class InputDataTransformer(ABC):
    '''
    Transform dataclass to protobuf message
    '''
    @classmethod
    @abstractmethod
    def transform(cls, input_data: T) -> Message:
        '''
        Transform dataclass to protobuf message
        '''
        pass


class OutputDataTransformer(ABC):
    '''
    Transform protobuf message to dataclass
    '''
    @classmethod
    @abstractmethod
    def transform(cls, output_data: Message) -> T:
        '''
        Transform protobuf message to dataclass
        '''
        pass
