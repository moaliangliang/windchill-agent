"""知识库 — 基于 RAG 的 Windchill 文档智能搜索

流程:
  docs/*.md → 切片(chunk) → 向量化(embedding) → chromadb
                                                    ↓
  用户提问 → 向量化 → 相似度搜索 → DeepSeek 生成回答
"""

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Optional

# 使用 HuggingFace 镜像（国内网络）
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

# ── 配置 ──────────────────────────────────────────────────

DOCS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")
DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".kb_cache")
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

# DeepSeek API
DEEPSEEK_API_KEY = ""
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"

# 从环境变量读 DeepSeek Key
for _env_path in [
    os.path.expanduser("~/.env"),
    os.path.join(os.path.dirname(DOCS_DIR), ".env"),
    os.path.join(os.path.dirname(os.path.dirname(DOCS_DIR)), "backend", ".env"),
    os.path.join(os.path.dirname(os.path.dirname(DOCS_DIR)), "knowagent", ".env"),
    os.path.join(os.path.dirname(os.path.dirname(DOCS_DIR)), "knowagent", "backend", ".env"),
]:
    if os.path.exists(_env_path):
        with open(_env_path) as _f:
            for _line in _f:
                if _line.startswith("DEEPSEEK_API_KEY="):
                    DEEPSEEK_API_KEY = _line.split("=", 1)[1].strip().strip('"\'')

if not DEEPSEEK_API_KEY:
    DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")


# ── 文本切片 ──────────────────────────────────────────────

def chunk_text(text: str, filename: str = "") -> list[dict]:
    """将文档切成片段，保留来源信息"""
    chunks = []

    # 按 Markdown 标题分段
    sections = re.split(r'(^#+\s+.*$)', text, flags=re.MULTILINE)

    current_header = ""
    current_content = ""

    for sec in sections:
        sec = sec.strip()
        if not sec:
            continue
        if sec.startswith("#"):
            # 之前的内容形成一块
            if current_content:
                chunks.append({
                    "text": f"{current_header}\n{current_content}",
                    "source": filename,
                    "header": current_header.strip("# ").strip(),
                })
            current_header = sec
            current_content = ""
        else:
            current_content = sec

    if current_content:
        chunks.append({
            "text": f"{current_header}\n{current_content}",
            "source": filename,
            "header": current_header.strip("# ").strip(),
        })

    # 对长片段再做递归切分
    final_chunks = []
    for c in chunks:
        if len(c["text"]) > CHUNK_SIZE:
            text = c["text"]
            while len(text) > CHUNK_SIZE:
                # 在段落边界切分
                split_pos = text.rfind("\n\n", 0, CHUNK_SIZE)
                if split_pos < CHUNK_SIZE // 2:
                    split_pos = text.rfind("\n", 0, CHUNK_SIZE)
                if split_pos < CHUNK_SIZE // 2:
                    split_pos = CHUNK_SIZE

                final_chunks.append({
                    "text": text[:split_pos].strip(),
                    "source": c["source"],
                    "header": c["header"],
                })
                text = text[split_pos - CHUNK_OVERLAP:].strip()

            if text:
                final_chunks.append({
                    "text": text,
                    "source": c["source"],
                    "header": c["header"],
                })
        else:
            final_chunks.append(c)

    return final_chunks


# ── 知识库引擎 ────────────────────────────────────────────

