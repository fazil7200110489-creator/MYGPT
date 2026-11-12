"""Local OCR Service for extracting text from images and scanned documents.

Supports:
1. Local Tesseract OCR (`pytesseract`) when installed.
2. Local Windows Built-in WinRT OCR (`Windows.Media.Ocr.OcrEngine`) batch engine when
   Tesseract is absent on Windows.
3. Optional Vision LLM fallback (`vision_model`, Qwen2-VL-2B) when explicitly enabled
   for single-image transcription.

Never fabricates dummy placeholder text when OCR fails.
"""

import base64
import hashlib
import io
import json
import os
import subprocess
import tempfile
import threading
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image, ImageEnhance
from loguru import logger

try:
    import pytesseract

    TESSERACT_CMD_CANDIDATES = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for candidate in TESSERACT_CMD_CANDIDATES:
        if os.path.exists(candidate):
            pytesseract.pytesseract.tesseract_cmd = candidate
            break
except ImportError:
    pytesseract = None


_WINRT_BATCH_PS = r"""
$ProgressPreference = 'SilentlyContinue'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($WinRtTask, $ResultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    $netTask.Result
}
[Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType=WindowsRuntime] | Out-Null
[Windows.Media.Ocr.OcrEngine, Windows.Media.Ocr, ContentType=WindowsRuntime] | Out-Null
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
$results = @{}
if ($null -eq $engine) {
    Write-Output (@{"error"="WinRT OcrEngine unavailable"} | ConvertTo-Json -Compress)
    exit 0
}
for ($idx = 0; $idx -lt $ImagePaths.Count; $idx++) {
    $imgPath = $ImagePaths[$idx]
    $key = [string]$idx
    try {
        if (-not (Test-Path -LiteralPath $imgPath)) {
            $results[$key] = ""
            continue
        }
        $fs = [System.IO.File]::OpenRead($imgPath)
        $stream = $null
        $bitmap = $null
        try {
            $stream = [System.IO.WindowsRuntimeStreamExtensions]::AsRandomAccessStream($fs)
            $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
            $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
            $res = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
            $lines = @()
            foreach ($ln in $res.Lines) { $lines += $ln.Text }
            $results[$key] = ($lines -join "`n")
        } finally {
            if ($null -ne $bitmap) { $bitmap.Dispose() }
            if ($null -ne $stream) { $stream.Dispose() }
            $fs.Dispose()
        }
    } catch {
        $results[$key] = "__WINRT_ERR__:" + $_.Exception.Message
    }
}
$results | ConvertTo-Json -Compress -Depth 3
"""


