"""prompt_cache.py — DynamoDB-backed response cache to eliminate duplicate LLM calls."""
import boto3
import hashlib
import time
import logging
import json

logger = logging.getLogger("cost-router")

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
CACHE_TABLE_NAME = 'agent-response-cache'
CACHE_TTL_SECONDS = 300  # 5 minutes


class PromptCache:
    def __init__(self):
        self.table = dynamodb.Table(CACHE_TABLE_NAME)
        self.hits = 0
        self.misses = 0

    def _key(self, prompt: str) -> str:
        normalized = prompt.lower().strip()
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def get(self, prompt: str) -> dict | None:
        key = self._key(prompt)
        try:
            item = self.table.get_item(Key={'cache_key': key}).get('Item')
            if item and item.get('expires_at', 0) > int(time.time()):
                self.hits += 1
                logger.info(f"CACHE HIT: {prompt[:50]}... (saved LLM call)")
                return {
                    "response": item['response'],
                    "cached": True,
                    "model_used": item.get('model_used', 'cached'),
                    "tokens_saved": item.get('tokens_used', 0),
                    "cache_age_seconds": int(time.time()) - item.get('created_at', 0)
                }
        except Exception as e:
            logger.warning(f"Cache read error: {e}")
        self.misses += 1
        return None

    def put(self, prompt: str, response: str, model_used: str, tokens_used: int):
        key = self._key(prompt)
        try:
            self.table.put_item(Item={
                'cache_key': key,
                'prompt': prompt[:200],
                'response': response[:2000],
                'model_used': model_used,
                'tokens_used': tokens_used,
                'created_at': int(time.time()),
                'expires_at': int(time.time()) + CACHE_TTL_SECONDS
            })
        except Exception as e:
            logger.warning(f"Cache write error: {e}")

    def stats(self) -> dict:
        total = self.hits + self.misses
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": f"{(self.hits/max(total,1))*100:.0f}%",
            "estimated_savings": f"${self.hits * 0.001:.4f}"
        }
