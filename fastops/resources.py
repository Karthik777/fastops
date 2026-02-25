"""Cloud-agnostic resource provisioning: databases, caches, queues, storage, LLM endpoints, and serverless functions."""

__all__ = ['database', 'cache', 'queue', 'bucket', 'llm', 'function', 'search', 'stack']

import os
import json
import subprocess
from pathlib import Path


def database(name='db', engine='postgres', provider='docker', **kw):
    'Provision a database: postgres, mysql, or mongo'
    password = kw.get('password', os.environ.get('DB_PASSWORD', 'secret'))
    
    if provider == 'docker':
        if engine == 'postgres':
            version = kw.get('version', '16')
            env_dict = {
                'DATABASE_URL': f'postgresql://postgres:{password}@db:5432/{name}',
                'DB_PROVIDER': 'docker'
            }
            svc = {
                'image': f'postgres:{version}',
                'env': {
                    'POSTGRES_PASSWORD': password,
                    'POSTGRES_DB': name
                },
                'ports': {'5432': '5432'},
                'volumes': {'pgdata': '/var/lib/postgresql/data'},
                'restart': 'unless-stopped'
            }
            return (env_dict, svc)
        
        elif engine == 'mysql':
            version = kw.get('version', '8')
            env_dict = {
                'DATABASE_URL': f'mysql://root:{password}@db:3306/{name}',
                'DB_PROVIDER': 'docker'
            }
            svc = {
                'image': f'mysql:{version}',
                'env': {
                    'MYSQL_ROOT_PASSWORD': password,
                    'MYSQL_DATABASE': name
                },
                'ports': {'3306': '3306'},
                'volumes': {'mysqldata': '/var/lib/mysql'},
                'restart': 'unless-stopped'
            }
            return (env_dict, svc)
        
        elif engine == 'mongo':
            version = kw.get('version', '7')
            env_dict = {
                'DATABASE_URL': f'mongodb://admin:{password}@db:27017/{name}?authSource=admin',
                'DB_PROVIDER': 'docker'
            }
            svc = {
                'image': f'mongo:{version}',
                'env': {
                    'MONGO_INITDB_ROOT_USERNAME': 'admin',
                    'MONGO_INITDB_ROOT_PASSWORD': password
                },
                'ports': {'27017': '27017'},
                'volumes': {'mongodata': '/data/db'},
                'restart': 'unless-stopped'
            }
            return (env_dict, svc)
    
    elif provider == 'aws':
        from .aws import callaws
        instance_class = kw.get('instance_class', 'db.t3.micro')
        username = kw.get('username', 'appadmin')
        storage = kw.get('storage', 20)
        
        result = callaws('rds', 'create-db-instance',
                        '--db-instance-identifier', name,
                        '--engine', engine,
                        '--db-instance-class', instance_class,
                        '--master-username', username,
                        '--master-user-password', password,
                        '--allocated-storage', str(storage),
                        '--no-publicly-accessible',
                        '--storage-encrypted')
        
        endpoint = result['DBInstance']['Endpoint']['Address']
        port = result['DBInstance']['Endpoint']['Port']
        
        env_dict = {
            'DATABASE_URL': f'postgresql://{username}:{password}@{endpoint}:{port}/{name}',
            'DB_PROVIDER': 'rds'
        }
        return (env_dict, None)
    
    elif provider == 'azure':
        from .azure import callaz
        rg = kw.get('resource_group')
        sku = kw.get('sku', 'Standard_B1ms')
        version = kw.get('version', '16')
        storage_size = kw.get('storage_size', 32)
        admin_user = kw.get('admin_user', 'appadmin')
        
        result = callaz('postgres', 'flexible-server', 'create',
                       '--name', name,
                       '--resource-group', rg,
                       '--sku-name', sku,
                       '--version', str(version),
                       '--storage-size', str(storage_size),
                       '--admin-user', admin_user,
                       '--admin-password', password,
                       '--public-access', 'None')
        
        host = result.get('fullyQualifiedDomainName', f'{name}.postgres.database.azure.com')
        env_dict = {
            'DATABASE_URL': f'postgresql://{admin_user}:{password}@{host}:5432/{name}',
            'DB_PROVIDER': 'azure_postgres'
        }
        return (env_dict, None)
    
    return ({}, None)


