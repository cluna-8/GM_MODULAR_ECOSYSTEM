import httpx
import asyncio
import json


async def test_auditor_endpoints():
    url = "http://localhost:8001"

    print("Testing /health...")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{url}/health")
            print(f"Health check: {resp.status_code} - {resp.json()}")
        except Exception as e:
            print(f"Health check failed: {e}")

    print("\nTesting /audit/pre-process...")
    payload = {"text": "Tratamiento para Colecistectomía"}
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{url}/audit/pre-process", json=payload)
            print(f"Pre-process: {resp.status_code} - {resp.json()}")
        except Exception as e:
            print(f"Pre-process failed: {e}")

    print("\nTesting /audit/validate-safety...")
    payload = {
        "text": "Administrar antibiótico X...",
        "context": {"edad": 79, "alergias": "Penicilina"},
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{url}/audit/validate-safety", json=payload)
            print(f"Safety validation: {resp.status_code} - {resp.json()}")
        except Exception as e:
            print(f"Safety validation failed: {e}")


if __name__ == "__main__":
    asyncio.run(test_auditor_endpoints())
