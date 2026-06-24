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
import subprocess
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

    # 合并过小的切片（< 80 字符），确保每个切片有足够语义
    merged = []
    for c in final_chunks:
        if merged and len(merged[-1]["text"]) < 80:
            merged[-1]["text"] += "\n" + c["text"]
            merged[-1]["header"] = merged[-1]["header"] or c["header"]
        else:
            merged.append(c)
    final_chunks = merged

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

    def query(self, text: str, n_results: int = 8) -> list[dict]:
        """搜索知识库，返回最相关的文本块（向量 + 关键词混合检索）"""
        if not text:
            return []
        
        # 1. 向量检索
        chunks = self._vector_search(text, n_results)
        
        # 2. 关键词检索补充（总是执行，补充向量搜索的不足）
        kw_chunks = self._keyword_search(text, n_results)
        seen = set(c["text"][:50] for c in chunks)
        for c in kw_chunks:
            if c["text"][:50] not in seen:
                seen.add(c["text"][:50])
                chunks.append(c)
        
        # 按分数排序（score 越低越相关）
        chunks.sort(key=lambda x: x["score"])
        return chunks[:n_results]

    def _vector_search(self, text: str, n_results: int) -> list[dict]:
        """向量检索"""
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

    def _keyword_search(self, text: str, n_results: int) -> list[dict]:
        """关键词检索：找到匹配最多关键词的文档"""
        import glob
        from collections import Counter

        docs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")
        if not os.path.exists(docs_dir):
            return []

        # 提取关键词（过滤太短的词）
        import re as _re
        keywords = [w for w in _re.findall(r'[\w]{2,}', text) if len(w) >= 2]

        doc_scores = Counter()
        doc_lines = {}
        for f in glob.glob(os.path.join(docs_dir, "*.md")):
            fname = os.path.basename(f).replace(".md", "")
            try:
                with open(f, encoding="utf-8") as fh:
                    content = fh.read().lower()
                score = sum(1 for kw in keywords if kw.lower() in content)
                if score >= max(2, len(keywords) // 2):  # 至少匹配一半以上关键词
                    doc_scores[fname] = score
                    # 找包含最多关键词的那一行
                    best_line, best_count = "", 0
                    for line in content.split("\n"):
                        cnt = sum(1 for kw in keywords if kw.lower() in line)
                        if cnt > best_count:
                            best_count = cnt
                            best_line = line.strip()
                    doc_lines[fname] = best_line[:200] if best_line else ""
            except Exception:
                continue

        results = []
        for fname, score in doc_scores.most_common(n_results):
            # 读取文档前 800 字符作为内容（确保有足够上下文）
            full_text = ""
            for f in glob.glob(os.path.join(docs_dir, f"{fname}.md")):
                try:
                    with open(f, encoding="utf-8") as fh:
                        full_text = fh.read()[:800]
                except:
                    pass
            results.append({
                "text": full_text or doc_lines.get(fname, ""),
                "source": fname,
                "header": f"关键词匹配 (得分={score})",
                "score": score * -0.01,
            })
        return results

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
            for c in chunks[:8]
        ])

        # 调用 DeepSeek
        import httpx
        try:
            resp = httpx.post(
                f"{DEEPSEEK_BASE_URL}/chat/completions",
                json={
                    "model": DEEPSEEK_MODEL,
                    "messages": [
                        {"role": "system", "content": "你是一个 Windchill PLM 专家助手。请基于所有提供的参考资料回答问题，不要跳过任何信息。即使看起来是技术命令（如xconfmanager、SQL等），也要包含在回答中。如果参考资料有具体步骤、命令、参数配置，请详细列出。回答要专业、完整、步骤清晰。"},
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
            sources = "\n".join(f"📄 [{c['source']}] {c['header']}" for c in chunks[:5])
            return f"💡 {answer}\n\n{sources}"
        except Exception as e:
            # 降级为纯检索
            lines = [f"🔍 AI 回答失败 ({e})，返回检索结果:"]
            for c in chunks[:5]:
                lines.append(f"\n  📄 [{c['source']}] {c['header']}")
                lines.append(f"  {c['text'][:200]}...")
            return "\n".join(lines)


kb = KnowledgeBase()