def cache(name='redis', provider='docker', **kw):
    'Provision a Redis cache'
    if provider == 'docker':
        password = kw.get('password', '')
        env_dict = {
            'REDIS_URL': 'redis://redis:6379',
            'CACHE_PROVIDER': 'redis'
        }
        svc = {
            'image': 'redis:7-alpine',
            'command': 'redis-server --appendonly yes',
            'ports': {'6379': '6379'},
            'volumes': {'redis-data': '/data'},
            'restart': 'unless-stopped'
        }
        return (env_dict, svc)
    
    elif provider == 'aws':
        from .aws import callaws
        node_type = kw.get('node_type', 'cache.t3.micro')
        
        result = callaws('elasticache', 'create-cache-cluster',
                        '--cache-cluster-id', name,
                        '--cache-node-type', node_type,
                        '--engine', 'redis',
                        '--num-cache-nodes', '1')
        
        endpoint = result['CacheCluster']['CacheNodes'][0]['Endpoint']['Address']
        port = result['CacheCluster']['CacheNodes'][0]['Endpoint']['Port']
        
        env_dict = {
            'REDIS_URL': f'redis://{endpoint}:{port}',
            'CACHE_PROVIDER': 'elasticache'
        }
        return (env_dict, None)
    
    elif provider == 'azure':
        from .azure import callaz
        rg = kw.get('resource_group')
        sku = kw.get('sku', 'Basic')
        vm_size = kw.get('vm_size', 'C0')
        
        result = callaz('redis', 'create',
                       '--name', name,
                       '--resource-group', rg,
                       '--sku', sku,
                       '--vm-size', vm_size)
        
        host = result.get('hostName', f'{name}.redis.cache.windows.net')
        
        # Get access key
        keys = callaz('redis', 'list-keys',
                     '--name', name,
                     '--resource-group', rg)
        key = keys.get('primaryKey', '')
        
        env_dict = {
            'REDIS_URL': f'rediss://:{key}@{host}:6380',
            'CACHE_PROVIDER': 'azure_redis'
        }
        return (env_dict, None)
    
    return ({}, None)


def queue(name='tasks', provider='docker', **kw):
    'Provision a message queue'
    if provider == 'docker':
        password = kw.get('password', 'guest')
        env_dict = {
            'QUEUE_URL': f'amqp://guest:{password}@rabbitmq:5672/',
            'QUEUE_NAME': name
        }
        svc = {
            'image': 'rabbitmq:3-management',
            'env': {
                'RABBITMQ_DEFAULT_USER': 'guest',
                'RABBITMQ_DEFAULT_PASS': password
            },
            'ports': {'5672': '5672', '15672': '15672'},
            'volumes': {'rabbitmq-data': '/var/lib/rabbitmq'},
            'restart': 'unless-stopped'
        }
        return (env_dict, svc)
    
    elif provider == 'aws':
        from .aws import callaws
        
        result = callaws('sqs', 'create-queue',
                        '--queue-name', name,
                        '--attributes', json.dumps({
                            'VisibilityTimeout': '30',
                            'MessageRetentionPeriod': '345600'
                        }))
        
        env_dict = {
            'QUEUE_URL': result['QueueUrl'],
            'QUEUE_NAME': name,
            'QUEUE_PROVIDER': 'sqs'
        }
        return (env_dict, None)
    
    elif provider == 'azure':
        from .azure import callaz
        rg = kw.get('resource_group')
        namespace = kw.get('namespace', f'{name}-ns')
        
        # Create namespace
        callaz('servicebus', 'namespace', 'create',
              '--name', namespace,
              '--resource-group', rg)
        
        # Create queue
        callaz('servicebus', 'queue', 'create',
              '--name', name,
              '--namespace-name', namespace,
              '--resource-group', rg)
        
        # Get connection string
        keys = callaz('servicebus', 'namespace', 'authorization-rule', 'keys', 'list',
                     '--name', 'RootManageSharedAccessKey',
                     '--namespace-name', namespace,
                     '--resource-group', rg)
        
        env_dict = {
            'QUEUE_URL': keys.get('primaryConnectionString', ''),
            'QUEUE_NAME': name,
            'QUEUE_PROVIDER': 'servicebus'
        }
        return (env_dict, None)
    
    elif provider == 'gcp':
        # Create topic
        subprocess.run(['gcloud', 'pubsub', 'topics', 'create', name],
                      capture_output=True, text=True, check=True)
        
        # Create subscription
        sub_name = f'{name}-sub'
        subprocess.run(['gcloud', 'pubsub', 'subscriptions', 'create', sub_name,
                       '--topic', name],
                      capture_output=True, text=True, check=True)
        
        env_dict = {
            'QUEUE_TOPIC': name,
            'QUEUE_SUBSCRIPTION': sub_name,
            'QUEUE_PROVIDER': 'pubsub'
        }
        return (env_dict, None)
    
    return ({}, None)


