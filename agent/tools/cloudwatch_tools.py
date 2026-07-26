"""CloudWatch tools."""
import boto3
from strands import tool
from datetime import datetime, timedelta

@tool
def get_alarms(state: str = "ALARM") -> dict:
    """Get CloudWatch alarms by state."""
    cw = boto3.client('cloudwatch')
    if state == "ALL":
        response = cw.describe_alarms()
    else:
        response = cw.describe_alarms(StateValue=state)
    alarms = [{"name": a['AlarmName'], "metric": a['MetricName'], "state": a['StateValue']} for a in response.get('MetricAlarms', [])]
    return {"alarms": alarms, "count": len(alarms)}

@tool
def get_metric_statistics(namespace: str, metric_name: str, dimension_name: str, dimension_value: str, minutes: int = 30) -> dict:
    """Get metric statistics."""
    cw = boto3.client('cloudwatch')
    response = cw.get_metric_statistics(
        Namespace=namespace, MetricName=metric_name,
        Dimensions=[{'Name': dimension_name, 'Value': dimension_value}],
        StartTime=datetime.utcnow() - timedelta(minutes=minutes),
        EndTime=datetime.utcnow(), Period=300, Statistics=['Average', 'Maximum']
    )
    datapoints = sorted(response['Datapoints'], key=lambda x: x['Timestamp'])
    return {"datapoints": [{"time": dp['Timestamp'].isoformat(), "avg": round(dp['Average'], 2)} for dp in datapoints[-6:]]}
