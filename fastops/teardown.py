"""Resource teardown and lifecycle management. Safely destroy provisioned resources."""

__all__ = ['destroy', 'destroy_stack', 'status', 'teardown_gcp', 'destroy_cloud_run', 'destroy_cloud_sql', 'destroy_memorystore']

import os
import json
import subprocess
import shutil


def _docker_noop():
    'Docker resources managed by compose'
    return {'destroyed': True, 'message': 'Remove via docker compose down -v'}

def _not_found(msg):
    'Resource not found response'
    return {'destroyed': False, 'message': msg}

def _success(msg):
    'Successful deletion response'
    return {'destroyed': True, 'message': msg}


def destroy(resource_type, name, provider='docker', **kw):
    'Destroy a single provisioned resource'
    dispatchers = {
        'database': _destroy_database, 'cache': _destroy_cache, 'queue': _destroy_queue,
        'bucket': _destroy_bucket, 'llm': _destroy_llm, 'search': _destroy_search,
        'function': _destroy_function
    }
    if resource_type not in dispatchers:
        return {'destroyed': False, 'resource': name, 'provider': provider, 
                'message': f'Unknown resource type: {resource_type}'}
    result = dispatchers[resource_type](name, provider, **kw)
    result.setdefault('resource', name)
    result.setdefault('provider', provider)
    return result


def _destroy_database(name, provider, **kw):
    'Destroy a database instance'
    if provider == 'docker': return _docker_noop()
    elif provider == 'aws':
        from .aws import callaws
        try:
            callaws('rds', 'delete-db-instance', '--db-instance-identifier', name,
                   '--skip-final-snapshot', '--delete-automated-backups')
        except Exception as e:
            if 'DBInstanceNotFound' in str(e): return _not_found(f'RDS instance {name} not found')
            raise
        return _success(f'RDS instance {name} deletion initiated')
    elif provider == 'azure':
        from .azure import callaz
        rg = kw.get('resource_group')
        try:
            callaz('postgres', 'flexible-server', 'delete', '--name', name,
                  '--resource-group', rg, '--yes')
        except Exception as e:
            if 'ResourceNotFound' in str(e): return _not_found(f'Azure DB {name} not found')
            raise
        return _success(f'Azure Postgres {name} deleted')
    return _not_found(f'Unsupported provider: {provider}')


def _destroy_cache(name, provider, **kw):
    'Destroy a cache instance'
    if provider == 'docker': return _docker_noop()
    elif provider == 'aws':
        from .aws import callaws
        try:
            callaws('elasticache', 'delete-cache-cluster', '--cache-cluster-id', name)
        except Exception as e:
            if 'CacheClusterNotFound' in str(e): return _not_found(f'ElastiCache cluster {name} not found')
            raise
        return _success(f'ElastiCache cluster {name} deletion initiated')
    elif provider == 'azure':
        from .azure import callaz
        rg = kw.get('resource_group')
        try:
            callaz('redis', 'delete', '--name', name, '--resource-group', rg, '--yes')
        except Exception as e:
            if 'ResourceNotFound' in str(e): return _not_found(f'Azure Redis {name} not found')
            raise
        return _success(f'Azure Redis {name} deleted')
    return _not_found(f'Unsupported provider: {provider}')