def bucket(name, provider='docker', **kw):
    'Provision object storage'
    if provider == 'docker':
        access_key = kw.get('access_key', 'minioadmin')
        secret_key = kw.get('secret_key', 'minioadmin')
        
        env_dict = {
            'S3_ENDPOINT': 'http://minio:9000',
            'S3_BUCKET': name,
            'S3_ACCESS_KEY': access_key,
            'S3_SECRET_KEY': secret_key
        }
        svc = {
            'image': 'minio/minio:latest',
            'command': 'server /data --console-address ":9001"',
            'env': {
                'MINIO_ROOT_USER': access_key,
                'MINIO_ROOT_PASSWORD': secret_key
            },
            'ports': {'9000': '9000', '9001': '9001'},
            'volumes': {'minio-data': '/data'},
            'restart': 'unless-stopped'
        }
        return (env_dict, svc)
    
    elif provider == 'aws':
        from .aws import callaws
        region = kw.get('region', 'us-east-1')
        
        # Create bucket
        if region == 'us-east-1':
            callaws('s3api', 'create-bucket', '--bucket', name)
        else:
            callaws('s3api', 'create-bucket', '--bucket', name,
                   '--create-bucket-configuration', f'LocationConstraint={region}')
        
        # Enable encryption
        callaws('s3api', 'put-bucket-encryption',
               '--bucket', name,
               '--server-side-encryption-configuration', json.dumps({
                   'Rules': [{
                       'ApplyServerSideEncryptionByDefault': {
                           'SSEAlgorithm': 'AES256'
                       }
                   }]
               }))
        
        # Block public access
        callaws('s3api', 'put-public-access-block',
               '--bucket', name,
               '--public-access-block-configuration',
               'BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true')
        
        env_dict = {
            'S3_BUCKET': name,
            'S3_REGION': region,
            'STORAGE_PROVIDER': 'aws'
        }
        return (env_dict, None)
    
    elif provider == 'azure':
        from .azure import callaz
        rg = kw.get('resource_group')
        account_name = kw.get('account_name', name.replace('-', '').replace('_', '')[:24])
        
        # Create storage account
        callaz('storage', 'account', 'create',
              '--name', account_name,
              '--resource-group', rg,
              '--encryption-services', 'blob',
              '--min-tls-version', 'TLS1_2')
        
        # Create container
        callaz('storage', 'container', 'create',
              '--name', name,
              '--account-name', account_name)
        
        # Get connection string
        keys = callaz('storage', 'account', 'show-connection-string',
                     '--name', account_name,
                     '--resource-group', rg)
        
        env_dict = {
            'AZURE_STORAGE_CONNECTION_STRING': keys.get('connectionString', ''),
            'AZURE_STORAGE_CONTAINER': name,
            'STORAGE_PROVIDER': 'azure'
        }
        return (env_dict, None)
    
    elif provider == 'gcp':
        location = kw.get('location', 'us')
        
        # Create bucket
        subprocess.run(['gcloud', 'storage', 'buckets', 'create',
                       f'gs://{name}',
                       '--location', location,
                       '--uniform-bucket-level-access'],
                      capture_output=True, text=True, check=True)
        
        env_dict = {
            'GCS_BUCKET': name,
            'STORAGE_PROVIDER': 'gcp'
        }
        return (env_dict, None)
    
    return ({}, None)


