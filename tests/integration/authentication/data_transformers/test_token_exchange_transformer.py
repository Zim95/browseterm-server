# builtins
from unittest import TestCase
from typing import Dict, Any, Optional

# local
from src.authentication.data_transformers.token_exchange_transformer import TokenExchangeTransformer
from src.authentication.dto.token_exchange_dto import TokenExchangeResponseModel


class TestTokenExchangeTransformer(TestCase):
    '''
    Test the TokenExchangeTransformer.
    Tests transformation from OAuth token response to TokenExchangeResponseModel.
    '''

    def setUp(self) -> None:
        '''
        Setup test data for OAuth token exchange responses.
        '''
        # Complete OAuth token response
        self.token_response_complete: Dict[str, Any] = {
            'access_token': 'ya29.a0AfH6SMBx...',
            'refresh_token': '1//0gW4...',
            'expires_in': 3600,
            'token_type': 'Bearer',
            'scope': 'openid profile email'
        }

        # Minimal OAuth token response (only access_token)
        self.token_response_minimal: Dict[str, Any] = {
            'access_token': 'ghp_abc123...',
        }

        # Token response without refresh token
        self.token_response_no_refresh: Dict[str, Any] = {
            'access_token': 'token_xyz',
            'expires_in': 7200
        }

    def test_transform_complete_token_response(self) -> None:
        '''
        Test transformation of complete OAuth token response.
        '''
        # Transform
        token_model: TokenExchangeResponseModel = TokenExchangeTransformer.transform(
            self.token_response_complete
        )

        # Assert
        self.assertEqual(token_model.access_token, 'ya29.a0AfH6SMBx...')
        self.assertEqual(token_model.refresh_token, '1//0gW4...')
        self.assertEqual(token_model.expires_in, 3600)

    def test_transform_minimal_token_response(self) -> None:
        '''
        Test transformation of minimal OAuth token response.
        '''
        # Transform
        token_model: TokenExchangeResponseModel = TokenExchangeTransformer.transform(
            self.token_response_minimal
        )

        # Assert
        self.assertEqual(token_model.access_token, 'ghp_abc123...')
        self.assertIsNone(token_model.refresh_token)
        self.assertIsNone(token_model.expires_in)

    def test_transform_token_response_without_refresh_token(self) -> None:
        '''
        Test transformation when refresh_token is not present.
        '''
        # Transform
        token_model: TokenExchangeResponseModel = TokenExchangeTransformer.transform(
            self.token_response_no_refresh
        )

        # Assert
        self.assertEqual(token_model.access_token, 'token_xyz')
        self.assertIsNone(token_model.refresh_token)
        self.assertEqual(token_model.expires_in, 7200)

    def test_transform_handles_empty_access_token(self) -> None:
        '''
        Test transformation with empty access_token.
        '''
        token_response: Dict[str, Any] = {
            'access_token': '',
            'expires_in': 3600
        }
        token_model: TokenExchangeResponseModel = TokenExchangeTransformer.transform(token_response)

        self.assertEqual(token_model.access_token, '')
        self.assertEqual(token_model.expires_in, 3600)
