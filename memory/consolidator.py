"""Memory Consolidation Engine — Phase 11.1.

Background job that compresses episodic memory into semantic summaries.

Algorithm:
1. Group memory entries by namespace + category older than 24h
2. Find clusters via embedding similarity (cosine distance < 0.3)
3. Summarize each cluster into 1 semantic fact using Claude Haiku
4. Write consolidated entry with high confidence
5. Archive (not delete) source entries

Run via APScheduler every 4 hours, or manually via API.
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from typing import Optional

from core.models import fast_model

logger = logging.getLogger("claudeos.memory.consolidator")


def run_consolidation(namespace: Optional[str] = None, dry_run: bool = False) -> dict:
    """Run memory consolidation.

    Args:
        namespace: if set, consolidate only this namespace; else all namespaces
        dry_run: if True, log what would happen but don't write anything

    Returns:
        Summary dict with stats.
    """
    stats = {"namespaces_processed": 0, "clusters_found": 0, "entries_archived": 0, "entries_created": 0}

    try:
        namespaces = _get_namespaces(namespace)
        for ns in namespaces:
            ns_stats = _consolidate_namespace(ns, dry_run)
            stats["clusters_found"]   += ns_stats["clusters"]
            stats["entries_archived"] += ns_stats["archived"]
            stats["entries_created"]  += ns_stats["created"]
            stats["namespaces_processed"] += 1

        logger.info(
            "Consolidation complete: %d namespaces, %d clusters, %d archived → %d created",
            stats["namespaces_processed"], stats["clusters_found"],
            stats["entries_archived"], stats["entries_created"],
        )
    except Exception as e:
        logger.error("Consolidation failed: %s", e)
        stats["error"] = str(e)

    return stats


def _get_namespaces(namespace: Optional[str]) -> list[str]:
    if namespace:
        return [namespace]
    from memory.engine import namespace_counts
    return list(namespace_counts().keys())


def _consolidate_namespace(namespace: str, dry_run: bool) -> dict:
    stats = {"clusters": 0, "archived": 0, "created": 0}

    # Get entries eligible for consolidation (not yet consolidated, not archived, older than 24h)
    from core.database import get_db
    from core.utils import utcnow_str

    with get_db() as conn:
        rows = conn.execute(
            """SELECT id, category, key, value, confidence FROM memory_entries
               WHERE namespace = ?
                 AND (is_consolidated IS NULL OR is_consolidated = 0)
                 AND (archived IS NULL OR archived = 0)
                 AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
                 AND created_at <= datetime('now', '-24 hours')
               ORDER BY category, updated_at DESC
               LIMIT 200""",
            (namespace,),
        ).fetchall()

    if len(rows) < 5:  # Not enough to consolidate
        return stats

    # Group by category
    by_category: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_category[row["category"]].append(dict(row))

    for category, entries in by_category.items():
        if len(entries) < 3:
            continue

        # Find clusters using simple text similarity (avoid heavy computation)
        clusters = _cluster_entries(entries)

        for cluster in clusters:
            if len(cluster) < 2:
                continue  # Nothing to consolidate for single-entry clusters

            stats["clusters"] += 1
            if not dry_run:
                _consolidate_cluster(namespace, category, cluster, stats)

    return stats


def _cluster_entries(entries: list[dict]) -> list[list[dict]]:
    """Simple clustering by category sub-grouping.
    Groups entries by first 2 words of key as a cheap heuristic.
    For production, replace with vector clustering (k-means over embeddings).
    """
    groups: dict[str, list[dict]] = defaultdict(list)
    for entry in entries:
        # Group by first keyword in key
        prefix = " ".join(entry["key"].lower().split()[:2])
        groups[prefix].append(entry)

    # Return groups with >= 2 entries as clusters
    clusters = [g for g in groups.values() if len(g) >= 2]

    # Remaining singletons as one big cluster if enough of them
    singletons = [entry for g in groups.values() if len(g) == 1 for entry in g]
    if len(singletons) >= 5:
        clusters.append(singletons[:10])  # Consolidate up to 10 at once

    return clusters


def _consolidate_cluster(namespace: str, category: str, entries: list[dict], stats: dict) -> None:
    """Summarize a cluster into one semantic fact and archive sources."""
    try:
        from agents.executor import _get_client
        from memory.engine import write as mem_write
        from core.database import get_db
        from core.utils import utcnow_str

        # Build summary prompt
        bullet_list = "\n".join(f"- {e['key']}: {e['value']}" for e in entries[:10])
        summary_prompt = (
            f"Summarize these related memory entries from the '{namespace}' namespace, "
            f"category '{category}', into ONE concise consolidated fact. "
            f"Preserve all key information. Respond with just the summary (max 2 sentences):\n\n"
            f"{bullet_list}"
        )

        client = _get_client()
        response = client.messages.create(
            model=fast_model(),
            max_tokens=200,
            messages=[{"role": "user", "content": summary_prompt}],
            timeout=20.0,
        )
        summary = response.content[0].text.strip() if response.content else ""
        if not summary:
            return

        # Write consolidated entry
        source_ids = [e["id"] for e in entries]
        consolidated_key = f"[consolidated] {category} summary {entries[0]['key'][:30]}"

        consolidated = mem_write(
            namespace=namespace,
            category=category,
            key=consolidated_key,
            value=summary,
            source="consolidator",
            confidence=0.9,
            tags=["consolidated"],
        )

        # Mark source_ids on the new consolidated entry
        with get_db() as conn:
            conn.execute(
                "UPDATE memory_entries SET is_consolidated=1, consolidated_from=? WHERE id=?",
                (json.dumps(source_ids), consolidated.id),
            )
            # Archive source entries
            placeholders = ",".join("?" * len(source_ids))
            conn.execute(
                f"UPDATE memory_entries SET archived=1, updated_at=? WHERE id IN ({placeholders})",
                (utcnow_str(), *source_ids),
            )

        stats["entries_archived"] += len(source_ids)
        stats["entries_created"] += 1
        logger.debug("Consolidated %d entries → '%s'", len(source_ids), consolidated_key[:40])

    except Exception as e:
        logger.warning("Cluster consolidation failed: %s", e)