def llm(name='gpt-4o', provider='openai', **kw):
    'Provision LLM endpoint'
    if provider == 'docker':
        env_dict = {
            'LLM_ENDPOINT': 'http://ollama:11434',
            'LLM_MODEL': name,
            'LLM_PROVIDER': 'ollama'
        }
        svc = {
            'image': 'ollama/ollama:latest',
            'ports': {'11434': '11434'},
            'volumes': {'ollama-data': '/root/.ollama'},
            'restart': 'unless-stopped'
        }
        
        if kw.get('gpu'):
            svc['deploy'] = {
                'resources': {
                    'reservations': {
                        'devices': [{
                            'driver': 'nvidia',
                            'count': 1,
                            'capabilities': ['gpu']
                        }]
                    }
                }
            }
        
        return (env_dict, svc)
    
    elif provider == 'openai':
        api_key = os.environ.get('OPENAI_API_KEY', '${OPENAI_API_KEY}')
        env_dict = {
            'LLM_ENDPOINT': 'https://api.openai.com/v1',
            'LLM_MODEL': name,
            'LLM_PROVIDER': 'openai',
            'OPENAI_API_KEY': api_key
        }
        return (env_dict, None)
    
    elif provider == 'azure':
        from .azure import callaz
        rg = kw.get('resource_group')
        location = kw.get('location', 'eastus')
        
        # Create Azure OpenAI resource
        callaz('cognitiveservices', 'account', 'create',
              '--name', name,
              '--resource-group', rg,
              '--kind', 'OpenAI',
              '--sku', 'S0',
              '--location', location)
        
        # Deploy model
        deployment_name = kw.get('deployment', f'{name}-deployment')
        model_name = kw.get('model_name', 'gpt-4')
        callaz('cognitiveservices', 'account', 'deployment', 'create',
              '--name', name,
              '--resource-group', rg,
              '--deployment-name', deployment_name,
              '--model-name', model_name,
              '--model-version', kw.get('model_version', '0613'),
              '--model-format', 'OpenAI',
              '--sku-capacity', str(kw.get('capacity', 1)),
              '--sku-name', 'Standard')
        
        # Get endpoint and key
        account = callaz('cognitiveservices', 'account', 'show',
                        '--name', name,
                        '--resource-group', rg)
        endpoint = account.get('properties', {}).get('endpoint', '')
        
        keys = callaz('cognitiveservices', 'account', 'keys', 'list',
                     '--name', name,
                     '--resource-group', rg)
        
        env_dict = {
            'LLM_ENDPOINT': endpoint,
            'LLM_MODEL': model_name,
            'LLM_PROVIDER': 'azure_openai',
            'AZURE_OPENAI_API_KEY': keys.get('key1', ''),
            'AZURE_OPENAI_DEPLOYMENT': deployment_name
        }
        return (env_dict, None)
    
    elif provider == 'aws':
        model_id = kw.get('model_id', f'anthropic.{name}')
        region = kw.get('region', 'us-east-1')
        
        env_dict = {
            'LLM_MODEL': model_id,
            'LLM_PROVIDER': 'bedrock',
            'AWS_REGION': region
        }
        return (env_dict, None)
    
    return ({}, None)


def function(name, runtime='python3.12', handler='main.handler', provider='aws', **kw):
    'Provision serverless function'
    if provider == 'aws':
        from .aws import callaws
        role = kw.get('role') or os.environ.get('LAMBDA_ROLE_ARN')
        zip_path = kw.get('zip_path', 'function.zip')
        timeout = kw.get('timeout', 30)
        memory = kw.get('memory', 256)
        
        result = callaws('lambda', 'create-function',
                        '--function-name', name,
                        '--runtime', runtime,
                        '--handler', handler,
                        '--role', role,
                        '--zip-file', f'fileb://{zip_path}',
                        '--timeout', str(timeout),
                        '--memory-size', str(memory))
        
        env_dict = {
            'FUNCTION_ARN': result['FunctionArn'],
            'FUNCTION_NAME': name,
            'FUNCTION_PROVIDER': 'lambda'
        }
        return (env_dict, None)
    
    elif provider == 'azure':
        from .azure import callaz
        rg = kw.get('resource_group')
        location = kw.get('location', 'eastus')
        storage_account = kw.get('storage_account', f'{name}storage')
        
        # Create storage account
        callaz('storage', 'account', 'create',
              '--name', storage_account,
              '--resource-group', rg,
              '--location', location)
        
        # Create function app
        callaz('functionapp', 'create',
              '--name', name,
              '--resource-group', rg,
              '--consumption-plan-location', location,
              '--runtime', 'python',
              '--runtime-version', runtime.replace('python', ''),
              '--storage-account', storage_account,
              '--os-type', 'Linux')
        
        env_dict = {
            'FUNCTION_URL': f'https://{name}.azurewebsites.net',
            'FUNCTION_NAME': name,
            'FUNCTION_PROVIDER': 'azure_functions'
        }
        return (env_dict, None)
    
    elif provider == 'gcp':
        region = kw.get('region', 'us-central1')
        entry_point = kw.get('entry_point', handler.split('.')[-1])
        
        result = subprocess.run(['gcloud', 'functions', 'deploy', name,
                                '--runtime', runtime,
                                '--trigger-http',
                                '--allow-unauthenticated',
                                '--entry-point', entry_point,
                                '--region', region],
                               capture_output=True, text=True, check=True)
        
        # Parse output for URL
        output = result.stdout
        url = ''
        for line in output.split('\n'):
            if 'url:' in line.lower():
                url = line.split(':', 1)[1].strip()
        
        env_dict = {
            'FUNCTION_URL': url,
            'FUNCTION_NAME': name,
            'FUNCTION_PROVIDER': 'gcp_functions'
        }
        return (env_dict, None)
    
    return ({}, None)


