#!/usr/bin/env python3
"""
Enterprise Secret Management System
エンタープライズシークレット管理システム

参考:
- AWS Secrets Manager Documentation
- HashiCorp Vault Best Practices
- Azure Key Vault Documentation

重要な洞察:
"The AES key is the weakest link in the chain and needs protection at all costs."
- .envファイルでの鍵保管は脆弱
- シークレット管理ソリューションの使用を推奨
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, List
import os
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class SecretProvider(Enum):
    """シークレットプロバイダー"""
    AWS_SECRETS_MANAGER = "aws"
    HASHICORP_VAULT = "vault"
    AZURE_KEY_VAULT = "azure"
    GCP_SECRET_MANAGER = "gcp"
    ENVIRONMENT = "env"  # 開発用フォールバック


@dataclass
class SecretMetadata:
    """シークレットメタデータ"""
    name: str
    version: str
    created_at: str
    updated_at: str
    provider: SecretProvider


class SecretManager(ABC):
    """シークレット管理の抽象インターフェース"""

    @abstractmethod
    def get_secret(self, secret_name: str) -> str:
        """
        シークレットを取得

        Args:
            secret_name: シークレット名

        Returns:
            シークレット値
        """
        pass

    @abstractmethod
    def set_secret(self, secret_name: str, secret_value: str) -> bool:
        """
        シークレットを設定

        Args:
            secret_name: シークレット名
            secret_value: シークレット値

        Returns:
            成功フラグ
        """
        pass

    @abstractmethod
    def delete_secret(self, secret_name: str) -> bool:
        """
        シークレットを削除

        Args:
            secret_name: シークレット名

        Returns:
            成功フラグ
        """
        pass

    @abstractmethod
    def list_secrets(self) -> List[str]:
        """
        シークレット一覧を取得

        Returns:
            シークレット名のリスト
        """
        pass

    @abstractmethod
    def rotate_secret(self, secret_name: str, new_value: str) -> bool:
        """
        シークレットをローテーション

        Args:
            secret_name: シークレット名
            new_value: 新しい値

        Returns:
            成功フラグ
        """
        pass


class AWSSecretsManager(SecretManager):
    """AWS Secrets Manager統合"""

    def __init__(self, region: str = 'us-east-1'):
        """
        初期化

        Args:
            region: AWSリージョン
        """
        try:
            import boto3
            self.client = boto3.client('secretsmanager', region_name=region)
            self.region = region
            logger.info(f"Initialized AWS Secrets Manager (region: {region})")
        except ImportError:
            logger.error("boto3 not installed. Install: pip install boto3")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize AWS Secrets Manager: {e}")
            raise

    def get_secret(self, secret_name: str) -> str:
        """シークレットを取得"""
        try:
            response = self.client.get_secret_value(SecretId=secret_name)

            # JSON形式の場合
            if 'SecretString' in response:
                secret = response['SecretString']
                try:
                    secret_dict = json.loads(secret)
                    # キーが一つの場合はその値を返す
                    if len(secret_dict) == 1:
                        return list(secret_dict.values())[0]
                    return secret
                except json.JSONDecodeError:
                    return secret
            # バイナリの場合
            else:
                return response['SecretBinary'].decode('utf-8')

        except self.client.exceptions.ResourceNotFoundException:
            logger.error(f"Secret not found: {secret_name}")
            raise
        except Exception as e:
            logger.error(f"Failed to get secret: {e}")
            raise

    def set_secret(self, secret_name: str, secret_value: str) -> bool:
        """シークレットを設定"""
        try:
            # シークレットが存在するか確認
            try:
                self.client.describe_secret(SecretId=secret_name)
                # 存在する場合は更新
                self.client.update_secret(
                    SecretId=secret_name,
                    SecretString=secret_value
                )
                logger.info(f"Updated secret: {secret_name}")
            except self.client.exceptions.ResourceNotFoundException:
                # 存在しない場合は作成
                self.client.create_secret(
                    Name=secret_name,
                    SecretString=secret_value
                )
                logger.info(f"Created secret: {secret_name}")

            return True

        except Exception as e:
            logger.error(f"Failed to set secret: {e}")
            return False

    def delete_secret(self, secret_name: str) -> bool:
        """シークレットを削除"""
        try:
            self.client.delete_secret(
                SecretId=secret_name,
                ForceDeleteWithoutRecovery=False,  # 30日間の復旧期間
                RecoveryWindowInDays=30
            )
            logger.info(f"Deleted secret (30-day recovery): {secret_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete secret: {e}")
            return False

    def list_secrets(self) -> List[str]:
        """シークレット一覧を取得"""
        try:
            response = self.client.list_secrets()
            return [secret['Name'] for secret in response.get('SecretList', [])]

        except Exception as e:
            logger.error(f"Failed to list secrets: {e}")
            return []

    def rotate_secret(self, secret_name: str, new_value: str) -> bool:
        """シークレットをローテーション"""
        try:
            # 新しい値で更新
            self.client.update_secret(
                SecretId=secret_name,
                SecretString=new_value
            )

            # ローテーションを記録
            self.client.tag_resource(
                SecretId=secret_name,
                Tags=[
                    {
                        'Key': 'LastRotation',
                        'Value': json.dumps({'timestamp': str(os.times())})
                    }
                ]
            )

            logger.info(f"Rotated secret: {secret_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to rotate secret: {e}")
            return False


class HashiCorpVaultManager(SecretManager):
    """HashiCorp Vault統合"""

    def __init__(self, vault_url: str = 'http://localhost:8200', token: Optional[str] = None):
        """
        初期化

        Args:
            vault_url: Vault URL
            token: 認証トークン
        """
        try:
            import hvac
            self.client = hvac.Client(
                url=vault_url,
                token=token or os.getenv('VAULT_TOKEN')
            )

            if not self.client.is_authenticated():
                raise ValueError("Vault authentication failed")

            logger.info(f"Initialized HashiCorp Vault ({vault_url})")

        except ImportError:
            logger.error("hvac not installed. Install: pip install hvac")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Vault: {e}")
            raise

    def get_secret(self, secret_name: str) -> str:
        """シークレットを取得"""
        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                path=secret_name
            )
            return response['data']['data']['value']

        except Exception as e:
            logger.error(f"Failed to get secret from Vault: {e}")
            raise

    def set_secret(self, secret_name: str, secret_value: str) -> bool:
        """シークレットを設定"""
        try:
            self.client.secrets.kv.v2.create_or_update_secret(
                path=secret_name,
                secret={'value': secret_value}
            )
            logger.info(f"Set secret in Vault: {secret_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to set secret in Vault: {e}")
            return False

    def delete_secret(self, secret_name: str) -> bool:
        """シークレットを削除"""
        try:
            self.client.secrets.kv.v2.delete_metadata_and_all_versions(
                path=secret_name
            )
            logger.info(f"Deleted secret from Vault: {secret_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete secret from Vault: {e}")
            return False

    def list_secrets(self) -> List[str]:
        """シークレット一覧を取得"""
        try:
            response = self.client.secrets.kv.v2.list_secrets(path='')
            return response['data']['keys']

        except Exception as e:
            logger.error(f"Failed to list secrets from Vault: {e}")
            return []

    def rotate_secret(self, secret_name: str, new_value: str) -> bool:
        """シークレットをローテーション"""
        return self.set_secret(secret_name, new_value)


class EnvironmentSecretManager(SecretManager):
    """環境変数ベースのシークレット管理（開発用フォールバック）"""

    def __init__(self):
        """初期化"""
        logger.warning(
            "Using environment-based secret manager. "
            "NOT recommended for production!"
        )
        self._secrets = {}

    def get_secret(self, secret_name: str) -> str:
        """シークレットを取得"""
        # 環境変数から取得
        value = os.getenv(secret_name)

        if value is None:
            # メモリキャッシュから取得
            value = self._secrets.get(secret_name)

        if value is None:
            raise KeyError(f"Secret not found: {secret_name}")

        return value

    def set_secret(self, secret_name: str, secret_value: str) -> bool:
        """シークレットを設定"""
        os.environ[secret_name] = secret_value
        self._secrets[secret_name] = secret_value
        return True

    def delete_secret(self, secret_name: str) -> bool:
        """シークレットを削除"""
        if secret_name in os.environ:
            del os.environ[secret_name]
        if secret_name in self._secrets:
            del self._secrets[secret_name]
        return True

    def list_secrets(self) -> List[str]:
        """シークレット一覧を取得"""
        # プレフィックスでフィルタリング
        prefix = "COCOA_"
        return [
            key for key in os.environ.keys()
            if key.startswith(prefix)
        ]

    def rotate_secret(self, secret_name: str, new_value: str) -> bool:
        """シークレットをローテーション"""
        return self.set_secret(secret_name, new_value)


class SecretManagerFactory:
    """シークレットマネージャーファクトリー"""

    @staticmethod
    def create(
        provider: SecretProvider = SecretProvider.ENVIRONMENT,
        **kwargs
    ) -> SecretManager:
        """
        シークレットマネージャーを作成

        Args:
            provider: プロバイダー種別
            **kwargs: プロバイダー固有のパラメータ

        Returns:
            SecretManagerインスタンス
        """
        if provider == SecretProvider.AWS_SECRETS_MANAGER:
            region = kwargs.get('region', os.getenv('AWS_REGION', 'us-east-1'))
            return AWSSecretsManager(region=region)

        elif provider == SecretProvider.HASHICORP_VAULT:
            vault_url = kwargs.get(
                'vault_url',
                os.getenv('VAULT_URL', 'http://localhost:8200')
            )
            token = kwargs.get('token', os.getenv('VAULT_TOKEN'))
            return HashiCorpVaultManager(vault_url=vault_url, token=token)

        elif provider == SecretProvider.ENVIRONMENT:
            return EnvironmentSecretManager()

        else:
            raise ValueError(f"Unsupported provider: {provider}")


def get_secret_manager(provider: Optional[str] = None) -> SecretManager:
    """
    環境に応じたシークレットマネージャーを取得

    Args:
        provider: プロバイダー名 ('aws', 'vault', 'env')

    Returns:
        SecretManagerインスタンス
    """
    # 環境変数から自動検出
    if provider is None:
        provider = os.getenv('SECRET_PROVIDER', 'env')

    provider_map = {
        'aws': SecretProvider.AWS_SECRETS_MANAGER,
        'vault': SecretProvider.HASHICORP_VAULT,
        'env': SecretProvider.ENVIRONMENT
    }

    provider_enum = provider_map.get(provider.lower(), SecretProvider.ENVIRONMENT)

    return SecretManagerFactory.create(provider_enum)


def main():
    """テスト実行"""
    print("Enterprise Secret Management System\n")
    print("=" * 70)

    # 環境変数ベース（開発用）
    print("\n1. Environment-based Secret Manager (Development)")
    print("-" * 70)

    manager = get_secret_manager('env')

    # シークレット設定
    manager.set_secret('COCOA_TEST_SECRET', 'my_secret_value_123')
    print("   ✓ Secret set: COCOA_TEST_SECRET")

    # シークレット取得
    value = manager.get_secret('COCOA_TEST_SECRET')
    print(f"   ✓ Secret retrieved: {value}")

    # シークレット一覧
    secrets = manager.list_secrets()
    print(f"   ✓ Secrets found: {len(secrets)}")

    # AWS Secrets Manager (実際のAWS環境が必要)
    print("\n2. AWS Secrets Manager (Production)")
    print("-" * 70)
    print("   Configuration:")
    print("   - Provider: aws")
    print("   - Region: us-east-1 (default)")
    print("   - Required: AWS credentials configured")
    print("\n   Usage:")
    print("     manager = get_secret_manager('aws')")
    print("     value = manager.get_secret('prod/database/password')")

    # HashiCorp Vault (実際のVault環境が必要)
    print("\n3. HashiCorp Vault (Enterprise)")
    print("-" * 70)
    print("   Configuration:")
    print("   - Provider: vault")
    print("   - URL: http://localhost:8200 (default)")
    print("   - Required: VAULT_TOKEN environment variable")
    print("\n   Usage:")
    print("     manager = get_secret_manager('vault')")
    print("     value = manager.get_secret('secret/data/api-key')")

    print("\n" + "=" * 70)
    print("Best Practice:")
    print('  ✓ Use AWS/Vault for production')
    print('  ✓ Never store secrets in .env files')
    print('  ✓ Rotate secrets every 90 days')
    print('  ✓ Use least-privilege access')
    print("=" * 70)


if __name__ == "__main__":
    main()
