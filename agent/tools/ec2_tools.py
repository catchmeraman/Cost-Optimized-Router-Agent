"""EC2 tools."""
import boto3
from strands import tool

@tool
def describe_instances(status_filter: str = "all") -> dict:
    """List EC2 instances."""
    ec2 = boto3.client('ec2')
    filters = [] if status_filter == "all" else [{"Name": "instance-state-name", "Values": [status_filter]}]
    response = ec2.describe_instances(Filters=filters)
    instances = [{"id": i['InstanceId'], "name": next((t['Value'] for t in i.get('Tags', []) if t['Key'] == 'Name'), 'unnamed'), "state": i['State']['Name'], "type": i['InstanceType']} for res in response['Reservations'] for i in res['Instances']]
    return {"instances": instances, "count": len(instances)}

@tool
def manage_instance(instance_id: str, action: str) -> dict:
    """Start, stop, or reboot EC2 instance."""
    ec2 = boto3.client('ec2')
    if action == "start": ec2.start_instances(InstanceIds=[instance_id])
    elif action == "stop": ec2.stop_instances(InstanceIds=[instance_id])
    elif action == "reboot": ec2.reboot_instances(InstanceIds=[instance_id])
    return {"instance_id": instance_id, "action": action, "status": "initiated"}
