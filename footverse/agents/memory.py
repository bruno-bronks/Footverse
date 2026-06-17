"""Memory/RAG do Footverse — Fase 1.

Constrói um índice Chroma a partir do estado persistido do `Repository`
(clubes, jogadores, ledger, temporada) e expõe um método `search()` usado
pela tool `buscar_historico` dos agentes.

Não armazena eventos separados: lê do store SQL que já é fonte de verdade.
Rebuilds são baratos (5 documentos curtos por clube) e acontecem uma vez por
invocação do agente.

Variável de ambiente:
  FOOTVERSE_MEMORY_DIR — diretório para persistir o índice Chroma em disco.
                         Sem ela, Chroma roda efêmero (in-memory).
"""

from __future__ import annotations

import hashlib
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..state.repository import Repository
    from chromadb import Collection

from .. import config
from ..state.models import INITIAL_GRANT, SEASON_REWARD, TRANSFER_BUY

_PREMIO_DESC: dict[int, str] = {
    config.PREMIO_POR_RESULTADO["CAMPEAO"]:   "CAMPEÃO",
    config.PREMIO_POR_RESULTADO["PROMOVIDO"]: "PROMOVIDO",
    config.PREMIO_POR_RESULTADO["PERMANECE"]: "PERMANECEU",
    config.PREMIO_POR_RESULTADO["REBAIXADO"]: "REBAIXADO",
}


def _fmt_fvs(v: int) -> str:
    return f"FV${v / 1_000_000:.1f}M" if abs(v) >= 1_000_000 else f"FV${v:,}"


def _SimpleHashEmbedding():
    """Bag-of-words com hashing — zero deps de ML, usado apenas em testes.

    Retorna uma instância de EmbeddingFunction[Documents] compatível com
    chromadb 1.x sem precisar baixar nenhum modelo ONNX.
    """
    from chromadb import EmbeddingFunction, Documents, Embeddings

    _DIM = 512

    class _HashEF(EmbeddingFunction[Documents]):
        def __call__(self, input: Documents) -> Embeddings:
            result = []
            for doc in input:
                vec = [0.0] * _DIM
                for word in doc.lower().split():
                    h = int(hashlib.md5(word.encode()).hexdigest()[:8], 16)
                    vec[h % _DIM] += 1.0
                norm = sum(v * v for v in vec) ** 0.5 or 1.0
                result.append([v / norm for v in vec])
            return result

    return _HashEF()