class KnowledgeBase:
    """基于 chromadb 的向量知识库"""

    def __init__(self):
        self._collection = None
        self._embedding_fn = None

    def _get_embedding_fn(self):
        """延迟加载 embedding 模型"""
        if self._embedding_fn is None:
            from sentence_transformers import SentenceTransformer
            model_name = "paraphrase-multilingual-MiniLM-L12-v2"
            import sys as _sys
            print("  📦 加载 AI 模型（首次约30秒）...", end="", flush=True)
            model = SentenceTransformer(model_name)
            self._embedding_fn = lambda texts: model.encode(texts).tolist()
            print("\r  ✅ AI 模型就绪（下次即用）")
        return self._embedding_fn

    def _get_collection(self):
        """获取 chromadb 集合"""
        if self._collection is None:
            import chromadb
            os.makedirs(DB_DIR, exist_ok=True)
            client = chromadb.PersistentClient(path=DB_DIR)
            try:
                self._collection = client.get_collection("windchill_docs")
            except Exception:
                self._collection = client.create_collection(
                    "windchill_docs",
                    metadata={"hnsw:space": "cosine"},
                )
        return self._collection

    def build(self, docs_dir: str = DOCS_DIR) -> str:
        """构建/重建知识库索引"""
        if not os.path.exists(docs_dir):
            return "❌ docs/ 目录不存在"

        import glob
        files = sorted(glob.glob(os.path.join(docs_dir, "*.md")))
        if not files:
            return "❌ docs/ 目录下没有 .md 文件"

        # 收集所有切片
        all_chunks = []
        for f in files:
            fname = os.path.basename(f).replace(".md", "")
            with open(f, encoding="utf-8") as fh:
                text = fh.read()
            chunks = chunk_text(text, fname)
            all_chunks.extend(chunks)

        if not all_chunks:
            return "❌ 文档切片失败"

        # 生成向量
        texts = [c["text"] for c in all_chunks]
        print(f"  📦 正在向量化 {len(texts)} 个文本块...")
        embed_fn = self._get_embedding_fn()
        embeddings = embed_fn(texts)

        # 写入 chromadb
        collection = self._get_collection()
        # 清空旧数据
        try:
            count = collection.count()
            if count > 0:
                collection.delete(where={})
        except Exception:
            pass

        ids = []
        metadatas = []
        seen_ids = set()
        for i, (chunk, embedding) in enumerate(zip(all_chunks, embeddings)):
            chunk_id = hashlib.md5(f"{i}_{chunk['text'][:50]}".encode()).hexdigest()[:12]
            if chunk_id in seen_ids:
                chunk_id = hashlib.md5(f"{i}_{chunk['text']}".encode()).hexdigest()[:16]
            seen_ids.add(chunk_id)
            ids.append(chunk_id)
            metadatas.append({
                "source": chunk["source"],
                "header": chunk.get("header", ""),
                "text": chunk["text"][:200],
            })

        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=[c["text"] for c in all_chunks],
            metadatas=metadatas,
        )

        return f"✅ 知识库已构建: {len(all_chunks)} 个文本块，来自 {len(files)} 篇文档"

    def query(self, text: str, n_results: int = 5) -> list[dict]:
        """搜索知识库，返回最相关的文本块"""
        if not text:
            return []
        embed_fn = self._get_embedding_fn()
        collection = self._get_collection()

        query_embedding = embed_fn([text])[0]
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
        )

        chunks = []
        for i in range(len(results["ids"][0])):
            chunks.append({
                "text": results["documents"][0][i],
                "source": results["metadatas"][0][i]["source"],
                "header": results["metadatas"][0][i].get("header", ""),
                "score": results["distances"][0][i] if "distances" in results else 0,
            })
        return chunks

    def ask(self, question: str) -> str:
        """搜索知识库 + DeepSeek 生成回答"""
        if not DEEPSEEK_API_KEY:
            # 无 API Key 时只返回检索结果
            chunks = self.query(question)
            if not chunks:
                return "❌ 知识库未构建，请先运行: kb_build"
            lines = [f"🔍 找到 {len(chunks)} 个相关片段:"]
            for c in chunks:
                lines.append(f"\n  📄 [{c['source']}] {c['header']}")
                lines.append(f"  {c['text'][:200]}...")
            return "\n".join(lines)

        # 检索
        chunks = self.query(question)
        if not chunks:
            return "❌ 知识库未构建，请先运行: kb_build"

        # 构建上下文
        context = "\n\n---\n\n".join([
            f"[来源: {c['source']} - {c['header']}]\n{c['text'][:1000]}"
            for c in chunks[:5]
        ])

        # 调用 DeepSeek
        import httpx
        try:
            resp = httpx.post(
                f"{DEEPSEEK_BASE_URL}/chat/completions",
                json={
                    "model": DEEPSEEK_MODEL,
                    "messages": [
                        {"role": "system", "content": "你是一个 Windchill PLM 专家助手。请基于提供的参考资料回答问题。如果参考资料不足以回答，请如实说不知道。回答要简洁、专业。"},
                        {"role": "user", "content": f"参考资料:\n{context}\n\n问题: {question}"},
                    ],
                    "max_tokens": 1000,
                    "temperature": 0.3,
                },
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
                timeout=30,
            )
            result = resp.json()
            answer = result["choices"][0]["message"]["content"].strip()
            sources = "\n".join(f"📄 [{c['source']}] {c['header']}" for c in chunks[:3])
            return f"💡 {answer}\n\n{sources}"
        except Exception as e:
            # 降级为纯检索
            lines = [f"🔍 AI 回答失败 ({e})，返回检索结果:"]
            for c in chunks[:3]:
                lines.append(f"\n  📄 [{c['source']}] {c['header']}")
                lines.append(f"  {c['text'][:200]}...")
            return "\n".join(lines)


kb = KnowledgeBase()
