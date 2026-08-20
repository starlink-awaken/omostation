from __future__ import annotations

import logging
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from importlib import import_module
from multiprocessing import cpu_count
from typing import Any, Self, TypeVar, cast

from eidos.graph_store import CandidateEntity, CandidateRelation

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Builder'
Layer: L3
Constraint: "Must handle multiprocessing safely with proper resource cleanup"
Summary: "ParallelExtractor - Multi-process batch extraction for NKS knowledge graph"
Tags:
- nks
- parallel-processing
- batch-extraction
- multiprocessing
Authority: organs/D-Memory/AGENTS.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Parallel Extractor ≡ Module
# 内涵 ≝ {Parallel, Extractor}
# 外延 ≝ {e | e ∈ D-Memory ∧ implements(e, ParallelExtractor)}
# 功能 ⊢ {Parallel_Extractor, Init_Parallel, Validate_Extractor}
# =============================================================================

_log = logging.getLogger(__name__)

# Optional tqdm for progress tracking
try:
    from tqdm import tqdm  # type: ignore[reportAssignmentType]

    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False

    # Dummy tqdm class for when tqdm is not available
    class tqdm:  # type: ignore[no-redef]  # noqa: N801
        """Dummy progress bar when tqdm is not available."""

        def __init__(self, total: int = 0, desc: str = "", **kwargs: Any) -> None:
            self.total = total
            self.desc = desc
            self.n = 0
            if desc:
                _log.info("[{desc}] Starting batch of {total} items...")

        def update(self, n: int = 1) -> None:
            self.n += n

        def close(self) -> None:
            pass

        def __enter__(self) -> Self:
            return self

        def __exit__(self, *args: Any) -> None:
            _log.info("[{self.desc}] Completed {self.n}/{self.total} items")


# Type variable for extractor classes
T = TypeVar("T")


