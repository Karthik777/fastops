"""Resource config export and Pythonic client wrappers. Turns env dicts into saveable configs and ready-to-use Python clients."""

__all__ = ['ResourceConfig']

import json
from pathlib import Path


class ResourceConfig:
    'A config object holding all resource connection details'
    
    def __init__(self, resources=None):
        self._resources = dict(resources or {})
    
    @classmethod
    def from_env(cls, env_dict):
        'Build config from the merged env dict returned by stack()'
        resources = _detect_resource_groups(env_dict)
        return cls(resources)
    
    @classmethod
    def load(cls, path='resources.json'):
        'Load config from JSON file'
        return cls(json.loads(Path(path).read_text()))
    
    def save(self, path='resources.json'):
        'Save config to JSON file'
        Path(path).write_text(json.dumps(self._resources, indent=2))
        return path
    
    def to_env(self):
        'Flatten back to a dict of env vars (skip keys starting with _)'
        result = {}
        for name, group in self._resources.items():
            for key, value in group.items():
                if not key.startswith('_'):
                    result[key] = value
        return result
    
    def to_dotenv(self, path='.env'):
        'Write a .env file'
        env = self.to_env()
        lines = [f'{key}={value}' for key, value in env.items()]
        Path(path).write_text('\n'.join(lines))
        return path
    
    def connect(self, resource_name):
        'Return a ready-to-use Python client for the named resource'
        if resource_name not in self._resources:
            available = ', '.join(self.names)
            raise ValueError(f'Resource "{resource_name}" not found. Available: {available}')
        
        group = self._resources[resource_name]
        resource_type = group.get('_type')
        
        if resource_type in ('postgres', 'mysql', 'sqlite'):
            return _connect_database(group)
        elif resource_type == 'mongo':
            return _connect_mongo(group)
        elif resource_type == 'redis':
            return _connect_redis(group)
        elif resource_type in ('minio', 's3', 'azure_blob', 'gcs'):
            return _connect_storage(group)
        elif resource_type in ('rabbitmq', 'sqs', 'servicebus', 'pubsub'):
            return _connect_queue(group)
        elif resource_type in ('elasticsearch', 'opensearch', 'azure_search'):
            return _connect_search(group)
        elif resource_type in ('openai', 'azure_openai', 'ollama', 'bedrock'):
            return _connect_llm(group)
        else:
            available = ', '.join(self.names)
            raise ValueError(f'Unknown resource type "{resource_type}". Available resources: {available}')
    
    def __getitem__(self, key):
        return self._resources[key]
    
    def __contains__(self, key):
        return key in self._resources
    
    def __repr__(self):
        parts = [f'{name}({group.get("_type", "unknown")})' for name, group in self._resources.items()]
        return f'ResourceConfig({", ".join(parts)})'
    
    @property
    def names(self):
        return list(self._resources.keys())


