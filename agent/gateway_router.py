"""gateway_router.py — Direct API routing for simple queries, bypassing LLM entirely."""
import boto3
import logging

logger = logging.getLogger("cost-router")


DIRECT_ROUTES = {
    "list instances": {
        "service": "ec2",
        "method": "describe_instances",
        "params": {},
        "format": lambda r: [
            {"id": i["InstanceId"], "name": next((t["Value"] for t in i.get("Tags", []) if t["Key"] == "Name"), "unnamed"), "state": i["State"]["Name"], "type": i["InstanceType"]}
            for res in r["Reservations"] for i in res["Instances"]
        ]
    },
    "list alarms": {
        "service": "cloudwatch",
        "method": "describe_alarms",
        "params": {"StateValue": "ALARM"},
        "format": lambda r: [
            {"name": a["AlarmName"], "metric": a["MetricName"], "state": a["StateValue"]}
            for a in r["MetricAlarms"]
        ]
    },
    "running instances": {
        "service": "ec2",
        "method": "describe_instances",
        "params": {"Filters": [{"Name": "instance-state-name", "Values": ["running"]}]},
        "format": lambda r: [
            {"id": i["InstanceId"], "name": next((t["Value"] for t in i.get("Tags", []) if t["Key"] == "Name"), "unnamed"), "type": i["InstanceType"]}
            for res in r["Reservations"] for i in res["Instances"]
        ]
    },
    "stopped instances": {
        "service": "ec2",
        "method": "describe_instances",
        "params": {"Filters": [{"Name": "instance-state-name", "Values": ["stopped"]}]},
        "format": lambda r: [
            {"id": i["InstanceId"], "name": next((t["Value"] for t in i.get("Tags", []) if t["Key"] == "Name"), "unnamed")}
            for res in r["Reservations"] for i in res["Instances"]
        ]
    }
}


def try_direct_route(prompt: str) -> dict | None:
    """If query matches a direct API route, call API without using LLM."""
    prompt_lower = prompt.lower().strip()

    for pattern, config in DIRECT_ROUTES.items():
        if pattern in prompt_lower:
            try:
                client = boto3.client(config["service"], region_name="us-east-1")
                method = getattr(client, config["method"])
                response = method(**config["params"])
                result = config["format"](response)
                logger.info(f"DIRECT ROUTE: '{pattern}' → {config['service']}.{config['method']} (0 tokens)")
                return {
                    "response": f"Found {len(result)} results: {result}",
                    "routed": "direct_api",
                    "pattern_matched": pattern,
                    "tokens_used": 0,
                    "model_used": "none (direct API)",
                    "data": result
                }
            except Exception as e:
                logger.warning(f"Direct route failed for '{pattern}': {e}")
                return None

    return None