@dataclass
class BatchExtractionResult:
    """Result of parallel batch extraction.

    Attributes:
        total_files: Total number of files processed
        successful: Number of successfully processed files
        failed: List of (file_path, error_message) tuples for failed files
        entities: All extracted entities from successful files
        relations: All extracted relations from successful files
        duration_seconds: Total processing time
        worker_count: Number of workers used
    """

    total_files: int = 0
    successful: int = 0
    failed: list[tuple[str, str]] = field(default_factory=list)
    entities: list[CandidateEntity] = field(default_factory=list)
    relations: list[CandidateRelation] = field(default_factory=list)
    duration_seconds: float = 0.0
    worker_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary for serialization."""
        return {
            "total_files": self.total_files,
            "successful": self.successful,
            "failed_count": len(self.failed),
            "failed": self.failed,
            "entities_count": len(self.entities),
            "relations_count": len(self.relations),
            "duration_seconds": round(self.duration_seconds, 2),
            "worker_count": self.worker_count,
            "files_per_second": (
                round(self.total_files / self.duration_seconds, 2) if self.duration_seconds > 0 else 0
            ),
        }

    def __repr__(self) -> str:
        return (
            f"BatchExtractionResult("
            f"files={self.successful}/{self.total_files}, "
            f"failed={len(self.failed)}, "
            f"entities={len(self.entities)}, "
            f"relations={len(self.relations)}, "
            f"time={self.duration_seconds:.2f}s, "
            f"workers={self.worker_count})"
        )


def _ping_test_func() -> bool:
    """Picklable test function for ping()."""
    return True


def _init_worker() -> None:
    """Initialize worker process by validating importability."""
    import_module("organs.D_Memory.organs.nks")


def _load_extractor_class(extractor_class_name: str) -> type:
    extractor_modules = {
        "TreeSitterExtractor": "organs.D_Memory.organs.nks.tree_sitter_extractor",
        "CodeExtractor": "organs.D_Memory.organs.nks.code_extractor",
    }
    module_name = extractor_modules.get(
        extractor_class_name,
        "organs.D_Memory.organs.nks.tree_sitter_extractor",
    )
    class_name = extractor_class_name if extractor_class_name in extractor_modules else "TreeSitterExtractor"
    module = import_module(module_name)
    return cast("type", getattr(module, class_name))


def _extract_file_worker(file_path: str, extractor_class_name: str) -> tuple[str, list[dict], list[dict], str | None]:
    """Worker function for parallel extraction (must be picklable).

    This function is executed in separate processes and must be self-contained.

    Args:
        file_path: Path to the file to extract from
        extractor_class_name: Name of the extractor class to use

    Returns:
        Tuple of (file_path, entities_dicts, relations_dicts, error_message)
        error_message is None if extraction succeeded
    """
    # Initialize paths in worker process

    try:
        _init_worker()

        extractor = _load_extractor_class(extractor_class_name)()

        # Read file content
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(file_path, encoding="latin-1", errors="ignore") as f:
                content = f.read()

        # Extract based on extractor type
        if hasattr(extractor, "extract_from_file"):
            result = extractor.extract_from_file(content, file_path)
        elif hasattr(extractor, "extract_from_python"):
            result = extractor.extract_from_python(content, file_path)
        else:
            return file_path, [], [], "Extractor has no suitable extract method"

        # Convert entities and relations to dictionaries for pickling
        entities_dicts = []
        relations_dicts = []

        for entity in getattr(result, "entities", []):
            entities_dicts.append(
                {
                    "entity_id": entity.entity_id,
                    "name": entity.name,
                    "properties": entity.properties,
                    "source_file": entity.source_file,
                }
            )

        for relation in getattr(result, "relations", []):
            relations_dicts.append(
                {
                    "source_id": relation.source_id,
                    "target_id": relation.target_id,
                    "relation_type": relation.relation_type,
                    "properties": relation.properties,
                    "source_file": relation.source_file,
                    "confidence": getattr(relation, "confidence", 1.0),
                }
            )

        return file_path, entities_dicts, relations_dicts, None

    except (OSError, ImportError, TypeError, ValueError) as e:
        return file_path, [], [], f"InitError: {e}"
    except RuntimeError as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        return file_path, [], [], error_msg


class ParallelExtractor:
    """ParallelExtractor - Multi-process batch extraction for NKS.

    Provides CPU-parallel extraction of entities and relations from multiple
    source files using a process pool. Designed for batch processing of
    large codebases.

    Example:
        >>> extractor = ParallelExtractor(max_workers=4)
        >>> files = ["a.py", "b.py", "c.py"]
        >>> result = extractor.extract_batch(files)
        >>> _log.info("Extracted {len(result.entities)} entities")
    """

    def __init__(self, max_workers: int | None = None) -> None:
        """Initialize ParallelExtractor.

        Args:
            max_workers: Number of worker processes. Defaults to CPU count.
        """

        self.max_workers = max_workers or cpu_count()
        self._deduct_metabolic_tax(amount=5.0)

        # Track statistics
        self._files_processed = 0
        self._files_failed = 0

    def _deduct_metabolic_tax(self, amount: float) -> None:
        _ = amount

    def extract_batch(
        self,
        file_paths: list[str],
        extractor_class: type = None,  # type: ignore
        batch_size: int = 100,
        show_progress: bool = True,
    ) -> BatchExtractionResult:
        """Extract from multiple files in parallel.

        Args:
            file_paths: List of file paths to process
            extractor_class: Extractor class to use (default: TreeSitterExtractor)
            batch_size: Number of files per batch (for memory management)
            show_progress: Whether to show progress bar

        Returns:
            BatchExtractionResult with all extraction results
        """
        # Default to TreeSitterExtractor
        if extractor_class is None:
            extractor_class = _load_extractor_class("TreeSitterExtractor")

        # Get extractor class name for worker
        extractor_class_name = extractor_class.__name__

        # Initialize result
        result = BatchExtractionResult(total_files=len(file_paths), worker_count=self.max_workers)

        if not file_paths:
            return result

        start_time = time.time()

        # Process files in batches to manage memory
        batches = [file_paths[i : i + batch_size] for i in range(0, len(file_paths), batch_size)]

        total_processed = 0

        if show_progress and TQDM_AVAILABLE:
            progress_bar = tqdm(total=len(file_paths), desc="Extracting files")
        elif show_progress:
            progress_bar = tqdm(total=len(file_paths), desc="Extracting files")
        else:
            progress_bar = None

        for batch in batches:
            batch_result = self._process_batch(batch, extractor_class_name)

            # Aggregate results
            result.entities.extend(batch_result.entities)
            result.relations.extend(batch_result.relations)
            result.failed.extend(batch_result.failed)
            result.successful += batch_result.successful

            total_processed += len(batch)

            if progress_bar:
                progress_bar.update(len(batch))

        if progress_bar:
            progress_bar.close()

        result.duration_seconds = time.time() - start_time

        # Deduct metabolic tax based on files processed
        self._deduct_metabolic_tax(amount=0.1 * result.total_files)

        return result

    def _process_batch(self, file_paths: list[str], extractor_class_name: str) -> BatchExtractionResult:
        """Process a single batch of files.

        Args:
            file_paths: List of file paths in this batch
            extractor_class_name: Name of extractor class

        Returns:
            BatchExtractionResult for this batch
        """
        result = BatchExtractionResult(total_files=len(file_paths))

        try:
            # Use ProcessPoolExecutor for true parallelism
            with ProcessPoolExecutor(max_workers=self.max_workers, initializer=_init_worker) as executor:
                # Submit all tasks
                future_to_file = {
                    executor.submit(_extract_file_worker, file_path, extractor_class_name): file_path
                    for file_path in file_paths
                }

                # Collect results as they complete
                for future in as_completed(future_to_file):
                    file_path = future_to_file[future]

                    try:
                        _, entities_dicts, relations_dicts, error = future.result(timeout=300)

                        if error:
                            result.failed.append((file_path, error))
                            self._files_failed += 1
                        else:
                            self._consume_worker_payload(result, entities_dicts, relations_dicts)
                            result.successful += 1
                            self._files_processed += 1

                    except (OSError, TypeError, ValueError, RuntimeError) as e:
                        error_msg = f"{type(e).__name__}: {str(e)}"
                        result.failed.append((file_path, error_msg))
                        self._files_failed += 1
        except (NotImplementedError, PermissionError, OSError) as e:
            _log.warning("Falling back to sequential batch processing: %s", e)
            return self._process_batch_without_process_pool(file_paths, extractor_class_name)

        return result

    def _process_batch_without_process_pool(
        self, file_paths: list[str], extractor_class_name: str
    ) -> BatchExtractionResult:
        result = BatchExtractionResult(total_files=len(file_paths), worker_count=1)
        for file_path in file_paths:
            _, entities_dicts, relations_dicts, error = _extract_file_worker(file_path, extractor_class_name)
            if error:
                result.failed.append((file_path, error))
                self._files_failed += 1
                continue

            self._consume_worker_payload(result, entities_dicts, relations_dicts)
            result.successful += 1
            self._files_processed += 1

        return result

    @staticmethod
    def _consume_worker_payload(
        result: BatchExtractionResult,
        entities_dicts: list[dict[str, Any]],
        relations_dicts: list[dict[str, Any]],
    ) -> None:
        for entity_dict in entities_dicts:
            result.entities.append(
                CandidateEntity(
                    entity_id=entity_dict["entity_id"],
                    name=entity_dict["name"],
                    properties=entity_dict["properties"],
                    source_file=entity_dict["source_file"],
                )
            )

        for relation_dict in relations_dicts:
            result.relations.append(
                CandidateRelation(
                    source_id=relation_dict["source_id"],
                    target_id=relation_dict["target_id"],
                    relation_type=relation_dict["relation_type"],
                    properties=relation_dict["properties"],
                    source_file=relation_dict["source_file"],
                    confidence=relation_dict.get("confidence", 1.0),
                )
            )

    def extract_batch_sequential(
        self,
        file_paths: list[str],
        extractor_class: type = None,  # type: ignore
        show_progress: bool = True,
    ) -> BatchExtractionResult:
        """Extract from multiple files sequentially (fallback method).

        Useful for debugging or when multiprocessing is not available.

        Args:
            file_paths: List of file paths to process
            extractor_class: Extractor class to use
            show_progress: Whether to show progress bar

        Returns:
            BatchExtractionResult with all extraction results
        """
        # Default to TreeSitterExtractor
        if extractor_class is None:
            extractor_class = _load_extractor_class("TreeSitterExtractor")

        # Create extractor instance
        extractor = extractor_class()

        result = BatchExtractionResult(total_files=len(file_paths), worker_count=1)

        if not file_paths:
            return result

        start_time = time.time()

        # Use tqdm for progress if available
        iterator = tqdm(file_paths, desc="Extracting (sequential)") if show_progress else file_paths  # type: ignore[reportArgumentType]

        for file_path in iterator:  # type: ignore[reportGeneralTypeIssues]
            entities, relations, error = self._extract_single(file_path, extractor)

            if error:
                result.failed.append((file_path, error))
            else:
                result.entities.extend(entities)
                result.relations.extend(relations)
                result.successful += 1

        result.duration_seconds = time.time() - start_time

        # Deduct metabolic tax
        self._deduct_metabolic_tax(amount=0.1 * result.total_files)

        return result

    def _extract_single(
        self, file_path: str, extractor: Any
    ) -> tuple[list[CandidateEntity], list[CandidateRelation], str | None]:
        """Extract from single file.

        Args:
            file_path: Path to file to extract from
            extractor: Configured extractor instance

        Returns:
            Tuple of (entities, relations, error_message)
            error_message is None if extraction succeeded
        """
        try:
            # Read file content
            try:
                with open(file_path, encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except UnicodeDecodeError:
                with open(file_path, encoding="latin-1", errors="ignore") as f:
                    content = f.read()

            # Extract based on extractor capabilities
            if hasattr(extractor, "extract_from_file"):
                extraction_result = extractor.extract_from_file(content, file_path)
            elif hasattr(extractor, "extract_from_python"):
                extraction_result = extractor.extract_from_python(content, file_path)
            else:
                return [], [], "Extractor has no suitable extract method"

            entities = getattr(extraction_result, "entities", [])
            relations = getattr(extraction_result, "relations", [])

            return entities, relations, None

        except (OSError, TypeError, ValueError, RuntimeError) as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            return [], [], error_msg

    def get_stats(self) -> dict[str, Any]:
        """Get extraction statistics.

        Returns:
            Dictionary with processing statistics
        """
        return {
            "files_processed": self._files_processed,
            "files_failed": self._files_failed,
            "max_workers": self.max_workers,
            "cpu_count": cpu_count(),
        }

    def reset_stats(self) -> None:
        """Reset processing statistics."""
        self._files_processed = 0
        self._files_failed = 0

    def ping(self) -> bool:
        """Health check for ParallelExtractor.

        Returns:
            True if extractor is operational
        """
        try:
            # Check if we can create a process pool
            with ProcessPoolExecutor(max_workers=1, initializer=_init_worker) as executor:
                future = executor.submit(_ping_test_func)
                return future.result(timeout=5)
        except (NotImplementedError, PermissionError, OSError):
            try:
                _init_worker()
                return True
            except (OSError, ValueError, RuntimeError):
                return False
        except (TypeError, ValueError, RuntimeError):
            return False