def search(name='search', provider='docker', **kw):
    'Provision search engine'
    if provider == 'docker':
        env_dict = {
            'SEARCH_URL': 'http://elasticsearch:9200',
            'SEARCH_PROVIDER': 'elasticsearch'
        }
        svc = {
            'image': 'elasticsearch:8.12.0',
            'env': {
                'discovery.type': 'single-node',
                'xpack.security.enabled': 'false',
                'ES_JAVA_OPTS': '-Xms512m -Xmx512m'
            },
            'ports': {'9200': '9200'},
            'volumes': {'es-data': '/usr/share/elasticsearch/data'},
            'restart': 'unless-stopped'
        }
        return (env_dict, svc)
    
    elif provider == 'aws':
        from .aws import callaws
        instance_type = kw.get('instance_type', 't3.small.search')
        volume_size = kw.get('volume_size', 20)
        
        result = callaws('opensearch', 'create-domain',
                        '--domain-name', name,
                        '--engine-version', 'OpenSearch_2.11',
                        '--cluster-config', json.dumps({
                            'InstanceType': instance_type,
                            'InstanceCount': 1
                        }),
                        '--ebs-options', json.dumps({
                            'EBSEnabled': True,
                            'VolumeType': 'gp3',
                            'VolumeSize': volume_size
                        }))
        
        endpoint = result['DomainStatus']['Endpoint']
        
        env_dict = {
            'SEARCH_URL': f'https://{endpoint}',
            'SEARCH_PROVIDER': 'opensearch'
        }
        return (env_dict, None)
    
    elif provider == 'azure':
        from .azure import callaz
        rg = kw.get('resource_group')
        sku = kw.get('sku', 'basic')
        
        # Create search service
        callaz('search', 'service', 'create',
              '--name', name,
              '--resource-group', rg,
              '--sku', sku)
        
        # Get admin key
        keys = callaz('search', 'admin-key', 'show',
                     '--service-name', name,
                     '--resource-group', rg)
        
        env_dict = {
            'SEARCH_URL': f'https://{name}.search.windows.net',
            'SEARCH_API_KEY': keys.get('primaryKey', ''),
            'SEARCH_PROVIDER': 'azure_search'
        }
        return (env_dict, None)
    
    return ({}, None)


def stack(resources, provider='docker'):
    'Compose multiple resources into a unified stack'
    from .compose import Compose
    
    merged_env = {}
    dc = Compose()
    volumes = []
    
    for name, resource_fn in resources.items():
        env, svc = resource_fn()
        merged_env.update(env)
        
        if svc is not None:
            dc = dc.svc(name, **svc)
            
            # Collect volume names
            if 'volumes' in svc and isinstance(svc['volumes'], dict):
                for vol_key in svc['volumes'].keys():
                    # Skip bind mounts (paths starting with . or /)
                    if not str(vol_key).startswith('.') and not str(vol_key).startswith('/'):
                        volumes.append(vol_key)
    
    # Add unique volumes to Compose
    for vol in set(volumes):
        dc = dc.volume(vol)
    
    return (merged_env, dc, list(set(volumes)))