def _detect_resource_groups(env_dict):
    'Parse env dict and return {name: {_type, ...env_vars...}}'
    resources = {}
    
    # Database detection
    if 'DATABASE_URL' in env_dict:
        url = env_dict['DATABASE_URL']
        if url.startswith('postgresql'):
            db_type = 'postgres'
        elif url.startswith('mysql'):
            db_type = 'mysql'
        elif url.startswith('mongodb'):
            db_type = 'mongo'
        elif url.startswith('sqlite'):
            db_type = 'sqlite'
        else:
            db_type = 'postgres'  # default
        
        resources['db'] = {
            '_type': db_type,
            'DATABASE_URL': url
        }
        if 'DB_PROVIDER' in env_dict:
            resources['db']['DB_PROVIDER'] = env_dict['DB_PROVIDER']
    
    # Redis cache detection
    if 'REDIS_URL' in env_dict:
        resources['cache'] = {
            '_type': 'redis',
            'REDIS_URL': env_dict['REDIS_URL']
        }
        if 'CACHE_PROVIDER' in env_dict:
            resources['cache']['CACHE_PROVIDER'] = env_dict['CACHE_PROVIDER']
    
    # Queue detection
    if 'QUEUE_URL' in env_dict or 'QUEUE_TOPIC' in env_dict:
        queue_provider = env_dict.get('QUEUE_PROVIDER', 'rabbitmq')
        resources['queue'] = {
            '_type': queue_provider,
        }
        if 'QUEUE_URL' in env_dict:
            resources['queue']['QUEUE_URL'] = env_dict['QUEUE_URL']
        if 'QUEUE_TOPIC' in env_dict:
            resources['queue']['QUEUE_TOPIC'] = env_dict['QUEUE_TOPIC']
        if 'QUEUE_NAME' in env_dict:
            resources['queue']['QUEUE_NAME'] = env_dict['QUEUE_NAME']
        if 'QUEUE_SUBSCRIPTION' in env_dict:
            resources['queue']['QUEUE_SUBSCRIPTION'] = env_dict['QUEUE_SUBSCRIPTION']
    
    # Storage detection
    storage_keys = ['S3_ENDPOINT', 'S3_BUCKET', 'AZURE_STORAGE_CONNECTION_STRING', 'GCS_BUCKET']
    if any(key in env_dict for key in storage_keys):
        provider = env_dict.get('STORAGE_PROVIDER', 'docker')
        storage_type_map = {
            'docker': 'minio',
            'aws': 's3',
            'azure': 'azure_blob',
            'gcp': 'gcs'
        }
        storage_type = storage_type_map.get(provider, 'minio')
        
        resources['storage'] = {'_type': storage_type}
        for key in ['S3_ENDPOINT', 'S3_BUCKET', 'S3_ACCESS_KEY', 'S3_SECRET_KEY',
                    'AZURE_STORAGE_CONNECTION_STRING', 'AZURE_STORAGE_CONTAINER',
                    'GCS_BUCKET', 'S3_REGION', 'STORAGE_PROVIDER']:
            if key in env_dict:
                resources['storage'][key] = env_dict[key]
    
    # LLM detection
    if 'LLM_ENDPOINT' in env_dict or 'LLM_MODEL' in env_dict:
        llm_provider = env_dict.get('LLM_PROVIDER', 'openai')
        resources['llm'] = {'_type': llm_provider}
        for key in ['LLM_ENDPOINT', 'LLM_MODEL', 'LLM_PROVIDER', 'OPENAI_API_KEY',
                    'AZURE_OPENAI_API_KEY', 'AZURE_OPENAI_DEPLOYMENT', 'AWS_REGION']:
            if key in env_dict:
                resources['llm'][key] = env_dict[key]
    
    # Search detection
    if 'SEARCH_URL' in env_dict:
        search_provider = env_dict.get('SEARCH_PROVIDER', 'elasticsearch')
        resources['search'] = {
            '_type': search_provider,
            'SEARCH_URL': env_dict['SEARCH_URL']
        }
        if 'SEARCH_PROVIDER' in env_dict:
            resources['search']['SEARCH_PROVIDER'] = env_dict['SEARCH_PROVIDER']
        if 'SEARCH_API_KEY' in env_dict:
            resources['search']['SEARCH_API_KEY'] = env_dict['SEARCH_API_KEY']
    
    return resources


def _connect_database(group):
    'Connect to SQL database using fastsql or sqlalchemy'
    url = group.get('DATABASE_URL')
    
    try:
        from fastsql import database
        return database(url)
    except ImportError:
        pass
    
    try:
        import sqlalchemy
        return sqlalchemy.create_engine(url).connect()
    except ImportError:
        raise ImportError('Install fastsql (pip install fastsql) or sqlalchemy to connect to databases.')


def _connect_mongo(group):
    'Connect to MongoDB'
    url = group.get('DATABASE_URL')
    
    try:
        from pymongo import MongoClient
        return MongoClient(url)
    except ImportError:
        raise ImportError('Install pymongo (pip install pymongo) to connect to MongoDB.')


def _connect_redis(group):
    'Connect to Redis'
    url = group.get('REDIS_URL')
    
    try:
        import redis
        return redis.Redis.from_url(url)
    except ImportError:
        raise ImportError('Install redis (pip install redis) to connect to Redis.')


def _connect_storage(group):
    'Connect to object storage using fsspec'
    storage_type = group.get('_type')
    
    try:
        import fsspec
    except ImportError:
        raise ImportError('Install fsspec (pip install fsspec s3fs adlfs) to connect to storage.')
    
    if storage_type == 'minio':
        # MinIO with S3 protocol
        endpoint = group.get('S3_ENDPOINT')
        key = group.get('S3_ACCESS_KEY')
        secret = group.get('S3_SECRET_KEY')
        return fsspec.filesystem('s3', key=key, secret=secret, 
                                client_kwargs={'endpoint_url': endpoint})
    elif storage_type == 's3':
        # AWS S3 (uses default credentials)
        return fsspec.filesystem('s3')
    elif storage_type == 'azure_blob':
        # Azure Blob Storage
        connection_string = group.get('AZURE_STORAGE_CONNECTION_STRING')
        return fsspec.filesystem('abfs', connection_string=connection_string)
    elif storage_type == 'gcs':
        # Google Cloud Storage (uses default credentials)
        return fsspec.filesystem('gcs')
    else:
        raise ValueError(f'Unknown storage type: {storage_type}')


