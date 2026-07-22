#!/usr/bin/env python3
"""
MCP Server для работы с файлами (Sandboxed & LLM-Optimized)
Зависимости: pip install mcp
"""
import os
import json
import shutil
import re
import logging
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

# ================= НАСТРОЙКИ =================
# Песочница: все пути будут ограничены этой директорией.
BASE_DIR = Path("F:/ai_проекты/pythonExample").resolve()

MAX_READ_LINES = 500  # Макс. строк за одно чтение
MAX_LIST_ITEMS = 200  # Макс. элементов в списке директории
MAX_SEARCH_RESULTS = 50  # Макс. результатов поиска
# =============================================

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

mcp = FastMCP("custom-files-sandbox")


# ================= ХЕЛПЕРЫ =================
def resolve_safe_path(path_str: str) -> Path:
    """Приводит путь к абсолютному и гарантирует, что он внутри BASE_DIR."""
    p = (BASE_DIR / path_str).resolve()
    try:
        p.relative_to(BASE_DIR)
    except ValueError:
        raise PermissionError(f"Доступ запрещён: путь выходит за пределы песочницы {BASE_DIR}")
    return p


def make_result(status: str, content: str, metadata: Optional[dict] = None) -> str:
    """Единый формат ответа для LLM (всегда валидный JSON)."""
    return json.dumps({
        "status": status,  # "success" | "partial" | "error"
        "content": content,
        "metadata": metadata or {}
    }, ensure_ascii=False)


# =============================================

@mcp.tool()
async def read_file(path: str, start_line: int = 1, end_line: Optional[int] = None) -> str:
    """Читает текстовый файл. Автоматически режет большие файлы, блокирует бинарные."""
    try:
        p = resolve_safe_path(path)
        if not p.exists() or not p.is_file():
            return make_result("error", f"Файл не найден: {path}")

        # Защита от бинарных файлов (поиск null-байтов)
        with open(p, "rb") as f:
            if b'\x00' in f.read(8192):
                return make_result("error", "Обнаружен бинарный файл. Используйте парсеры для PDF/изображений/etc.")

        with open(p, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        total = len(lines)
        start = max(1, start_line) - 1
        end = min(end_line or (start + MAX_READ_LINES), total)

        chunk = "".join(lines[start:end])
        meta = {"total_lines": total, "shown_from": start + 1, "shown_to": end}

        if total > MAX_READ_LINES and not end_line:
            meta["warning"] = "Файл обрезан. Укажите end_line для чтения следующих частей."
            return make_result("partial", chunk, meta)
        return make_result("success", chunk, meta)
    except PermissionError as e:
        return make_result("error", str(e))
    except Exception as e:
        return make_result("error", f"Ошибка чтения: {e}")


@mcp.tool()
async def write_file(path: str, content: str) -> str:
    """Записывает содержимое в файл (создаёт или перезаписывает)."""
    try:
        p = resolve_safe_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        return make_result("success", f"Файл сохранён: {p}")
    except PermissionError as e:
        return make_result("error", str(e))
    except Exception as e:
        return make_result("error", f"Ошибка записи: {e}")


@mcp.tool()
async def append_to_file(path: str, content: str) -> str:
    """Добавляет текст в конец файла без перезаписи."""
    try:
        p = resolve_safe_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(content)
        return make_result("success", f"Текст добавлен в: {p}")
    except PermissionError as e:
        return make_result("error", str(e))
    except Exception as e:
        return make_result("error", f"Ошибка добавления: {e}")


@mcp.tool()
async def list_directory(path: str, recursive: bool = False, max_items: int = MAX_LIST_ITEMS) -> str:
    """Возвращает список файлов и папок в формате JSON."""
    try:
        p = resolve_safe_path(path)
        if not p.is_dir(): return make_result("error", f"Не директория: {path}")

        pattern = "**/*" if recursive else "*"
        items = sorted([str(i.relative_to(p)) for i in p.glob(pattern)])
        limited = items[:max_items]

        meta = {"total_found": len(items), "shown": len(limited), "truncated": len(items) > max_items}
        return make_result("success", json.dumps(limited, ensure_ascii=False, indent=2), meta)
    except PermissionError as e:
        return make_result("error", str(e))
    except Exception as e:
        return make_result("error", f"Ошибка чтения: {e}")


@mcp.tool()
async def get_file_info(path: str) -> str:
    """Метаданные файла/директории (размер, даты, права)."""
    try:
        p = resolve_safe_path(path)
        if not p.exists(): return make_result("error", f"Путь не найден: {path}")

        stat = p.stat()
        info = {
            "path": str(p),
            "name": p.name,
            "is_file": p.is_file(),
            "is_dir": p.is_dir(),
            "size_bytes": stat.st_size,
            "modified_timestamp": stat.st_mtime,
            "permissions": oct(stat.st_mode)[-3:]
        }
        return make_result("success", "", info)
    except PermissionError as e:
        return make_result("error", str(e))
    except Exception as e:
        return make_result("error", f"Ошибка метаданных: {e}")


@mcp.tool()
async def delete_path(path: str, force: bool = False) -> str:
    """Удаляет файл или директорию. force=True требуется для непустых папок."""
    try:
        p = resolve_safe_path(path)
        if not p.exists(): return make_result("error", f"Путь не найден: {path}")

        if p.is_file() or p.is_symlink():
            p.unlink()
        elif p.is_dir():
            if force:
                shutil.rmtree(p)
            elif any(p.iterdir()):
                return make_result("error", "Директория не пуста. Добавьте force=True для рекурсивного удаления.")
            else:
                p.rmdir()
        else:
            return make_result("error", "Неизвестный тип объекта.")
        return make_result("success", f"Удалено: {path}")
    except PermissionError as e:
        return make_result("error", str(e))
    except Exception as e:
        return make_result("error", f"Ошибка удаления: {e}")


@mcp.tool()
async def move_rename(src: str, dst: str) -> str:
    """Перемещает или переименовывает файл/директорию."""
    try:
        s = resolve_safe_path(src)
        d = resolve_safe_path(dst)
        if not s.exists(): return make_result("error", f"Источник не найден: {src}")

        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(s), str(d))
        return make_result("success", f"Перемещено: {src} -> {dst}")
    except PermissionError as e:
        return make_result("error", str(e))
    except Exception as e:
        return make_result("error", f"Ошибка перемещения: {e}")