class MemoryStore:
    """Índice vetorial do histórico de um clube, alimentado pelo store SQL.

    Documentos indexados (5 por clube):
      - perfil       — nome, divisão, saldo
      - temporada    — estado atual da temporada
      - historico    — temporadas encerradas inferidas do ledger
      - elenco       — jogadores atuais com OVR e forma
      - financas     — resumo do ledger (grants, compras, prêmios)
    """

    def __init__(
        self,
        store: Repository,
        club_id: str,
        persist_dir: str | None = None,
        _embedding_fn=None,          # injeção para testes (evita download ONNX)
    ) -> None:
        import chromadb

        self._store = store
        self._club_id = club_id

        if persist_dir:
            self._client = chromadb.PersistentClient(path=persist_dir)
        else:
            self._client = chromadb.EphemeralClient()

        if _embedding_fn is not None:
            ef = _embedding_fn
        else:
            from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
            ef = DefaultEmbeddingFunction()
        # Ephemeral client is a singleton in chromadb 1.x — use a UUID suffix so
        # each MemoryStore instance gets its own isolated collection (safe for tests).
        # Persistent mode uses a stable name so data survives across restarts.
        base = f"fv_{club_id.replace('-', '_')}"
        coll_name = base if persist_dir else f"{base}_{uuid.uuid4().hex[:8]}"
        self._col: Collection = self._client.get_or_create_collection(
            coll_name, embedding_function=ef
        )

    # ── construção do índice ──────────────────────────────────────────────────

    def build(self) -> int:
        """Reconstrói (upsert) todos os documentos do clube. Retorna o total."""
        docs, ids, metas = self._make_documents()
        self._col.upsert(documents=docs, ids=ids, metadatas=metas)
        return len(docs)

    def _make_documents(self) -> tuple[list[str], list[str], list[dict]]:
        club = self._store.get_club(self._club_id)
        if club is None:
            return [], [], []
        season = self._store.get_season(self._club_id)
        pids = self._store.elenco(self._club_id)

        docs, ids, metas = [], [], []

        def add(doc_id: str, text: str, tipo: str) -> None:
            docs.append(text)
            ids.append(f"{self._club_id}_{doc_id}")
            metas.append({"tipo": tipo, "club_id": self._club_id})

        # ── 1. Perfil ─────────────────────────────────────────────────────────
        add("perfil", (
            f"Clube: {club.nome} | Divisão atual: {club.divisao} | "
            f"Saldo: {_fmt_fvs(club.saldo_fvs)} | "
            f"Elenco: {len(pids)} jogadores"
        ), "perfil")

        # ── 2. Temporada atual ────────────────────────────────────────────────
        if season:
            rodadas = len(season.rodadas)
            pontos = club.pontos_temporada_centi / 100
            add("temporada", (
                f"Temporada {season.temporada} | Divisão: {season.divisao} | "
                f"Status: {season.status} | "
                f"Rodadas jogadas: {rodadas}/{config.RODADAS_POR_TEMPORADA} | "
                f"Pontos acumulados: {pontos:.1f}"
            ), "temporada")

        # ── 3. Histórico de temporadas (via SEASON_REWARD no ledger) ─────────
        ledger_entries = self._store.get_ledger(self._club_id)
        premios = [(e.ref, e.valor_fvs) for e in ledger_entries if e.tipo == SEASON_REWARD]
        if premios:
            partes = []
            for ref, valor in premios:
                desc = _PREMIO_DESC.get(valor, f"{_fmt_fvs(valor)}")
                partes.append(f"{ref}: {desc} ({_fmt_fvs(valor)})")
            add("historico", "Histórico de temporadas: " + " | ".join(partes), "historico")
        else:
            add("historico", "Histórico: nenhuma temporada encerrada ainda.", "historico")

        # ── 4. Elenco atual ───────────────────────────────────────────────────
        if pids:
            por_setor: dict[str, list[str]] = {}
            for pid in pids:
                mp = self._store.get_player(pid)
                if mp is None:
                    continue
                setor = mp.setor
                por_setor.setdefault(setor, []).append(
                    f"{mp.player.posicao_natural} OVR{mp.ovr} forma{mp.player.forma}"
                )
            partes = [f"{s}: {', '.join(ps)}" for s, ps in sorted(por_setor.items())]
            add("elenco", f"Elenco ({len(pids)} jogadores) — " + " | ".join(partes), "elenco")
        else:
            add("elenco", "Elenco vazio — nenhum jogador comprado ainda.", "elenco")

        # ── 5. Resumo financeiro ──────────────────────────────────────────────
        grant = sum(e.valor_fvs for e in ledger_entries if e.tipo == INITIAL_GRANT)
        compras = abs(sum(e.valor_fvs for e in ledger_entries if e.tipo == TRANSFER_BUY))
        premios_total = sum(e.valor_fvs for e in ledger_entries if e.tipo == SEASON_REWARD)
        add("financas", (
            f"Finanças: grant inicial {_fmt_fvs(grant)} | "
            f"Gasto em compras: {_fmt_fvs(compras)} ({len(pids)} jogadores) | "
            f"Prêmios recebidos: {_fmt_fvs(premios_total)} | "
            f"Saldo atual: {_fmt_fvs(club.saldo_fvs)}"
        ), "financas")

        return docs, ids, metas

    # ── busca ─────────────────────────────────────────────────────────────────

    def search(self, query: str, n_results: int = 3) -> str:
        """Busca semântica no índice e retorna os documentos mais relevantes."""
        total = self._col.count()
        if total == 0:
            return "Nenhum histórico disponível ainda."
        n = min(n_results, total)
        results = self._col.query(query_texts=[query], n_results=n)
        docs = results["documents"][0] if results["documents"] else []
        if not docs:
            return "Nenhum registro encontrado para essa consulta."
        return "\n---\n".join(docs)
