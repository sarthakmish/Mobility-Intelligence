"""Quick probe to test LLM Farm connectivity directly."""
import httpx

API_KEY = "9c93482a1c6b4581b4f88071d86e8f0f"
BASE = "https://aoai-farm.bosch-temp.com"

tests = [
    {
        "name": "Claude Sonnet 4.6 — Bearer",
        "url": f"{BASE}/api/google/v1/publishers/anthropic/models/claude-sonnet-4-6:rawPredict",
        "headers": {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        "body": {"anthropic_version": "vertex-2023-10-16", "max_tokens": 50,
                 "messages": [{"role": "user", "content": "Say hello in one word."}]},
    },
    {
        "name": "Claude Sonnet 4.6 — subscription-key",
        "url": f"{BASE}/api/google/v1/publishers/anthropic/models/claude-sonnet-4-6:rawPredict",
        "headers": {"genaiplatform-farm-subscription-key": API_KEY, "Content-Type": "application/json"},
        "body": {"anthropic_version": "vertex-2023-10-16", "max_tokens": 50,
                 "messages": [{"role": "user", "content": "Say hello in one word."}]},
    },
    {
        "name": "Claude Haiku 4.5 — Bearer",
        "url": f"{BASE}/api/google/v1/publishers/anthropic/models/claude-haiku-4-5@20251001:rawPredict",
        "headers": {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        "body": {"anthropic_version": "vertex-2023-10-16", "max_tokens": 50,
                 "messages": [{"role": "user", "content": "Say hello in one word."}]},
    },
    {
        "name": "GPT-5 mini — Bearer",
        "url": f"{BASE}/api/openai/deployments/gpt-5-mini-2025-08-07/chat/completions?api-version=2025-04-01-preview",
        "headers": {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        "body": {"model": "gpt-5-mini-2025-08-07",
                 "messages": [{"role": "user", "content": "Say hello in one word."}],
                 "max_completion_tokens": 50},
    },
    {
        "name": "Embeddings — subscription-key",
        "url": f"{BASE}/api/openai/deployments/askbosch-prod-farm-openai-text-embedding-3-small/embeddings?api-version=2024-10-21",
        "headers": {"genaiplatform-farm-subscription-key": API_KEY, "Content-Type": "application/json"},
        "body": {"input": "test embedding"},
    },
]

print("=" * 70)
print("LLM Farm Connectivity Probe")
print("=" * 70)

for t in tests:
    print(f"\n[{t['name']}]")
    try:
        r = httpx.post(t["url"], headers=t["headers"], json=t["body"], timeout=30)
        print(f"  STATUS: {r.status_code}")
        if r.is_success:
            data = r.json()
            if "content" in data:
                print(f"  REPLY: {data['content'][0]['text'][:100]}")
            elif "choices" in data:
                print(f"  REPLY: {data['choices'][0]['message']['content'][:100]}")
            elif "data" in data:
                print(f"  EMBEDDING DIMS: {len(data['data'][0]['embedding'])}")
            print("  ✅ WORKING")
        else:
            print(f"  BODY: {r.text[:300]}")
            print("  ❌ FAILED")
    except Exception as e:
        print(f"  EXCEPTION: {e}")
        print("  ❌ ERROR")

print("\n" + "=" * 70)