@mcp.tool()
async def search_files(directory: str, pattern: str = "*", recursive: bool = True,
                       max_results: int = MAX_SEARCH_RESULTS) -> str:
    """Поиск файлов по glob-маске (например *.py, config.*, docs/*)."""
    try:
        p = resolve_safe_path(directory)
        if not p.is_dir(): return make_result("error", f"Не директория: {directory}")

        search_pattern = f"**/{pattern}" if recursive else pattern
        matches = sorted([str(f.relative_to(p)) for f in p.glob(search_pattern) if f.is_file()])
        limited = matches[:max_results]

        meta = {"total": len(matches), "shown": len(limited), "truncated": len(matches) > max_results}
        return make_result("success", json.dumps(limited, ensure_ascii=False, indent=2), meta)
    except PermissionError as e:
        return make_result("error", str(e))
    except Exception as e:
        return make_result("error", f"Ошибка поиска: {e}")


@mcp.tool()
async def search_in_files(
        directory: str,
        pattern: str,
        file_mask: str = "*.py",
        recursive: bool = True,
        max_results: int = MAX_SEARCH_RESULTS,
        ignore_case: bool = True
) -> str:
    """Поиск текста внутри файлов (аналог grep). Возвращает строки с номерами."""
    try:
        p = resolve_safe_path(directory)
        if not p.is_dir(): return make_result("error", f"Не директория: {directory}")

        flags = re.IGNORECASE if ignore_case else 0
        regex = re.compile(pattern, flags)
        results = []
        search_pattern = f"**/{file_mask}" if recursive else file_mask

        for file_path in p.glob(search_pattern):
            if not file_path.is_file(): continue
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    for i, line in enumerate(f, 1):
                        if regex.search(line):
                            rel = file_path.relative_to(p)
                            results.append(f"{rel}:{i}: {line.strip()}")
                            if len(results) >= max_results: break
                if len(results) >= max_results: break
            except Exception:
                continue

        return make_result("success", "\n".join(results) if results else "Совпадений не найдено.",
                           {"count": len(results)})
    except PermissionError as e:
        return make_result("error", str(e))
    except Exception as e:
        return make_result("error", f"Ошибка поиска: {e}")


if __name__ == "__main__":
    logger.info(f"🚀 MCP Server запускается. Песочница: {BASE_DIR}")
    mcp.run()