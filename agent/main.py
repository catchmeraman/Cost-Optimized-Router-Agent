"""main.py — Cost-Optimized Router Agent for AgentCore Runtime.
Combines: Model Routing + Prompt Cache + Direct API Gateway."""
import json
import logging
import time
import uuid
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
from opentelemetry import baggage, context
from strands import Agent
from strands.models import BedrockModel
from model_router import select_model, NOVA_LITE, NOVA_PRO
from prompt_cache import PromptCache
from gateway_router import try_direct_route
from tools.cloudwatch_tools import get_alarms, get_metric_statistics
from tools.ec2_tools import describe_instances, manage_instance
from tools.sns_tools import send_notification

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("cost-router")

cache = PromptCache()

SYSTEM_PROMPT = """DevOps AI Agent. Tools: CloudWatch, EC2, SNS.
Rules: 1) Diagnose before act 2) Explain reasoning 3) Justify destructive actions"""

TOOLS = [get_alarms, get_metric_statistics, describe_instances, manage_instance, send_notification]


def create_agent(model_id: str) -> Agent:
    return Agent(
        model=BedrockModel(model_id=model_id, region_name="us-east-1"),
        system_prompt=SYSTEM_PROMPT,
        tools=TOOLS
    )


# Pre-create agents for both tiers (avoid cold start on each request)
agent_lite = create_agent(NOVA_LITE)
agent_pro = create_agent(NOVA_PRO)


class RouterHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        start = time.time()

        try:
            request = json.loads(body)
            prompt = request.get("prompt", "")
            session_id = request.get("session_id", str(uuid.uuid4()))

            ctx = baggage.set_baggage("session.id", session_id)
            token = context.attach(ctx)

            try:
                result = self._route_and_respond(prompt, session_id)
            finally:
                context.detach(token)

            duration = (time.time() - start) * 1000

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                **result,
                "session_id": session_id,
                "duration_ms": round(duration, 1),
                "cache_stats": cache.stats()
            }).encode())

        except Exception as e:
            logger.error(f"Error: {e}\n{traceback.format_exc()}")
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def _route_and_respond(self, prompt: str, session_id: str) -> dict:
        """Three-layer routing: Cache → Direct API → Model-Routed Agent."""

        # Layer 1: Check cache
        cached = cache.get(prompt)
        if cached:
            return cached

        # Layer 2: Try direct API route (zero LLM cost)
        direct = try_direct_route(prompt)
        if direct:
            cache.put(prompt, direct["response"], "direct_api", 0)
            return direct

        # Layer 3: Route to appropriate model
        model_id, reason, tier = select_model(prompt)
        agent = agent_pro if tier == "pro" else agent_lite
        logger.info(f"[{session_id}] Model: {tier} ({reason}) | Prompt: {prompt[:60]}...")

        response = agent(prompt)
        response_text = str(response)

        # Cache the response
        cache.put(prompt, response_text, model_id, 500)  # Estimate 500 tokens

        return {
            "response": response_text,
            "model_used": model_id,
            "routing_reason": reason,
            "tier": tier,
            "tokens_used": 500,  # Estimated
            "cached": False
        }

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({
            "status": "healthy",
            "agent": "cost-optimized-router",
            "version": "1.0",
            "strategies": ["model_routing", "prompt_cache", "direct_api_gateway"],
            "cache_stats": cache.stats()
        }).encode())

    def log_message(self, format, *args):
        logger.debug(f"HTTP: {format % args}")


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 8080), RouterHandler)
    logger.info("Cost-Optimized Router Agent starting on port 8080")
    logger.info("Strategies: Model Routing + Prompt Cache + Direct API Gateway")
    server.serve_forever()