class OCRService:
    """Handles local OCR operations for images and scanned/mixed PDF documents."""

    def __init__(self) -> None:
        self._cache_lock = threading.Lock()
        self._image_ocr_cache: OrderedDict[Tuple[str, bool, str], Dict[str, Any]] = OrderedDict()
        self._pdf_ocr_cache: OrderedDict[Tuple[str, Tuple[int, ...], int, str], List[Dict[str, Any]]] = OrderedDict()
        self._max_cache_entries = 128
        self.tesseract_available = False
        try:
            if pytesseract is not None:
                version = pytesseract.get_tesseract_version()
                self.tesseract_available = True
                logger.info(f"Local Tesseract OCR is available. Version: {version}")
        except Exception as e:
            logger.info(
                f"Tesseract binary unavailable ({e}). Checking Windows built-in WinRT OCR..."
            )
        self.winrt_available = self._check_winrt_available()
        if self.winrt_available:
            logger.info("Local Windows built-in WinRT OCR is available.")
        elif not self.tesseract_available:
            logger.warning("No local OS OCR engine (Tesseract or WinRT) is currently available.")

    def _check_winrt_available(self) -> bool:
        if os.name != "nt":
            return False
        try:
            ps_check = (
                "$ProgressPreference='SilentlyContinue';"
                "Add-Type -AssemblyName System.Runtime.WindowsRuntime;"
                "[Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime] | Out-Null;"
                "$e=[Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages();"
                "if ($null -ne $e) { Write-Output 'WINRT_OK' }"
            )
            enc = base64.b64encode(ps_check.encode("utf-16-le")).decode("ascii")
            res = subprocess.run(
                ["powershell", "-NoProfile", "-EncodedCommand", enc],
                capture_output=True,
                text=True,
                timeout=12,
            )
            return "WINRT_OK" in (res.stdout or "")
        except Exception:
            return False

    def active_engine_name(self) -> str:
        if self.tesseract_available:
            return "tesseract"
        if self.winrt_available:
            return "windows_winrt_ocr"
        return "none"

    def preprocess_image(self, img: Image.Image) -> Image.Image:
        """Applies grayscale, contrast boost, sharpening, and gentle deskew for OCR."""
        img = img.convert("L")
        img = ImageEnhance.Contrast(img).enhance(2.0)
        img = ImageEnhance.Sharpness(img).enhance(2.0)

        try:
            import numpy as np

            w, h = img.size
            img_small = img.resize((max(1, w // 4), max(1, h // 4))) if w > 1000 else img
            best_angle = 0
            max_variance = 0.0
            for angle in range(-6, 7):
                rot_img = img_small.rotate(angle, resample=Image.BICUBIC, expand=True)
                rot_data = np.asarray(rot_img)
                rot_bin = (rot_data < 127).astype(np.uint8)
                profile = np.sum(rot_bin, axis=1)
                variance = float(np.var(profile))
                if variance > max_variance:
                    max_variance = variance
                    best_angle = angle
            if best_angle != 0:
                img = img.rotate(best_angle, resample=Image.BICUBIC, expand=True)
        except Exception as e:
            logger.debug(f"Deskew skipped: {e}")

        return img

    def get_ocr_confidence(self, img: Image.Image) -> float:
        """Returns average word confidence from Tesseract (0-100) when available."""
        if not self.tesseract_available or pytesseract is None:
            return 0.0
        try:
            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
            confidences = [int(c) for c in data.get("conf", []) if c != "-1" and c is not None]
            if confidences:
                return sum(confidences) / len(confidences)
        except Exception as e:
            logger.warning(f"Could not extract OCR word confidences: {e}")
        return 0.0

    def _run_winrt_batch(self, image_paths: List[str], timeout: int = 90) -> Dict[str, str]:
        """Runs local Windows WinRT OCR on a batch of image paths in a single subprocess."""
        if not self.winrt_available or not image_paths:
            return {}
        try:
            abs_paths = [os.path.abspath(p) for p in image_paths]
            ps_items = ["'" + p.replace("'", "''") + "'" for p in abs_paths]
            ps_array = "@(" + ",".join(ps_items) + ")"
            script = f"$ImagePaths = {ps_array}\n" + _WINRT_BATCH_PS
            enc = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-EncodedCommand", enc],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            stdout = (proc.stdout or "").strip()
            if not stdout:
                logger.warning(f"WinRT OCR produced empty stdout (stderr={proc.stderr!r})")
                return {}
            # Take last JSON line if any warnings precede it
            json_line = stdout.splitlines()[-1].strip()
            parsed = json.loads(json_line)
            if isinstance(parsed, dict) and "error" not in parsed:
                cleaned_out: Dict[str, str] = {}
                for k, v in parsed.items():
                    idx = int(k)
                    orig_path = abs_paths[idx]
                    sval = str(v or "").strip()
                    if sval.startswith("__WINRT_ERR__:"):
                        logger.warning(f"WinRT OCR page error for {orig_path}: {sval}")
                        cleaned_out[orig_path] = ""
                    else:
                        cleaned_out[orig_path] = sval
                return cleaned_out
            logger.warning(f"WinRT OCR returned error payload: {parsed}")
            return {}
        except Exception as e:
            logger.error(f"WinRT batch OCR failed: {e}")
            return {}

    def _hash_file(self, filepath: str) -> Optional[str]:
        try:
            h = hashlib.sha256()
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
            return h.hexdigest()
        except OSError:
            return None

    def ocr_image_detailed(
        self,
        image_path: str,
        allow_vision_fallback: bool = False,
    ) -> Dict[str, Any]:
        """Runs local OCR on an image (SHA-256 cached) and returns structured text + engine."""
        if not os.path.exists(image_path):
            return {
                "ok": False,
                "text": "OCR_FAILED",
                "engine": "none",
                "confidence": 0.0,
                "error": f"Image file not found: {image_path}",
            }

        file_hash = self._hash_file(image_path)
        cache_key = (file_hash, allow_vision_fallback, self.active_engine_name()) if file_hash else None
        if cache_key is not None:
            with self._cache_lock:
                cached = self._image_ocr_cache.get(cache_key)
                if cached is not None:
                    self._image_ocr_cache.move_to_end(cache_key)
                    return dict(cached)

        res = self._ocr_image_uncached(image_path, allow_vision_fallback=allow_vision_fallback)
        if cache_key is not None and res.get("ok"):
            with self._cache_lock:
                self._image_ocr_cache[cache_key] = dict(res)
                while len(self._image_ocr_cache) > self._max_cache_entries:
                    self._image_ocr_cache.popitem(last=False)
        return res

    def _ocr_image_uncached(
        self,
        image_path: str,
        allow_vision_fallback: bool = False,
    ) -> Dict[str, Any]:
        """Uncached local OCR implementation for an image."""

        abs_path = os.path.abspath(image_path)
        try:
            if self.tesseract_available and pytesseract is not None:
                img = Image.open(abs_path)
                proc_img = self.preprocess_image(img)
                text = pytesseract.image_to_string(proc_img).strip()
                conf = self.get_ocr_confidence(proc_img)
                logger.info(f"Tesseract image OCR confidence: {conf:.1f}% ({len(text)} chars)")
                if text:
                    return {
                        "ok": True,
                        "text": text,
                        "engine": "tesseract",
                        "confidence": round(conf, 2),
                        "error": None,
                    }

            if self.winrt_available:
                # Preprocess copy into temp PNG for higher contrast on faint scans
                tmp_path = None
                try:
                    img = Image.open(abs_path)
                    # Only enhance if small or dark; RGB/L works cleanly with WinRT
                    if img.mode not in ("RGB", "RGBA", "L"):
                        img = img.convert("RGB")
                    # Upscale small images (<900px width) so bitmap fonts remain legible
                    if img.width < 900:
                        scale = 2
                        img = img.resize((img.width * scale, img.height * scale), Image.BICUBIC)
                    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
                        tmp_path = tf.name
                    img.save(tmp_path)
                    batch = self._run_winrt_batch([tmp_path])
                    text = (batch.get(os.path.abspath(tmp_path)) or "").strip()
                    if not text:
                        batch_raw = self._run_winrt_batch([abs_path])
                        text = (batch_raw.get(abs_path) or "").strip()
                    if text:
                        return {
                            "ok": True,
                            "text": text,
                            "engine": "windows_winrt_ocr",
                            "confidence": 82.0 if len(text) > 20 else 60.0,
                            "error": None,
                        }
                finally:
                    if tmp_path and os.path.exists(tmp_path):
                        try:
                            os.remove(tmp_path)
                        except OSError:
                            pass

            if allow_vision_fallback:
                try:
                    from backend.app.services.llm.vision_model import vision_model

                    if vision_model._llm is not None:
                        v_text = vision_model.analyze_image(
                            abs_path,
                            prompt="Transcribe all printed text, tables, dates, numbers, and organization names visible in this scanned tender image verbatim.",
                            task="ocr",
                            max_tokens=512,
                        )
                        if v_text and "Visual Inspection" not in v_text:
                            return {
                                "ok": True,
                                "text": v_text.strip(),
                                "engine": "qwen2_vl_vision",
                                "confidence": 75.0,
                                "error": None,
                            }
                except Exception as ve:
                    logger.warning(f"Vision OCR fallback error: {ve}")

            return {
                "ok": False,
                "text": "OCR_FAILED",
                "engine": self.active_engine_name(),
                "confidence": 0.0,
                "error": "No readable text detected by local OCR engine.",
            }
        except Exception as e:
            logger.error(f"Image OCR failed for {image_path}: {e}")
            return {
                "ok": False,
                "text": "OCR_FAILED",
                "engine": self.active_engine_name(),
                "confidence": 0.0,
                "error": str(e),
            }

    def extract_text_from_image(self, image_path: str) -> str:
        """Extracts text from an image locally, returning OCR_FAILED if unreadable."""
        logger.info(f"Running OCR on image: {image_path}")
        res = self.ocr_image_detailed(image_path, allow_vision_fallback=False)
        return res["text"] if res["ok"] else "OCR_FAILED"

    def extract_pages_from_scanned_pdf(
        self,
        pdf_path: str,
        page_numbers: Optional[List[int]] = None,
        dpi: int = 200,
    ) -> List[Dict[str, Any]]:
        """Renders target PDF pages and runs local OCR preserving page_number per page."""
        if not os.path.exists(pdf_path):
            logger.error(f"PDF file not found: {pdf_path}")
            return []

        try:
            import fitz  # PyMuPDF
        except ImportError as e:
            logger.error(f"PyMuPDF unavailable for PDF OCR rendering: {e}")
            return []

        doc = fitz.open(pdf_path)
        target_pages = page_numbers if page_numbers is not None else list(range(1, len(doc) + 1))
        pdf_hash = self._hash_file(pdf_path)
        pdf_cache_key = (pdf_hash, tuple(target_pages), dpi, self.active_engine_name()) if pdf_hash else None
        if pdf_cache_key is not None:
            with self._cache_lock:
                cached_pages = self._pdf_ocr_cache.get(pdf_cache_key)
                if cached_pages is not None:
                    self._pdf_ocr_cache.move_to_end(pdf_cache_key)
                    doc.close()
                    return [dict(item) for item in cached_pages]

        page_results: List[Dict[str, Any]] = []
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)

        temp_dir = tempfile.mkdtemp(prefix="mygpt_ocr_")
        rendered_map: Dict[int, str] = {}
        try:
            for p_num in target_pages:
                if p_num < 1 or p_num > len(doc):
                    continue
                page = doc[p_num - 1]
                pix = page.get_pixmap(matrix=matrix)
                if self.tesseract_available and pytesseract is not None:
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    proc = self.preprocess_image(img)
                    page_text = pytesseract.image_to_string(proc).strip()
                    conf = self.get_ocr_confidence(proc)
                    page_results.append({
                        "page_number": p_num,
                        "text": page_text,
                        "is_ocr": True,
                        "ocr_confidence": round(conf, 2),
                        "engine": "tesseract",
                        "unreadable_reason": None if page_text else "OCR produced empty text",
                    })
                else:
                    out_png = os.path.abspath(os.path.join(temp_dir, f"page_{p_num}.png"))
                    pix.save(out_png)
                    rendered_map[p_num] = out_png

            if rendered_map:
                if self.winrt_available:
                    # Process in batches of 15 pages to bound subprocess runtime cleanly
                    items = sorted(rendered_map.items())
                    batch_texts: Dict[str, str] = {}
                    for i in range(0, len(items), 15):
                        chunk_paths = [path for _, path in items[i : i + 15]]
                        batch_texts.update(self._run_winrt_batch(chunk_paths, timeout=120))

                    for p_num, png_path in items:
                        txt = (batch_texts.get(png_path) or "").strip()
                        page_results.append({
                            "page_number": p_num,
                            "text": txt,
                            "is_ocr": True,
                            "ocr_confidence": 80.0 if len(txt) > 25 else (55.0 if txt else 0.0),
                            "engine": "windows_winrt_ocr",
                            "unreadable_reason": None if txt else "WinRT OCR extracted no text on rendered page",
                        })
                else:
                    for p_num in sorted(rendered_map):
                        page_results.append({
                            "page_number": p_num,
                            "text": "",
                            "is_ocr": True,
                            "ocr_confidence": 0.0,
                            "engine": "none",
                            "unreadable_reason": "No local OCR engine available (Tesseract/WinRT unavailable)",
                        })
        finally:
            doc.close()
            for p_path in rendered_map.values():
                if os.path.exists(p_path):
                    try:
                        os.remove(p_path)
                    except OSError:
                        pass
            try:
                os.rmdir(temp_dir)
            except OSError:
                pass

        if pdf_cache_key is not None and any((r.get("text") or "").strip() for r in page_results):
            with self._cache_lock:
                self._pdf_ocr_cache[pdf_cache_key] = [dict(item) for item in page_results]
                while len(self._pdf_ocr_cache) > self._max_cache_entries:
                    self._pdf_ocr_cache.popitem(last=False)

        return page_results

    def extract_text_from_scanned_pdf(self, pdf_path: str) -> str:
        """Extracts concatenated OCR text across all rendered pages of a PDF."""
        logger.info(f"Running local OCR on PDF: {pdf_path}")
        pages = self.extract_pages_from_scanned_pdf(pdf_path)
        parts = [f"--- Page {p['page_number']} ---\n{p['text']}" for p in pages if p.get("text")]
        full_text = "\n\n".join(parts).strip()
        return full_text if full_text else "OCR_FAILED"


ocr_service = OCRService()
