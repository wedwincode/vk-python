import argparse
import asyncio
import json
import sys
from typing import Final

base_delay: Final = 2

async def simulate_service(name: str, delay: float) -> dict:
    await asyncio.sleep(delay)
    return {"name": name, "status": "ok", "latency": delay}


async def check_one_service(
    config: dict,
    timeout: float,
    max_retries: int,
    semaphore: asyncio.Semaphore
) -> dict:
    if max_retries < 0:
        raise ValueError("max_retries should be greater than or equal to 0")

    total_attempts = max_retries + 1

    last_error = None
    for attempt_index in range(total_attempts):
        try:
            async with semaphore:
                async with asyncio.timeout(timeout):
                    result = await simulate_service(
                        config["name"],
                        config["delay"]
                    )

            result["attempts"] = attempt_index + 1
            return result

        except (TimeoutError, ConnectionError) as exc:
            last_error = exc

            if attempt_index < max_retries:
                retry_delay = base_delay * (2 ** attempt_index)
                await asyncio.sleep(retry_delay)


    status = "timeout" if isinstance(last_error, TimeoutError) else "error"

    return {
        "name": config["name"],
        "status": status,
        "attempts": total_attempts,
    }

async def check_services(
    configs: list[dict],
    timeout_per_service: float,
    max_retries: int = 3,
    max_concurrent: int = 2
) -> list[dict]:
    semaphore = asyncio.Semaphore(max_concurrent)

    async def check_with_index(index: int, config: dict) -> tuple[int, dict]:
        result = await check_one_service(
            config,
            timeout_per_service,
            max_retries,
            semaphore,
        )
        return index, result

    tasks = [
        check_with_index(index, config)
        for index, config in enumerate(configs)
    ]

    results = [None] * len(tasks)
    completed = 0

    for task in asyncio.as_completed(tasks):
        index, result = await task
        results[index] = result

        completed += 1
        print(f"\rCompleted {completed}/{len(tasks)}", end="", flush=True)
    print()

    return results


async def perform_check(timeout: float, retries: int, concurrency: int, output: str) -> None:
    services = [
        {"name": "1", "delay": 3},
        {"name": "2", "delay": 3},
        {"name": "3", "delay": 5},
        {"name": "4", "delay": 1},
    ]

    results = await check_services(services, timeout, retries, concurrency)

    if output:
        with open(output, "w", encoding="utf-8") as file:
            json.dump(results, file, ensure_ascii=False, indent=2)

    got_error = any(res.get("status") != "ok" for res in results)
    sys.exit(1 if got_error else 0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="CLI service check tool")
    parser.add_argument("--timeout", type=float, required=True)
    parser.add_argument("--retries", type=int, required=True)
    parser.add_argument("--concurrency", type=int, required=True)
    parser.add_argument("--output")

    args = parser.parse_args()

    asyncio.run(
        perform_check(
            args.timeout,
            args.retries,
            args.concurrency,
            args.output,
        )
    )