def _connect_queue(group):
    'Connect to message queue'
    queue_type = group.get('_type')
    url = group.get('QUEUE_URL')
    
    if queue_type == 'rabbitmq':
        try:
            import pika
            return pika.BlockingConnection(pika.URLParameters(url)).channel()
        except ImportError:
            raise ImportError('Install pika (pip install pika) to connect to RabbitMQ.')
    elif queue_type == 'sqs':
        try:
            import boto3
            return boto3.client('sqs')
        except ImportError:
            raise ImportError('Install boto3 (pip install boto3) to connect to AWS SQS.')
    elif queue_type == 'servicebus':
        try:
            from azure.servicebus import ServiceBusClient
            return ServiceBusClient.from_connection_string(url)
        except ImportError:
            raise ImportError('Install azure-servicebus (pip install azure-servicebus) to connect to Azure Service Bus.')
    elif queue_type == 'pubsub':
        try:
            from google.cloud import pubsub_v1
            return pubsub_v1.PublisherClient()
        except ImportError:
            raise ImportError('Install google-cloud-pubsub (pip install google-cloud-pubsub) to connect to Google Pub/Sub.')
    else:
        raise ValueError(f'Unknown queue type: {queue_type}')


def _connect_search(group):
    'Connect to search engine'
    search_type = group.get('_type')
    url = group.get('SEARCH_URL')
    
    if search_type == 'elasticsearch':
        try:
            from elasticsearch import Elasticsearch
            return Elasticsearch(url)
        except ImportError:
            raise ImportError('Install elasticsearch (pip install elasticsearch) to connect to Elasticsearch.')
    elif search_type == 'opensearch':
        try:
            from opensearchpy import OpenSearch
            return OpenSearch(hosts=[url])
        except ImportError:
            raise ImportError('Install opensearch-py (pip install opensearch-py) to connect to OpenSearch.')
    elif search_type == 'azure_search':
        try:
            from azure.search.documents import SearchClient
            from azure.core.credentials import AzureKeyCredential
            api_key = group.get('SEARCH_API_KEY')
            # Parse endpoint and index name from URL
            # URL format: https://{name}.search.windows.net
            return SearchClient(endpoint=url, index_name='*', credential=AzureKeyCredential(api_key))
        except ImportError:
            raise ImportError('Install azure-search-documents (pip install azure-search-documents) to connect to Azure Search.')
    else:
        raise ValueError(f'Unknown search type: {search_type}')


def _connect_llm(group):
    'Connect to LLM endpoint'
    llm_type = group.get('_type')
    
    # Try lisette first (AnswerDotAI's litellm wrapper)
    if llm_type in ('openai', 'azure_openai', 'ollama'):
        model = group.get('LLM_MODEL', 'gpt-4o')
        
        try:
            from lisette import Chat
            return Chat(model)
        except ImportError:
            pass
        
        # Fallback to raw openai
        try:
            import openai
            
            if llm_type == 'openai':
                api_key = group.get('OPENAI_API_KEY')
                return openai.OpenAI(api_key=api_key)
            elif llm_type == 'azure_openai':
                endpoint = group.get('LLM_ENDPOINT')
                api_key = group.get('AZURE_OPENAI_API_KEY')
                return openai.AzureOpenAI(
                    azure_endpoint=endpoint,
                    api_key=api_key,
                    api_version='2024-02-01'
                )
            elif llm_type == 'ollama':
                endpoint = group.get('LLM_ENDPOINT')
                return openai.OpenAI(base_url=f'{endpoint}/v1', api_key='ollama')
        except ImportError:
            raise ImportError('Install lisette (pip install lisette) or openai (pip install openai) to connect to LLM services.')
    
    elif llm_type == 'bedrock':
        try:
            import boto3
            region = group.get('AWS_REGION', 'us-east-1')
            return boto3.client('bedrock-runtime', region_name=region)
        except ImportError:
            raise ImportError('Install boto3 (pip install boto3) to connect to AWS Bedrock.')
    
    else:
        raise ValueError(f'Unknown LLM type: {llm_type}')
