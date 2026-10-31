"""Stockage vectoriel du module 2 (réutilisé par les modules 3, 4 et 5) : Weaviate, ou une base en mémoire de repli.

Adapté de l'adaptateur de souleymanecoulibaly-stack (branche tp-rag-lagune-bank).
Une collection offre `add(ids, embeddings, documents, metadatas)` et `query(query_embeddings, n_results)`. La distance est
`l2-squared` : plus elle est petite, plus le chunk est proche de la question.
Weaviate Cloud si WEAVIATE_URL est renseignée, sinon Weaviate local (`docker compose up -d`), sinon la mémoire (ou VECTEUR=memoire).
"""
import os

import numpy as np

CHAMPS = ["source", "titre", "version", "date_effet", "date_fin", "page"]   # métadonnées conservées avec chaque chunk


# ------------------------------------------------------------------ repli en mémoire
class MemoryClient:
    """Même rôle que le client Weaviate : fabrique des collections, se ferme."""

    def close(self):
        pass


class MemoryCollection:
    """Collection en mémoire : comparaison avec tous les vecteurs, rien n'est conservé après le notebook."""

    def __init__(self, client, name):
        self.name, self._ids, self._vecteurs, self._textes, self._metas = name, [], [], [], []
        self.reutilisee = False

    def add(self, ids, embeddings, documents, metadatas):
        self._ids += list(ids)
        self._vecteurs += [np.asarray(v, dtype=float) for v in embeddings]
        self._textes += list(documents)
        self._metas += [{c: m.get(c, "") for c in CHAMPS} for m in metadatas]

    def query(self, query_embeddings, n_results=10):
        q = np.asarray(query_embeddings[0] if isinstance(query_embeddings[0], (list, tuple, np.ndarray)) else query_embeddings, dtype=float)
        distances = [float(np.sum((v - q) ** 2)) for v in self._vecteurs]          # l2-squared
        ordre = sorted(range(len(distances)), key=distances.__getitem__)[:n_results]
        return {"documents": [[self._textes[i] for i in ordre]], "distances": [[distances[i] for i in ordre]],
                "metadatas": [[self._metas[i] for i in ordre]]}


# ------------------------------------------------------------------ Weaviate
def connect():
    """Se connecte à Weaviate (cloud, puis local) ; à défaut, base en mémoire."""
    if os.getenv("VECTEUR") == "memoire":
        return MemoryClient()
    import weaviate
    url = os.getenv("WEAVIATE_URL")
    try:
        if url:
            return weaviate.connect_to_weaviate_cloud(cluster_url=url, auth_credentials=weaviate.auth.AuthApiKey(os.environ["WEAVIATE_API_KEY"]))
        return weaviate.connect_to_local()
    except Exception as e:                                                  # Docker non lancé, réseau bloqué...
        print(f"Weaviate injoignable ({type(e).__name__}) : repli sur la base en mémoire. "
              "Pour Weaviate : `docker compose up -d` à la racine du dépôt.")
        return MemoryClient()


class WeaviateCollection:
    """Collection Weaviate qui stocke nos propres embeddings. `reutilisee` : une collection déjà remplie a été reprise telle quelle."""

    def __init__(self, client, name, reutiliser=False):
        from weaviate.classes.config import Configure, DataType, Property, VectorDistances
        self.name, self.reutilisee = name, False
        if client.collections.exists(name):
            if reutiliser and client.collections.get(name).aggregate.over_all(total_count=True).total_count:
                self._col, self.reutilisee = client.collections.get(name), True       # déjà indexée : on ne recalcule pas les embeddings
                return
            client.collections.delete(name)
        self._col = client.collections.create(
            name,
            # nos propres embeddings (pas de vectoriseur Weaviate)
            vector_config=Configure.Vectors.self_provided(
                vector_index_config=Configure.VectorIndex.hnsw(distance_metric=VectorDistances.L2_SQUARED)),
            properties=[Property(name="text", data_type=DataType.TEXT)] + [Property(name=c, data_type=DataType.TEXT) for c in CHAMPS],
        )

    def add(self, ids, embeddings, documents, metadatas):
        from weaviate.util import generate_uuid5
        with self._col.batch.dynamic() as batch:
            for id_, vector, text, meta in zip(ids, embeddings, documents, metadatas):
                batch.add_object(properties={"text": text, **{c: str(meta.get(c, "")) for c in CHAMPS}},
                                 vector=list(vector), uuid=generate_uuid5(id_))   # Weaviate exige des UUID : dérivé de l'id du chunk
        if self._col.batch.failed_objects:
            raise RuntimeError(f"Échec d'indexation Weaviate : {self._col.batch.failed_objects[:3]}")

    def query(self, query_embeddings, n_results=10):
        from weaviate.classes.query import MetadataQuery
        vector = query_embeddings[0] if isinstance(query_embeddings[0], (list, tuple)) else query_embeddings
        res = self._col.query.near_vector(near_vector=list(vector), limit=n_results, return_metadata=MetadataQuery(distance=True))
        return {"documents": [[o.properties["text"] for o in res.objects]],
                "distances": [[o.metadata.distance for o in res.objects]],
                "metadatas": [[{c: o.properties.get(c, "") for c in CHAMPS} for o in res.objects]]}


def create_collection(client, name, reutiliser=False):
    """Une collection sur le client fourni par connect(). Elle est recréée si elle existe, sauf avec `reutiliser=True` et une collection non vide."""
    return MemoryCollection(client, name) if isinstance(client, MemoryClient) else WeaviateCollection(client, name, reutiliser)