def _destroy_queue(name, provider, **kw):
    'Destroy a message queue'
    if provider == 'docker': return _docker_noop()
    elif provider == 'aws':
        from .aws import callaws
        try:
            result = callaws('sqs', 'get-queue-url', '--queue-name', name)
            callaws('sqs', 'delete-queue', '--queue-url', result['QueueUrl'])
        except Exception as e:
            if 'NonExistentQueue' in str(e) or 'QueueDoesNotExist' in str(e):
                return _not_found(f'SQS queue {name} not found')
            raise
        return _success(f'SQS queue {name} deleted')
    elif provider == 'azure':
        from .azure import callaz
        rg = kw.get('resource_group')
        namespace = kw.get('namespace', f'{name}-ns')
        try:
            callaz('servicebus', 'namespace', 'delete', '--name', namespace,
                  '--resource-group', rg, '--yes')
        except Exception as e:
            if 'ResourceNotFound' in str(e): return _not_found(f'Azure ServiceBus namespace {namespace} not found')
            raise
        return _success(f'Azure ServiceBus namespace {namespace} deleted')
    elif provider == 'gcp':
        try:
            sub_name = f'{name}-sub'
            subprocess.run(['gcloud', 'pubsub', 'subscriptions', 'delete', sub_name, '--quiet'],
                          capture_output=True, text=True, check=True)
            subprocess.run(['gcloud', 'pubsub', 'topics', 'delete', name, '--quiet'],
                          capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            if 'NOT_FOUND' in e.stderr or 'does not exist' in e.stderr.lower():
                return _not_found(f'GCP Pub/Sub topic {name} not found')
            raise
        return _success(f'GCP Pub/Sub topic {name} deleted')
    return _not_found(f'Unsupported provider: {provider}')


def _destroy_bucket(name, provider, **kw):
    'Destroy object storage bucket'
    if provider == 'docker': return _docker_noop()
    elif provider == 'aws':
        from .aws import callaws
        try:
            callaws('s3', 'rm', f's3://{name}', '--recursive')
            callaws('s3api', 'delete-bucket', '--bucket', name)
        except Exception as e:
            if 'NoSuchBucket' in str(e): return _not_found(f'S3 bucket {name} not found')
            raise
        return _success(f'S3 bucket {name} deleted')
    elif provider == 'azure':
        from .azure import callaz
        rg = kw.get('resource_group')
        account_name = kw.get('account_name', name.replace('-', '').replace('_', '')[:24])
        try:
            callaz('storage', 'container', 'delete', '--name', name,
                  '--account-name', account_name, '--yes')
            callaz('storage', 'account', 'delete', '--name', account_name,
                  '--resource-group', rg, '--yes')
        except Exception as e:
            if 'ResourceNotFound' in str(e) or 'NotFound' in str(e):
                return _not_found(f'Azure storage {name} not found')
            raise
        return _success(f'Azure storage account {account_name} deleted')
    elif provider == 'gcp':
        try:
            subprocess.run(['gcloud', 'storage', 'rm', '-r', f'gs://{name}', '--quiet'],
                          capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            if 'NOT_FOUND' in e.stderr or 'does not exist' in e.stderr.lower():
                return _not_found(f'GCS bucket {name} not found')
            raise
        return _success(f'GCS bucket {name} deleted')
    return _not_found(f'Unsupported provider: {provider}')


def _destroy_llm(name, provider, **kw):
    'Destroy LLM endpoint'
    if provider == 'docker': return _docker_noop()
    elif provider == 'openai': return _success('No teardown needed for OpenAI')
    elif provider == 'azure':
        from .azure import callaz
        rg = kw.get('resource_group')
        deployment_name = kw.get('deployment', f'{name}-deployment')
        try:
            callaz('cognitiveservices', 'account', 'deployment', 'delete',
                  '--name', name, '--resource-group', rg, '--deployment-name', deployment_name)
            callaz('cognitiveservices', 'account', 'delete',
                  '--name', name, '--resource-group', rg)
        except Exception as e:
            if 'ResourceNotFound' in str(e): return _not_found(f'Azure OpenAI {name} not found')
            raise
        return _success(f'Azure OpenAI account {name} deleted')
    elif provider == 'aws': return _success('No teardown needed for Bedrock')
    return _not_found(f'Unsupported provider: {provider}')


def _destroy_search(name, provider, **kw):
    'Destroy search engine'
    if provider == 'docker': return _docker_noop()
    elif provider == 'aws':
        from .aws import callaws
        try:
            callaws('opensearch', 'delete-domain', '--domain-name', name)
        except Exception as e:
            if 'ResourceNotFoundException' in str(e): return _not_found(f'OpenSearch domain {name} not found')
            raise
        return _success(f'OpenSearch domain {name} deletion initiated')
    elif provider == 'azure':
        from .azure import callaz
        rg = kw.get('resource_group')
        try:
            callaz('search', 'service', 'delete', '--name', name, '--resource-group', rg, '--yes')
        except Exception as e:
            if 'ResourceNotFound' in str(e): return _not_found(f'Azure Search {name} not found')
            raise
        return _success(f'Azure Search {name} deleted')
    return _not_found(f'Unsupported provider: {provider}')


def _destroy_function(name, provider, **kw):
    'Destroy serverless function'
    if provider == 'aws':
        from .aws import callaws
        try:
            callaws('lambda', 'delete-function', '--function-name', name)
        except Exception as e:
            if 'ResourceNotFoundException' in str(e): return _not_found(f'Lambda function {name} not found')
            raise
        return _success(f'Lambda function {name} deleted')
    elif provider == 'azure':
        from .azure import callaz
        rg = kw.get('resource_group')
        try:
            callaz('functionapp', 'delete', '--name', name, '--resource-group', rg, '--yes')
        except Exception as e:
            if 'ResourceNotFound' in str(e): return _not_found(f'Azure Function {name} not found')
            raise
        return _success(f'Azure Function {name} deleted')
    elif provider == 'gcp':
        region = kw.get('region', 'us-central1')
        try:
            subprocess.run(['gcloud', 'functions', 'delete', name, '--quiet', '--region', region],
                          capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            if 'NOT_FOUND' in e.stderr or 'does not exist' in e.stderr.lower():
                return _not_found(f'GCP function {name} not found')
            raise
        return _success(f'GCP function {name} deleted')
    return _not_found(f'Unsupported provider: {provider}')


def _infer_resource_type(env_dict):
    'Infer resource type from environment variables'
    if 'DATABASE_URL' in env_dict:
        return 'database'
    elif 'REDIS_URL' in env_dict:
        return 'cache'
    elif 'QUEUE_URL' in env_dict or 'QUEUE_TOPIC' in env_dict:
        return 'queue'
    elif any(k in env_dict for k in ['S3_ENDPOINT', 'S3_BUCKET', 'AZURE_STORAGE_CONNECTION_STRING', 'GCS_BUCKET']):
        return 'bucket'
    elif 'LLM_ENDPOINT' in env_dict or 'LLM_MODEL' in env_dict:
        return 'llm'
    elif 'SEARCH_URL' in env_dict:
        return 'search'
    elif 'FUNCTION_ARN' in env_dict or 'FUNCTION_URL' in env_dict:
        return 'function'
    else:
        return 'unknown'


def destroy_stack(resources, provider='docker', **kw):
    'Tear down all resources in a stack (reverse order for dependency safety)'
    results = {}
    # Reverse to tear down dependents before dependencies
    for name in reversed(list(resources.keys())):
        resource_fn = resources[name]
        # Infer resource type from the function name or env output
        env, _ = resource_fn()
        rtype = _infer_resource_type(env)
        results[name] = destroy(rtype, name, provider, **kw)
    return results


def status(resource_type, name, provider='docker', **kw):
    'Quick health check for a provisioned resource'
    if provider == 'docker':
        # Check if container is running
        result = subprocess.run(['docker', 'inspect', '--format', '{{.State.Status}}', name],
                              capture_output=True, text=True)
        running = result.returncode == 0 and 'running' in result.stdout
        return {'healthy': running, 'provider': 'docker', 'name': name}
    
    elif provider == 'aws':
        from .aws import callaws
        try:
            if resource_type == 'database':
                result = callaws('rds', 'describe-db-instances',
                               '--db-instance-identifier', name)
                status_val = result['DBInstances'][0]['DBInstanceStatus']
                return {'healthy': status_val == 'available', 'provider': 'aws',
                       'name': name, 'status': status_val}
            
            elif resource_type == 'cache':
                result = callaws('elasticache', 'describe-cache-clusters',
                               '--cache-cluster-id', name)
                status_val = result['CacheClusters'][0]['CacheClusterStatus']
                return {'healthy': status_val == 'available', 'provider': 'aws',
                       'name': name, 'status': status_val}
            
            elif resource_type == 'bucket':
                # Try to list bucket (will fail if not exists)
                callaws('s3api', 'head-bucket', '--bucket', name)
                return {'healthy': True, 'provider': 'aws', 'name': name}
            
            elif resource_type == 'search':
                result = callaws('opensearch', 'describe-domain', '--domain-name', name)
                status_val = result['DomainStatus']['Processing']
                return {'healthy': not status_val, 'provider': 'aws',
                       'name': name, 'processing': status_val}
            
            elif resource_type == 'function':
                result = callaws('lambda', 'get-function', '--function-name', name)
                state = result['Configuration']['State']
                return {'healthy': state == 'Active', 'provider': 'aws',
                       'name': name, 'state': state}
        
        except Exception as e:
            return {'healthy': False, 'provider': 'aws', 'name': name,
                   'message': f'Resource not found or error: {str(e)}'}
    
    elif provider == 'azure':
        from .azure import callaz
        rg = kw.get('resource_group')
        try:
            if resource_type == 'database':
                result = callaz('postgres', 'flexible-server', 'show',
                              '--name', name,
                              '--resource-group', rg)
                state = result.get('state', '')
                return {'healthy': state == 'Ready', 'provider': 'azure',
                       'name': name, 'state': state}
            
            elif resource_type == 'cache':
                result = callaz('redis', 'show',
                              '--name', name,
                              '--resource-group', rg)
                status_val = result.get('provisioningState', '')
                return {'healthy': status_val == 'Succeeded', 'provider': 'azure',
                       'name': name, 'status': status_val}
            
            elif resource_type == 'search':
                result = callaz('search', 'service', 'show',
                              '--name', name,
                              '--resource-group', rg)
                status_val = result.get('provisioningState', '')
                return {'healthy': status_val == 'Succeeded', 'provider': 'azure',
                       'name': name, 'status': status_val}
            
            elif resource_type == 'function':
                result = callaz('functionapp', 'show',
                              '--name', name,
                              '--resource-group', rg)
                state = result.get('state', '')
                return {'healthy': state == 'Running', 'provider': 'azure',
                       'name': name, 'state': state}
        
        except Exception as e:
            return {'healthy': False, 'provider': 'azure', 'name': name,
                   'message': f'Resource not found or error: {str(e)}'}
    
    return {'healthy': False, 'provider': provider, 'name': name,
           'message': 'Unsupported provider or resource type'}


# GCP-specific teardown functions

def destroy_cloud_run(name, region, project=None):
    'Delete a Cloud Run service'
    from .gcp import callgcloud
    proj_args = ['--project', project] if project else []
    try:
        callgcloud('run', 'services', 'delete', name, 
                   '--region', region, '--quiet', *proj_args)
        print(f'Deleted Cloud Run service: {name}')
    except RuntimeError as e:
        print(f'Error deleting Cloud Run service: {e}')

def destroy_cloud_sql(name, project=None):
    'Delete a Cloud SQL instance'
    from .gcp import callgcloud
    proj_args = ['--project', project] if project else []
    try:
        callgcloud('sql', 'instances', 'delete', name, 
                   '--quiet', *proj_args)
        print(f'Deleted Cloud SQL instance: {name}')
    except RuntimeError as e:
        print(f'Error deleting Cloud SQL instance: {e}')

def destroy_memorystore(name, region, project=None):
    'Delete a Memorystore (Redis) instance'
    from .gcp import callgcloud
    proj_args = ['--project', project] if project else []
    try:
        callgcloud('redis', 'instances', 'delete', name, 
                   '--region', region, '--quiet', *proj_args)
        print(f'Deleted Memorystore instance: {name}')
    except RuntimeError as e:
        print(f'Error deleting Memorystore instance: {e}')

def teardown_gcp(name, region='us-central1', project=None, postgres=False, redis=False):
    'Tear down all GCP resources for an application'
    print(f'Tearing down GCP resources for {name}...')
    
    # Delete Cloud Run service
    destroy_cloud_run(name, region, project)
    
    # Delete Cloud SQL if it was created
    if postgres:
        destroy_cloud_sql(f'{name}-db', project)
    
    # Delete Memorystore if it was created
    if redis:
        destroy_memorystore(f'{name}-redis', region, project)
    
    print(f'Teardown complete for {name}')
