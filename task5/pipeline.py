import hashlib
import logging
import multiprocessing
import random
import sys
import sysconfig
import time
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from multiprocessing.managers import SyncManager
from threading import Lock


class Pipeline:

    def __init__(self, max_workers: int | None = None) -> None:
        self.results = {}
        self._max_workers = max_workers

    def fetcher(self, task_id: int) -> str:
        time.sleep(0.1)  # imitate downloading
        return f"task-{task_id}-{random.randint(1000, 10000)}"

    @staticmethod
    def processor(data: str) -> str:
        result = data.encode()

        for _ in range(100_000):
            result = hashlib.sha256(result).digest()

        return result.hex()

    def storer(self, task_id: int, data: str) -> None:
        self.results[task_id] = data

    def worker(self, task_id: int) -> None:
        fetched_data = self.fetcher(task_id)
        processed_data = self.processor(fetched_data)
        self.storer(task_id, processed_data)

    def run(self, tasks: list[int]) -> dict[int, str]:
        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            futures = [
                executor.submit(self.worker, task_id)
                for task_id in tasks
            ]

            for future in futures:
                future.result()

        return self.results


class SafePipeline(Pipeline):

    def __init__(self, max_workers: int | None = None) -> None:
        super().__init__(max_workers)
        self._lock: Lock = Lock()

    def storer(self, task_id: int, data: str) -> None:
        with self._lock:
            super().storer(task_id, data)


class AdaptivePipeline(SafePipeline):

    def __init__(self, max_workers: int | None = None) -> None:
        super().__init__(max_workers)
        self._manager: SyncManager | None = None

    def is_gil_disabled(self) -> bool:
        py_gil_disabled = bool(sysconfig.get_config_var("Py_GIL_DISABLED"))

        is_gil_enabled = getattr(sys, "_is_gil_enabled", None)

        if is_gil_enabled is None:
            return False

        return py_gil_disabled and not is_gil_enabled()

    def get_executor(self) -> type[ThreadPoolExecutor] | type[ProcessPoolExecutor]:
        if self.is_gil_disabled():
            logging.info("GIL disabled: using ThreadPoolExecutor")
            return ThreadPoolExecutor

        logging.info("GIL enabled: using ProcessPoolExecutor for CPU-bound processor")
        return ProcessPoolExecutor

    def run(self, tasks: list[int]) -> dict[int, str]:
        executor_class = self.get_executor()

        if executor_class is ProcessPoolExecutor:
            self._manager = multiprocessing.Manager()
            self.results = self._manager.dict()

        fetched_items = [
            (task_id, self.fetcher(task_id))
            for task_id in tasks
        ]

        with executor_class(max_workers=self._max_workers) as executor:
            futures = {
                executor.submit(self.processor, data): task_id
                for task_id, data in fetched_items
            }

            for future, task_id in futures.items():
                processed_data = future.result()
                self.storer(task_id, processed_data)

        return dict(self.results)


class RobustPipeline(AdaptivePipeline):
    def worker(self, task_id: int) -> None:
        try:
            super().worker(task_id)
        except Exception:
            logging.exception("Exception at worker task_id=%s", task_id)

    def run(self, tasks: list[int]) -> dict[int, str]:
        executor_class = self.get_executor()

        if executor_class is ThreadPoolExecutor:
            with executor_class(max_workers=self._max_workers) as executor:
                futures = [
                    executor.submit(self.worker, task_id)
                    for task_id in tasks
                ]

                for future in futures:
                    future.result()

            return dict(self.results)

        self._manager = multiprocessing.Manager()
        self.results = self._manager.dict()

        fetched_items = []

        for task_id in tasks:
            try:
                fetched_items.append((task_id, self.fetcher(task_id)))
            except Exception:
                logging.exception("Exception at fetcher task_id=%s", task_id)

        with ProcessPoolExecutor(max_workers=self._max_workers) as executor:
            futures = {
                executor.submit(self.processor, data): task_id
                for task_id, data in fetched_items
            }

            for future, task_id in futures.items():
                try:
                    processed_data = future.result()
                    self.storer(task_id, processed_data)
                except Exception:
                    logging.exception("Exception at processor/storer task_id=%s", task_id)

        return dict(self.results)

if __name__ == "__main__":
    pipeline = RobustPipeline()
    print(pipeline.run([1, 2, 3, 4, 5]))