import sqlite3
import numpy as np
from router.features import get_embedding
from common.config import settings

# Graceful import check for UMAP and HDBSCAN
try:
    import umap
    import hdbscan
    HAS_UMAP_HDBSCAN = True
except ImportError:
    HAS_UMAP_HDBSCAN = False
    from sklearn.decomposition import PCA
    from sklearn.cluster import DBSCAN

def get_failed_traces_data(db_file: str = "agentlab.db") -> list[dict]:
    """
    Pulls failed traces from the database. A trace is represented by a request_id
    that had a success = 0 on any step, or had failure signals.
    """
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    # Get request_ids that had failures
    cursor.execute("""
        SELECT DISTINCT request_id 
        FROM agent_responses 
        WHERE success = 0
    """)
    failed_requests = [r[0] for r in cursor.fetchall()]
    
    traces = []
    for req_id in failed_requests:
        # Fetch all steps for this request
        cursor.execute("""
            SELECT agent_id, output, success, timestamp
            FROM agent_responses
            WHERE request_id = ?
            ORDER BY timestamp ASC
        """, (req_id,))
        steps = cursor.fetchall()
        
        # Concatenate outputs for embedding context
        combined_text = "\n".join([f"{step[0]}: {step[1]}" for step in steps])
        
        traces.append({
            "request_id": req_id,
            "combined_text": combined_text,
            "steps": [{"agent_id": s[0], "output": s[1], "success": s[2]} for s in steps]
        })
        
    conn.close()
    return traces

def cluster_failed_requests(db_file: str = "agentlab.db") -> dict[int, list[dict]]:
    """
    Embeds failed traces, reduces dimensions, clusters them, and returns a dictionary 
    mapping cluster_id (int) to a list of trace dictionaries.
    """
    traces = get_failed_traces_data(db_file)
    if not traces:
        return {}
        
    # Get embeddings for each trace combined text
    embeddings = []
    for t in traces:
        embeddings.append(get_embedding(t["combined_text"]))
    X = np.array(embeddings)
    
    if len(X) < 3:
        # Too few items to cluster, group all in a single cluster 0
        return {0: traces}
        
    labels = []
    if HAS_UMAP_HDBSCAN:
        try:
            # Reduce dimensions using UMAP (minimum n_neighbors = 2 due to small sample size)
            n_neighbors = min(15, len(X) - 1)
            n_components = min(5, len(X) - 2)
            if n_neighbors >= 2 and n_components >= 2:
                reducer = umap.UMAP(n_neighbors=n_neighbors, n_components=n_components, random_state=42)
                X_reduced = reducer.fit_transform(X)
            else:
                X_reduced = X
                
            # Cluster using HDBSCAN
            clusterer = hdbscan.HDBSCAN(min_cluster_size=2, gen_min_span_tree=True)
            labels = clusterer.fit_predict(X_reduced)
        except Exception as e:
            print(f"[cluster] UMAP/HDBSCAN failed: {e}. Falling back to PCA/DBSCAN.")
            labels = []
            
    # Fallback to PCA + DBSCAN if UMAP/HDBSCAN is not installed or failed
    if len(labels) == 0:
        pca = PCA(n_components=min(5, len(X)))
        X_reduced = pca.fit_transform(X)
        
        # Use DBSCAN for robust density clustering
        clusterer = DBSCAN(eps=0.5, min_samples=2)
        labels = clusterer.fit_predict(X_reduced)
        
    # Group traces by label
    clusters = {}
    for idx, label in enumerate(labels):
        lbl = int(label)
        if lbl not in clusters:
            clusters[lbl] = []
        clusters[lbl].append(traces[idx])
        
    return clusters
